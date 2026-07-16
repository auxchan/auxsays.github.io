#!/usr/bin/env python3
"""Tests for the Microsoft PowerPoint per-app attribution parser in the Office adapter.

Offline only: canned Microsoft 365 Apps release-notes HTML is fed directly to the pure
parser (no network). Proves the fail-closed attribution rules: only entries that explicitly
name PowerPoint (word-boundary) or are explicitly suite-wide produce a PowerPoint record;
Word/Excel/Outlook-only and generic entries are rejected; generic suite channel/build rows
never become PowerPoint records; exact version+build identity is required (fail closed);
and records stay official_only with 0 reports.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_attribution.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import microsoft_office_updates as mso
from lib.write_update_record import build_front_matter

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


PP_SOURCE = {
    "company_id": "microsoft",
    "product_id": "microsoft-powerpoint",
    "company": "Microsoft",
    "software": "Microsoft PowerPoint",
    "public_category": "Productivity",
    "ingestion": {
        "parser_profile": "microsoft_365_powerpoint_release_notes",
        "target_app": "powerpoint",
        "channel": "Current Channel",
        "official_url": "https://learn.microsoft.com/officeupdates/release-notes-microsoft365-apps",
        "secondary_official_url": "https://learn.microsoft.com/officeupdates/update-history-microsoft365-apps-by-date",
    },
}

REL_NOTES = """
<h2>Version 2606 (Build 20131.20154)</h2>
<p>Current Channel released July 14, 2026.</p>
<h3>Feature updates</h3>
<ul>
  <li>PowerPoint: New Cameo presenter layouts.</li>
  <li>Word: Improved citations pane.</li>
</ul>
<h3>Resolved issues</h3>
<ul>
  <li>Excel: Fixed a crash opening large workbooks.</li>
  <li>We fixed an issue affecting all apps where the app may close unexpectedly on launch.</li>
</ul>
<h2>Version 2605 (Build 20029.20064)</h2>
<h3>Resolved issues</h3>
<ul><li>Word: Fixed printing.</li><li>Outlook: Fixed search.</li></ul>
"""

# The suite update-history TABLE (what Microsoft 365 Apps uses). It has NO app names, so the
# app-attribution parser must produce zero PowerPoint records from it (no misattribution).
SUITE_TABLE = """
<table>
<tr><th>Channel</th><th>Version</th><th>Build</th><th>Latest release date</th></tr>
<tr><td>Current Channel</td><td>2606</td><td>20131.20154</td><td>July 14, 2026</td></tr>
</table>
"""


def _parse(html):
    return mso._records_from_office_app_release_notes(PP_SOURCE, PP_SOURCE["ingestion"]["official_url"], html, 5)


def run() -> int:
    print("=" * 60)
    print("Microsoft PowerPoint attribution tests")
    print("=" * 60)

    recs = _parse(REL_NOTES)
    check("only the PowerPoint/suite-wide version is attributed (1 record)", len(recs) == 1, str([r["version"] for r in recs]))
    r = recs[0] if recs else {}

    # --- accepted: explicit PowerPoint entry -------------------------------
    check("accepted: explicit PowerPoint feature -> record for version 2606", r.get("version") == "2606", str(r.get("version")))
    check("body carries the PowerPoint entry", "PowerPoint" in (r.get("body") or ""), (r.get("body") or "")[:120])

    # --- rejected: other-app-only entries are not in the body --------------
    check("Word-only entry not attributed to PowerPoint", "citations pane" not in (r.get("body") or ""))
    check("Excel-only entry not attributed to PowerPoint", "large workbooks" not in (r.get("body") or ""))
    check("version 2605 (Word/Outlook only) produced no PowerPoint record", all(x.get("version") != "2605" for x in recs))

    # --- explicit suite-wide applicability ---------------------------------
    check("explicit all-apps entry is attributed (suite-wide)", "all apps" in (r.get("body") or "").lower())
    check("suite-wide applicability lists both the app and the suite id",
          r.get("applicability") == ["microsoft-powerpoint", "microsoft-365-apps"], str(r.get("applicability")))
    check("applies_to_label marks suite-wide", "suite-wide" in (r.get("applies_to_label") or ""), str(r.get("applies_to_label")))

    # --- channel/build/version identity preserved --------------------------
    check("structured identity: channel", r.get("target_channel") == "Current Channel", str(r.get("target_channel")))
    check("structured identity: exact build (not just marketing version)", r.get("target_build") == "20131.20154", str(r.get("target_build")))
    check("structured identity: app version", r.get("target_app_version") == "2606", str(r.get("target_app_version")))
    check("release date parsed", (r.get("published_at") or "").startswith("2026-07-14"), str(r.get("published_at")))

    # --- official-only invariants (write path derives official_only) -------
    check("official-only: no report_count / evidence_state on the record",
          r.get("report_count") is None and r.get("evidence_state") is None and r.get("consensus_label") is None,
          str({k: r.get(k) for k in ("report_count", "evidence_state", "consensus_label")}))
    front = build_front_matter(r)
    check("front matter is official_only with 0 reports",
          front["evidence_state"] == "official_only" and front["update_report_count"] == 0 and front["confirmed_patch_specific_report_count"] == 0,
          str({k: front[k] for k in ("evidence_state", "update_report_count")}))
    check("front matter carries structured identity + applicability",
          front.get("target_build") == "20131.20154" and front.get("applicability") == ["microsoft-powerpoint", "microsoft-365-apps"],
          str({k: front.get(k) for k in ("target_build", "applicability")}))

    # --- rejections: other apps / generic ----------------------------------
    for label, html in (
        ("Word-only version", '<h2>Version 2604 (Build 20000.20000)</h2><ul><li>Word: fix</li></ul>'),
        ("Excel-only version", '<h2>Version 2604 (Build 20000.20000)</h2><ul><li>Excel: fix</li></ul>'),
        ("Outlook-only version", '<h2>Version 2604 (Build 20000.20000)</h2><ul><li>Outlook: fix</li></ul>'),
        ("generic no-app version", '<h2>Version 2604 (Build 20000.20000)</h2><ul><li>Various reliability improvements.</li></ul>'),
    ):
        check(f"rejected: {label} -> no PowerPoint record", len(_parse(html)) == 0)

    # --- fail closed: missing exact identity -------------------------------
    check("fail closed: version heading but no build -> 0 records",
          len(_parse('<h2>Version 2603</h2><ul><li>PowerPoint: something</li></ul>')) == 0)
    check("DOM miss (empty) -> 0 records", len(_parse("")) == 0)

    # --- no misattribution from the suite table ----------------------------
    check("suite update-history table yields NO PowerPoint records (stays Microsoft 365 Apps)",
          len(_parse(SUITE_TABLE)) == 0)
    # ...and the suite parser itself still parses that table (Microsoft 365 Apps lane intact).
    suite_recs = mso._records_from_office_release_notes(
        {**PP_SOURCE, "product_id": "microsoft-365-apps", "software": "Microsoft 365 Apps"},
        "u", SUITE_TABLE, 5)
    check("suite parser still parses the update-history table (365 lane intact)",
          len(suite_recs) == 1 and suite_recs[0]["version"] == "2606", str(len(suite_recs)))

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
