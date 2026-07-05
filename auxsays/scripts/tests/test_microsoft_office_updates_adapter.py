#!/usr/bin/env python3
"""Tests for the Microsoft 365 / Office official update-notes adapter.

Offline only: the pure parser _records_from_office_release_notes is fed a canned
Microsoft 365 Apps "update history by date" table, so no live Microsoft request is
made. The fixture mirrors the real learn.microsoft.com column layout:
Channel | Version | Build | Latest release date | Version availability date | End of service.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import microsoft_office_updates as mso

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


def source() -> dict[str, object]:
    return {
        "company_id": "microsoft",
        "product_id": "microsoft-365-apps",
        "company": "Microsoft",
        "software": "Microsoft 365 Apps",
        "public_category": "Productivity",
        "ingestion": {
            "official_url": "https://learn.microsoft.com/en-us/officeupdates/update-history-microsoft365-apps-by-date",
            "secondary_official_url": "https://learn.microsoft.com/en-us/officeupdates/release-notes-microsoft365-apps",
            "parser_profile": "microsoft_365_apps_update_history",
        },
    }


URL = "https://learn.microsoft.com/en-us/officeupdates/update-history-microsoft365-apps-by-date"

# Mirrors the real update-history table (newest first), with non-target channels mixed in.
UPDATE_HISTORY_HTML = """
<html><body>
<h2>Microsoft 365 Apps update history</h2>
<table>
<thead>
<tr>
<th><strong>Channel</strong></th><th><strong>Version</strong></th><th><strong>Build</strong></th>
<th><strong>Latest release date</strong></th><th><strong>Version availability date</strong></th><th><strong>End of service</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td>Current Channel (Preview)</td><td>2607</td><td>20155.20000</td>
<td>June 28, 2026</td><td>June 20, 2026</td><td>Not applicable</td>
</tr>
<tr>
<td>Current Channel</td><td>2606</td><td>20131.20112</td>
<td>June 30, 2026</td><td>June 25, 2026</td><td>Version 2607 is released</td>
</tr>
<tr>
<td>Monthly Enterprise Channel</td><td>2605</td><td>20026.20174</td>
<td>June 10, 2026</td><td>June 10, 2026</td><td>Version 2606 is released</td>
</tr>
<tr>
<td>Current Channel</td><td>2605</td><td>20026.20182</td>
<td>June 10, 2026</td><td>May 28, 2026</td><td>Version 2606 is released</td>
</tr>
</tbody>
</table>
</body></html>
"""

LANDING_ONLY_HTML = """
<html><body>
  <h1>Release notes for Microsoft 365 Apps</h1>
  <p>Choose a channel to view its release notes. No update-history table on this page.</p>
</body></html>
"""


def teams_source() -> dict[str, object]:
    return {
        "company_id": "microsoft",
        "product_id": "microsoft-teams",
        "company": "Microsoft",
        "software": "Microsoft Teams",
        "public_category": "Workplace Critical",
        "ingestion": {
            "official_url": "https://learn.microsoft.com/en-us/officeupdates/teams-app-versioning",
            "secondary_official_url": "https://support.microsoft.com/en-us/office/what-s-new-in-microsoft-teams-d7092a6d-c896-424c-b362-a472d5f105de",
            "parser_profile": "microsoft_teams_version_history",
        },
    }


TEAMS_URL = "https://learn.microsoft.com/en-us/officeupdates/teams-app-versioning"

# Mirrors the real Teams version-history table:
# Release year | Release date ("July 01") | Teams version (4-part) | SlimCore version (3-part).
TEAMS_HTML = """
<html><body>
<h2>New Teams app version</h2>
<table>
<thead>
<tr><th>Release year</th><th>Release date</th><th>Teams version</th><th>SlimCore version</th></tr>
</thead>
<tbody>
<tr><td>2026</td><td>July 01</td><td>26163.407.4839.8659</td><td>2026.22.0</td></tr>
<tr><td>2026</td><td>June 17</td><td>26149.1804.4788.5681</td><td>2026.20.0</td></tr>
</tbody>
</table>
<h2>Public preview</h2>
<table>
<tbody>
<tr><td>2026</td><td>June 28</td><td>26170.100.4900.1000</td><td>2026.24.0</td></tr>
</tbody>
</table>
<h2>Classic Teams app version</h2>
<table>
<tbody>
<tr><td>2025</td><td>March 03</td><td>1.7.00.16873</td><td></td></tr>
</tbody>
</table>
</body></html>
"""

TEAMS_LANDING_HTML = "<html><body><h1>Version history</h1><p>No version table on this page.</p></body></html>"


def run() -> int:
    print("=" * 60)
    print("Microsoft 365 / Office updates adapter tests")
    print("=" * 60)

    records = mso._records_from_office_release_notes(source(), URL, UPDATE_HISTORY_HTML, 5)

    check("two Current Channel version rows produce two records", len(records) == 2, str([r.get("version") for r in records]))

    if records:
        first = records[0]
        check("newest Current Channel version is first (2606)", first.get("version") == "2606", str(first.get("version")))
        check("build number is captured in the title", "20131.20112" in str(first.get("title")), str(first.get("title")))
        check("build number is captured in official_summary", "Build 20131.20112" in str(first.get("official_summary")), str(first.get("official_summary")))
        check("latest release date normalized to ISO (June 30, 2026)", first.get("published_at") == "2026-06-30T00:00:00Z", str(first.get("published_at")))
        check("official body names the channel + version", "Current Channel" in str(first.get("body")) and "Version 2606" in str(first.get("body")), str(first.get("body"))[:200])
        check("record is official-only: no report_count", first.get("report_count") is None and first.get("update_report_count") is None, str({k: first.get(k) for k in ("report_count", "update_report_count")}))
        check("record is official-only: no evidence/consensus state", first.get("evidence_state") is None and first.get("consensus_label") is None and first.get("consensus_collection_status") is None, str({k: first.get(k) for k in ("evidence_state", "consensus_label", "consensus_collection_status")}))
        check("record is classified as official release_notes", first.get("source_type") == "release_notes" and first.get("official_source_type") == "release_notes", str(first.get("source_type")))
        check("record carries official source url + capture status", str(first.get("official_url")).startswith("https://learn.microsoft.com") and first.get("capture_status") == "captured-from-official-microsoft365-update-history", str(first.get("capture_status")))
        check("record carries reference official_sources list", isinstance(first.get("official_sources"), list) and len(first.get("official_sources")) >= 1, str(first.get("official_sources")))

    if len(records) >= 2:
        check("second record is the next Current Channel version (2605)", records[1].get("version") == "2605", str(records[1].get("version")))

    check("preview channel row is excluded (no 2607)", all(r.get("version") != "2607" for r in records), str([r.get("version") for r in records]))
    check("non-Current channels excluded (only Current Channel builds)", all("20026.20174" not in str(r.get("title")) for r in records), str([r.get("title") for r in records]))

    limited = mso._records_from_office_release_notes(source(), URL, UPDATE_HISTORY_HTML, 1)
    check("limit is respected (limit=1 -> one record)", len(limited) == 1 and limited[0].get("version") == "2606", str([r.get("version") for r in limited]))

    check("empty HTML yields no records", mso._records_from_office_release_notes(source(), URL, "", 5) == [], "empty string")
    check("landing page with no table yields no records", mso._records_from_office_release_notes(source(), URL, LANDING_ONLY_HTML, 5) == [], "landing-only")

    # --- Microsoft Teams (microsoft_teams_version_history profile) ------------
    check("Teams profile routes to the Teams parser", mso._PROFILE_PARSERS.get("microsoft_teams_version_history") is mso._records_from_teams_version_history)
    check("M365 profile still routes to the M365 parser", mso._PROFILE_PARSERS.get("microsoft_365_apps_update_history") is mso._records_from_office_release_notes)

    teams = mso._records_from_teams_version_history(teams_source(), TEAMS_URL, TEAMS_HTML, 5)
    check("two GA Teams version rows produce two records", len(teams) == 2, str([r.get("version") for r in teams]))

    if teams:
        t0 = teams[0]
        check("newest Teams version is first (26163...)", t0.get("version") == "26163.407.4839.8659", str(t0.get("version")))
        check("4-part Teams version parsed, SlimCore not mistaken", t0.get("version") == "26163.407.4839.8659", str(t0.get("version")))
        check("split year + month/day normalized to ISO (2026-07-01)", t0.get("published_at") == "2026-07-01T00:00:00Z", str(t0.get("published_at")))
        check("Teams title carries software + version", "Microsoft Teams" in str(t0.get("title")) and "26163.407.4839.8659" in str(t0.get("title")), str(t0.get("title")))
        check("Teams official_summary names the version", "26163.407.4839.8659" in str(t0.get("official_summary")), str(t0.get("official_summary")))
        check("Teams record official-only: no report/consensus fields", t0.get("report_count") is None and t0.get("update_report_count") is None and t0.get("evidence_state") is None and t0.get("consensus_label") is None, str({k: t0.get(k) for k in ("report_count", "evidence_state", "consensus_label")}))
        check("Teams record classified as official release_notes", t0.get("source_type") == "release_notes" and t0.get("capture_status") == "captured-from-official-microsoft-teams-version-history", str(t0.get("capture_status")))

    if len(teams) >= 2:
        check("second Teams record is the next GA version (26149...)", teams[1].get("version") == "26149.1804.4788.5681", str(teams[1].get("version")))

    check("preview-section Teams row excluded (no 26170...)", all(r.get("version") != "26170.100.4900.1000" for r in teams), str([r.get("version") for r in teams]))
    check("classic 1.x Teams build excluded", all(not str(r.get("version")).startswith("1.") for r in teams), str([r.get("version") for r in teams]))

    teams_limited = mso._records_from_teams_version_history(teams_source(), TEAMS_URL, TEAMS_HTML, 1)
    check("Teams limit respected (limit=1 -> one record)", len(teams_limited) == 1 and teams_limited[0].get("version") == "26163.407.4839.8659", str([r.get("version") for r in teams_limited]))

    check("Teams empty HTML yields no records", mso._records_from_teams_version_history(teams_source(), TEAMS_URL, "", 5) == [], "empty")
    check("Teams landing page (no version table) yields no records", mso._records_from_teams_version_history(teams_source(), TEAMS_URL, TEAMS_LANDING_HTML, 5) == [], "landing")

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
