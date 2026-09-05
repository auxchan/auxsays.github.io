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

NEWLINE = chr(10)
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

REC_24H2 = PatchRecord("microsoft-windows-11", "24H2", Path("2026-06-23-windows-11-24h2-26100-8737.md"), "2026-06-23T00:00:00Z", "current", "Windows 11", "26100.8737")
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
        # Canonical build-aware filename: one Windows record is one cumulative update.
        rec_path = Path(d) / "2026-06-23-windows-11-24h2-26100-8737.md"
        rec_path.write_text(wur._dump_record(wur.build_front_matter({
            "company_id": "microsoft", "product_id": "microsoft-windows-11", "company": "Microsoft",
            "software": "Windows 11", "version": "24H2", "published_at": "2026-06-23T00:00:00Z",
            "source_url": "https://learn.microsoft.com/en-us/windows/release-health/",
            "body": "Windows 11 24H2 official record.", "official_summary": "Windows 11 24H2.",
            "target_feature_version": "24H2", "target_kb": "KB5095093",
            "target_os_build": "26100.8737", "target_build": "26100.8737",
            "target_release_date": "2026-06-23T00:00:00Z",
        })), encoding="utf-8")
        record = PatchRecord("microsoft-windows-11", "24H2", rec_path, "2026-06-23T00:00:00Z", "current", "Windows 11", "26100.8737")

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

    # --- intent / update-attribution hardening ----------------------------
    def cr(target, title, body, **kw):
        r = row_reason(target, title, body, **kw)
        return r.get("counted"), r.get("exclusion_reason")

    # The 9 genuine observed accepts still count (each is update-attributed A/B/C).
    genuine = [
        ("exact-KB install failure", TARGET_25H2, "2026-06 Update (KB5095093) (26200.8737) will not install", "I have been restarting to install this update for over a week with no success."),
        ("exact-build install failure", TARGET_25H2, "Update failed to install", "2026-06 Preview Update (KB5095093) (26200.8737) failed to install; error 0x80070306."),
        ("Windows Update not functioning", TARGET_25H2, "WINDOWS UPDATE not functioning", "For 5 days Windows Update not functioning; 2026-06 Preview Update (KB5095093) (26200.8737) keeps failing."),
        ("failed attempts to run update", TARGET_25H2, "2026-06 update issues", "The problem started when I attempted to run the 2026-06 Preview Update (KB5095093) (26200.8737). After a few failed attempts I contacted support."),
        ("NAS/VPN broke after update", TARGET_25H2, "After update (KB5095093) I cannot connect to NAS over vpn", "After installing KB5095093 on Windows 11 25H2 my VPN connection broke; I now have no network access to the office NAS shares."),
        ("File Explorer bug / rollback fixed", TARGET_25H2, "Build 26200.8737 (KB5095093): windows explorer has a blank-window bug", "Win+E repeatedly shows a blank window. Uninstalling KB5095093 fixed it."),
        ("taskbar tray after update / uninstall fixed", TARGET_25H2, "Problem with KB5095093 update to Win 11 Home", "Windows 11 25H2 Home. The taskbar system tray stopped working after the update. Uninstalling KB5095093 fixed it."),
        ("face recognition fails after upgrade", TARGET_25H2, "Windows Hello Face Recognition fails after cold boot on Windows 11 25H2 (Build 26200.8737)", "After upgrading to Windows 11 25H2 (26200.8737), Windows Hello face recognition stopped working after a cold boot; it is broken."),
        ("hypervisor boot hang on exact build", TARGET_25H2, "Windows 11 25H2 (26200.8737): enabling the hypervisor causes a boot hang into Automatic Repair", "On build 26200.8737 enabling the hypervisor causes a boot hang into Automatic Repair."),
    ]
    for label, target, title, body in genuine:
        c, rr = cr(target, title, body)
        check(f"intent: GENUINE still counts — {label}", c is True and rr is None, f"counted={c} reason={rr}")

    # Shared KB5095093 must not leak to the wrong train.
    c, rr = cr(TARGET_24H2, "KB5095093 install failure on 25H2", "KB5095093 on Windows 11 25H2 will not install.")
    check("intent: shared KB5095093 does not leak to 24H2 (post names 25H2)", c is False and rr == "wrong_feature_train_for_kb", f"{c} {rr}")

    # The 5 observed false accepts are now rejected with specific reasons.
    false_accepts = [
        ("secure certificate / BIOS config", "Secure Certificate has not been updated to the 2023 version", "Windows 11 25H2 (26200.8737) (KB5095093). Secure boot=on, CSM disabled, TPM 2.0. My secure certificate has not been updated and refresh is slow. Is this a bios setting?", "build_only_in_system_specs"),
        ("MCT ISO / spam meta", "Very strange Windows 11 MCT .ISO 26200.8653", "This thread was rejected by the system as spam. Build 26200.8737 crashes when I create the MCT ISO.", "meta_or_spam_report"),
        ("Xbox Game Bar cosmetic / build in specs", "Xbox Game Bar Home widget incorrectly shows Windows OS as a game", "This cosmetic bug is annoying. Edition Windows 11 Pro, OS Build 26200.8737, KB5095093 installed.", "build_only_in_system_specs"),
        ("point-in-time restore feature question", "Windows 11 Point in time restore feature", "Windows 11 25H2 26200.8737 KB5095093. The 72 hour limit is greyed out and fails to change. Does this mean that at 72 hours Windows won't delete the restore point?", "feature_question_not_regression"),
        ("intel driver how-to question", "why can't I upgrade the intel graphic driver beyond 32.0.101.6129", "Windows 11 25H2 26200.8737 KB5095093. Why can't I upgrade my Intel graphics driver? The driver crashes constantly.", "driver_update_question_not_windows_patch"),
    ]
    for label, title, body, want in false_accepts:
        c, rr = cr(TARGET_25H2, title, body)
        check(f"intent: FALSE ACCEPT now rejected — {label}", c is False and rr == want, f"counted={c} reason={rr} want={want}")

    # Broader intent behavior.
    c, rr = cr(TARGET_25H2, "My PC crashes randomly", "My PC crashes. Windows 11 25H2, OS Build 26200.8737, KB5095093 installed.")
    check("intent: build only in system-spec block -> build_only_in_system_specs", c is False and rr == "build_only_in_system_specs", f"{c} {rr}")
    c, rr = cr(TARGET_25H2, "why can't I change this", "Windows 11 25H2 26200.8737 KB5095093. Why can't I change this setting? The app crashes randomly.")
    check("intent: 'why can't I' with no update-attribution rejected", c is False and rr in ("how_to_question_not_regression", "missing_update_attribution", "build_only_in_system_specs"), f"{c} {rr}")
    c, rr = cr(TARGET_25H2, "does this mean", "Windows 11 25H2 26200.8737 KB5095093. The toggle is greyed out and the app crashes. Does this mean it is disabled?")
    check("intent: 'does this mean' with no update-attribution rejected", c is False and rr == "feature_question_not_regression", f"{c} {rr}")
    c, rr = cr(TARGET_25H2, "printer stopped working after KB", "After installing KB5095093 on Windows 11 25H2 my printer stopped working.")
    check("intent: update-attributed regression with exact identity counts", c is True and rr is None, f"{c} {rr}")
    c, rr = cr(TARGET_25H2, "generic support with KB/build", "Windows 11 25H2 26200.8737 KB5095093. How do I open Settings? The app crashes sometimes.")
    check("intent: generic how-to with KB/build (no attribution) rejected", c is False and rr in ("how_to_question_not_regression", "missing_update_attribution"), f"{c} {rr}")

    # Existing gates remain intact (regression).
    check("intent: date-only inference still rejected", cr(TARGET_25H2, "Patch Tuesday broke boot", "After June 2026 Patch Tuesday my PC won't boot.")[1] == "date_only_inference")
    check("intent: vague latest update still rejected", cr(TARGET_25H2, "latest update broke it", "The latest Windows update caused a BSOD.")[1] == "vague_latest_update")
    check("intent: wrong KB still rejected", cr(TARGET_25H2, "KB5090000 crash", "KB5090000 on Windows 11 25H2 causes a BSOD.")[1] == "wrong_kb_for_current_patch")
    c, rr = cr(TARGET_25H2, "Build 26200.8737 (KB5095093): boot hang", "On build 26200.8737 enabling the hypervisor causes a boot hang.", date="2026-06-10T00:00:00Z")
    check("intent: source_date before target_release_date still rejected", c is False and rr == "date_before_release", f"{c} {rr}")

    # Preview-channel gating DEFERRED (documented). The 25H2/24H2 records mark channel only
    # in prose ("General Availability Channel"); the observed false accepts were NOT
    # preview-related, so preview_channel_mismatch is intentionally NOT enforced. A
    # Preview-Update report of the exact current KB/build still counts.
    # TODO: revisit if a structured channel field is added to Windows records.
    c, rr = cr(TARGET_25H2, "2026-06 Preview Update (KB5095093) (26200.8737) will not install", "Release Preview Channel: the 2026-06 Preview Update (KB5095093) (26200.8737) will not install.")
    check("preview-channel DEFERRED: exact-patch Preview-Update install failure still counts (TODO channel gating)", c is True and rr is None, f"{c} {rr}")

    # --- safety: NOT registered + no writeback by default -------------------
    import run_patch_evidence_collection as runner
    default_registry = runner.build_collectors({})  # default env: activation flag off
    check(
        "collector is NOT registered in the production runner by default (no default Windows writeback)",
        "microsoft-windows-11" not in runner.COLLECTORS and "microsoft-windows-11" not in default_registry,
        f"base={sorted(runner.COLLECTORS)} default_runtime={sorted(default_registry)}",
    )

    with tempfile.TemporaryDirectory() as d:
        # Canonical build-aware filename: one Windows record is one cumulative update.
        rec_path = Path(d) / "2026-06-23-windows-11-24h2-26100-8737.md"
        rec_path.write_text(wur._dump_record(wur.build_front_matter({
            "company_id": "microsoft", "product_id": "microsoft-windows-11", "company": "Microsoft",
            "software": "Windows 11", "version": "24H2", "published_at": "2026-06-23T00:00:00Z",
            "source_url": "https://learn.microsoft.com/en-us/windows/release-health/",
            "body": "Windows 11 24H2.", "official_summary": "Windows 11 24H2.",
            "target_feature_version": "24H2", "target_kb": "KB5095093",
            "target_os_build": "26100.8737", "target_build": "26100.8737",
            "target_release_date": "2026-06-23T00:00:00Z",
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

    # --- one report, one patch -----------------------------------------------
    # REGRESSION. `append_evidence_rows` refuses a source_url already present under the same
    # `evidence_key`, and that key's build slot was empty for Windows -- so the append guard was
    # build-blind and a URL could physically exist only once for the product. Stamping the exact
    # build onto rows (required for build-aware counting) silently WIDENED the key, and one thread
    # naming two builds became two counted rows on two different patches. Production run
    # 33944086829 wrote 14 such pairs, including one "ngcctnrsvc crashes" report counted for both
    # 24H2 26100.9168 and 25H2 26200.9168 -- both ship KB5121003.
    print(NEWLINE + "[exclusivity] one report is never counted on two patches")
    shared_url = "https://learn.microsoft.com/en-us/answers/questions/5973125/ngcctnrsvc-crashes"
    shared = {"source_url": shared_url,
              "report_title": "KB5121003 crashes ucrtbase.dll after installing",
              "report_text": "After installing KB5121003 ngcctnrsvc crashes three times in "
                             "ucrtbase.dll with 0xc0000409. Same on Windows 11 24H2 (26100.9168) "
                             "and 25H2 (26200.9168) here.",
              "source_date": "2026-09-01"}
    tgt_25 = {"target_feature_version": "25H2", "target_kb": "KB5121003",
              "target_os_build": "26200.9168", "target_release_date": "2026-08-11T00:00:00Z",
              "update_version": "25H2"}
    tgt_24 = {"target_feature_version": "24H2", "target_kb": "KB5121003",
              "target_os_build": "26100.9168", "target_release_date": "2026-08-11T00:00:00Z",
              "update_version": "24H2"}
    rec_25 = PatchRecord("microsoft-windows-11", "25H2", Path("x.md"),
                         "2026-08-11T00:00:00Z", "current", "Windows 11", "26200.9168")
    rec_24 = PatchRecord("microsoft-windows-11", "24H2", Path("y.md"),
                         "2026-08-11T00:00:00Z", "current", "Windows 11", "26100.9168")
    # Without a claims map both records accept it -- the defect, reproduced.
    a25, _ = win.evaluate_candidates(rec_25, tgt_25, [dict(shared)], CAPTURED)
    a24, _ = win.evaluate_candidates(rec_24, tgt_24, [dict(shared)], CAPTURED)
    check("exclusivity: without the claims map BOTH patches accept it (the defect)",
          len(a25) == 1 and len(a24) == 1, f"{len(a25)} {len(a24)}")
    # With one shared claims map, the first record to walk keeps it and the second refuses.
    claims: dict = {}
    b25, r25 = win.evaluate_candidates(rec_25, tgt_25, [dict(shared)], CAPTURED, claims)
    b24, r24 = win.evaluate_candidates(rec_24, tgt_24, [dict(shared)], CAPTURED, claims)
    check("exclusivity: the first patch to walk keeps the report",
          len(b25) == 1 and b25[0].get("target_build") == "26200.9168", str(len(b25)))
    check("exclusivity: the second patch refuses it as a cross-patch duplicate",
          len(b24) == 0 and len(r24) == 1
          and r24[0].get("exclusion_reason") == "cross_patch_duplicate",
          str([r.get("exclusion_reason") for r in r24]))
    # The refused row KEEPS the build it was refused for. `counted: false` is what keeps it out of
    # every count; the build is what lets the audit trail say WHICH patch refused this URL. Blanking
    # it puts a stored row under (product, version, ''), a key no record has, and
    # audit_consensus_evidence reports that as an integrity error -- measured: the first repair of
    # these rows added exactly 2.
    check("exclusivity: the refused row still records WHICH patch refused it",
          r24 and str(r24[0].get("target_build") or "") == "26100.9168",
          str(r24[0].get("target_build")))
    check("exclusivity: ...and being uncounted is what keeps it out of the count",
          r24 and r24[0].get("counted") is False, str(r24[0].get("counted")))
    # ...and it holds ACROSS runs, because the map is seeded from stored evidence.
    stored_claims = {shared_url.lower(): ("microsoft-windows-11", "25H2", "26200.9168")}
    c24, cr24 = win.evaluate_candidates(rec_24, tgt_24, [dict(shared)], CAPTURED, stored_claims)
    check("exclusivity: a URL already stored for another patch is refused on a later run",
          len(c24) == 0 and cr24 and cr24[0].get("exclusion_reason") == "cross_patch_duplicate",
          str([r.get("exclusion_reason") for r in cr24]))
    # The same patch re-discovering its OWN report is not a cross-patch duplicate; the append
    # guard deduplicates that, and turning it into a rejection would flip a real row to uncounted.
    same_claims = {shared_url.lower(): ("microsoft-windows-11", "25H2", "26200.9168")}
    d25, _dr = win.evaluate_candidates(rec_25, tgt_25, [dict(shared)], CAPTURED, same_claims)
    check("exclusivity: a patch re-finding its OWN report still accepts it",
          len(d25) == 1, str(len(d25)))

    # --- the runner's ownership validator accepts what this collector emits --
    # WHY THIS EXISTS. Ownership validation runs in run_patch_evidence_collection, NOT in this
    # module's dry-run, so a collector can look completely healthy locally and still fail the whole
    # production run closed. It did: run 33941301615 aborted with
    # `ownership_violation:method_health_version_unresolved` because health rows still keyed on
    # (product, "25H2", "") -- an identity no Windows record has had since one record came to mean
    # one cumulative update. Drive the REAL validator against a REAL health row, against the live
    # record set, so the gap between "the module is happy" and "the runner accepts it" is closed.
    print(NEWLINE + "[ownership] the runner's validator accepts this collector's method health")
    from lib import collector_ownership as own  # noqa: PLC0415
    live = win.generated_records("microsoft-windows-11")
    check("ownership: there are live Windows records to validate against", bool(live), "none found")
    if live:
        rec = live[0]
        health = win.health_for_method(rec, win.record_target(rec), "2026-09-01T00:00:00Z",
                                       [], [], [], [], [])
        check("ownership: the health row states the record's exact build",
              str(health.get("target_build") or "") == rec.target_build,
              f"{health.get('target_build')!r} vs {rec.target_build!r}")
        raised = None
        try:
            own.validate_method_health("microsoft-windows-11", [health])
        except Exception as exc:  # noqa: BLE001 - the violation type is the assertion
            raised = exc
        check("ownership: validate_method_health ACCEPTS it", raised is None, str(raised))
        # And the negative: a row that names no build must still be refused, or this check would
        # pass for the wrong reason on a version-only fallback nobody intended to add.
        stripped = {**health, "target_build": ""}
        refused = None
        try:
            own.validate_method_health("microsoft-windows-11", [stripped])
        except Exception as exc:  # noqa: BLE001
            refused = exc
        # The reason CODE, not the message text: the code is the contract the runner reports and
        # the message is prose that may legitimately be reworded.
        # The EVIDENCE surface, same reasoning. `_validate_ownership` runs only under --write
        # (txn is None on a dry run), so neither this module's dry-run nor the runner's dry-run
        # reaches it; a row shape that cannot resolve would surface for the first time as a
        # production abort. Build a real accepted row and put it through the real validator.
        import yaml as _yaml  # noqa: PLC0415
        own_candidate = {"source_url": "https://learn.microsoft.com/en-us/answers/questions/1/x",
                "report_title": f"{win.record_target(rec).get('target_kb')} "
                                f"({rec.target_build}) will not install",
                "report_text": f"After installing {win.record_target(rec).get('target_kb')} "
                               f"({rec.target_build}) the update fails with error 0x800f0991.",
                "source_date": "2026-09-01"}
        ev_row = win.row_from_candidate(rec, win.record_target(rec), own_candidate,
                                        "2026-09-01T00:00:00Z")
        check("ownership: an accepted evidence row carries the record's exact build",
              ev_row.get("counted") is True
              and str(ev_row.get("target_build") or "") == rec.target_build,
              f"counted={ev_row.get('counted')} reason={ev_row.get('exclusion_reason')!r} "
              f"build={ev_row.get('target_build')!r}")
        before = _yaml.safe_dump({"schema_version": 1, "evidence": []})
        after = _yaml.safe_dump({"schema_version": 1, "evidence": [ev_row]})
        ev_raised = None
        try:
            own.validate_evidence("microsoft-windows-11", before, after)
        except Exception as exc:  # noqa: BLE001
            ev_raised = exc
        check("ownership: validate_evidence ACCEPTS the appended row", ev_raised is None,
              str(ev_raised))
        ev_stripped = {**ev_row, "target_build": ""}
        ev_refused = None
        try:
            own.validate_evidence("microsoft-windows-11", before,
                                  _yaml.safe_dump({"schema_version": 1, "evidence": [ev_stripped]}))
        except Exception as exc:  # noqa: BLE001
            ev_refused = exc
        check("ownership: a build-less evidence row is still REFUSED",
              ev_refused is not None
              and getattr(ev_refused, "reason", getattr(ev_refused, "code", "")) == "evidence_version_unresolved",
              f"{type(ev_refused).__name__}: {ev_refused}")
        check("ownership: a build-less health row is still REFUSED",
              refused is not None
              and getattr(refused, "reason", getattr(refused, "code", "")) == "method_health_version_unresolved",
              f"{type(refused).__name__}: {refused} "
              f"reason={getattr(refused, 'reason', getattr(refused, 'code', None))!r}")

    # --- the consensus writeback is batched, not per record -----------------
    # WHY THIS IS PINNED. `apply_consensus_writeback` rebuilds the whole picture on every call:
    # _index_generated_records reads all 1110 generated records (4.2s measured) and run_dry_run
    # regroups the entire evidence corpus (5.4s). Calling it inside the record loop cost 4 x 9.6s
    # while one Windows record meant one servicing TRAIN. There are 71 records now, so the same
    # code costs 11 minutes a run -- spent out of the collector's wall-clock budget, i.e. paid in
    # records never searched. Assert the CALL COUNT, because the runtime cost is invisible to every
    # other check in this file: the records come out identical either way.
    print(NEWLINE + "[batched writeback] the whole-corpus rebuild happens once, not once per record")
    import apply_consensus_to_records as acr_mod  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as d:
        recs = []
        for build, kb in (("26100.8737", "KB5095093"), ("26100.8973", "KB5101684"),
                          ("26100.9168", "KB5121003")):
            rp = Path(d) / f"2026-06-23-windows-11-24h2-{build.replace('.', '-')}.md"
            rp.write_text(wur._dump_record(wur.build_front_matter({
                "company_id": "microsoft", "product_id": "microsoft-windows-11",
                "company": "Microsoft", "software": "Windows 11", "version": "24H2",
                "published_at": "2026-06-23T00:00:00Z",
                "source_url": "https://learn.microsoft.com/en-us/windows/release-health/",
                "body": "Windows 11 24H2.", "official_summary": "Windows 11 24H2.",
                "target_feature_version": "24H2", "target_kb": kb,
                "target_os_build": build, "target_build": build,
                "target_release_date": "2026-06-23T00:00:00Z",
            })), encoding="utf-8")
            recs.append(PatchRecord("microsoft-windows-11", "24H2", rp,
                                    "2026-06-23T00:00:00Z", "current", "Windows 11", build))

        def _run(accept: bool) -> dict:
            counts = {"index": 0, "dry_run": 0, "results": 0}
            orig = (win.generated_records, win.collect_for_record, win.append_evidence_rows,
                    acr_mod._index_generated_records, acr_mod.run_dry_run)
            try:
                win.generated_records = lambda pid, tv=None, **k: list(recs)
                # Every record "accepts" a row (or none), so every one is a writeback candidate.
                win.collect_for_record = lambda record, context, claims=None: (
                    ([{"source_url": "https://x/1"}] if accept else []), [], {})
                win.append_evidence_rows = lambda rows, *a, **k: (1 if accept else 0, 1, [])
                acr_mod._index_generated_records = lambda *a, **k: (
                    counts.__setitem__("index", counts["index"] + 1), {})[1]
                acr_mod.run_dry_run = lambda **k: (
                    counts.__setitem__("dry_run", counts["dry_run"] + 1), [])[1]
                out = win.WindowsLearnQnaCollector().collect(
                    SimpleNamespace(write=True, since=None, max_pages=1, target_versions=None))
                counts["results"] = len(out)
            finally:
                (win.generated_records, win.collect_for_record, win.append_evidence_rows,
                 acr_mod._index_generated_records, acr_mod.run_dry_run) = orig
            return counts

        accepted_run = _run(accept=True)
        check("batched: all three records were walked", accepted_run["results"] == 3,
              str(accepted_run))
        check("batched: the record index is built ONCE for the whole run",
              accepted_run["index"] == 1, f"index builds={accepted_run['index']} for 3 records")
        check("batched: the evidence corpus is regrouped ONCE for the whole run",
              accepted_run["dry_run"] == 1, f"dry runs={accepted_run['dry_run']} for 3 records")
        empty_run = _run(accept=False)
        check("batched: a run that accepted nothing rebuilds nothing",
              empty_run["index"] == 0 and empty_run["dry_run"] == 0, str(empty_run))

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
