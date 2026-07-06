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
