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
        "official_url": "https://learn.microsoft.com/en-us/officeupdates/current-channel",
        "secondary_official_url": "https://learn.microsoft.com/en-us/officeupdates/update-history-microsoft365-apps-by-date",
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

# Representative *server-rendered Current Channel* release-notes page (the repaired primary
# source). Multiple versions, mixed per-app attribution, exact builds + release dates.
CURRENT_CHANNEL = """
<h2>Version 2607 (Build 20200.20100)</h2>
<p>Current Channel released August 11, 2026.</p>
<h3>Resolved issues</h3>
<ul>
  <li>PowerPoint: Fixed an issue where the app could crash when saving a presentation that contains SmartArt.</li>
</ul>
<h2>Version 2606 (Build 20131.20154)</h2>
<p>Current Channel released July 14, 2026.</p>
<h3>Resolved issues</h3>
<ul>
  <li>Word: Fixed an issue with the citations pane.</li>
  <li>Excel: Fixed a crash opening large workbooks.</li>
  <li>Outlook: Fixed an issue with search folders.</li>
</ul>
<h2>Version 2605 (Build 20029.20064)</h2>
<p>Current Channel released June 9, 2026.</p>
<h3>Resolved issues</h3>
<ul>
  <li>Various performance and reliability improvements across Microsoft 365.</li>
</ul>
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

    # === Current Channel (repaired primary source) contract =================
    cc = _parse(CURRENT_CHANNEL)
    cc_versions = sorted(x.get("version") for x in cc)
    pp = next((x for x in cc if x.get("version") == "2607"), {})

    # Case 1: explicit PowerPoint resolved issue -> accepted with exact identity + PP-only applicability
    check("CC case1: explicit PowerPoint resolved issue accepted (v2607)", pp.get("version") == "2607", str(cc_versions))
    check("CC case1: exact build preserved", pp.get("target_build") == "20200.20100", str(pp.get("target_build")))
    check("CC case1: exact app version preserved", pp.get("target_app_version") == "2607", str(pp.get("target_app_version")))
    check("CC case1: Current Channel preserved", pp.get("target_channel") == "Current Channel", str(pp.get("target_channel")))
    check("CC case1: release date preserved", (pp.get("published_at") or "").startswith("2026-08-11"), str(pp.get("published_at")))
    check("CC case1: applicability is PowerPoint-only (no suite id)", pp.get("applicability") == ["microsoft-powerpoint"], str(pp.get("applicability")))
    check("CC case1: official source URL is the Current Channel page", pp.get("source_url") == PP_SOURCE["ingestion"]["official_url"], str(pp.get("source_url")))

    # Cases 2-4: Word / Excel / Outlook-only version (2606) -> no PowerPoint record; no leak
    check("CC case2-4: Word/Excel/Outlook-only version (2606) yields no PowerPoint record", all(x.get("version") != "2606" for x in cc))
    check("CC case2-4: no other-app text leaks into any PowerPoint record",
          all(t not in (x.get("body") or "") for x in cc for t in ("citations pane", "large workbooks", "search folders")))

    # Case 5: generic Microsoft 365 servicing (2605) with no app attribution -> rejected
    check("CC case5: generic Microsoft 365 version (2605) yields no PowerPoint record", all(x.get("version") != "2605" for x in cc))
    check("CC: exactly one PowerPoint record from the multi-version page (only v2607)", cc_versions == ["2607"], str(cc_versions))

    # Case 6: explicit suite-wide materially-applicable item -> accepted with shared applicability + one source identity
    suite_ok = _parse('<h2>Version 2608 (Build 20250.20050)</h2><p>Current Channel released September 8, 2026.</p>'
                      '<h3>Resolved issues</h3><ul><li>We fixed an issue affecting all apps where the app may fail to launch.</li></ul>')
    check("CC case6: explicit suite-wide item accepted (1 record)", len(suite_ok) == 1, str(len(suite_ok)))
    check("CC case6: shared applicability [powerpoint, 365-apps]",
          bool(suite_ok) and suite_ok[0].get("applicability") == ["microsoft-powerpoint", "microsoft-365-apps"],
          str(suite_ok[0].get("applicability") if suite_ok else None))
    check("CC case6: common source identity preserved (source_url == official_url)",
          bool(suite_ok) and suite_ok[0].get("source_url") == suite_ok[0].get("official_url") == PP_SOURCE["ingestion"]["official_url"])

    # Cases 7-9: fail closed on missing version / build / release date
    check("CC case7: missing version heading -> 0 records",
          len(_parse('<h3>Resolved issues</h3><ul><li>PowerPoint: crash fix.</li></ul>')) == 0)
    check("CC case8: version but no build -> 0 records",
          len(_parse('<h2>Version 2609</h2><p>Current Channel released October 13, 2026.</p><ul><li>PowerPoint: crash fix.</li></ul>')) == 0)
    check("CC case9: version+build but no release date -> 0 records (fail closed)",
          len(_parse('<h2>Version 2610 (Build 20300.20010)</h2><ul><li>PowerPoint: crash fix.</li></ul>')) == 0)

    # Case 10: JavaScript-shell / DOM-miss -> 0 records, no fabricated fallback
    js_shell = '<!doctype html><html><head><script>window.__data={};</script></head><body><div id="root"></div></body></html>'
    check("CC case10: JavaScript-shell / DOM-miss input -> 0 records (no fabricated fallback)", len(_parse(js_shell)) == 0)

    # Case 11: official-only invariants on the accepted CC record
    if pp:
        fcc = build_front_matter(pp)
        check("CC case11: front matter official_only + 0 reports + 0 confirmed",
              fcc["evidence_state"] == "official_only" and fcc["update_report_count"] == 0 and fcc["confirmed_patch_specific_report_count"] == 0,
              str({k: fcc.get(k) for k in ("evidence_state", "update_report_count", "confirmed_patch_specific_report_count")}))
        check("CC case11: no community report count / evidence state / consensus label on the record",
              pp.get("report_count") is None and pp.get("evidence_state") is None and pp.get("consensus_label") is None)
        check("CC case11: no complaint themes inferred from official notes", fcc.get("complaint_themes") in (None, [], ""))
        check("CC case11: known-issues field not polluted by identity metadata",
              "20200.20100" not in str(fcc.get("known_issues_present") or "") and "microsoft-powerpoint" not in str(fcc.get("known_issues_present") or ""))

    # === Release-date year derivation from the 4-digit YYMM version ==========
    # The real Current Channel page prints the per-version date WITHOUT a year
    # ("Version 2606: July 14"); the year is derived from the version number.
    yd = _parse('<h3>Version 2607: August 11</h3><p>Version 2607 (Build 20200.20100)</p>'
                '<h4>Resolved issues</h4><ul><li>PowerPoint: Fixed a crash saving SmartArt.</li></ul>')
    check("date-derivation: 'Version 2607: August 11' -> 2026-08-11 (year from YYMM)",
          len(yd) == 1 and (yd[0].get("published_at") or "").startswith("2026-08-11"),
          str(yd[0].get("published_at") if yd else None))
    # Year rollover: a late-year version shipping early the next calendar year
    ydw = _parse('<h3>Version 2512: January 15</h3><p>Version 2512 (Build 18800.20050)</p>'
                 '<h4>Resolved issues</h4><ul><li>PowerPoint: Fixed a hang on launch.</li></ul>')
    check("date-derivation: 'Version 2512: January 15' -> 2026-01-15 (year rollover)",
          len(ydw) == 1 and (ydw[0].get("published_at") or "").startswith("2026-01-15"),
          str(ydw[0].get("published_at") if ydw else None))
    # A full 'Month DD, YYYY' date is still honored when present (backward compatible)
    check("date-derivation: full 'Month DD, YYYY' still honored", (pp.get("published_at") or "").startswith("2026-08-11"))
    # No 'Month DD' at all -> fail closed (no fabricated date)
    check("date-derivation: version+build but NO month/day -> 0 records (fail closed)",
          len(_parse('<h3>Version 2611</h3><p>Version 2611 (Build 20400.20010)</p><ul><li>PowerPoint: fix.</li></ul>')) == 0)

    # --- invalid / impossible date rejection (fail closed; never fabricate) ---
    check("invalid-date: impossible day 'July 40' -> 0 records",
          len(_parse('<h3>Version 2607: July 40</h3><p>Version 2607 (Build 20200.20100)</p><ul><li>PowerPoint: fix.</li></ul>')) == 0)
    check("invalid-date: 'February 30, 2026' full date -> 0 records (no backtrack to Feb 3)",
          len(_parse('<h3>Version 2602 (Build 19725.20126)</h3><p>Current Channel released February 30, 2026.</p><ul><li>PowerPoint: fix.</li></ul>')) == 0)
    check("invalid-date: month substring in a word ('Smarch 5') not matched -> 0 records",
          len(_parse('<h3>Version 2607: Smarch 5</h3><p>Version 2607 (Build 20200.20100)</p><ul><li>PowerPoint: fix.</li></ul>')) == 0)
    check("invalid-date: malformed YYMM version (month 00) -> 0 records",
          len(_parse('<h3>Version 2600: July 14</h3><p>Version 2600 (Build 20200.20100)</p><ul><li>PowerPoint: fix.</li></ul>')) == 0)
    check("unit: _iso_date rejects an impossible day (Feb 30)", mso._iso_date(2026, 2, 30) == "")
    check("unit: _iso_date accepts a valid date", mso._iso_date(2026, 7, 14) == "2026-07-14T00:00:00Z")

    # --- adjacent release sections: own date + no date/issue leakage ----------
    adj = _parse('<h3>Version 2607: August 11</h3><p>Version 2607 (Build 20200.20100)</p><ul><li>PowerPoint: crashAlpha.</li></ul>'
                 '<h3>Version 2606: July 14</h3><p>Version 2606 (Build 20131.20154)</p><ul><li>PowerPoint: crashBeta.</li></ul>')
    by_ver = {r["version"]: r for r in adj}
    check("adjacent sections: both PowerPoint versions produced", set(by_ver) == {"2607", "2606"}, str(sorted(by_ver)))
    check("adjacent sections: v2607 keeps its OWN date (2026-08-11)", (by_ver.get("2607", {}).get("published_at") or "").startswith("2026-08-11"))
    check("adjacent sections: v2606 keeps its OWN date (2026-07-14)", (by_ver.get("2606", {}).get("published_at") or "").startswith("2026-07-14"))
    check("adjacent sections: v2607 keeps its OWN build", by_ver.get("2607", {}).get("target_build") == "20200.20100")
    check("adjacent sections: no issue-text leak (v2607 has crashAlpha, not crashBeta)",
          "crashAlpha" in (by_ver.get("2607", {}).get("body") or "") and "crashBeta" not in (by_ver.get("2607", {}).get("body") or ""))

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
