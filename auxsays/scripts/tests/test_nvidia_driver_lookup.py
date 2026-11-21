#!/usr/bin/env python3
"""NVIDIA driver official ingestion: family identity, stop rules, health, request budget, provenance.

Offline. Every NVIDIA response comes from fixtures recorded on 2026-11-19 (tests/fixtures/
nvidia_driver_lookup/: both family lookups and two details records, with only the per-row list of GPU
model names removed) or is derived from them. The transport is replaced at the adapter's own
`fetch_text` seam, and HTTP failures are raised in lib.http's own message format, so the adapter's
classification path is the production one. The redirect checks (F') go one layer lower: the REAL
lib.http.fetch_text and redirect handler over a fake urllib HTTPS transport that records every URL that
reaches the wire. Section J walks patch-ingest.yml's steps as the runner would. Write-path checks write
only into temporary directories.

Run with: python auxsays/scripts/tests/test_nvidia_driver_lookup.py
"""
from __future__ import annotations

import contextlib
import copy
import http.client
import io
import json
import os
import re
import sys
import tempfile
import traceback
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
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


def ingest(tmp: Path, sources: list[dict], net, extra: tuple[str, ...] = ()) -> dict:
    """Drive the REAL runner (patch_ingest.main) in write mode against temporary paths.

    `outputs` is what the run appended to $GITHUB_OUTPUT (a fresh file per run)."""
    config = tmp / "sources.yml"
    config.write_text(yaml.safe_dump(sources, sort_keys=False), encoding="utf-8")
    nv.fetch_text = net
    saved = {k: os.environ.get(k) for k in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT")}
    os.environ["GITHUB_STEP_SUMMARY"] = str(tmp / "summary.md")
    gh_output = tmp / "github_output.txt"
    gh_output.write_text("", encoding="utf-8")
    os.environ["GITHUB_OUTPUT"] = str(gh_output)
    argv = sys.argv
    sys.argv = ["patch_ingest.py", "--config", str(config), "--state", str(tmp / "state.json"),
                "--output", str(tmp / "generated"), "--no-refresh-linked-bodies", *extra]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = patch_ingest.main()
    finally:
        sys.argv = argv
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    state_path = tmp / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    return {"rc": rc, "state": state, "outputs": gh_output.read_text(encoding="utf-8"),
            "files": sorted((tmp / "generated").glob("*.md")) if (tmp / "generated").exists() else []}


class FakeHTTPS(urllib.request.HTTPSHandler):
    """A urllib HTTPS transport served from routes, BELOW lib.http's real opener and redirect handler.

    Every URL that reaches the transport is recorded in `seen`, so "no request reached host X" is a
    fact about the wire, not about what the adapter chose to report."""

    def __init__(self, routes: dict):
        super().__init__()
        self.routes = routes          # host -> callable(url) -> (status, headers, body bytes)
        self.seen: list[str] = []

    def https_open(self, req):
        url = req.full_url
        self.seen.append(url)
        host = urllib.parse.urlsplit(url).hostname or ""
        route = self.routes.get(host)
        status, headers, payload = route(url) if route else (599, {}, b"unrouted")
        msg = http.client.HTTPMessage()
        for key, value in headers.items():
            msg[key] = value
        resp = urllib.response.addinfourl(io.BytesIO(payload), msg, url, status)
        resp.msg = http.client.responses.get(status, "")
        return resp

    def hosts(self) -> list[str]:
        return [urllib.parse.urlsplit(u).hostname or "" for u in self.seen]


@contextlib.contextmanager
def wire(routes: dict):
    """Swap lib.http's opener for one with the REAL redirect handler over a FakeHTTPS transport, and
    give the adapter the REAL lib.http.fetch_text."""
    fake = FakeHTTPS(routes)
    real_opener, real_fetch = http_lib._OPENER, nv.fetch_text
    http_lib._OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                   http_lib._AuthStrippingRedirectHandler(), fake)
    nv.fetch_text = http_lib.fetch_text
    try:
        yield fake
    finally:
        http_lib._OPENER = real_opener
        nv.fetch_text = real_fetch


def lookup_route(product_id: str):
    return lambda url: (200, {"Content-Type": "text/html; charset=UTF-8"},
                        json.dumps(LOOKUP[product_id]).encode("utf-8"))


def redirect_to(location: str | None, status: int = 302):
    return lambda url: (status, ({"Location": location} if location is not None else {}), b"")


class _Ctx(dict):
    def __missing__(self, key):          # an unset step output or input reads as '' in Actions
        return ""


def gha_if(expr: str, ctx: dict, status: dict) -> bool:
    """Evaluate a workflow `if:` (the subset these workflows use) the way Actions does.

    An expression with no status function gets Actions' implicit `success() &&`."""
    text = re.sub(r"^\s*\$\{\{|\}\}\s*$", "", str(expr or "").strip()).strip() or "success()"
    if not re.search(r"\b(success|failure|cancelled|always)\(\)", text):
        text = f"success() && ({text})"
    py = text.replace("&&", " and ").replace("||", " or ")
    py = re.sub(r"!(?!=)", " not ", py)
    py = re.sub(r"\b(success|failure|cancelled|always)\(\)", r"FN_\1", py)
    py = re.sub(r"\b(?:github|steps)(?:\.[A-Za-z_][\w-]*)+", lambda m: f"CTX[{m.group(0)!r}]", py)
    py = re.sub(r"\bnull\b", "None", py)
    env = {"CTX": _Ctx(ctx), "FN_success": status["success"], "FN_failure": status["failure"],
           "FN_cancelled": status["cancelled"], "FN_always": True}
    return bool(eval(py, {"__builtins__": {}}, env))  # noqa: S307 - workflow text from this repo


def simulate_job(steps: list[dict], inputs: dict, fails: set, outputs: dict, cancel_after: str = "") -> dict:
    """Walk a job's steps as the runner does: evaluate each `if`, record outcomes and outputs.

    `fails` names the steps (by id, else name) that fail when they run; `outputs` gives a step's
    outputs, set even when it fails (the runner reads $GITHUB_OUTPUT after a failed step too)."""
    ctx: dict = {f"github.event.inputs.{k}": v for k, v in inputs.items()}
    failed = cancelled = False
    ran: dict[str, str] = {}
    for step in steps:
        key = step.get("id") or step.get("name")
        status = {"success": not failed and not cancelled, "failure": failed and not cancelled,
                  "cancelled": cancelled}
        if not gha_if(step.get("if", ""), ctx, status):
            ran[key] = "skipped"
            ctx[f"steps.{key}.outcome"] = "skipped"
            continue
        outcome = "failure" if key in fails else "success"
        ran[key] = outcome
        ctx[f"steps.{key}.outcome"] = outcome
        for name, value in (outputs.get(key) or {}).items():
            ctx[f"steps.{key}.outputs.{name}"] = value
        failed = failed or outcome == "failure"
        if key == cancel_after:
            cancelled = True
    ran["__job__"] = "failure" if failed else "success"
    return ran


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
    check("A4 product ids, driver families and badges never cross",
          g.get("product_id") == GRD and g.get("driver_family") == "GeForce Game Ready" and g.get("logo_text") == "GRD"
          and s.get("product_id") == NSD and s.get("driver_family") == "NVIDIA Studio" and s.get("logo_text") == "NSD")
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
        "not_dch": dict(extra, ID="900007", Version="621.35", IsDC="0"),
    }
    for info in cases.values():
        mixed.lookups[GRD]["IDS"].insert(0, {"downloadInfo": info})
    mixed.lookups[GRD]["Success"] = str(len(mixed.lookups[GRD]["IDS"]))
    recs, probe, _, exc = run_fetch(mixed, GRD, scan={"details_verified": [i["ID"] for i in rows(LOOKUP[GRD])]})
    published = {r["version"] for r in recs}
    check("C1 none of hotfix / beta / non-WHQL / Studio-named / unknown / flag-mismatch / non-DCH rows is published",
          exc is None and not (published & {"621.12", "621.30", "621.31", "621.32", "621.33", "621.34", "621.35"}),
          f"{exc!r} {sorted(published)}")
    skipped = (probe.get("nvidia") or {}).get("skipped") or {}
    check("C2 each skip is counted by its reason, never silently dropped",
          skipped.get("name_not_this_family") == 3 and skipped.get("beta") == 1
          and skipped.get("not_whql") == 1 and skipped.get("studio_flag_disagrees_with_name") == 1
          and skipped.get("not_dch_package") == 1,
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
        # An HTML page with no refusal wording at all (a maintenance or error page served at 200) is
        # still not JSON: it must be caught by its shape, not by its words.
        "html_plain": body("<!DOCTYPE html><html><head><title>NVIDIA</title></head><body>Back soon</body></html>"),
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
        # A clearing time must be after the refusal AND already passed. Refusal times are stored at
        # second precision, so "refusal + 1 s" can still lie in the future when these runs take
        # milliseconds. Backdate the stored refusal in this TEMPORARY state (never the repo's) so the
        # clearing times below are unambiguously past. Read defensively so a regression fails the
        # checks below by name instead of crashing the suite.
        state_path = tmp / "state.json"
        temp_state = json.loads(state_path.read_text(encoding="utf-8"))
        refused_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=2)
        for pid in (GRD, NSD):
            stored = ((temp_state.get("sources", {}).get(pid) or {}).get("scan") or {}).get("access_refused")
            if isinstance(stored, dict):
                stored["at"] = refused_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        state_path.write_text(json.dumps(temp_state), encoding="utf-8")
        early = (refused_at - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        late = (refused_at + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        # Clear ONCE: the same clearing time stays in config; a NEW refusal after it suspends again.
        nv.reset_process_state()
        net5 = Net()
        net5.override["lookup"] = http_error(403)
        fifth = ingest(tmp, [source(GRD, access_refusal_cleared_at=late),
                             source(NSD, access_refusal_cleared_at=late)], net5)
        nv.reset_process_state()
        net6 = Net()
        sixth = ingest(tmp, [source(GRD, access_refusal_cleared_at=late),
                             source(NSD, access_refusal_cleared_at=late)], net6)
        check("E14 a clearing time clears once: a later refusal is asked once, then suspended again",
              len(net5.calls) == 1 and net6.calls == [] and len(sixth["files"]) == len(fourth["files"])
              and (sixth["state"]["sources"][GRD].get("scan") or {}).get("access_refused"),
              f"{len(net5.calls)} then {net6.calls}")

    print("\n=== E'. a failed run that recorded a NEW refusal says so, so the workflow still commits it ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nv.reset_process_state()
        net = Net()
        net.override["lookup"] = http_error(403)
        first = ingest(tmp, [source(GRD), source(NSD)], net)
        check("E15 a FAILED write run that recorded a new refusal emits access_refusal_recorded=true",
              first["rc"] == 1 and "access_refusal_recorded=true" in first["outputs"].splitlines(),
              repr(first["outputs"]))
        nv.reset_process_state()
        second = ingest(tmp, [source(GRD), source(NSD)], Net())
        check("E16 the next run (already suspended, also FAILED) emits nothing: the refusal is not new",
              second["rc"] == 1 and "access_refusal_recorded" not in second["outputs"], repr(second["outputs"]))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nv.reset_process_state()
        net = Net()
        net.override["lookup"] = http_error(500)
        failed = ingest(tmp, [source(GRD), source(NSD)], net)
        check("E17 a FAILED run with no refusal emits nothing (its commit is still skipped, as before)",
              failed["rc"] == 1 and "access_refusal_recorded" not in failed["outputs"], repr(failed["outputs"]))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nv.reset_process_state()
        net = Net()
        net.override["lookup"] = http_error(403)
        dry = ingest(tmp, [source(GRD), source(NSD)], net, extra=("--dry-run",))
        check("E18 a dry run emits nothing and writes no state",
              "access_refusal_recorded" not in dry["outputs"] and not (tmp / "state.json").exists(),
              repr(dry["outputs"]))
    check("E19 the runner's refusal snapshot reads only a dated scan.access_refused",
          patch_ingest.access_refusals({"sources": {
              "a": {"scan": {"access_refused": {"at": "2026-11-19T00:00:00Z", "detail": "HTTP 403"}}},
              "b": {"scan": {"access_refused": {"detail": "no time"}}}, "c": {"scan": {}}, "d": "junk"}})
          == {"a": "2026-11-19T00:00:00Z"})

    print("\n=== E''. a FUTURE clearing time never re-arms requests ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        net = Net()
        net.override["lookup"] = http_error(403)
        future = "2099-01-01T00:00:00Z"
        for _ in range(4):
            nv.reset_process_state()                       # four separate processes (runs)
            ingest(tmp, [source(GRD, access_refusal_cleared_at=future),
                         source(NSD, access_refusal_cleared_at=future)], net)
        check("E20 against a standing 403 with a 2099 clearing time, four runs make ONE request in total",
              len(net.calls) == 1, f"{len(net.calls)} requests: {net.calls}")
    scan = {"access_refused": {"at": "2026-11-19T00:00:00Z", "detail": "HTTP 403"}}
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    nv.reset_process_state()
    try:
        nv._check_suspension(dict(scan), {"access_refusal_cleared_at": "2026-11-21T00:00:00Z"}, now=now)
        future_held = False
    except nv.AccessRefused:
        future_held = True
    cleared = dict(scan)
    try:
        nv._check_suspension(cleared, {"access_refusal_cleared_at": "2026-11-19T12:00:00Z"}, now=now)
        past_cleared = "access_refused" not in cleared
    except nv.AccessRefused:
        past_cleared = False
    check("E21 a clearing time after the refusal clears only once it has passed",
          future_held and past_cleared, f"future_held={future_held} past_cleared={past_cleared}")

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

    print("\n=== F'. redirects are checked BEFORE they are followed (real lib.http, fake wire) ===")
    verified_all = {"details_verified": [i["ID"] for i in rows(LOOKUP[GRD])]}
    nv.reset_process_state()
    with wire({"gfwsl.geforce.com": redirect_to("https://mirror.example.net/drivers.json"),
               "mirror.example.net": lookup_route(GRD)}) as fake:
        recs, _, scan, exc = run_fetch(nv.fetch_text, GRD, scan=copy.deepcopy(verified_all))
    check("F10 a 302 to an unlisted host: authority stop, ZERO requests to that host, nothing published",
          isinstance(exc, nv.SourceAuthorityStop) and not recs and fake.hosts() == ["gfwsl.geforce.com"]
          and "access_refused" not in scan, f"{exc!r} wire={fake.seen}")
    hop = {"n": 0}

    def two_hops(url):
        hop["n"] += 1
        return (302, {"Location": "/services_toolkit/next"}, b"") if hop["n"] == 1 \
            else (302, {"Location": "https://mirror.example.net/x"}, b"")
    nv.reset_process_state()
    with wire({"gfwsl.geforce.com": two_hops, "mirror.example.net": lookup_route(GRD)}) as fake:
        recs, _, _, exc = run_fetch(nv.fetch_text, GRD, scan=copy.deepcopy(verified_all))
    check("F11 the bound holds on EVERY hop: same host followed, then the off-host hop refused unsent",
          isinstance(exc, nv.SourceAuthorityStop) and not recs
          and fake.hosts() == ["gfwsl.geforce.com", "gfwsl.geforce.com"], f"{exc!r} wire={fake.seen}")
    same = {"n": 0}

    def same_host(url):
        same["n"] += 1
        if same["n"] == 1:
            return 302, {"Location": url.replace("numberOfResults=12", "numberOfResults=12&sort1=0")}, b""
        return 200, {"Content-Type": "text/html; charset=UTF-8"}, json.dumps(LOOKUP[GRD]).encode("utf-8")
    nv.reset_process_state()
    with wire({"gfwsl.geforce.com": same_host}) as fake:
        recs, _, _, exc = run_fetch(nv.fetch_text, GRD, scan=copy.deepcopy(verified_all))
    check("F12 a redirect that stays on the same NVIDIA host is followed and publishes normally",
          exc is None and len(recs) == 12 and fake.hosts() == ["gfwsl.geforce.com"] * 2,
          f"{exc!r} {len(recs)} wire={fake.seen}")
    for label, route in (("a file: Location", redirect_to("file:///etc/passwd")),
                         ("no Location at all", redirect_to(None)),
                         ("plain http on the same host", redirect_to("http://gfwsl.geforce.com/x")),
                         ("the same host on another port", redirect_to("https://gfwsl.geforce.com:8443/x")),
                         ("a userinfo authority", redirect_to("https://user@gfwsl.geforce.com/x")),
                         ("the other NVIDIA fetch host", redirect_to("https://www.nvidia.com/x", 301))):
        nv.reset_process_state()
        with wire({"gfwsl.geforce.com": route, "www.nvidia.com": lookup_route(GRD)}) as fake:
            recs, _, scan, exc = run_fetch(nv.fetch_text, GRD, scan=copy.deepcopy(verified_all))
        check(f"F13 {label}: authority stop, nothing followed, nothing published",
              isinstance(exc, nv.SourceAuthorityStop) and not recs and fake.hosts() == ["gfwsl.geforce.com"]
              and "access_refused" not in scan, f"{exc!r} wire={fake.seen}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nv.reset_process_state()
        with wire({"gfwsl.geforce.com": redirect_to("https://mirror.example.net/drivers.json"),
                   "www.nvidia.com": lookup_route(GRD), "mirror.example.net": lookup_route(GRD)}) as fake:
            run = ingest(tmp, [source(GRD), source(NSD)], nv.fetch_text)
        bucket = run["state"]["sources"][GRD]
        check("F14 write run (real runner): no record, no request to the mirror, an error with no suspension",
              run["files"] == [] and "mirror.example.net" not in fake.hosts() and len(fake.seen) == 2
              and bucket.get("last_error_type") and not (bucket.get("scan") or {}).get("access_refused"),
              f"{run['files']} wire={fake.seen} {bucket.get('last_error_type')}")
    with wire({"gfwsl.geforce.com": redirect_to("https://mirror.example.net/x"),
               "mirror.example.net": lambda url: (200, {}, b"{}")}) as fake:
        result = http_lib.fetch_text("https://gfwsl.geforce.com/start")
    check("F15 the bound is opt-in: an unbounded fetch_text follows redirects exactly as before",
          result.final_url == "https://mirror.example.net/x" and fake.hosts() == ["gfwsl.geforce.com",
                                                                                   "mirror.example.net"],
          f"{result.final_url} wire={fake.seen}")
    check("F16 redirect_allowed: https, listed host, default port, no userinfo -- nothing else",
          http_lib.redirect_allowed("https://gfwsl.geforce.com/a", frozenset({"gfwsl.geforce.com"}))
          and http_lib.redirect_allowed("https://gfwsl.geforce.com:443/a", frozenset({"gfwsl.geforce.com"}))
          and not any(http_lib.redirect_allowed(u, frozenset({"gfwsl.geforce.com"})) for u in (
              "http://gfwsl.geforce.com/a", "https://gfwsl.geforce.com:444/a", "https://u:p@gfwsl.geforce.com/a",
              "https://gfwsl.geforce.com.example.net/a", "https://gfwsl.geforce.com:bad/a", "")))
    reached: list = []
    real_opener, real_curl = http_lib._OPENER, http_lib._curl_fetch_text

    class _Dead:
        def open(self, req, timeout=None):
            raise urllib.error.URLError("simulated")
    http_lib._OPENER = _Dead()
    http_lib._curl_fetch_text = lambda url, *a, **k: reached.append(url)
    try:
        for bound in (None, frozenset({"helpx.adobe.com"})):
            with contextlib.suppress(Exception):
                http_lib.fetch_text("https://helpx.adobe.com/x.html", curl_fallback=True, redirect_hosts=bound)
    finally:
        http_lib._OPENER, http_lib._curl_fetch_text = real_opener, real_curl
    check("F17 a bounded fetch never takes the curl fallback (curl follows redirects on its own)",
          reached == ["https://helpx.adobe.com/x.html"], str(reached))

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

    print("\n=== J. the workflow: a FAILED run that recorded a refusal still commits; nothing else changes ===")
    wf = yaml.safe_load((_REPO / ".github/workflows/patch-ingest.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["ingest"]["steps"]
    ids = {st.get("id") for st in steps}
    check("J1 both ingestion steps, both pre-commit gates and the commit carry the ids the gate reads",
          {"ingest_enabled", "ingest_selected", "precommit_logos", "precommit_qa", "commit"} <= ids, str(ids))
    routine = {"source": None, "dry_run": None}
    refused = {"access_refusal_recorded": "true"}
    gates = ("precommit_logos", "precommit_qa", "commit")
    converge = ("Converge records whose patch identity this run advanced",
                "Promote Windows consensus to its current patch identity", "Converge DaVinci archive status")
    scenarios = [
        # label, inputs, failing steps, step outputs, cancel after, expected {step: outcome}
        ("J2 a routine healthy run commits (unchanged)", routine, set(), {}, "",
         {"commit": "success", "precommit_qa": "success", converge[0]: "success", "__job__": "success"}),
        ("J3 a FAILED run that recorded a new refusal: gates run, the state is committed, the job stays failed",
         routine, {"ingest_enabled"}, {"ingest_enabled": refused}, "",
         {"precommit_logos": "success", "precommit_qa": "success", "commit": "success",
          converge[0]: "skipped", converge[1]: "skipped", converge[2]: "skipped", "__job__": "failure"}),
        ("J4 a FAILED run with no refusal still skips every gate and the commit (unchanged)",
         routine, {"ingest_enabled"}, {}, "",
         {"precommit_logos": "skipped", "precommit_qa": "skipped", "commit": "skipped", "__job__": "failure"}),
        ("J5 refusal path, QA fails: no commit", routine, {"ingest_enabled", "precommit_qa"},
         {"ingest_enabled": refused}, "", {"commit": "skipped", "__job__": "failure"}),
        ("J6 refusal path, the logo gate fails: no commit", routine, {"ingest_enabled", "precommit_logos"},
         {"ingest_enabled": refused}, "", {"precommit_qa": "success", "commit": "skipped", "__job__": "failure"}),
        ("J7 a healthy ingest whose QA fails still does not commit (unchanged)", routine, {"precommit_qa"}, {}, "",
         {"commit": "skipped", "__job__": "failure"}),
        ("J8 a converge failure still skips the gates and the commit (unchanged)", routine, {converge[0]}, {}, "",
         {"precommit_logos": "skipped", "precommit_qa": "skipped", "commit": "skipped"}),
        ("J9 a dry run never commits, refusal or not", {"source": None, "dry_run": "true"}, {"ingest_enabled"},
         {"ingest_enabled": refused}, "", {"precommit_qa": "skipped", "commit": "skipped"}),
        ("J10 a cancelled run never commits on the refusal path", routine, {"ingest_enabled"},
         {"ingest_enabled": refused}, "ingest_enabled", {"commit": "skipped"}),
        ("J11 a selected-source dispatch that failed with a new refusal commits too",
         {"source": GRD, "dry_run": "false"}, {"ingest_selected"}, {"ingest_selected": refused}, "",
         {"ingest_enabled": "skipped", "commit": "success", "__job__": "failure"}),
        ("J12 an output of 'false' is not the refusal path", routine, {"ingest_enabled"},
         {"ingest_enabled": {"access_refusal_recorded": "false"}}, "", {"commit": "skipped"}),
    ]
    for label, inputs, fails, outputs, cancel_after, expected in scenarios:
        ran = simulate_job(steps, inputs, fails, outputs, cancel_after)
        wrong = {k: (ran.get(k), v) for k, v in expected.items() if ran.get(k) != v}
        check(label, not wrong, f"got/expected {wrong}")
    run_text = "\n".join(str(st.get("run") or "") for st in steps if st.get("id") in ("ingest_enabled", "ingest_selected"))
    check("J13 the ingestion steps still run the runner directly, so its exit code is the step's outcome",
          "|| rc" not in run_text and "continue-on-error" not in json.dumps(steps)
          and run_text.count("python auxsays/scripts/patch_ingest.py") == 4, run_text)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
