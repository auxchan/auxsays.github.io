#!/usr/bin/env python3
"""Tests: official_* Release Health fields persist through the write path.

Covers build_front_matter (new records) and refresh_existing_record (the path the
already-existing Windows 11 records take on every cron run), and confirms the fields
never leak into consensus / user-report / known_issues semantics. This is the
requirement that Tier-1 surfacing depends on: if the counts did not survive
refresh_existing_record, the enriched signal would silently disappear.
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import write_update_record as wur

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


def base_record(**overrides) -> dict[str, object]:
    record = {
        "company_id": "microsoft",
        "product_id": "microsoft-windows-11",
        "company": "Microsoft",
        "software": "Windows 11",
        "version": "23H2",
        "published_at": "2026-06-09T00:00:00Z",
        "source_url": "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information",
        "body": "Windows 11 23H2 base body.",
        "source_type": "release_health",
        "official_source_type": "release_health",
    }
    record.update(overrides)
    return record


def read_fm(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    return yaml.safe_load(parts[1]) if len(parts) >= 3 else {}


def run() -> int:
    print("=" * 60)
    print("write_update_record official_* field persistence")
    print("=" * 60)

    # --- build_front_matter (new records) -----------------------------------
    fm = wur.build_front_matter(base_record(
        official_active_issue_count=2, official_resolved_issue_count=0,
        official_safeguard_hold_count=0, official_known_issues_present=True,
    ))
    check("build_front_matter emits official_active_issue_count", fm.get("official_active_issue_count") == 2, str(fm.get("official_active_issue_count")))
    check("build_front_matter emits official_known_issues_present", fm.get("official_known_issues_present") is True, str(fm.get("official_known_issues_present")))
    check("build_front_matter keeps record official_only + 0 reports", fm.get("evidence_state") == "official_only" and fm.get("update_report_count") == 0, str({k: fm.get(k) for k in ("evidence_state", "update_report_count")}))
    check("build_front_matter does NOT set known_issues_present from official fields", fm.get("known_issues_present") is None, str(fm.get("known_issues_present")))
    check("build_front_matter keeps complaint_themes empty", fm.get("complaint_themes") == [], str(fm.get("complaint_themes")))

    fm_none = wur.build_front_matter(base_record())
    check("build_front_matter omits official_* when the record has none (non-issue products)", "official_active_issue_count" not in fm_none and "official_known_issues_present" not in fm_none, str([k for k in fm_none if k.startswith("official_")]))

    # --- refresh_existing_record (the cron path for existing records) --------
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        path, action = wur.write_record(out, base_record(
            official_active_issue_count=2, official_resolved_issue_count=0,
            official_safeguard_hold_count=0, official_known_issues_present=True,
        ))
        check("initial write creates the record", action == "created" and path.exists(), action)
        check("created record persists official_active_issue_count=2", read_fm(path).get("official_active_issue_count") == 2, str(read_fm(path).get("official_active_issue_count")))

        # Issues later resolve: 2 active -> 0 active, 2 resolved. Must update-on-change.
        _, action2 = wur.refresh_existing_record(path, base_record(
            official_active_issue_count=0, official_resolved_issue_count=2,
            official_safeguard_hold_count=0, official_known_issues_present=False,
        ))
        fm_ref = read_fm(path)
        check("refresh with changed counts marks record refreshed", action2 == "refreshed", action2)
        check("refresh persists updated official_active_issue_count=0", fm_ref.get("official_active_issue_count") == 0, str(fm_ref.get("official_active_issue_count")))
        check("refresh persists updated official_resolved_issue_count=2", fm_ref.get("official_resolved_issue_count") == 2, str(fm_ref.get("official_resolved_issue_count")))
        check("refresh flips official_known_issues_present to False", fm_ref.get("official_known_issues_present") is False, str(fm_ref.get("official_known_issues_present")))
        check("refresh keeps report counts at 0", fm_ref.get("update_report_count") == 0 and fm_ref.get("confirmed_patch_specific_report_count") == 0, str({k: fm_ref.get(k) for k in ("update_report_count", "confirmed_patch_specific_report_count")}))
        check("refresh keeps evidence_state official_only", fm_ref.get("evidence_state") == "official_only", str(fm_ref.get("evidence_state")))
        check("refresh never sets known_issues_present / complaint_themes from official fields", fm_ref.get("known_issues_present") in (None, False) and fm_ref.get("complaint_themes") in (None, []), str({k: fm_ref.get(k) for k in ("known_issues_present", "complaint_themes")}))

        # Idempotent refresh (same counts) must not re-mark the counts as changed.
        _, action3 = wur.refresh_existing_record(path, base_record(
            official_active_issue_count=0, official_resolved_issue_count=2,
            official_safeguard_hold_count=0, official_known_issues_present=False,
        ))
        check("idempotent refresh does not re-mark counts changed", action3 in ("unchanged", "freshness-updated"), action3)

        # A transient status miss (incoming record has no official fields) must NOT wipe
        # the last-known counts.
        wur.refresh_existing_record(path, base_record())
        check("refresh without official fields preserves last-known counts", read_fm(path).get("official_resolved_issue_count") == 2, str(read_fm(path).get("official_resolved_issue_count")))

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
