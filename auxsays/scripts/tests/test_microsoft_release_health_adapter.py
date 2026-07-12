#!/usr/bin/env python3
"""Tests for the Microsoft Windows release-health official-ingestion adapter.

Offline only: the pure parser _records_from_windows_release_information is fed a
canned Windows 11 "release information" page, so no live Microsoft request is made.
The fixture mirrors the real learn.microsoft.com/windows/release-health layout:
a "current versions by servicing option" summary table (Version | Servicing option |
Availability date | End of updates... | Latest update for ESU | Latest revision date |
Latest build), an LTSC editions table, a per-build "release history" table
(Servicing option | Update type | Availability date | Build | KB article), and a
trailing end-of-servicing table whose old versions must never be ingested.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

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


def source() -> dict[str, object]:
    return {
        "company_id": "microsoft",
        "product_id": "microsoft-windows-11",
        "company": "Microsoft",
        "software": "Windows 11",
        "public_category": "Operating Systems",
        "ingestion": {
            "official_url": "https://learn.microsoft.com/en-us/windows/release-health/",
            "secondary_official_url": "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information",
            "parser_profile": "windows_release_health",
        },
    }


URL = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"

# Mirrors the real release-information page. The current-versions summary table holds
# GA-channel rows (newest first). 24H2's "latest build" (26100.9999) is intentionally
# absent from the release-history table so its KB is omitted (never guessed). An LTSC
# row (23H2) is mixed in to prove the servicing-channel skip, and a trailing
# end-of-servicing table (21H2) must never be reached.
WIN11_HTML = """
<html><body>
<h2 id="windows-11-current-versions-by-servicing-option">Windows 11 current versions by servicing option</h2>
<table>
<thead>
<tr>
<th>Version</th><th>Servicing option</th><th>Availability date</th>
<th>End of updates: Home, Pro...</th><th>End of updates: Enterprise...</th>
<th>Latest update for ESU</th><th>Latest revision date</th><th>Latest build</th>
</tr>
</thead>
<tbody>
<tr><td>26H1</td><td>General Availability Channel</td><td>2026-02-10</td><td>2028-03-14</td><td>2029-03-13</td><td>Not applicable</td><td>2026-06-23</td><td>28000.2340</td></tr>
<tr><td>25H2</td><td>General Availability Channel</td><td>2025-09-30</td><td>2027-10-12</td><td>2028-10-10</td><td>Not applicable</td><td>2026-06-23</td><td>26200.8737</td></tr>
<tr><td>24H2</td><td>General Availability Channel</td><td>2024-10-01</td><td>2026-10-13</td><td>2027-10-12</td><td>Not applicable</td><td>2026-06-23</td><td>26100.9999</td></tr>
<tr><td>23H2</td><td>Long-Term Servicing Channel (LTSC)</td><td>2023-10-31</td><td>2028-11-10</td><td>2028-11-10</td><td>Not applicable</td><td>2026-06-23</td><td>22631.5000</td></tr>
</tbody>
</table>

<h2 id="enterprise-and-iot-enterprise-ltsc-editions">Enterprise and IoT Enterprise LTSC editions</h2>
<table>
<thead>
<tr><th>Version</th><th>Servicing option</th><th>Availability date</th><th>Mainstream support end date</th><th>Extended support end date</th><th>Latest update for ESU</th><th>Latest revision date</th><th>Latest build</th></tr>
</thead>
<tbody>
<tr><td>24H21</td><td>Long-Term Servicing Channel (LTSC)</td><td>2024-10-01</td><td>2029-10-09</td><td>2034-10-10</td><td>Not applicable</td><td>2026-06-23</td><td>26100.8737</td></tr>
</tbody>
</table>

<h2 id="windows-11-release-history">Windows 11 release history</h2>
<table>
<thead>
<tr><th>Servicing option</th><th>Update type</th><th>Availability date</th><th>Build</th><th>KB article</th></tr>
</thead>
<tbody>
<tr><td>General Availability Channel</td><td>2026-06 D</td><td>2026-06-23</td><td>28000.2340</td><td>KB5095091</td></tr>
<tr><td>General Availability Channel</td><td>2026-06 D</td><td>2026-06-23</td><td>26200.8737</td><td>KB5095093</td></tr>
<tr><td>General Availability Channel</td><td>2026-06 B</td><td>2026-06-09</td><td>26200.8655</td><td>KB5094126</td></tr>
</tbody>
</table>

<h2 id="windows-11-end-of-servicing">Windows 11 versions that have reached end of servicing</h2>
<table>
<thead>
<tr><th>Version</th><th>Servicing option</th><th>Availability date</th><th>End of updates: Home...</th><th>End of updates: Enterprise...</th><th>Latest update for ESU</th><th>Latest revision date</th><th>Latest build</th></tr>
</thead>
<tbody>
<tr><td>21H2</td><td>General Availability Channel</td><td>2021-10-04</td><td>2023-10-10</td><td>2024-10-08</td><td>Not applicable</td><td>2024-10-08</td><td>22000.3260</td></tr>
</tbody>
</table>
</body></html>
"""

LANDING_ONLY_HTML = """
<html><body>
  <h1>Windows release health</h1>
  <p>Stay informed about the latest known issues. Choose a version to view its status. No table on this hub page.</p>
</body></html>
"""

# For the KB-map ambiguity check: a build mapped to two different KBs must be dropped.
AMBIGUOUS_HISTORY_HTML = """
<table>
<tr><th>Servicing option</th><th>Update type</th><th>Availability date</th><th>Build</th><th>KB article</th></tr>
<tr><td>GA</td><td>2026-06 D</td><td>2026-06-23</td><td>26200.8737</td><td>KB5095093</td></tr>
<tr><td>GA</td><td>2026-06 C</td><td>2026-06-20</td><td>26200.8737</td><td>KB5099999</td></tr>
<tr><td>GA</td><td>2026-06 B</td><td>2026-06-09</td><td>26100.8655</td><td>KB5094126</td></tr>
</table>
"""

STATUS_URL_TEMPLATE = "https://learn.microsoft.com/en-us/windows/release-health/status-windows-11-{version_slug}"

# Mirrors a Release Health status page: a "Known issues" summary table
# (Summary | Originating update | Status | Last updated) plus a help footer that
# merely LINKS to a safeguard-holds article (must never create a false hold).
STATUS_MIXED_HTML = """
<html><body>
<h1>Windows 11, version 24H2 known issues and notifications</h1>
<h2>Known issues</h2>
<table>
<tr><th>Summary</th><th>Originating update</th><th>Status</th><th>Last updated</th></tr>
<tr><td>GIF functionality in the Windows Emoji Panel might become unavailable</td><td>N/A</td><td>Resolved KB5095093</td><td>2026-06-30 10:55 PT</td></tr>
<tr><td>Audio playback might stop after installing the June update</td><td>OS Build 26100.8655 KB5094126 2026-06-09</td><td>Confirmed</td><td>2026-06-23 10:07 PT</td></tr>
</table>
<h2>Report a problem with Windows updates</h2>
<p>Learn how to <a href="https://support.microsoft.com/topic/kb5006965-how-to-check-information-about-safeguard-holds-affecting-your-device">check safeguard holds affecting your device</a>.</p>
</body></html>
"""

# A status page whose single known issue is an actual safeguard hold (explicit ID).
STATUS_SAFEGUARD_HTML = """
<html><body>
<h1>Windows 11, version 23H2 known issues and notifications</h1>
<h2>Known issues</h2>
<table>
<tr><th>Summary</th><th>Originating update</th><th>Status</th><th>Last updated</th></tr>
<tr><td>Devices with a specific display driver are held from the update. Safeguard ID: 56789012</td><td>OS Build 22631.7219 KB5093998 2026-06-09</td><td>Confirmed</td><td>2026-06-18 20:53 PT</td></tr>
</table>
</body></html>
"""

# A status page with NO known-issues table, only a footer safeguard link.
STATUS_FOOTER_ONLY_HTML = """
<html><body>
<h1>Windows 11, version 26H1 known issues and notifications</h1>
<p>There are currently no known issues. See <a href="https://support.microsoft.com/topic/kb5006965-safeguard-holds">safeguard holds</a> help.</p>
</body></html>
"""

# A status page whose issues are all resolved (should NOT raise an active-issue warning).
STATUS_RESOLVED_ONLY_HTML = """
<html><body>
<h1>Windows 11, version 24H2 known issues and notifications</h1>
<h2>Known issues</h2>
<table>
<tr><th>Summary</th><th>Originating update</th><th>Status</th><th>Last updated</th></tr>
<tr><td>GIF functionality in the Windows Emoji Panel might become unavailable</td><td>N/A</td><td>Resolved KB5095093</td><td>2026-06-30 10:55 PT</td></tr>
<tr><td>Deleting a file from the Recycle Bin shows an internal filename</td><td>OS Build 26100.8655 KB5094126</td><td>Resolved KB5095093</td><td>2026-06-23 10:07 PT</td></tr>
</table>
</body></html>
"""


class _FakeResult:
    def __init__(self, text: str, url: str) -> None:
        self.text = text
        self.final_url = url
        self.url = url
        self.status = 200


def _fake_http(url_to_html: dict, raise_on: str = ""):
    def fake(url, *args, **kwargs):
        if raise_on and raise_on in url:
            raise RuntimeError("simulated status-page fetch failure")
        return _FakeResult(url_to_html.get(url, ""), url)
    return fake


def enriched_source() -> dict[str, object]:
    src = source()
    src["ingestion"] = {
        **src["ingestion"],
        "known_issues_capture": True,
        "status_url_template": STATUS_URL_TEMPLATE,
    }
    return src


def run() -> int:
    print("=" * 60)
    print("Microsoft Windows release-health adapter tests")
    print("=" * 60)

    records = mrh._records_from_windows_release_information(source(), URL, WIN11_HTML, 5)

    check("three current GA versions produce three records", len(records) == 3, str([r.get("version") for r in records]))

    if records:
        first = records[0]
        check("newest current GA version is first (26H1)", first.get("version") == "26H1", str(first.get("version")))
        check("latest OS build captured in official_summary", "28000.2340" in str(first.get("official_summary")), str(first.get("official_summary")))
        check("latest OS build captured in body", "28000.2340" in str(first.get("body")), str(first.get("body"))[:200])
        check("KB resolved from release-history build match (KB5095091)", "KB5095091" in str(first.get("official_summary")) and "KB5095091" in str(first.get("body")), str(first.get("official_summary")))
        check("latest revision date normalized to ISO (2026-06-23)", first.get("published_at") == "2026-06-23T00:00:00Z", str(first.get("published_at")))
        check("title carries software + feature version", first.get("title") == "Windows 11 26H1", str(first.get("title")))
        check("version field is the feature version (26H1)", first.get("version") == "26H1", str(first.get("version")))
        check("record is official-only: no report_count", first.get("report_count") is None and first.get("update_report_count") is None, str({k: first.get(k) for k in ("report_count", "update_report_count")}))
        check("record is official-only: no evidence/consensus state", first.get("evidence_state") is None and first.get("consensus_label") is None and first.get("consensus_collection_status") is None, str({k: first.get(k) for k in ("evidence_state", "consensus_label", "consensus_collection_status")}))
        check("record classified as official release_health", first.get("source_type") == "release_health" and first.get("official_source_type") == "release_health", str(first.get("source_type")))
        check("record does NOT claim release_notes_captured", first.get("official_note_status") == "official_source_captured", str(first.get("official_note_status")))
        check("record carries official url + capture status", str(first.get("official_url")).startswith("https://learn.microsoft.com") and first.get("capture_status") == "captured-from-official-windows-release-health", str(first.get("capture_status")))
        check("record carries reference official_sources list", isinstance(first.get("official_sources"), list) and len(first.get("official_sources")) >= 1, str(first.get("official_sources")))

    versions = [r.get("version") for r in records]
    check("record order is newest-first (26H1, 25H2, 24H2)", versions == ["26H1", "25H2", "24H2"], str(versions))

    if len(records) >= 2:
        check("second record resolves its own KB (25H2 -> KB5095093)", records[1].get("version") == "25H2" and "KB5095093" in str(records[1].get("official_summary")), str(records[1].get("official_summary")))

    if len(records) >= 3:
        third = records[2]
        check("KB omitted (not guessed) when build has no release-history match (24H2)", third.get("version") == "24H2" and "KB" not in str(third.get("official_summary")) and "26100.9999" in str(third.get("official_summary")), str(third.get("official_summary")))

    check("LTSC servicing row excluded (no 23H2 record)", all(r.get("version") != "23H2" for r in records), str(versions))
    check("footnote-suffixed LTSC version '24H21' never parsed as a version", all(r.get("version") != "24H21" for r in records), str(versions))
    check("end-of-servicing table never reached (no old 21H2 record)", all(r.get("version") != "21H2" for r in records), str(versions))

    # --- structured current-patch identity (target_* fields) ----------------
    if len(records) >= 3:
        first_rec, second_rec, third_rec = records[0], records[1], records[2]
        check("target_feature_version = feature train (26H1)", first_rec.get("target_feature_version") == "26H1", str(first_rec.get("target_feature_version")))
        check("target_os_build = latest OS build (28000.2340)", first_rec.get("target_os_build") == "28000.2340", str(first_rec.get("target_os_build")))
        check("target_kb = unambiguously-mapped KB (KB5095091)", first_rec.get("target_kb") == "KB5095091", str(first_rec.get("target_kb")))
        check("target_release_date = ISO revision date (2026-06-23)", first_rec.get("target_release_date") == "2026-06-23T00:00:00Z", str(first_rec.get("target_release_date")))
        check("target_os_build is train-specific (25H2 -> 26200.8737 / KB5095093)", second_rec.get("target_os_build") == "26200.8737" and second_rec.get("target_kb") == "KB5095093", str({k: second_rec.get(k) for k in ("target_os_build", "target_kb")}))
        check("target_kb empty (never guessed) when build has no unambiguous KB (24H2)", third_rec.get("target_os_build") == "26100.9999" and (third_rec.get("target_kb") or "") == "", str({k: third_rec.get(k) for k in ("target_os_build", "target_kb")}))

    limited = mrh._records_from_windows_release_information(source(), URL, WIN11_HTML, 1)
    check("limit respected (limit=1 -> one record, 26H1)", len(limited) == 1 and limited[0].get("version") == "26H1", str([r.get("version") for r in limited]))

    check("empty HTML yields no records", mrh._records_from_windows_release_information(source(), URL, "", 5) == [], "empty string")
    check("landing/hub page with no table yields no records", mrh._records_from_windows_release_information(source(), URL, LANDING_ONLY_HTML, 5) == [], "landing-only")

    # --- regex + KB-map unit guards -----------------------------------------
    check("version regex fullmatches 24H2 but not the 24H21 footnote form", mrh.VERSION_RE.fullmatch("24H2") is not None and mrh.VERSION_RE.fullmatch("24H21") is None)
    check("version regex matches 26H1 / 25H2", mrh.VERSION_RE.fullmatch("26H1") is not None and mrh.VERSION_RE.fullmatch("25H2") is not None)
    check("build regex fullmatches 26100.8737 but not the ESU token '2026-06 D'", mrh.BUILD_RE.fullmatch("26100.8737") is not None and mrh.BUILD_RE.fullmatch("2026-06 D") is None)
    check("servicing text 'General Availability Channel' is not a version", mrh.VERSION_RE.fullmatch("General Availability Channel") is None)

    kb_map = mrh._build_kb_map(WIN11_HTML)
    check("build->KB map resolves an unambiguous build", kb_map.get("28000.2340") == "KB5095091" and kb_map.get("26200.8737") == "KB5095093", str(kb_map))
    check("build->KB map omits a build with no KB row (26100.9999)", "26100.9999" not in kb_map, str(kb_map))

    ambiguous_map = mrh._build_kb_map(AMBIGUOUS_HISTORY_HTML)
    check("build->KB map drops ambiguous build (two KBs -> omitted)", "26200.8737" not in ambiguous_map and ambiguous_map.get("26100.8655") == "KB5094126", str(ambiguous_map))

    # --- fetch() profile gate (offline: returns [] before any network call) --
    bad_profile = source()
    bad_profile["ingestion"] = {**bad_profile["ingestion"], "parser_profile": "manual_watch"}
    check("fetch() ignores unsupported parser_profile (returns [] offline)", mrh.fetch(bad_profile, limit=3) == [], "unsupported profile")

    # --- Release Health status-page parser (known / resolved / safeguard) ----
    mixed = mrh._known_issues_from_status_page(STATUS_MIXED_HTML, "24H2")
    check("status parser returns one row per known issue (2)", len(mixed) == 2, str(len(mixed)))
    if len(mixed) == 2:
        resolved_issue, active_issue = mixed[0], mixed[1]
        check("resolved issue -> state resolved + resolving KB extracted", resolved_issue["state"] == "resolved" and resolved_issue["resolving_kb"] == "KB5095093", str(resolved_issue))
        check("N/A originating update parsed as empty build+kb", resolved_issue["originating_build"] == "" and resolved_issue["originating_kb"] == "", str(resolved_issue))
        check("Confirmed issue -> state active, no resolving KB", active_issue["state"] == "active" and active_issue["resolving_kb"] == "", str(active_issue))
        check("originating OS build and KB parsed", active_issue["originating_build"] == "26100.8655" and active_issue["originating_kb"] == "KB5094126", str(active_issue))
        check("last_updated captured", active_issue["last_updated"] == "2026-06-23 10:07 PT", str(active_issue.get("last_updated")))
        check("footer/help safeguard link does NOT create a safeguard hold", all(i["safeguard_id"] == "" for i in mixed), str([i["safeguard_id"] for i in mixed]))

    sg = mrh._known_issues_from_status_page(STATUS_SAFEGUARD_HTML, "23H2")
    check("safeguard ID captured only when explicitly present in the row", len(sg) == 1 and sg[0]["safeguard_id"] == "56789012", str(sg))
    check("empty status HTML -> no issues", mrh._known_issues_from_status_page("", "24H2") == [], "empty")
    check("footer-only status page (no summary table) -> no issues", mrh._known_issues_from_status_page(STATUS_FOOTER_ONLY_HTML, "26H1") == [], "footer-only")

    # --- deterministic roll-up text -----------------------------------------
    roll1 = mrh._issue_rollup_text("Windows 11", "24H2", mixed)
    roll2 = mrh._issue_rollup_text("Windows 11", "24H2", mixed)
    check("roll-up is deterministic (stable across calls)", roll1 == roll2 and roll1 != "", "determinism")
    check("roll-up header counts active/resolved/safeguard correctly", "1 active known issue(s), 1 resolved, 0 safeguard hold(s)" in roll1, roll1.splitlines()[0] if roll1 else "")
    check("roll-up labels it official Microsoft Release Health, not user reports", "Microsoft Release Health status (official)" in roll1 and "not user reports" in roll1, roll1.splitlines()[0] if roll1 else "")
    check("roll-up bullet carries status + originating + last updated + resolving KB", "resolved by KB5095093" in roll1 and "OS Build 26100.8655 KB5094126" in roll1 and "last updated" in roll1, roll1)
    check("empty issue list -> no roll-up text", mrh._issue_rollup_text("Windows 11", "24H2", []) == "", "empty roll")
    sg_roll = mrh._issue_rollup_text("Windows 11", "23H2", sg)
    check("safeguard roll-up counts the hold and shows the ID", "1 safeguard hold(s)" in sg_roll and "safeguard ID 56789012" in sg_roll, sg_roll)

    # --- deterministic issue counts (drive the official_* fields) ------------
    check("_issue_counts returns (active, resolved, safeguard) for mixed page", mrh._issue_counts(mixed) == (1, 1, 0), str(mrh._issue_counts(mixed)))
    check("_issue_counts counts a real safeguard hold", mrh._issue_counts(sg) == (1, 0, 1), str(mrh._issue_counts(sg)))
    check("_issue_counts of empty list is all zeros", mrh._issue_counts([]) == (0, 0, 0), "empty")
    resolved_only = mrh._known_issues_from_status_page(STATUS_RESOLVED_ONLY_HTML, "24H2")
    ra, rr, rs = mrh._issue_counts(resolved_only)
    check("resolved-only page -> 0 active, present would be False (no active warning)", ra == 0 and rr == 2 and rs == 0 and bool(ra or rs) is False, str((ra, rr, rs)))

    # --- fetch() body enrichment (offline via monkeypatched HTTP) -----------
    RELEASE_URL = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
    fake_map = {
        RELEASE_URL: WIN11_HTML,
        STATUS_URL_TEMPLATE.replace("{version_slug}", "26h1"): STATUS_FOOTER_ONLY_HTML,
        STATUS_URL_TEMPLATE.replace("{version_slug}", "25h2"): STATUS_MIXED_HTML,
        STATUS_URL_TEMPLATE.replace("{version_slug}", "24h2"): STATUS_MIXED_HTML,
    }
    _orig = mrh.fetch_text
    try:
        mrh.fetch_text = _fake_http(fake_map)
        enriched = mrh.fetch(enriched_source(), limit=6)
    finally:
        mrh.fetch_text = _orig
    by_ver = {r.get("version"): r for r in enriched}
    check("fetch() still returns the base current versions", set(by_ver) == {"26H1", "25H2", "24H2"}, str(sorted(by_ver)))
    if "24H2" in by_ver:
        body24 = str(by_ver["24H2"].get("body"))
        check("24H2 body enriched with official issue roll-up", "Microsoft Release Health status (official)" in body24 and "1 active known issue(s), 1 resolved" in body24, body24[-160:])
        check("enriched record stays official-only (no report/consensus/known_issues fields)", by_ver["24H2"].get("report_count") is None and by_ver["24H2"].get("evidence_state") is None and by_ver["24H2"].get("consensus_collection_status") is None and by_ver["24H2"].get("known_issues_present") is None, str({k: by_ver["24H2"].get(k) for k in ("report_count", "evidence_state", "known_issues_present")}))
        check("24H2 emits official_* count fields (1 active, 1 resolved, 0 safeguard)", by_ver["24H2"].get("official_active_issue_count") == 1 and by_ver["24H2"].get("official_resolved_issue_count") == 1 and by_ver["24H2"].get("official_safeguard_hold_count") == 0, str({k: by_ver["24H2"].get(k) for k in ("official_active_issue_count", "official_resolved_issue_count", "official_safeguard_hold_count")}))
        check("24H2 official_known_issues_present true when active issues exist", by_ver["24H2"].get("official_known_issues_present") is True, str(by_ver["24H2"].get("official_known_issues_present")))
        check("official_* fields never populate known_issues_present or complaint_themes", by_ver["24H2"].get("known_issues_present") is None and by_ver["24H2"].get("complaint_themes") is None, "separation")
    if "26H1" in by_ver:
        body26 = str(by_ver["26H1"].get("body"))
        check("26H1 (no known issues) body NOT enriched, base intact", "Microsoft Release Health status (official)" not in body26 and "current General Availability Channel" in body26, body26[-120:])
        check("26H1 (no issues parsed) emits NO official_* fields", by_ver["26H1"].get("official_active_issue_count") is None and by_ver["26H1"].get("official_known_issues_present") is None, str(by_ver["26H1"].get("official_active_issue_count")))

    # --- status-page fetch failure must leave the base record intact --------
    _orig2 = mrh.fetch_text
    try:
        mrh.fetch_text = _fake_http({RELEASE_URL: WIN11_HTML}, raise_on="status-windows-11")
        failed = mrh.fetch(enriched_source(), limit=6)
    finally:
        mrh.fetch_text = _orig2
    fby = {r.get("version"): r for r in failed}
    check("status fetch failure still yields the base records", set(fby) == {"26H1", "25H2", "24H2"}, str(sorted(fby)))
    if "24H2" in fby:
        fbody = str(fby["24H2"].get("body"))
        check("status fetch failure leaves base body unmodified (no roll-up)", "Microsoft Release Health status (official)" not in fbody and "current General Availability Channel" in fbody, fbody[-120:])

    # --- known_issues_capture unset -> no enrichment attempt at all ----------
    _orig3 = mrh.fetch_text
    try:
        mrh.fetch_text = _fake_http({RELEASE_URL: WIN11_HTML}, raise_on="status-windows-11")
        no_capture = mrh.fetch(source(), limit=6)  # source() has no known_issues_capture
    finally:
        mrh.fetch_text = _orig3
    check("known_issues_capture unset -> no status fetch, base records returned", {r.get("version") for r in no_capture} == {"26H1", "25H2", "24H2"}, str(sorted({r.get("version") for r in no_capture})))

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
