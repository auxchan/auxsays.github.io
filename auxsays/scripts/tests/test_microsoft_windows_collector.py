#!/usr/bin/env python3
"""Tests for the Windows 11 Learn Q&A community-evidence collector.

Offline only: synthetic PatchRecords/targets and canned candidate dicts; the Learn Q&A
source is monkeypatched, so no network. No _data writes, no live generated records. Proves
the deterministic acceptance rules, exact KB/OS-build identity stamping, dedup, method
health, and that accepted rows are correctly aged out by the PR#14 identity gate on
rollover.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_microsoft_windows_collector.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from patch_collectors.base import PatchRecord, windows_identity_gate
import patch_collectors.microsoft_windows as win
import lib.write_update_record as wur

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


TARGET_24H2 = {
    "target_feature_version": "24H2",
    "target_kb": "KB5095093",
    "target_os_build": "26100.8737",
    "target_release_date": "2026-06-23T00:00:00Z",
    "update_version": "24H2",
}
# 25H2 shares KB5095093 with 24H2 but has a distinct OS build.
TARGET_25H2 = {
    "target_feature_version": "25H2",
    "target_kb": "KB5095093",
    "target_os_build": "26200.8737",
    "target_release_date": "2026-06-23T00:00:00Z",
    "update_version": "25H2",
}
TARGET_24H2_ROLLED = {**TARGET_24H2, "target_kb": "KB5099999", "target_os_build": "26100.9001", "target_release_date": "2026-07-14T00:00:00Z"}

REC_24H2 = PatchRecord("microsoft-windows-11", "24H2", Path("2026-06-23-windows-11-24h2.md"), "2026-06-23T00:00:00Z", "current", "Windows 11")
REC_25H2 = PatchRecord("microsoft-windows-11", "25H2", Path("2026-06-23-windows-11-25h2.md"), "2026-06-23T00:00:00Z", "current", "Windows 11")
CAPTURED = "2026-07-01T00:00:00Z"


def cand(title: str, body: str, date: str = "2026-06-30T00:00:00Z", q_slug: str = "q") -> dict:
    return {
        "source_type": "microsoft_learn_qna",
        "source_name": "Microsoft Learn Q&A",
        "source_url": f"https://learn.microsoft.com/en-us/answers/questions/2412345/{q_slug}",
        "parent_title": title,
        "report_title": title,
        "report_text": body,
        "source_date": date,
    }


def row_reason(target, title, body, **kw):
    row = win.row_from_candidate(REC_24H2 if target is TARGET_24H2 or target is TARGET_24H2_ROLLED else REC_25H2, target, cand(title, body, **kw), CAPTURED)
    return row


def run() -> int:
    print("=" * 60)
    print("Windows 11 Learn Q&A collector tests")
    print("=" * 60)

    # --- accepted -----------------------------------------------------------
    r = row_reason(TARGET_24H2, "KB5095093 breaks printing on Windows 11 24H2", "After installing KB5095093 on Windows 11 24H2 my printer stopped working.")
    check("accepted: exact KB + feature train counts", r.get("counted") is True and r.get("match_basis") == "exact_kb_feature_train", str({k: r.get(k) for k in ("counted", "match_basis", "exclusion_reason")}))
    check("accepted row stamps matched_kb + matched_feature_version", r.get("matched_kb") == "KB5095093" and r.get("matched_feature_version") == "24H2", str({k: r.get(k) for k in ("matched_kb", "matched_feature_version", "matched_os_build")}))

    rb = row_reason(TARGET_24H2, "BSOD after update", "OS Build 26100.8737 causes a BSOD every boot after the update.")
    check("accepted: exact OS build counts", rb.get("counted") is True and rb.get("match_basis") == "exact_os_build" and rb.get("matched_os_build") == "26100.8737", str({k: rb.get(k) for k in ("counted", "match_basis", "matched_os_build")}))

    # shared KB across trains: 25H2 record, report cites KB5095093 + 25H2 -> counts for 25H2.
    r25 = row_reason(TARGET_25H2, "KB5095093 boot failure on 25H2", "Windows 11 25H2 with KB5095093 now fails to boot.")
    check("accepted: shared KB counts for the matching train (25H2)", r25.get("counted") is True and r25.get("matched_feature_version") == "25H2", str({k: r25.get(k) for k in ("counted", "matched_feature_version")}))
    # ...but the same KB on the wrong build does NOT count for 25H2.
    r25b = row_reason(TARGET_25H2, "26100.8737 BSOD", "OS Build 26100.8737 BSOD on every boot.")
    check("rejected: 24H2 build does not count for the 25H2 record", r25b.get("counted") is False, str(r25b.get("exclusion_reason")))

    # --- rejected -----------------------------------------------------------
    def reason(title, body, target=TARGET_24H2, **kw):
        return row_reason(target, title, body, **kw).get("exclusion_reason")

    check("rejected: exact KB with wrong feature train", reason("KB5095093 on 25H2 BSOD", "KB5095093 on Windows 11 25H2 causes a BSOD.") == "wrong_feature_train_for_kb", reason("KB5095093 on 25H2 BSOD", "KB5095093 on Windows 11 25H2 causes a BSOD."))
    check("rejected: wrong KB for the same feature train", reason("KB5090000 BSOD", "KB5090000 on Windows 11 24H2 causes a BSOD.") == "wrong_kb_for_current_patch", reason("KB5090000 BSOD", "KB5090000 on Windows 11 24H2 causes a BSOD."))
    check("rejected: missing KB/build identity", reason("Windows 11 crashes", "Windows 11 crashes after the update, no idea which one.") == "missing_kb_or_build", reason("Windows 11 crashes", "Windows 11 crashes after the update, no idea which one."))
    check("rejected: vague 'latest update' without exact KB/build", reason("Latest update broke my PC", "The latest Windows update caused a BSOD on my machine.") == "vague_latest_update", reason("Latest update broke my PC", "The latest Windows update caused a BSOD on my machine."))
    check("rejected: date-only inference", reason("Patch Tuesday broke boot", "After June 2026 Patch Tuesday my PC won't boot.") == "date_only_inference", reason("Patch Tuesday broke boot", "After June 2026 Patch Tuesday my PC won't boot."))
    check("rejected: generic support / how-to question", reason("How do I update?", "How do I install Windows 11 24H2? Is it safe?") == "generic_support_request", reason("How do I update?", "How do I install Windows 11 24H2? Is it safe?"))
    check("rejected: official notes / known-issues doc", reason("24H2 release notes", "Windows 11 24H2 release notes and what's new in this version.") == "official_note_not_user_report", reason("24H2 release notes", "Windows 11 24H2 release notes and what's new in this version."))
    check("rejected: release announcement", reason("24H2 available", "Windows 11 24H2 is now available for download.") == "release_announcement_not_user_report", reason("24H2 available", "Windows 11 24H2 is now available for download."))
    check("rejected: source_date before target_release_date", reason("Early build BSOD", "OS Build 26100.8737 BSOD on boot.", date="2026-06-10T00:00:00Z") == "date_before_release", reason("Early build BSOD", "OS Build 26100.8737 BSOD on boot.", date="2026-06-10T00:00:00Z"))
    check("rejected: tenant/service incident without client identity", reason("Exchange Online outage", "Our Exchange Online tenant had a service incident, no printing at all.") == "tenant_service_incident_not_client_patch", reason("Exchange Online outage", "Our Exchange Online tenant had a service incident, no printing at all."))

    # --- dedup --------------------------------------------------------------
    dup1 = cand("BSOD after update", "OS Build 26100.8737 causes a BSOD.", q_slug="dup")
    dup2 = cand("BSOD after update (repost)", "OS Build 26100.8737 causes a BSOD again.", q_slug="dup")
    acc, rej = win.evaluate_candidates(REC_24H2, TARGET_24H2, [dup1, dup2], CAPTURED)
    check("duplicate specific question URL is deduped (one accepted)", len(acc) == 1, f"accepted={len(acc)} rejected={len(rej)}")

    # --- accepted row is correctly aged out by the PR#14 identity gate ------
    accepted_row = rb  # exact-build row above, matched_os_build == 26100.8737
    ok_now, _ = windows_identity_gate(accepted_row, TARGET_24H2)
    check("accepted row is valid through the identity gate for the current patch", ok_now is True and accepted_row.get("evidence_valid_for_current_patch") is True)
    ok_after, reason_after = windows_identity_gate(accepted_row, TARGET_24H2_ROLLED)
    check("stale after rollover: the same accepted row would NOT count post-rollover", ok_after is False and reason_after == "stale_due_to_patch_rollover", f"ok={ok_after} reason={reason_after}")

    # --- search terms + record target ---------------------------------------
    check("search terms are exact KB + OS build only (feature train is not a standalone search)", win.search_query_terms(TARGET_24H2) == ["KB5095093", "26100.8737"], str(win.search_query_terms(TARGET_24H2)))
    check("record with no target identity searches nothing (fail-closed, no fake consensus)", win.search_query_terms({}) == [])

    # --- method health ------------------------------------------------------
    check("method status: accepted -> success", win.learn_qna_method_status([{"x": 1}], [{"counted": True}], [], []) == "success")
    check("method status: accepted + errors -> partial", win.learn_qna_method_status([{"x": 1}], [{"counted": True}], [], [{"reason": "x"}]) == "partial")
    check("method status: candidates found, none accepted -> no_results", win.learn_qna_method_status([{"x": 1}], [], [{"counted": False}], []) == "no_results")
    check("method status: only blocked errors -> blocked", win.learn_qna_method_status([], [], [], [{"reason": "learn_qna_search_fetch_failed:blocked:rate_limited", "blocked_signature": "blocked"}]) == "blocked")
    check("method status: only parse errors -> broken", win.learn_qna_method_status([], [], [], [{"reason": "learn_qna_search_fetch_failed:feed_parse_failed:ParseError", "blocked_signature": "broken"}]) == "broken")
    check("method status: reachable, nothing -> no_results", win.learn_qna_method_status([], [], [], []) == "no_results")

    # --- collect_for_record end-to-end (source monkeypatched, no network) ---
    with tempfile.TemporaryDirectory() as d:
        rec_path = Path(d) / "2026-06-23-windows-11-24h2.md"
        rec_path.write_text(wur._dump_record(wur.build_front_matter({
            "company_id": "microsoft", "product_id": "microsoft-windows-11", "company": "Microsoft",
            "software": "Windows 11", "version": "24H2", "published_at": "2026-06-23T00:00:00Z",
            "source_url": "https://learn.microsoft.com/en-us/windows/release-health/",
            "body": "Windows 11 24H2 official record.", "official_summary": "Windows 11 24H2.",
            "target_feature_version": "24H2", "target_kb": "KB5095093",
            "target_os_build": "26100.8737", "target_release_date": "2026-06-23T00:00:00Z",
        })), encoding="utf-8")
        record = PatchRecord("microsoft-windows-11", "24H2", rec_path, "2026-06-23T00:00:00Z", "current", "Windows 11")

        original = win.learn_qna.collect_learn_qna_candidates
        try:
            def _stub_ok(*, queries, context, errors, source_type, source_name):
                return [cand("KB5095093 BSOD on 24H2", "KB5095093 on Windows 11 24H2 causes a BSOD.", q_slug="ok"),
                        cand("How do I update?", "How do I update Windows 11 24H2 safely?", q_slug="howto")]
            win.learn_qna.collect_learn_qna_candidates = _stub_ok
            accepted, rejected, health = win.collect_for_record(record, SimpleNamespace(write=False, since=None, max_pages=1, target_versions=None))
            check("collect_for_record: one accepted, one rejected, success health", len(accepted) == 1 and len(rejected) == 1 and health[0]["status"] == "success", f"acc={len(accepted)} rej={len(rejected)} status={health[0]['status']}")
            check("collect_for_record: accepted row carries matched identity", accepted and accepted[0].get("matched_kb") == "KB5095093", str(accepted[0].get("matched_kb") if accepted else None))

            def _stub_blocked(*, queries, context, errors, source_type, source_name):
                errors.append({"reason": "learn_qna_search_fetch_failed:blocked:rate_limited", "blocked_signature": "blocked"})
                return []
            win.learn_qna.collect_learn_qna_candidates = _stub_blocked
            accepted2, rejected2, health2 = win.collect_for_record(record, SimpleNamespace(write=False, since=None, max_pages=1, target_versions=None))
            check("collect_for_record: blocked source -> blocked health, no accepted rows", len(accepted2) == 0 and health2[0]["status"] == "blocked", f"status={health2[0]['status']}")
        finally:
            win.learn_qna.collect_learn_qna_candidates = original

    # --- non-Windows safety -------------------------------------------------
    check("collector targets only microsoft-windows-11", win.WindowsLearnQnaCollector.product_id == "microsoft-windows-11")
    # A non-Windows evidence row is never touched by this collector's identity logic;
    # the shared gate only fires for microsoft-windows-11 (covered by test_windows_patch_identity).
    obs_gate_ok, _ = windows_identity_gate({"matched_os_build": "", "matched_kb": ""}, {"target_os_build": "", "target_kb": ""})
    check("non-Windows/empty identity is not silently counted (fail-closed)", obs_gate_ok is False)

    # --- safety: NOT registered + no writeback by default -------------------
    import run_patch_evidence_collection as runner
    check("collector is NOT registered in the production runner (no default Windows writeback)", "microsoft-windows-11" not in runner.COLLECTORS, str(sorted(runner.COLLECTORS)))

    with tempfile.TemporaryDirectory() as d:
        rec_path = Path(d) / "2026-06-23-windows-11-24h2.md"
        rec_path.write_text(wur._dump_record(wur.build_front_matter({
            "company_id": "microsoft", "product_id": "microsoft-windows-11", "company": "Microsoft",
            "software": "Windows 11", "version": "24H2", "published_at": "2026-06-23T00:00:00Z",
            "source_url": "https://learn.microsoft.com/en-us/windows/release-health/",
            "body": "Windows 11 24H2.", "official_summary": "Windows 11 24H2.",
            "target_feature_version": "24H2", "target_kb": "KB5095093",
            "target_os_build": "26100.8737", "target_release_date": "2026-06-23T00:00:00Z",
        })), encoding="utf-8")
        synthetic = PatchRecord("microsoft-windows-11", "24H2", rec_path, "2026-06-23T00:00:00Z", "current", "Windows 11")

        orig_records = win.generated_records
        orig_source = win.learn_qna.collect_learn_qna_candidates
        orig_append = win.append_evidence_rows
        calls = {"append": 0}
        try:
            win.generated_records = lambda pid, tv=None, **k: [synthetic]
            win.learn_qna.collect_learn_qna_candidates = lambda **k: []  # no network
            win.append_evidence_rows = lambda rows, *a, **k: (calls.__setitem__("append", calls["append"] + 1), (0, 0, []))[1]

            calls["append"] = 0
            win.WindowsLearnQnaCollector().collect(SimpleNamespace(write=False, since=None, max_pages=1, target_versions=None))
            check("dry-run (write=False) NEVER calls append_evidence_rows", calls["append"] == 0, f"append calls={calls['append']}")

            calls["append"] = 0
            win.WindowsLearnQnaCollector().collect(SimpleNamespace(write=True, since=None, max_pages=1, target_versions=None))
            check("write path is implemented (write=True reaches append_evidence_rows)", calls["append"] == 1, f"append calls={calls['append']}")
        finally:
            win.generated_records = orig_records
            win.learn_qna.collect_learn_qna_candidates = orig_source
            win.append_evidence_rows = orig_append

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


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
