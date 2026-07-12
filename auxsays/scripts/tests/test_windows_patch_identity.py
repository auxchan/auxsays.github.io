#!/usr/bin/env python3
"""Windows patch-identity + exact-KB/build counting gate.

Offline only: synthetic records/evidence fixtures, temp files for write/refresh. No
network, no live generated records, no _data writes. Proves the fail-closed rule that a
Windows report counts ONLY for a record's current KB/OS build, and that evidence for an
older KB/build stops counting the moment the record rolls over to a newer patch.

Windows patch decisions are per cumulative update (KB / OS build), but records are keyed
by feature train (24H2/25H2/...). OS build is the train-specific primary identity; KB is
secondary because a KB can be shared across trains (e.g. 24H2 and 25H2 both ship
KB5095093).

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_windows_patch_identity.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import patch_collectors.base as base
from patch_collectors.base import windows_identity_gate, WINDOWS_PRODUCT_ID
import apply_consensus_to_records as ac
import build_consensus_from_evidence as bc
import lib.write_update_record as wur
from adapters import microsoft_release_health as mrh

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


# Current 24H2 patch identity (record side).
TARGET_24H2 = {
    "product_id": WINDOWS_PRODUCT_ID,
    "update_version": "24H2",
    "target_feature_version": "24H2",
    "target_kb": "KB5095093",
    "target_os_build": "26100.8737",
    "target_release_date": "2026-06-23T00:00:00Z",
}
# The same train after a rollover to a newer cumulative update.
TARGET_24H2_ROLLED = {
    **TARGET_24H2,
    "target_kb": "KB5099999",
    "target_os_build": "26100.9001",
    "target_release_date": "2026-07-14T00:00:00Z",
}


def win_row(**overrides) -> dict:
    """A Windows evidence row that passes every non-identity gate by default."""
    row = {
        "product_id": WINDOWS_PRODUCT_ID,
        "update_version": "24H2",
        "source_url": "https://learn.microsoft.com/en-us/answers/questions/2412345/kb5095093-breaks-printing",
        "patch_version_matched": True,
        "counted": True,
        "sentiment": "negative",
        "severity": "high",
        "matched_kb": "KB5095093",
        "matched_os_build": "26100.8737",
        "matched_feature_version": "24H2",
        "source_date": "2026-06-25",
    }
    row.update(overrides)
    return row


def run() -> int:
    print("=" * 60)
    print("Windows patch-identity counting-gate tests")
    print("=" * 60)

    # --- A. windows_identity_gate (unit) ------------------------------------
    ok, reason = windows_identity_gate(win_row(), TARGET_24H2)
    check("accepted: exact OS-build regression counts", ok and reason is None, str(reason))

    # KB + feature train, build differs (build not cited) -> secondary match counts.
    ok, reason = windows_identity_gate(win_row(matched_os_build=""), TARGET_24H2)
    check("accepted: exact KB + feature-train regression counts", ok and reason is None, str(reason))

    # KB matches but the feature train is wrong (shared-KB cross-train) -> rejected.
    ok, reason = windows_identity_gate(
        win_row(matched_os_build="26200.8737", matched_feature_version="25H2"), TARGET_24H2)
    check("rejected: KB match with wrong feature train", (not ok) and reason == "wrong_feature_train_for_kb", str(reason))

    # Wrong KB/build for the SAME train (never the current patch) -> stale/rollover.
    ok, reason = windows_identity_gate(
        win_row(matched_kb="KB5090000", matched_os_build="26100.7000"), TARGET_24H2)
    check("rejected: wrong KB for same feature train", (not ok) and reason == "stale_due_to_patch_rollover", str(reason))

    # No matched identity at all ("latest update" / date-only / generic) -> fail closed.
    ok, reason = windows_identity_gate(win_row(matched_kb="", matched_os_build=""), TARGET_24H2)
    check("rejected: missing KB/build identity fails closed", (not ok) and reason == "missing_kb_or_build", str(reason))

    # Record has no target identity yet (legacy / unpopulated) -> fail closed.
    ok, reason = windows_identity_gate(win_row(), {"update_version": "24H2"})
    check("rejected: record missing target identity fails closed", (not ok) and reason == "windows_record_missing_target_identity", str(reason))

    # Source date before the current patch's release date -> rejected.
    ok, reason = windows_identity_gate(win_row(source_date="2026-06-10"), TARGET_24H2)
    check("rejected: source_date before target_release_date", (not ok) and reason == "source_date_before_target_release_date", str(reason))

    # Stale after rollover: the exact same row that counted for KB-A no longer counts
    # once the record's current target advances to KB-B.
    ok_before, _ = windows_identity_gate(win_row(), TARGET_24H2)
    ok_after, reason_after = windows_identity_gate(win_row(), TARGET_24H2_ROLLED)
    check("stale after rollover: same row counts before, not after", ok_before and (not ok_after) and reason_after == "stale_due_to_patch_rollover", f"before={ok_before} after={ok_after} {reason_after}")

    # --- B. _filter_rows integration + count drop on rollover ---------------
    inc1, exc1 = ac._filter_rows([win_row()], product_id=WINDOWS_PRODUCT_ID, version="24H2", is_candidate_mode=False, record=TARGET_24H2)
    check("filter: current-KB row is counted (count=1)", len(inc1) == 1 and len(exc1) == 0, f"inc={len(inc1)} exc={len(exc1)}")

    inc2, exc2 = ac._filter_rows([win_row()], product_id=WINDOWS_PRODUCT_ID, version="24H2", is_candidate_mode=False, record=TARGET_24H2_ROLLED)
    check("filter: SAME row drops to count=0 after rollover", len(inc2) == 0 and len(exc2) == 1, f"inc={len(inc2)} exc={len(exc2)}")
    if exc2:
        check("filter: stale row carries rollover diagnostics", exc2[0].get("_exclusion_reason") == "stale_due_to_patch_rollover" and exc2[0].get("evidence_valid_for_current_patch") is False and exc2[0].get("stale_due_to_patch_rollover") is True, str({k: exc2[0].get(k) for k in ("_exclusion_reason", "evidence_valid_for_current_patch", "stale_due_to_patch_rollover")}))

    # Non-Windows rows are never touched by the identity gate.
    obs_row = {"product_id": "obs-studio", "update_version": "32.1.1", "source_url": "https://x/y", "patch_version_matched": True, "counted": True, "sentiment": "negative", "severity": "high"}
    inc_obs, _ = ac._filter_rows([obs_row], product_id="obs-studio", version="32.1.1", is_candidate_mode=False, record={"product_id": "obs-studio", "update_version": "32.1.1"})
    check("non-Windows product bypasses the identity gate", len(inc_obs) == 1, str(inc_obs))

    # --- C. end-to-end _result_for_group count (writeback field) ------------
    with tempfile.TemporaryDirectory() as d:
        rec_path = Path(d) / "2026-06-23-windows-11-24h2.md"
        rec_path.write_text(wur._dump_record(wur.build_front_matter({
            "company_id": "microsoft", "product_id": WINDOWS_PRODUCT_ID, "company": "Microsoft",
            "software": "Windows 11", "version": "24H2", "published_at": "2026-06-23T00:00:00Z",
            "source_url": "https://learn.microsoft.com/en-us/windows/release-health/",
            "body": "Windows 11 24H2 official record.", "official_summary": "Windows 11 24H2.",
            "target_feature_version": "24H2", "target_kb": "KB5095093",
            "target_os_build": "26100.8737", "target_release_date": "2026-06-23T00:00:00Z",
        })), encoding="utf-8")

        def index_for(target):
            return {(WINDOWS_PRODUCT_ID, "24H2"): {
                "path": rec_path.name, "abs_path": rec_path,
                "product_id": WINDOWS_PRODUCT_ID, "update_version": "24H2",
                "evidence_state": "official_only", "legacy_manual_report_count": None,
                **target,
            }}

        res_cur = ac._result_for_group(WINDOWS_PRODUCT_ID, "24H2", [win_row()], is_candidate_mode=False, records_index=index_for(TARGET_24H2))
        check("result: confirmed count = 1 for current KB", res_cur["confirmed_patch_specific_report_count"] == 1, str(res_cur["confirmed_patch_specific_report_count"]))

        res_rolled = ac._result_for_group(WINDOWS_PRODUCT_ID, "24H2", [win_row()], is_candidate_mode=False, records_index=index_for(TARGET_24H2_ROLLED))
        check("result: confirmed count = 0 after rollover (old KB evidence stops counting)", res_rolled["confirmed_patch_specific_report_count"] == 0, str(res_rolled["confirmed_patch_specific_report_count"]))

    # --- D. adapter emits target_* + write/refresh persistence --------------
    win_record = {
        "company_id": "microsoft", "product_id": WINDOWS_PRODUCT_ID, "company": "Microsoft",
        "software": "Windows 11", "version": "24H2", "published_at": "2026-06-23T00:00:00Z",
        "source_url": "https://learn.microsoft.com/en-us/windows/release-health/",
        "body": "Windows 11 24H2.", "official_summary": "Windows 11 24H2.",
        "target_feature_version": "24H2", "target_kb": "KB5095093",
        "target_os_build": "26100.8737", "target_release_date": "2026-06-23T00:00:00Z",
    }
    front = wur.build_front_matter(win_record)
    check("write: build_front_matter persists target_* fields", front.get("target_os_build") == "26100.8737" and front.get("target_kb") == "KB5095093" and front.get("target_feature_version") == "24H2" and front.get("target_release_date") == "2026-06-23T00:00:00Z", str({k: front.get(k) for k in wur.WINDOWS_IDENTITY_FIELDS}))

    non_win = {k: v for k, v in win_record.items() if not k.startswith("target_")}
    non_win.update({"product_id": "obs-studio", "software": "OBS Studio", "version": "32.1.1"})
    front_non = wur.build_front_matter(non_win)
    check("write: non-Windows record carries NO target_* keys", all(f not in front_non for f in wur.WINDOWS_IDENTITY_FIELDS), str([f for f in wur.WINDOWS_IDENTITY_FIELDS if f in front_non]))

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "2026-06-23-windows-11-24h2.md"
        path.write_text(wur._dump_record(wur.build_front_matter(win_record)), encoding="utf-8")
        # Refresh with a NEW current KB/build (a Patch-Tuesday advance).
        rolled_record = {**win_record, "target_kb": "KB5099999", "target_os_build": "26100.9001",
                         "target_release_date": "2026-07-14T00:00:00Z",
                         "body": "Windows 11 24H2 (July).", "source_last_checked": "2026-07-14T00:00:00Z"}
        _, status = wur.refresh_existing_record(path, rolled_record)
        refreshed, _body = wur._front_matter(path)
        check("refresh: target_os_build advances on build change (not stale)", refreshed.get("target_os_build") == "26100.9001", f"status={status} got={refreshed.get('target_os_build')}")
        check("refresh: target_kb advances on KB change", refreshed.get("target_kb") == "KB5099999", str(refreshed.get("target_kb")))
        check("refresh: target_release_date advances", refreshed.get("target_release_date") == "2026-07-14T00:00:00Z", str(refreshed.get("target_release_date")))

    # build_consensus wiring reads target_* from generated records.
    with tempfile.TemporaryDirectory() as d:
        gen = Path(d)
        (gen / "2026-06-23-windows-11-24h2.md").write_text(wur._dump_record(wur.build_front_matter(win_record)), encoding="utf-8")
        original_dir = bc.GENERATED_DIR
        bc.GENERATED_DIR = gen
        try:
            idx = bc.windows_target_index()
        finally:
            bc.GENERATED_DIR = original_dir
        entry = idx.get((WINDOWS_PRODUCT_ID, "24H2")) or {}
        check("build_consensus: windows_target_index reads target_* from records", entry.get("target_os_build") == "26100.8737" and entry.get("target_kb") == "KB5095093", str(entry))

    # --- E. adapter parser emits target_* (reuse the adapter's own path) ----
    recs = mrh._records_from_windows_release_information(
        {"company_id": "microsoft", "product_id": WINDOWS_PRODUCT_ID, "company": "Microsoft", "software": "Windows 11", "ingestion": {}},
        "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information",
        "<table><tr><th>Version</th><th>Latest revision date</th><th>Latest build</th></tr>"
        "<tr><td>24H2</td><td>2026-06-23</td><td>26100.8737</td></tr></table>"
        "<table><tr><th>Servicing option</th><th>Update type</th><th>Build</th><th>KB article</th></tr>"
        "<tr><td>GA</td><td>2026-06 B</td><td>26100.8737</td><td>KB5095093</td></tr></table>",
        5,
    )
    check("adapter parser emits target_os_build + target_kb", len(recs) == 1 and recs[0].get("target_os_build") == "26100.8737" and recs[0].get("target_kb") == "KB5095093", str(recs))

    # --- F. Microsoft source-URL specificity rules --------------------------
    su = base.source_url_is_specific
    check("url: Microsoft Q&A question URL is specific", su("https://learn.microsoft.com/en-us/answers/questions/2412345/kb5095093-fails") is True)
    check("url: Microsoft Learn docs page is NOT a specific report", su("https://learn.microsoft.com/en-us/officeupdates/current-channel") is False)
    check("url: Tech Community m-p thread permalink is specific", su("https://techcommunity.microsoft.com/t5/windows-11/kb-issue/m-p/4123456") is True)
    check("url: Tech Community Aurora thread with message id is specific", su("https://techcommunity.microsoft.com/discussions/windowsserver/kb-install-fails/4123456") is True)
    check("url: Tech Community board root is NOT specific", su("https://techcommunity.microsoft.com/category/windows") is False)
    check("url: reddit /comments/ still specific (regression)", su("https://www.reddit.com/r/windows11/comments/abc123/kb_issue/") is True)

    # --- G. make_evidence_row stamps matched_* when provided -----------------
    stamped = base.make_evidence_row(
        product_id=WINDOWS_PRODUCT_ID, update_version="24H2", source_type="ms_learn_qna",
        source_name="Microsoft Q&A", source_url="https://learn.microsoft.com/en-us/answers/questions/2412345/x",
        parent_title="", report_title="KB5095093 breaks printing", report_text="printing crashes after KB5095093",
        captured_at="2026-06-25T00:00:00Z", source_date="2026-06-25", target_release_date="2026-06-23T00:00:00Z",
        patch_version_matched=True, matched_version="24H2", match_basis="exact_os_build",
        counted=True, exclusion_reason=None, issue_theme="print", workflow_area="printing",
        platform="windows", severity="high", sentiment="negative",
        matched_kb="KB5095093", matched_os_build="26100.8737", matched_feature_version="24H2",
    )
    check("make_evidence_row stamps matched_kb/os_build/feature", stamped.get("matched_kb") == "KB5095093" and stamped.get("matched_os_build") == "26100.8737" and stamped.get("matched_feature_version") == "24H2", str({k: stamped.get(k) for k in ("matched_kb", "matched_os_build", "matched_feature_version")}))
    plain = base.make_evidence_row(
        product_id="obs-studio", update_version="32.1.1", source_type="github_issue",
        source_name="GitHub", source_url="https://github.com/obsproject/obs-studio/issues/1",
        parent_title="", report_title="crash", report_text="crash", captured_at="", source_date="",
        target_release_date="", patch_version_matched=True, matched_version="32.1.1", match_basis="exact_version_text",
        counted=True, exclusion_reason=None, issue_theme="", workflow_area="", platform="", severity="high", sentiment="negative",
    )
    check("make_evidence_row omits matched_* when not provided (non-Windows clean)", "matched_kb" not in plain and "matched_os_build" not in plain, str([k for k in plain if k.startswith("matched_")]))

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
