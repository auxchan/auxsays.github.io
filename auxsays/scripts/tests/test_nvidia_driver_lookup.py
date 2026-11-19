#!/usr/bin/env python3
"""NVIDIA driver official ingestion: family identity, stop rules, health, request budget, provenance.

Offline. Every NVIDIA response comes from fixtures recorded on 2026-11-19 (tests/fixtures/
nvidia_driver_lookup/: both family lookups and two details records, with only the per-row list of GPU
model names removed) or is derived from them. The transport is replaced at the adapter's own
`fetch_text` seam, and HTTP failures are raised in lib.http's own message format, so the adapter's
classification path is the production one. Write-path checks write only into temporary directories.

Run with: python auxsays/scripts/tests/test_nvidia_driver_lookup.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import re
import sys
import tempfile
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import adapters.nvidia_driver_lookup as nv  # noqa: E402
import build_monitoring_projection as monitoring  # noqa: E402
import patch_ingest  # noqa: E402
from lib import http as http_lib  # noqa: E402
from lib import nvidia_driver_identity as identity  # noqa: E402
from lib import state as state_lib  # noqa: E402
from lib import write_update_record as writer  # noqa: E402
from lib.http import FetchResult  # noqa: E402

FX = _SCRIPTS / "tests" / "fixtures" / "nvidia_driver_lookup"
GRD, NSD = identity.GAME_READY, identity.STUDIO
PROVENANCE = {
    "source_origin": "NVIDIA official",
    "collection_method": "public driver-lookup endpoint",
    "collection_authorization": "owner risk acceptance; NVIDIA permission not established",
}

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def load(name: str) -> dict:
    return json.loads((FX / name).read_text(encoding="utf-8"))


LOOKUP = {GRD: load("lookup_crd0.json"), NSD: load("lookup_crd1.json")}
DETAILS_TEMPLATE = load("dd_283968.json")


def source(product_id: str, **ingestion) -> dict:
    software = {GRD: "GeForce Game Ready Driver", NSD: "NVIDIA Studio Driver"}[product_id]
    ing = {"type": "download_portal", "adapter": "nvidia_driver_lookup",
           "official_url": "https://www.nvidia.com/en-us/geforce/drivers/",
           "api_url": nv.lookup_url(product_id), "provenance": dict(PROVENANCE)}
    ing.update(ingestion)
    return {"company_id": "nvidia", "product_id": product_id, "company": "NVIDIA", "software": software,
            "public_category": "Hardware / Drivers", "enabled": True, "ingestion": ing}


def rows(payload: dict) -> list[dict]:
    return [r["downloadInfo"] for r in payload["IDS"]]


def details_for(info: dict) -> dict:
    envelope = copy.deepcopy(DETAILS_TEMPLATE)
    envelope["driverDetails"]["IDS"] = [{"downloadInfo": copy.deepcopy(info)}]
    return envelope


class Net:
    """The NVIDIA services, served from fixtures. Records every URL asked for."""

    def __init__(self, lookups: dict | None = None):
        self.lookups = copy.deepcopy(lookups or LOOKUP)
        self.calls: list[str] = []
        self.override: dict[str, object] = {}   # "lookup:<pid>" / "details:<id>" -> handler

    def __call__(self, url, timeout=30, headers=None, **kwargs):
        self.calls.append(url)
        self.headers = dict(headers or {})
        key = None
        if "DriverManualLookup" in url:
            key = "lookup:" + (GRD if url.endswith("upCRD=0") else NSD)
        else:
            match = re.search(r"%22ddID%22%3A%22(\d+)%22", url)
            key = "details:" + (match.group(1) if match else "?")
        handler = self.override.get(key) or self.override.get(key.split(":")[0])
        if callable(handler):
            return handler(url)
        if key.startswith("lookup:"):
            return FetchResult(url=url, status=200, headers={"content-type": "text/html; charset=UTF-8"},
                               text=json.dumps(self.lookups[key.split(":")[1]]), final_url=url)
        wanted = key.split(":")[1]
        for payload in self.lookups.values():
            for info in rows(payload):
                if info["ID"] == wanted:
                    return FetchResult(url=url, status=200, headers={"content-type": "application/json"},
                                       text=json.dumps(details_for(info)), final_url=url)
        raise http_lib._format_fetch_error("HTTP 404", url, "not found")

    def lookups_made(self) -> int:
        return sum("DriverManualLookup" in u for u in self.calls)

    def details_made(self) -> int:
        return sum("getDownloadDetails" in u for u in self.calls)


def http_error(code: int):
    def handler(url):
        raise http_lib._format_fetch_error(f"HTTP {code}", url, "<html>denied</html>")
    return handler


def body(text: str, final_url: str | None = None):
    def handler(url):
        return FetchResult(url=url, status=200, headers={}, text=text, final_url=final_url or url)
    return handler


def run_fetch(net: Net, product_id: str, scan: dict | None = None, **ingestion):
    nv.fetch_text = net
    probe: dict = {}
    scan = {} if scan is None else scan
    try:
        records = nv.fetch(source(product_id, **ingestion), limit=200, scan_state=scan, probe=probe)
        return records, probe, scan, None
    except Exception as exc:  # noqa: BLE001 - the exception IS the result under test
        return [], probe, scan, exc


def ingest(tmp: Path, sources: list[dict], net: Net) -> dict:
    """Drive the REAL runner (patch_ingest.main) in write mode against temporary paths."""
    config = tmp / "sources.yml"
    config.write_text(yaml.safe_dump(sources, sort_keys=False), encoding="utf-8")
    nv.fetch_text = net
    argv, summary = sys.argv, os.environ.get("GITHUB_STEP_SUMMARY")
    os.environ["GITHUB_STEP_SUMMARY"] = str(tmp / "summary.md")
    sys.argv = ["patch_ingest.py", "--config", str(config), "--state", str(tmp / "state.json"),
                "--output", str(tmp / "generated"), "--no-refresh-linked-bodies"]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = patch_ingest.main()
    finally:
        sys.argv = argv
        if summary is None:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        else:
            os.environ["GITHUB_STEP_SUMMARY"] = summary
    state = json.loads((tmp / "state.json").read_text(encoding="utf-8"))
    return {"rc": rc, "state": state, "files": sorted((tmp / "generated").glob("*.md"))
            if (tmp / "generated").exists() else []}


def front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---\n", 2)[1]) or {}


def run() -> int:
    original_fetch = nv.fetch_text
    try:
        _run()
    finally:
        nv.fetch_text = original_fetch
        nv.reset_process_state()
    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


def _run() -> None:
    print("\n=== A. the 621.14 shared version: one record per family, nothing crosses ===")
    nv.reset_process_state()
    net = Net()
    grd, grd_probe, grd_scan, err1 = run_fetch(net, GRD)
    nsd, nsd_probe, nsd_scan, err2 = run_fetch(net, NSD)
    check("A1 both families fetch without a stop", err1 is None and err2 is None, f"{err1!r} {err2!r}")
    grd_1414 = [r for r in grd if r["version"] == "621.14"]
    nsd_1414 = [r for r in nsd if r["version"] == "621.14"]
    check("A2 621.14 yields exactly one Game Ready and one Studio record",
          len(grd_1414) == 1 and len(nsd_1414) == 1, f"{len(grd_1414)} / {len(nsd_1414)}")
    g, s = (grd_1414 or [{}])[0], (nsd_1414 or [{}])[0]
    check("A3 each record carries its own family's NVIDIA download id (283968 / 283966)",
          g.get("nvidia_download_id") == "283968" and s.get("nvidia_download_id") == "283966",
          f"{g.get('nvidia_download_id')} / {s.get('nvidia_download_id')}")
    check("A4 product ids and driver families never cross",
          g.get("product_id") == GRD and g.get("driver_family") == "GeForce Game Ready"
          and s.get("product_id") == NSD and s.get("driver_family") == "NVIDIA Studio")
    check("A5 each record links only its own driver page",
          g.get("source_url", "").endswith("/283968/") and s.get("source_url", "").endswith("/283966/")
          and "283966" not in json.dumps(g) and "283968" not in json.dumps(s))
    check("A6 record identity is (product_id, version), the download id is provenance",
          g.get("record_id") == f"nvidia_driver_lookup:{GRD}:621.14"
          and s.get("record_id") == f"nvidia_driver_lookup:{NSD}:621.14")
    check("A7 no Studio row ever appears in a Game Ready record set, and the reverse",
          all(r["driver_family"] == "GeForce Game Ready" for r in grd)
          and all(r["driver_family"] == "NVIDIA Studio" for r in nsd))
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        p1, a1 = writer.write_record(out, dict(g, source_last_checked="2026-11-19T00:00:00Z"))
        p2, a2 = writer.write_record(out, dict(s, source_last_checked="2026-11-19T00:00:00Z"))
        f1, f2 = front(p1), front(p2)
        check("A8 the real writer creates two files for one version", a1 == a2 == "created" and p1 != p2,
              f"{a1} {a2} {p1.name} {p2.name}")
        check("A9 the two permalinks are each family's own page",
              f1.get("permalink") == "/updates/nvidia/nvidia-geforce-game-ready/621-14/"
              and f2.get("permalink") == "/updates/nvidia/nvidia-studio-driver/621-14/",
              f"{f1.get('permalink')} {f2.get('permalink')}")
        p3, a3 = writer.write_record(out, dict(g, source_last_checked="2026-11-20T00:00:00Z"))
        check("A10 re-ingesting Game Ready 621.14 refreshes ITS record, never the Studio one",
              p3 == p1 and a3 in {"refreshed", "freshness-updated", "unchanged"}
              and front(p2).get("nvidia_download_id") == "283966", f"{p3.name} {a3}")
        fields = ("driver_family", "driver_branch", "nvidia_download_id", "release_date_precision",
                  "source_origin", "collection_method", "collection_authorization")
        check("A11 every NVIDIA identity and provenance field reaches disk (the teams_edition lesson)",
              all(f1.get(k) for k in fields) and f1.get("collection_authorization") == PROVENANCE["collection_authorization"],
              str({k: f1.get(k) for k in fields}))
        check("A12 the record is official-only with zero reports",
              f1.get("evidence_state") == "official_only" and f1.get("update_report_count") == 0
              and f1.get("update_consensus_label") == "Insufficient data", str((f1.get("evidence_state"),
                                                                              f1.get("update_report_count"))))

    print("\n=== B. version, branch, date and URL are SUPPLIED by NVIDIA, never inferred ===")
    fixture_row = next(i for i in rows(LOOKUP[GRD]) if i["ID"] == "283968")
    check("B1 version is the row's Version", g.get("version") == fixture_row["Version"])
    check("B2 branch is the row's Release", g.get("driver_branch") == "R" + fixture_row["Release"],
          g.get("driver_branch", ""))
    check("B3 date is the row's ReleaseDateTime, at day precision",
          g.get("published_at") == "2026-11-04T00:00:00Z" and g.get("release_date_precision") == "day")
    check("B4 the driver page is the row's DetailsURL", g.get("source_url") == fixture_row["DetailsURL"])
    for field in ("Release", "Version", "ReleaseDateTime", "DetailsURL"):
        nv.reset_process_state()
        bad = Net()
        for info in rows(bad.lookups[GRD]):
            info.pop(field, None)
        recs, _, _, exc = run_fetch(bad, GRD)
        check(f"B5 a listing without {field} is a schema stop with no records",
              not recs and isinstance(exc, nv.SchemaIntegrityStop), repr(exc))
    check("B6 the weekday must agree with the date", nv.release_date("Wed Nov 04, 2026") == date(2026, 11, 4))
    try:
        nv.release_date("Thu Nov 04, 2026")
        weekday_stop = False
    except nv.SchemaIntegrityStop:
        weekday_stop = True
    check("B7 'Thu Nov 04, 2026' (wrong weekday) is a schema stop", weekday_stop)

    print("\n=== C. hotfix, beta, unknown and other-family names fail closed ===")
    nv.reset_process_state()
    mixed = Net()
    extra = copy.deepcopy(rows(mixed.lookups[GRD])[0])
    cases = {
        "hotfix": dict(extra, ID="900001", Version="621.12", Name="GeForce Hotfix Driver"),
        "beta": dict(extra, ID="900002", Version="621.30", IsBeta="1"),
        "not_whql": dict(extra, ID="900003", Version="621.31", IsWHQL="0"),
        "studio_named": dict(extra, ID="900004", Version="621.32", Name="NVIDIA%20Studio%20Driver"),
        "unknown": dict(extra, ID="900005", Version="621.33", Name="NVIDIA%20App"),
        "crd_flag": dict(extra, ID="900006", Version="621.34", IsCRD="1"),
    }
    for info in cases.values():
        mixed.lookups[GRD]["IDS"].insert(0, {"downloadInfo": info})
    mixed.lookups[GRD]["Success"] = str(len(mixed.lookups[GRD]["IDS"]))
    recs, probe, _, exc = run_fetch(mixed, GRD, scan={"details_verified": [i["ID"] for i in rows(LOOKUP[GRD])]})
    published = {r["version"] for r in recs}
    check("C1 none of hotfix / beta / non-WHQL / Studio-named / unknown / flag-mismatch rows is published",
          exc is None and not (published & {"621.12", "621.30", "621.31", "621.32", "621.33", "621.34"}),
          f"{exc!r} {sorted(published)}")
    skipped = (probe.get("nvidia") or {}).get("skipped") or {}
    check("C2 each skip is counted by its reason, never silently dropped",
          skipped.get("name_not_this_family") == 3 and skipped.get("beta") == 1
          and skipped.get("not_whql") == 1 and skipped.get("studio_flag_disagrees_with_name") == 1,
          str(skipped))
    check("C3 the genuine Game Ready rows still publish beside them", "621.14" in published and "621.24" in published)
    check("C4 the identity rule directly: a Studio name in the Game Ready query matches nothing",
          identity.listing_matches(GRD, {"Name": "NVIDIA Studio Driver", "IsCRD": "1", "IsBeta": "0",
                                         "IsDC": "1", "IsWHQL": "0"})[0] is False)
    check("C5 Studio rows are accepted without a WHQL flag (as NVIDIA returns them)",
          identity.listing_matches(NSD, {"Name": "NVIDIA Studio Driver", "IsCRD": "1", "IsBeta": "0",
                                         "IsDC": "1", "IsWHQL": "0"})[0] is True)
    nv.reset_process_state()
    alien = Net()
    for info in rows(alien.lookups[GRD]):
        info["Name"] = "GeForce%20Hotfix%20Driver"
    recs, probe, _, exc = run_fetch(alien, GRD)
    check("C6 a listing where no row is this family publishes nothing and reports a mismatch",
          exc is None and not recs and probe.get("extraction_mismatch") is True
          and probe.get("upstream_candidates") == 12, str(probe))
    check("C7 that mismatch makes the source broken at once, not quiet",
          state_lib.classify_success(0, 0, 0, extraction_mismatch=True) == "broken")
    nv.reset_process_state()
    twin = Net()
    dup = dict(copy.deepcopy(rows(twin.lookups[GRD])[1]), ID="999999",
               DetailsURL="https://www.nvidia.com/en-us/drivers/details/999999/")
    twin.lookups[GRD]["IDS"].append({"downloadInfo": dup})
    twin.lookups[GRD]["Success"] = "13"
    recs, probe, _, exc = run_fetch(twin, GRD)
    check("C8 one version under two download ids in one family: neither is published",
          exc is None and "621.14" not in {r["version"] for r in recs}
          and (probe.get("nvidia") or {}).get("skipped", {}).get("ambiguous_version") == 2, str(probe))

    print("\n=== D. reports: an explicit other-family mention vetoes the thread's family ===")
    check("D1 'Driver Regression: 621.14 NDIVIA Studio Driver' in the Game Ready 621.14 thread is vetoed",
          identity.report_family("Driver Regression: 621.14 NDIVIA Studio Driver", thread_family=GRD) is None)
    check("D2 a bare '621.14' report in the Game Ready feedback thread belongs to Game Ready",
          identity.report_family("621.14 makes my SSD write constantly", thread_family=GRD) == GRD)
    check("D3 a bare '621.14' report outside a family thread belongs to neither",
          identity.report_family("621.14 makes my SSD write constantly") is None)
    check("D4 a report naming both families belongs to neither",
          identity.report_family("Game Ready 621.14 and Studio driver 621.14 both crash", thread_family=GRD) is None)
    check("D5 'OBS Studio 33' is not a Studio-driver mention",
          identity.report_family("OBS Studio 33 drops frames on 621.14", thread_family=GRD) == GRD)
    check("D6 a Studio-named report in the Studio thread belongs to Studio",
          identity.report_family("NVIDIA Studio 621.14 broke Resolve", thread_family=NSD) == NSD)
    check("D7 a Game Ready-named report in the Studio thread is vetoed",
          identity.report_family("GRD 621.14 has the same bug", thread_family=NSD) is None)

    print("\n=== E. access refusal: blocked health, no records, no retry, suspended ===")
    refusals = {
        "403": http_error(403), "401": http_error(401), "429": http_error(429), "451": http_error(451),
        "challenge": lambda url: (_ for _ in ()).throw(http_lib._format_fetch_error(
            "Browser challenge", url, "bot-protection interstitial served at HTTP 200")),
        "html": body("<!DOCTYPE html><html><body>Access Denied</body></html>"),
        "rejection": body(json.dumps({"error": "Access denied: automated requests are not permitted"})),
    }
    for name, handler in refusals.items():
        nv.reset_process_state()
        net = Net()
        net.override["lookup"] = handler
        recs, _, scan, exc = run_fetch(net, GRD)
        check(f"E1 {name}: AccessRefused, no records, one request, suspension recorded",
              isinstance(exc, nv.AccessRefused) and not recs and len(net.calls) == 1
              and isinstance(scan.get("access_refused"), dict),
              f"{exc!r} calls={len(net.calls)} scan={scan}")
        check(f"E2 {name}: classified `blocked`", state_lib.classify_error(str(exc)) == "blocked",
              state_lib.classify_error(str(exc)))
    nv.reset_process_state()
    net = Net()
    net.override["details"] = http_error(429)
    recs, _, scan, exc = run_fetch(net, GRD)
    check("E3 a refusal on the details service stops the family too",
          isinstance(exc, nv.AccessRefused) and not recs and net.details_made() == 1, repr(exc))
    nv.reset_process_state()
    net = Net()
    net.override["lookup"] = http_error(500)
    recs, _, scan, exc = run_fetch(net, GRD)
    check("E4 a 500 is an ordinary failure, not a refusal (nothing suspended)",
          exc is not None and not isinstance(exc, nv.AccessRefused) and "access_refused" not in scan, repr(exc))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nv.reset_process_state()
        net = Net()
        net.override["lookup:" + GRD] = http_error(403)
        sources = [source(GRD), source(NSD)]
        first = ingest(tmp, sources, net)
        b_grd = first["state"]["sources"][GRD]
        b_nsd = first["state"]["sources"][NSD]
        check("E5 write run: no record written for either family", first["files"] == [], str(first["files"]))
        check("E6 write run: the second family made NO request after the first was refused",
              len(net.calls) == 1, str(net.calls))
        check("E7 health bucket: error type blocked on both families",
              b_grd.get("last_error_type") == "blocked" and b_nsd.get("last_error_type") == "blocked",
              f"{b_grd.get('last_error_type')} / {b_nsd.get('last_error_type')}")
        check("E8 both suspensions are persisted in the committed state",
              (b_grd.get("scan") or {}).get("access_refused") and (b_nsd.get("scan") or {}).get("access_refused"))
        check("E9 the run fails rather than reading green (nothing trustworthy collected)",
              first["rc"] == 1 and first["state"].get("last_run_health") == "failed",
              f"rc={first['rc']} {first['state'].get('last_run_health')}")
        nv.reset_process_state()          # a NEW process: only the persisted suspension remains
        net2 = Net()                      # NVIDIA would now answer -- it must not be asked
        second = ingest(tmp, sources, net2)
        b_grd = second["state"]["sources"][GRD]
        check("E10 the next run makes ZERO requests (no retry loop across runs)", net2.calls == [], str(net2.calls))
        check("E11 the next run is `failing`/`blocked`, which the public projection shows as blocked",
              b_grd.get("status") == "failing" and b_grd.get("last_error_type") == "blocked"
              and monitoring.derive_state(sources[0], b_grd, now=datetime.now(timezone.utc)) == "blocked",
              f"{b_grd.get('status')} {b_grd.get('last_error_type')}")
        refused_at = datetime.fromisoformat(b_grd["scan"]["access_refused"]["at"].replace("Z", "+00:00"))
        early = (refused_at - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        late = (refused_at + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        nv.reset_process_state()
        net3 = Net()
        third = ingest(tmp, [source(GRD, access_refusal_cleared_at=early),
                             source(NSD, access_refusal_cleared_at="not a time")], net3)
        check("E12 a clearing time BEFORE the refusal, or an unparseable one, keeps it suspended",
              net3.calls == [] and third["files"] == [], str(net3.calls))
        nv.reset_process_state()
        net4 = Net()
        fourth = ingest(tmp, [source(GRD, access_refusal_cleared_at=late),
                              source(NSD, access_refusal_cleared_at=late)], net4)
        names = sorted(p.name for p in fourth["files"])
        check("E13 a reviewed clearing time AFTER the refusal resumes collection for both families",
              net4.lookups_made() == 2 and len(names) == 4
              and "access_refused" not in (fourth["state"]["sources"][GRD].get("scan") or {}), str(names))

    print("\n=== F. schema and source-authority stops ===")
    schema_cases = {
        "no IDS envelope": lambda n: n.lookups[GRD].pop("IDS"),
        "Success disagrees with rows": lambda n: n.lookups[GRD].__setitem__("Success", "11"),
        "echo is the Studio query": lambda n: n.lookups[GRD]["Request"][0].__setitem__("theUserRequestedCRD", "1"),
        "echo is not DCH": lambda n: n.lookups[GRD]["Request"][0].__setitem__("theSystemIsDc", "0"),
        "version not NNN.NN": lambda n: rows(n.lookups[GRD])[0].__setitem__("Version", "621.24 Hotfix"),
        "driver page names another id": lambda n: rows(n.lookups[GRD])[0].__setitem__(
            "DetailsURL", "https://www.nvidia.com/en-us/drivers/details/111111/"),
    }
    for name, mutate in schema_cases.items():
        nv.reset_process_state()
        net = Net()
        mutate(net)
        recs, _, scan, exc = run_fetch(net, GRD)
        check(f"F1 {name}: schema stop, no records, nothing suspended",
              isinstance(exc, nv.SchemaIntegrityStop) and not recs and "access_refused" not in scan, repr(exc))
    check("F2 a schema stop is recorded as a parser error",
          state_lib.classify_error(str(nv.SchemaIntegrityStop("x (parse stop)"))) == "parser_error")
    nv.reset_process_state()
    net = Net()
    net.override["lookup"] = body("not json at all")
    recs, _, _, exc = run_fetch(net, GRD)
    check("F3 a non-JSON body without refusal wording is a schema stop", isinstance(exc, nv.SchemaIntegrityStop), repr(exc))
    nv.reset_process_state()
    net = Net()
    recs, _, _, exc = run_fetch(net, GRD, api_url=nv.lookup_url(GRD).replace("gfwsl.geforce.com", "gfwsl.example.com"))
    check("F4 a configured lookup on another host: authority stop BEFORE any request",
          isinstance(exc, nv.SourceAuthorityStop) and net.calls == [], repr(exc))
    nv.reset_process_state()
    net = Net()
    recs, _, _, exc = run_fetch(net, GRD, api_url=nv.lookup_url(NSD))
    check("F5 the Studio query configured on the Game Ready source: authority stop BEFORE any request",
          isinstance(exc, nv.SourceAuthorityStop) and net.calls == [], repr(exc))
    nv.reset_process_state()
    net = Net()
    net.override["lookup"] = lambda url: FetchResult(url=url, status=200, headers={},
                                                     text=json.dumps(LOOKUP[GRD]), final_url="https://mirror.example.net/x")
    recs, _, _, exc = run_fetch(net, GRD)
    check("F6 a redirect to another host is an authority stop with no records",
          isinstance(exc, nv.SourceAuthorityStop) and not recs, repr(exc))
    nv.reset_process_state()
    net = Net()
    rows(net.lookups[GRD])[0]["DetailsURL"] = "https://drivers.example.com/en-us/drivers/details/285320/"
    recs, _, _, exc = run_fetch(net, GRD)
    check("F7 a driver page off www.nvidia.com is an authority stop", isinstance(exc, nv.SourceAuthorityStop), repr(exc))
    nv.reset_process_state()
    net = Net()
    recs, _, _, exc = run_fetch(net, GRD, provenance={})
    check("F8 a source without its provenance writes nothing and asks nothing",
          isinstance(exc, nv.SchemaIntegrityStop) and net.calls == [], repr(exc))
    nv.reset_process_state()
    net = Net()
    bad = copy.deepcopy(next(i for i in rows(LOOKUP[GRD]) if i["ID"] == "285320"))
    bad["ReleaseDateTime"] = "Fri Nov 13, 2026"
    net.override["details:285320"] = body(json.dumps(details_for(bad)))
    recs, probe, scan, exc = run_fetch(net, GRD)
    check("F9 a details record that disagrees with the lookup is not published, and is counted",
          exc is None and "621.24" not in {r["version"] for r in recs}
          and (probe.get("nvidia") or {}).get("skipped", {}).get("details_disagree") == 1
          and "285320" not in scan.get("details_verified", []), str(probe))

    print("\n=== G. request budget: one lookup, details for NEW drivers only ===")
    nv.reset_process_state()
    net = Net()
    scan: dict = {}
    recs, probe, scan, exc = run_fetch(net, GRD, scan=scan)
    check("G1 first run: 1 lookup + 2 details, 2 records, 10 held for later runs",
          net.lookups_made() == 1 and net.details_made() == 2 and len(recs) == 2
          and (probe.get("nvidia") or {}).get("withheld_for_next_run") == 10, f"{net.calls} {probe}")
    check("G2 the newest two drivers come first", [r["version"] for r in recs] == ["621.24", "621.14"],
          str([r["version"] for r in recs]))
    net2 = Net()
    recs2, _, scan, _ = run_fetch(net2, GRD, scan=scan)
    check("G3 second run verifies only the next two (no re-read of verified drivers)",
          net2.details_made() == 2 and len(recs2) == 4
          and not any("285320" in u or "283968" in u for u in net2.calls), str(net2.calls))
    for _ in range(6):
        run_fetch(Net(), GRD, scan=scan)
    net3 = Net()
    recs3, probe3, scan, _ = run_fetch(net3, GRD, scan=scan)
    check("G4 once every listed driver is verified a run makes exactly one request",
          net3.calls and len(net3.calls) == 1 and len(recs3) == 12, f"{len(net3.calls)} {len(recs3)}")
    check("G5 the client identifies itself honestly, with no browser identity",
          net3.headers.get("User-Agent") == nv.USER_AGENT and "Mozilla" not in nv.USER_AGENT
          and net3.headers.get("Accept") == "application/json")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nv.reset_process_state()
        net = Net()
        run1 = ingest(tmp, [source(GRD), source(NSD)], net)
        names = sorted(p.name for p in run1["files"])
        check("G6 write run (real runner): two records per family, 6 requests in all",
              run1["rc"] == 0 and len(names) == 4 and len(net.calls) == 6, f"{names} {len(net.calls)}")
        check("G7 write run: the 621.14 pair exists once per family",
              "2026-11-04-geforce-game-ready-driver-621-14.md" in names
              and "2026-11-04-nvidia-studio-driver-621-14.md" in names, str(names))
        bucket = run1["state"]["sources"][GRD]
        check("G8 health bucket is healthy and carries the declared provenance",
              bucket.get("status") == "healthy" and bucket.get("provenance") == PROVENANCE, str(bucket.get("provenance")))
        net = Net()
        run2 = ingest(tmp, [source(GRD), source(NSD)], net)
        check("G9 second write run adds two more per family with 2 lookups + 4 details",
              len(run2["files"]) == 8 and net.lookups_made() == 2 and net.details_made() == 4,
              f"{len(run2['files'])} {net.calls}")

    print("\n=== H. record body: facts and links only ===")
    text = g.get("body", "")
    check("H1 the fixed issues NVIDIA lists are carried as facts",
          "[6979343]" in text and "Call of Duty: Modern Warfare 4: Game may display incorrect visual colors" in text)
    check("H2 NVIDIA's marketing paragraph and images are not copied",
          "best gaming experience" not in text and "<img" not in text and "images.nvidia.com" not in text)
    check("H3 the release-notes PDF link is NVIDIA's own",
          "https://us.download.nvidia.com/Windows/621.14/621.14-geforce-win11-x64-release-notes.pdf" in text)
    check("H4 a notes link on a non-NVIDIA host is never carried",
          nv.release_notes_pdf('<a href="https://files.example.com/621.14/notes.pdf">x</a>', "621.14") == "")
    check("H5 the official sources cite the driver page and notes, never the lookup service",
          [o["source_type"] for o in g.get("official_sources", [])] == ["download_portal", "release_notes"]
          and "gfwsl" not in json.dumps(g.get("official_sources")) and "gfwsl" not in text)
    check("H6 no 'patch notes' claim from a download-portal source",
          "patch notes" not in (text + g.get("official_summary", "") + g.get("summary", "")).lower())

    print("\n=== I. configuration, catalog and public text ===")
    config = yaml.safe_load((_REPO / "auxsays/_data/patch_ingestion_sources.yml").read_text(encoding="utf-8"))
    by_pid = {row.get("product_id"): row for row in config}
    check("I1 the bundled `nvidia` source is gone; both families have their own", "nvidia" not in by_pid
          and GRD in by_pid and NSD in by_pid)
    for pid in (GRD, NSD):
        ing = by_pid.get(pid, {}).get("ingestion") or {}
        check(f"I2 {pid}: enabled, pinned query, 12h, provenance as ruled, no window overrides",
              by_pid[pid].get("enabled") is True and ing.get("adapter") == "nvidia_driver_lookup"
              and ing.get("api_url") == nv.lookup_url(pid) and ing.get("polling_frequency") == "12h"
              and ing.get("provenance") == PROVENANCE and "record_limit" not in ing and "scan_limit" not in ing,
              str({k: ing.get(k) for k in ("adapter", "polling_frequency", "provenance")}))
    products = yaml.safe_load((_REPO / "auxsays/_data/patch_products.yml").read_text(encoding="utf-8"))
    ids = {p.get("id") for p in products}
    check("I3 the catalog has both driver products and no bundled `nvidia` product",
          {GRD, NSD} <= ids and "nvidia" not in ids)
    pages = {pid: _REPO / f"auxsays/updates/nvidia/{pid}/index.md" for pid in (GRD, NSD)}
    check("I4 each family has its product page", all(p.exists() for p in pages.values()))
    old = (_REPO / "auxsays/updates/nvidia/nvidia/index.md").read_text(encoding="utf-8")
    check("I5 the old /updates/nvidia/nvidia/ URL still resolves, redirecting to the NVIDIA profile",
          "permalink: /updates/nvidia/nvidia/" in old and 'url=/updates/nvidia/"' in old
          and 'window.location.replace("/updates/nvidia/")' in old)
    rendered = "\n".join(p.read_text(encoding="utf-8") for d in ("_layouts", "_includes")
                         for p in (_REPO / "auxsays" / d).rglob("*.html"))
    leaked = [k for k in ("collection_authorization", "collection_method", "source_origin", "nvidia_download_id")
              if k in rendered]
    check("I6 no layout or include renders the provenance fields into page text", not leaked, str(leaked))
    check("I7 the writer allow-list carries every NVIDIA field the adapter emits",
          set(writer.NVIDIA_DRIVER_FIELDS) <= set(writer.OPTIONAL_STRUCTURED_FIELDS)
          and {"driver_family", "nvidia_download_id", "collection_authorization"} <= set(writer.NVIDIA_DRIVER_FIELDS))
    check("I8 classify_error: 'access refused' is blocked; existing classes unchanged",
          state_lib.classify_error("Access refused by the official NVIDIA source (HTTP 429)") == "blocked"
          and state_lib.classify_error("HTTP 404 while fetching official source") == "not_found"
          and state_lib.classify_error("Timeout while fetching official source") == "timeout"
          and state_lib.classify_error("Browser challenge while fetching x") == "challenged")
    st: dict = {"sources": {"other": {"seen": [], "status": "healthy"}}}
    state_lib.record_provenance(st, "other", None)
    check("I9 a source that declares no provenance gets no provenance key (byte-identical buckets)",
          "provenance" not in st["sources"]["other"])


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
