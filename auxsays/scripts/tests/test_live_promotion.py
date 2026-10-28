#!/usr/bin/env python3
"""Every record writer promotes and revokes live consensus from one decision (AUX-056).

WHY IT EXISTS. Until this change no writer could store `consensus_live`: `maturity.certify_live`
declined every identity, so the label existed only as a deploy-time rendering decision. Now every
writer holds a run context -- the whole counted population, the method-health telemetry, the
thresholds and one instant -- and asks `live_eligibility.evaluate`, the same function the deploy-time
projection runs. A certifying identity is written live by whichever writer runs next, and revoked by
whichever writer runs after its monitoring stops. Nothing else about the record may move with it.

WHAT IS PINNED HERE, on synthetic site trees (records + evidence store + method health + config):
  [A] reconciliation, run as build_consensus_from_evidence.main runs it, promotes a certifying
      identity to the canonical live tuple and logs the transition with its reasons.
  [B] the consensus writer, run as its main runs it, proposes the same live tuple and its write
      keeps it.
  [C] a second run of both writers changes nothing.
  [D] monitoring goes stale: EACH writer on its own revokes all four axes together to the pilot
      tuple; counts, citations and verdict fields are untouched.
  [E] monitoring restored: each writer restores live.
  [F] a maturity-only change appends no "User reports found" status event.
  [G] the population empties: the official tuple on all four axes, projections retracted.
  [H] a writer holding no run context never promotes; an unreadable context declines and never
      raises; a writer's count that differs from the context's population declines.
  [I] a non-promotion product (DaVinci) and an exclusivity-short identity never promote.
  [J] verdict invariance: the decision fields are identical whether the identity is live or not.
  [K] QA: `live_exclusive_below_high_rung` fires on a live claim short of exclusive URLs.
  [L] the graph router blocks the run when PROMOTE returns non-zero; writeback is never reached.
  [M] the revalidation guard accepts the canonical live tuple and still refuses a mixed one.
  [N] davinci-updates.yml's reconcile is scoped to DaVinci; the cron lane's stays unscoped.

THE CLOCK. The writers' mains read the wall clock themselves (no test hook was added to a production
CLI), so the synthetic tree's timestamps are laid out relative to NOW, read once at import: fresh is
two hours old, stale twenty days, the release forty days. Library-level checks pass NOW explicitly.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_live_promotion.py
"""
from __future__ import annotations

import io
import json
import shlex
import sys
import tempfile
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
import build_consensus_from_evidence as bce  # noqa: E402
import qa_patch_records as qa  # noqa: E402
import revalidate_consensus_evidence as revalidate  # noqa: E402
from lib import collector_ownership as ownership  # noqa: E402
from lib import live_eligibility as le  # noqa: E402
from lib import maturity  # noqa: E402
from lib import report_counts as rc  # noqa: E402
from lib.write_update_record import DEFERRED_CONSENSUS_REPORT  # noqa: E402
from patch_collectors.base import (load_front_matter_and_body, normalize_url,  # noqa: E402
                                   write_front_matter_and_body)

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
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


# ------------------------------------------------------------------------------- synthetic world
def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


NOW = datetime.now(timezone.utc).replace(microsecond=0)
RELEASED = _iso(NOW - timedelta(days=40))
FRESH = _iso(NOW - timedelta(hours=2))
STALE = _iso(NOW - timedelta(days=20))      # after the release, past the 14-day freshness limit
HIGH = maturity.LIVE_MIN_ACCEPTED_REPORTS
N = HIGH + 7

OBS, DAV = "obs-studio", "blackmagic-davinci"
A_VER, S_VER, X_VER, D_VER = "99.0.0", "98.0.0", "97.0.0", "21.9"
A_KEY = (OBS, A_VER, "")
LABEL = {OBS: "OBS Studio", DAV: "DaVinci Resolve"}
AXES = set(maturity.AXES)
DECISION_FIELDS = ("quick_verdict", "update_decision_label", "update_decision_body",
                   "practical_recommendations", "update_consensus_label",
                   "update_consensus_confidence")
COUNT_FIELDS = ("update_report_count", "confirmed_patch_specific_report_count",
                "accepted_report_sources", "evidence_samples", "update_consensus_summary",
                "consensus_report", "evidence_last_checked", "status_events")


def methods(product: str) -> list[str]:
    return sorted(ownership.ALLOWED_METHODS[product] - ownership.MANUAL_ONLY_METHODS)


def report_rows(product: str, version: str, n: int, *, prefix: str | None = None) -> list[dict]:
    method = methods(product)[0]
    base_url = prefix or f"https://forum.test/{product}/{version}"
    return [{"id": f"{product}-{version}-{i}", "product_id": product, "update_version": version,
             "target_build": "", "source_url": f"{base_url}/t/{i}", "source_type": f"fam-{method}",
             "source_name": "Test forum", "report_title": f"crash after update {i}",
             "issue_theme": "crash", "sentiment": "negative", "severity": "high",
             "captured_at": "2026-10-01T00:00:00Z", "counted": True, "patch_version_matched": True}
            for i in range(n)]


def all_rows(*, without: tuple[str, str] | None = None) -> list[dict]:
    """A: 40 exclusive OBS reports. S: 40 OBS reports, 10 of whose URLs X also counts (30
    exclusive). X: those 10. D: 40 exclusive DaVinci reports. All monitoring-healthy."""
    shared = "https://forum.test/shared"
    rows = (report_rows(OBS, A_VER, N) + report_rows(OBS, S_VER, N, prefix=shared)
            + report_rows(OBS, X_VER, 10, prefix=shared) + report_rows(DAV, D_VER, N))
    return [r for r in rows if (r["product_id"], r["update_version"]) != without]


def health_rows(product: str, version: str, last_run: str) -> list[dict]:
    return [{"product_id": product, "update_version": version, "target_build": "",
             "method_id": m, "source_type": f"fam-{m}", "status": "success", "last_run": last_run}
            for m in methods(product)]


def emh(a_last_run: str = FRESH) -> list[dict]:
    return (health_rows(OBS, A_VER, a_last_run) + health_rows(OBS, S_VER, FRESH)
            + health_rows(OBS, X_VER, FRESH) + health_rows(DAV, D_VER, FRESH))


def record_front(product: str, version: str) -> dict:
    slug = version.replace(".", "-")
    return {"layout": "aux-update", "title": f"{LABEL[product]} {version}",
            "permalink": f"/updates/test/{product}/{slug}/", "update_entry": True,
            "company_id": "test", "product_id": product, "update_product": LABEL[product],
            "update_version": version, "target_build": "", "update_published_at": RELEASED,
            "update_status": "current", "update_report_count": 0,
            "confirmed_patch_specific_report_count": 0, **maturity.OFFICIAL_ONLY.axes(),
            "consensus_report": DEFERRED_CONSENSUS_REPORT, "update_consensus_label": "Insufficient data",
            "evidence_last_checked": "",
            "status_events": [{"at": RELEASED, "label": "Official source captured",
                               "note": "Release notes captured."}]}


IDS = {"A": (OBS, A_VER), "S": (OBS, S_VER), "X": (OBS, X_VER), "D": (DAV, D_VER)}


def rec_path(root: Path, ident: str) -> Path:
    product, version = IDS[ident]
    return root / "updates" / "generated" / f"2026-01-01-{product}-{version.replace('.', '-')}.md"


def _dump(path: Path, payload) -> None:
    path.write_bytes(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).encode("utf-8"))


def write_store(root: Path, rows: list[dict]) -> None:
    _dump(root / "_data" / "consensus_evidence.yml", {"evidence": rows})


def write_emh(root: Path, rows: list[dict]) -> None:
    _dump(root / "_data" / "evidence_method_health.yml", {"methods": rows})


def build_tree(root: Path) -> None:
    (root / "updates" / "generated").mkdir(parents=True)
    (root / "_data").mkdir()
    for ident, (product, version) in IDS.items():
        write_front_matter_and_body(rec_path(root, ident), record_front(product, version), "\nbody\n")
    write_store(root, all_rows())
    write_emh(root, emh())
    (root / "_config.yml").write_bytes(b"monitoring_min_healthy_methods: 2\nmonitoring_max_age_days: 14\n")


def front(root: Path, ident: str) -> dict:
    return load_front_matter_and_body(rec_path(root, ident))[0]


def axes(root: Path, ident: str) -> dict:
    return maturity.stored_axes(front(root, ident))


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted((root / "updates" / "generated").glob("*.md"))}


def restore(root: Path, snap: dict[str, bytes]) -> None:
    for name, data in snap.items():
        (root / "updates" / "generated" / name).write_bytes(data)


def load_front_matter_and_body_bytes(snap: dict[str, bytes], name: str) -> dict:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / name
        path.write_bytes(snap[name])
        return load_front_matter_and_body(path)[0]


def changed_keys(before: dict, after: dict) -> set[str]:
    return {k for k in set(before) | set(after) if before.get(k) != after.get(k)}


@contextmanager
def site(root: Path):
    """Point both writers' module paths at `root`, exactly as their mains resolve them."""
    saved_b = (bce.EVIDENCE_PATH, bce.GENERATED_DIR, bce.OUT_PATH)
    saved_a = (acr.DEFAULT_EVIDENCE_PATH, acr.GENERATED_DIR, acr.ROOT, acr.METHOD_HEALTH_PATH)
    try:
        bce.EVIDENCE_PATH = root / "_data" / "consensus_evidence.yml"
        bce.GENERATED_DIR = root / "updates" / "generated"
        bce.OUT_PATH = root / "consensus_status.json"
        acr.DEFAULT_EVIDENCE_PATH = root / "_data" / "consensus_evidence.yml"
        acr.GENERATED_DIR = root / "updates" / "generated"
        acr.ROOT = root
        acr.METHOD_HEALTH_PATH = root / "_data" / "evidence_method_health.yml"
        yield
    finally:
        bce.EVIDENCE_PATH, bce.GENERATED_DIR, bce.OUT_PATH = saved_b
        acr.DEFAULT_EVIDENCE_PATH, acr.GENERATED_DIR, acr.ROOT, acr.METHOD_HEALTH_PATH = saved_a


def run_main(fn, argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = fn(argv)
    return code, out.getvalue(), err.getvalue()


def reconcile(root: Path) -> tuple[int, str]:
    with site(root):
        code, out, _err = run_main(bce.main, [])
    return code, out


def promote(root: Path, product: str = OBS) -> tuple[int, dict, str]:
    with site(root):
        code, out, err = run_main(acr.main, ["--product-id", product, "--write-all", "--confirm-write"])
    try:
        payload = json.loads(out)
    except ValueError:
        payload = {}
    return code, payload, err


def lane(root: Path) -> None:
    reconcile(root)
    promote(root, OBS)
    promote(root, DAV)


def context(root: Path, now: datetime = NOW) -> le.RunContext:
    fronts = [load_front_matter_and_body(p)[0] for p in sorted((root / "updates" / "generated").glob("*.md"))]
    rows = rc.load_evidence_store(root / "_data" / "consensus_evidence.yml")
    return le.load_run_context(root, now=now).bind_evidence(rows, fronts)


def proposal(root: Path, ident: str, live_context) -> dict:
    product, version = IDS[ident]
    with site(root):
        index = acr._index_generated_records()
        rows = rc.load_evidence_store(root / "_data" / "consensus_evidence.yml")
        results = acr.run_dry_run(evidence_path=acr.DEFAULT_EVIDENCE_PATH, product_id_filter=product,
                                  is_candidate_mode=False, records_index=index, rows=rows,
                                  write_requested=True, live_context=live_context)
    return next(r for r in results if r["update_version"] == version)


# ------------------------------------------------------------------------------- [A]-[G] the lane
def section_lane(root: Path) -> dict[str, bytes]:
    print("\n[A] reconciliation promotes a certifying identity")
    code, out = reconcile(root)
    check("A1 build_consensus_from_evidence.main exits 0", code == 0, out[-300:])
    check("A2 the certifying identity is written with the canonical live tuple on all four axes",
          axes(root, "A") == maturity.CONSENSUS_LIVE.axes(), str(axes(root, "A")))
    check("A3 ...beside its authoritative count", front(root, "A").get("update_report_count") == N)
    name = rec_path(root, "A").name
    check("A4 the run log names the transition and why", f"{name}: maturity official -> live (certified)" in out,
          out[-600:])

    print("\n[B] the consensus writer proposes the same tuple, and its write keeps it")
    code, payload, err = promote(root, OBS)
    result = next((r for r in payload.get("results") or [] if r["update_version"] == A_VER), {})
    proposed = result.get("proposed_fields_if_written") or {}
    check("B1 apply_consensus_to_records.main exits 0", code == 0, err[-300:])
    check("B2 its proposal for the certified identity is the live tuple",
          {a: proposed.get(a) for a in maturity.AXES} == maturity.CONSENSUS_LIVE.axes(),
          str({a: proposed.get(a) for a in maturity.AXES}))
    after = front(root, "A")
    check("B3 ...and the record it wrote is still live, now carrying its projections",
          maturity.stored_axes(after) == maturity.CONSENSUS_LIVE.axes()
          and len(after.get("accepted_report_sources") or []) == N and after.get("quick_verdict"),
          str(maturity.stored_axes(after)))
    promote(root, DAV)

    print("\n[C] survival: a second run of both writers changes nothing")
    live = snapshot(root)
    lane(root)
    check("C1 every record is byte-identical after a second full lane", snapshot(root) == live,
          str([k for k in live if snapshot(root).get(k) != live[k]]))
    # The writer already skips an event equivalent to the record's LATEST one, and here that is the
    # "User reports found" event its own promotion wrote -- which would make F1/F2 pass with the
    # maturity-only rule deleted. A later, different event (as any other step may append) makes the
    # rule the only thing standing between a maturity flip and a new event.
    data, body = load_front_matter_and_body(rec_path(root, "A"))
    data["status_events"] = [*data.get("status_events", []),
                             {"at": FRESH, "label": "Record updated", "note": "Official source refreshed."}]
    write_front_matter_and_body(rec_path(root, "A"), data, body)
    live = snapshot(root)

    print("\n[D] monitoring goes stale: each writer revokes on its own")
    write_emh(root, emh(a_last_run=STALE))
    before = front(root, "A")
    code, out = reconcile(root)
    revoked = front(root, "A")
    check("D1 reconciliation revokes all four axes together, to the pilot tuple",
          maturity.stored_axes(revoked) == maturity.PILOT_SAMPLE.axes(), str(maturity.stored_axes(revoked)))
    check("D2 ...and changes NOTHING else on the record", changed_keys(before, revoked) == AXES,
          str(sorted(changed_keys(before, revoked))))
    check("D3 the run log names the revocation and the stale method",
          f"{rec_path(root, 'A').name}: maturity live -> pilot (monitoring:stale:" in out, out[-600:])
    restore(root, live)
    code, payload, err = promote(root, OBS)
    by_writer = front(root, "A")
    check("D4 the consensus writer, run alone, revokes all four axes too",
          maturity.stored_axes(by_writer) == maturity.PILOT_SAMPLE.axes(), str(maturity.stored_axes(by_writer)))
    check("D5 ...touching only the axes and its record_last_updated stamp",
          AXES <= changed_keys(before, by_writer) <= AXES | {"record_last_updated"},
          str(sorted(changed_keys(before, by_writer))))
    check("D6 counts, citations and verdict fields are byte-for-byte the live record's",
          all(by_writer.get(f) == before.get(f) for f in (*COUNT_FIELDS, *DECISION_FIELDS)))
    check("D7 the writer logs the transition it wrote",
          "maturity updates/generated/" in err.replace("\\", "/") and "live -> pilot" in err, err[-400:])

    print("\n[F] a maturity-only change appends no status event")
    check("F1 the revocation appended no 'User reports found' event",
          by_writer.get("status_events") == before.get("status_events"),
          str((by_writer.get("status_events") or [])[-1:]))

    print("\n[E] monitoring restored: live again, from either writer")
    write_emh(root, emh())
    code, payload, err = promote(root, OBS)
    restored = front(root, "A")
    check("E1 the consensus writer restores the live tuple", maturity.stored_axes(restored)
          == maturity.CONSENSUS_LIVE.axes(), str(maturity.stored_axes(restored)))
    check("F2 ...and the restoration appended no status event either",
          restored.get("status_events") == before.get("status_events"))
    restore(root, live)
    write_emh(root, emh(a_last_run=STALE))
    reconcile(root)
    write_emh(root, emh())
    reconcile(root)
    check("E2 reconciliation restores the live tuple", axes(root, "A") == maturity.CONSENSUS_LIVE.axes(),
          str(axes(root, "A")))
    # Values, not bytes: the two writers serialise YAML with different line widths.
    check("E3 a revoke-and-restore cycle leaves every record's front matter as it was",
          all(front(root, i) == load_front_matter_and_body_bytes(live, rec_path(root, i).name)
              for i in IDS))

    print("\n[G] the population empties: official on all four axes, projections retracted")
    write_store(root, all_rows(without=(OBS, A_VER)))
    code, out = reconcile(root)
    zero = front(root, "A")
    check("G1 the official tuple on all four axes and a zero count",
          maturity.stored_axes(zero) == maturity.OFFICIAL_ONLY.axes() and zero.get("update_report_count") == 0,
          str(maturity.stored_axes(zero)))
    check("G2 every count projection retracted (promotion product)",
          not any(f in zero for f in rc.ZERO_COUNT_PROJECTION_FIELDS)
          and zero.get("consensus_report") == DEFERRED_CONSENSUS_REPORT, str(sorted(zero)))
    check("G3 the run log names live -> official", f"{rec_path(root, 'A').name}: maturity live -> official" in out,
          out[-600:])
    write_store(root, all_rows())
    restore(root, live)
    return live


# ------------------------------------------------------------------------------- [F] write plan
def section_write_plan(root: Path) -> None:
    print("\n[F] the write plan: maturity-only vs a real change")
    data = front(root, "A")
    fields = {**{k: data.get(k) for k in COUNT_FIELDS if k != "status_events"},
              **maturity.PILOT_SAMPLE.axes(), "record_last_updated": "2099-01-01T00:00:00Z",
              "status_events_append": {"at": "2099-01-01T00:00:00Z", "label": "User reports found",
                                       "note": f"User report count updated to {N}."}}
    plan = acr._record_write_plan(data, fields)
    check("F3 an axes-only difference writes the axes but skips the event, by name",
          plan["status_events_append"]["reason"] == "skipped_maturity_only_change"
          and "status_events_append" not in plan["fields"]
          and all(plan["fields"].get(a) == v for a, v in maturity.PILOT_SAMPLE.axes().items()),
          str(plan["status_events_append"]))
    plan = acr._record_write_plan(data, {**fields, "update_report_count": N + 1,
                                         "status_events_append": {**fields["status_events_append"],
                                                                  "note": f"User report count updated to {N + 1}."}})
    check("F4 a count change beside it still appends the event",
          plan["status_events_append"]["reason"] == "applied_substantive_record_change"
          and "status_events_append" in plan["fields"], str(plan["status_events_append"]))


# ------------------------------------------------------------------------------- [H]-[J] library
def section_library(root: Path) -> None:
    print("\n[H] no context, an unreadable one, or a mismatched population never promotes")
    rows = rc.load_evidence_store(root / "_data" / "consensus_evidence.yml")
    gen = root / "updates" / "generated"
    live = snapshot(root)
    rec_a = front(root, "A")
    check("H1 certify_live with no run context is NOT_ENABLED for a certifying identity",
          maturity.certify_live(rec_a, [r for r in rows if r["update_version"] == A_VER])
          == maturity.NOT_ENABLED and context(root).decide(rec_a).live)
    check("H2 the consensus writer with no context proposes the non-live tuple",
          {a: proposal(root, "A", None)["proposed_fields_if_written"].get(a) for a in maturity.AXES}
          == maturity.PILOT_SAMPLE.axes())
    with redirect_stdout(io.StringIO()):
        rc.reconcile_record_counts(rows, gen)
    check("H3 reconciliation with no context writes a live record back to pilot -- never live",
          axes(root, "A") == maturity.PILOT_SAMPLE.axes(), str(axes(root, "A")))
    with redirect_stdout(io.StringIO()):
        rc.reconcile_record_counts(rows, gen)
    check("H4 ...and never promotes the pilot record it left", axes(root, "A") == maturity.PILOT_SAMPLE.axes())
    restore(root, live)

    emh_path = root / "_data" / "evidence_method_health.yml"
    emh_bytes = emh_path.read_bytes()
    emh_path.unlink()
    broken = le.load_run_context(root, now=NOW)
    check("H5 unreadable telemetry yields a context that names why, without raising",
          bool(broken.unavailable) and broken.decide(rec_a).live is False
          and broken.decide(rec_a).reasons[0].startswith("context_unavailable:"), str(broken.decide(rec_a)))
    code, out = reconcile(root)
    check("H6 reconciliation with no readable telemetry exits 0, warns, and writes nothing live",
          code == 0 and "::warning::live eligibility unavailable" in out
          and axes(root, "A") == maturity.PILOT_SAMPLE.axes(), out[-300:])
    emh_path.write_bytes(emh_bytes)
    restore(root, live)
    ctx = context(root)
    own = [r for r in rows if r["update_version"] == A_VER]
    mismatch = ctx.decide(rec_a, own[:-1])
    check("H7 a writer whose count differs from the context's population declines, by name",
          mismatch.live is False and mismatch.reasons == (f"population_mismatch:{N - 1}!={N}",),
          str(mismatch))
    check("H8 ...while the matching population certifies", ctx.decide(rec_a, own).live)

    print("\n[I] non-promotion products and exclusivity-short identities never promote")
    dav = ctx.decide(front(root, "D"))
    short = ctx.decide(front(root, "S"))
    check("I1 DaVinci, with 40 exclusive reports and healthy monitoring, declines ONLY as a "
          "non-promotion product", dav.reasons == ("not_promotion_product",), str(dav))
    check("I2 an identity with 40 reports but 30 exclusive URLs declines on exclusivity alone",
          short.reasons == ("exclusive_below_high_rung:30",), str(short))
    check("I3 ...and the lane stored neither of them live",
          axes(root, "D") == maturity.PILOT_SAMPLE.axes() and axes(root, "S") == maturity.PILOT_SAMPLE.axes()
          and axes(root, "X") == maturity.PILOT_SAMPLE.axes())

    print("\n[J] verdict invariance")
    certified = proposal(root, "A", ctx)["proposed_fields_if_written"]
    declined = proposal(root, "A", context(root, now=NOW + timedelta(days=30)))["proposed_fields_if_written"]
    check("J1 the same evidence certified and declined proposes different maturity",
          certified.get("evidence_state") == "consensus_live" and declined.get("evidence_state") == "pilot_sample")
    check("J2 ...and IDENTICAL decision fields",
          all(f in certified for f in DECISION_FIELDS)
          and all(certified.get(f) == declined.get(f) for f in DECISION_FIELDS),
          str([f for f in DECISION_FIELDS if certified.get(f) != declined.get(f)]))
    check("J3 ...and identical count and citation projections",
          all(certified.get(f) == declined.get(f) for f in
              ("update_report_count", "accepted_report_sources", "evidence_samples",
               "update_consensus_summary", "consensus_report")))


# ------------------------------------------------------------------------------- [K] QA
def section_qa(root: Path) -> None:
    print("\n[K] QA: a live claim needs the High rung in EXCLUSIVE accepted URLs")
    rows = rc.load_evidence_store(root / "_data" / "consensus_evidence.yml")
    groups = rc.counted_evidence_rows(rows, windows_targets={})
    counts = {k: len(v) for k, v in groups.items()}
    urls = {k: {normalize_url(str(r.get("source_url") or "")) for r in v} for k, v in groups.items()}

    def codes(data: dict) -> list[str]:
        errors, _ = qa.scan_live_consensus_claims([(Path("x.md"), data)], counts, urls)
        return [e["code"] for e in errors]

    live_a = front(root, "A")
    s = front(root, "S")
    live_s = {**s, **maturity.CONSENSUS_LIVE.axes()}
    check("K1 the writer's own live record passes every live-claim check", codes(live_a) == [],
          str(codes(live_a)))
    check("K2 a live claim with 40 reports but 30 exclusive URLs is an ERROR, by name",
          "live_exclusive_below_high_rung" in codes(live_s), str(codes(live_s)))
    check("K3 ...and it is the ONLY error: everything else about that claim is well formed",
          codes(live_s) == ["live_exclusive_below_high_rung"], str(codes(live_s)))
    alone = {k: v for k, v in urls.items() if k != (OBS, X_VER, "")}
    errors, _ = qa.scan_live_consensus_claims([(Path("x.md"), live_s)], counts, alone)
    check("K4 the same claim passes once no other identity counts its URLs (non-vacuous)",
          "live_exclusive_below_high_rung" not in [e["code"] for e in errors])


# ------------------------------------------------------------------------------- [L] graph router
def section_router() -> None:
    print("\n[L] the graph blocks the run when PROMOTE fails")
    import orchestrate_evidence_run as orch  # noqa: PLC0415 - heavy; only this section needs it
    from lib.orchestration import BLOCKED, DONE, OrchestrationState  # noqa: PLC0415

    def run_from_promote(rc_value: int) -> tuple[OrchestrationState, list]:
        calls: list = []
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "repo").mkdir()
            pipeline = orch.Pipeline(
                tdp / "repo", [OBS], write=True, checkpoint_dir=tdp / "ckpt", methods={},
                evidence_path=tdp / "absent.yml", health_path=tdp / "health.yml",
                generated_dir=tdp / "gen",
                authorities={"promote": lambda: {"rc": rc_value}, "qa": lambda: {"rc": 0},
                             "audit": lambda: {"rc": 0}},
                writeback=lambda: calls.append("writeback") or {"outcome": "stub"})
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                state = pipeline.build().run(OrchestrationState(run_id="t", product_ids=[OBS]), "PROMOTE")
        return state, calls

    failed, failed_calls = run_from_promote(2)
    check("L1 PROMOTE rc != 0 ends the run BLOCKED, named promote_failed",
          failed.terminal == BLOCKED and any(f["reason"] == "promote_failed" for f in failed.failures),
          f"{failed.terminal} {failed.failures}")
    check("L2 ...and the writeback is never reached", failed_calls == [], str(failed_calls))
    ok, ok_calls = run_from_promote(0)
    check("L3 the same run with PROMOTE rc 0 reaches the writeback and DONE (non-vacuous)",
          ok.terminal == DONE and ok_calls == ["writeback"], f"{ok.terminal} {ok.failures} {ok_calls}")


# ------------------------------------------------------------------------------- [M] revalidate
def section_revalidate() -> None:
    print("\n[M] the revalidation guard accepts a live record and still refuses a mixed one")
    count = 40

    def guard(axes_: dict, n: int = count) -> dict:
        with tempfile.TemporaryDirectory() as td:
            gen = Path(td)
            lines = ["---", f"product_id: {revalidate.EXPECTED_WRITEBACK_PRODUCT}",
                     f"update_version: {revalidate.EXPECTED_WRITEBACK_VERSION}",
                     f"update_report_count: {n}", f"confirmed_patch_specific_report_count: {n}",
                     *(f"{k}: {v}" for k, v in axes_.items()),
                     "evidence_last_checked: '2026-01-01T00:00:00Z'", "---", "body", ""]
            (gen / revalidate.EXPECTED_WRITEBACK_GENERATED_FILE).write_bytes("\n".join(lines).encode("utf-8"))
            result = {"product_id": revalidate.EXPECTED_WRITEBACK_PRODUCT,
                      "update_version": revalidate.EXPECTED_WRITEBACK_VERSION,
                      "counted_rows_selected": n, "fetches_urls": True,
                      "classification_counts": {"verified": n}}
            return revalidate.guarded_generated_freshness_writeback(
                result, generated_dir=gen, confirm_product=revalidate.EXPECTED_WRITEBACK_PRODUCT,
                confirm_version=revalidate.EXPECTED_WRITEBACK_VERSION, timestamp="2099-01-01T00:00:00Z")

    check("M1 the pilot tuple is accepted, as before", guard(maturity.PILOT_SAMPLE.axes())["success"] is True)
    live = guard(maturity.CONSENSUS_LIVE.axes())
    check("M2 the canonical live tuple is accepted: a live record stays revalidatable",
          live["success"] is True, str(live["guard_failures"]))
    mixed = guard({**maturity.CONSENSUS_LIVE.axes(), "intelligence_stage": "pilot"})
    check("M3 a tuple live on three axes and pilot on the fourth is refused",
          mixed["success"] is False and mixed["guard_failures"], str(mixed["guard_failures"]))
    thin = guard(maturity.CONSENSUS_LIVE.axes(), n=HIGH - 1)
    check("M4 the live tuple below the High rung is refused", thin["success"] is False)


# ------------------------------------------------------------------------------- [N] workflows
def _invocations(workflow: Path, script: str) -> list[list[str]]:
    """Every invocation of `script` in the workflow's run: scalars, tokenised the way a shell would
    (continuations joined, comments stripped quote-aware) -- not a grep of the file."""
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    found = []
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            text = str(step.get("run") or "").replace("\\\n", " ")
            for line in text.splitlines():
                tokens = shlex.split(line, comments=True)
                if any(t.endswith(script) for t in tokens):
                    found.append(tokens)
    return found


def _flag(tokens: list[str], flag: str) -> list[str]:
    values = [tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t == flag]
    return values + [t.split("=", 1)[1] for t in tokens if t.startswith(flag + "=")]


def section_workflows() -> None:
    print("\n[N] the dispatch-only DaVinci lane reconciles only DaVinci")
    wf = _REPO / ".github" / "workflows"
    dav = _invocations(wf / "davinci-updates.yml", "build_consensus_from_evidence.py")
    check("N1 davinci-updates.yml reconciles, and every reconcile names exactly blackmagic-davinci",
          bool(dav) and all(_flag(t, "--product-id") == [DAV] for t in dav), str(dav))
    cron = _invocations(wf / "obs-evidence-collection.yml", "build_consensus_from_evidence.py")
    check("N2 the scheduled lane's reconcile stays unscoped: it is the one that reconciles everything",
          bool(cron) and all(not _flag(t, "--product-id") for t in cron), str(cron))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="auxsays-live-promotion-") as td:
        root = Path(td) / "auxsays"
        build_tree(root)
        section_lane(root)
        section_write_plan(root)
        section_library(root)
        section_qa(root)
    section_router()
    section_revalidate()
    section_workflows()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
