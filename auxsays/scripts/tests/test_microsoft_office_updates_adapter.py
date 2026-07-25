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

# Mirrors the REAL teams-app-versioning hierarchy: cloud (h2) x app (h3) x platform (h4),
# each a distinct identity. Only Public cloud -> New Teams app version -> Windows is tracked.
# The same calendar release ships a different build per platform (Windows 26183.1903.4892.4448
# vs Mac 26183.1901.4874.5228), so mis-scoping would misreport a Windows user's patch state.
TEAMS_HTML = """
<html><body>
<h1>Version update history for the new and classic Microsoft Teams app</h1>
<p>Page last updated: October 2026.</p>
<h2>Public cloud offerings</h2>
  <h3>New Teams app version</h3>
    <h4>Mac</h4>
    <table><tr><td>2026</td><td>July 03</td><td>26183.1901.4874.5228</td><td>2026.22.0</td></tr></table>
    <h4>VDI</h4>
    <table><tr><td>2026</td><td>July 01</td><td>26183.2201.0001.0001</td><td>2026.22.0</td></tr></table>
    <h4>Web</h4>
    <table><tr><td>2026</td><td>July 01</td><td>26183.4101.0007.0001</td></tr></table>
    <h4>Windows</h4>
    <table>
    <thead><tr><th>Release year</th><th>Release date</th><th>Teams version</th><th>SlimCore version</th></tr></thead>
    <tbody>
    <tr><td>2026</td><td>July 01</td><td>26183.1903.4892.4448</td><td>2026.22.0</td></tr>
    <tr><td>2026</td><td>June 17</td><td>26149.1205.4798.6437</td><td>2026.20.0</td></tr>
    <tr><td>2026</td><td>June 03 (Public preview)</td><td>26120.9999.4700.0001</td><td>2026.24.0</td></tr>
    <tr><td>2026</td><td>February 30</td><td>26100.1000.4600.0002</td><td>2026.10.0</td></tr>
    <tr><td>2026</td><td></td><td>26090.900.4500.0003</td><td>2026.09.0</td></tr>
    </tbody>
    </table>
  <h3>Classic Teams app version</h3>
    <h4>Windows</h4>
    <table><tr><td>2024</td><td>April 09</td><td>2024.04.01.65</td><td></td></tr></table>
    <h4>Mobile: iOS</h4>
    <table><tr><td>2026</td><td>February 06</td><td>2026.02.01.06</td><td></td></tr></table>
    <h4>Mobile: Android</h4>
    <table><tr><td>2024</td><td>October 03</td><td>2024.40.01.07</td><td></td></tr></table>
<h2>Government cloud offerings</h2>
  <h3>New Teams app version</h3>
    <h4>Windows (GCCH)</h4>
    <table><tr><td>2026</td><td>July 01</td><td>26163.405.4842.717</td><td>2026.22.0</td></tr></table>
<h2>Sovereign cloud offerings</h2>
  <h3>Gallatin</h3>
    <h4>New Teams app version</h4>
    <table><tr><td>2026</td><td>July 01</td><td>26163.407.4839.8659</td><td>2026.22.0</td></tr></table>
</body></html>
"""

# The two records the Windows/Public/New-Teams identity should yield from TEAMS_HTML.
TEAMS_ACCEPTED = ["26183.1903.4892.4448", "26149.1205.4798.6437"]
# Everything that must be rejected (other platform/cloud/edition, preview, invalid/undated).
TEAMS_REJECTED = [
    "26183.1901.4874.5228",  # Public/New/Mac
    "26183.2201.0001.0001",  # Public/New/VDI
    "26183.4101.0007.0001",  # Public/New/Web
    "26120.9999.4700.0001",  # inline "Public preview" ring row
    "26100.1000.4600.0002",  # February 30 -> invalid calendar date
    "26090.900.4500.0003",   # undated row
    "2024.04.01.65",         # Public/Classic/Windows
    "2026.02.01.06",         # Public/Classic/Mobile: iOS
    "2024.40.01.07",         # Public/Classic/Mobile: Android
    "26163.405.4842.717",    # Government/New/Windows (GCCH)
    "26163.407.4839.8659",   # Sovereign/Gallatin/New Teams
]

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

    # --- Microsoft Teams: single-identity, fail-closed official ingestion -----
    # Identity: New Teams desktop client, Windows, Public cloud. Every other identity on the
    # teams-app-versioning page (other platforms/clouds/editions, preview/targeted rings) and
    # every malformed row is rejected.
    from types import SimpleNamespace
    from lib.write_update_record import build_front_matter
    check("Teams profile routes to the Teams parser", mso._PROFILE_PARSERS.get("microsoft_teams_version_history") is mso._records_from_teams_version_history)
    check("M365 profile still routes to the M365 parser", mso._PROFILE_PARSERS.get("microsoft_365_apps_update_history") is mso._records_from_office_release_notes)

    def T(html, limit=50):
        return mso._records_from_teams_version_history(teams_source(), TEAMS_URL, html, limit)

    teams = T(TEAMS_HTML)
    tvers = [r.get("version") for r in teams]

    # H1 / H2: exact stable new-Teams Windows version accepted; full 4-part build preserved.
    check("H1. exactly the two Windows/Public/New-Teams GA versions are accepted",
          tvers == TEAMS_ACCEPTED, str(tvers))
    check("H2. complete multi-component build preserved exactly (26183.1903.4892.4448)",
          teams and teams[0].get("version") == "26183.1903.4892.4448"
          and "26183.1903.4892.4448" in str(teams[0].get("title"))
          and "26183.1903.4892.4448" in str(teams[0].get("official_summary")), str(tvers[:1]))
    check("H2b. newest is first and dated (2026-07-01)",
          teams and teams[0].get("published_at") == "2026-07-01T00:00:00Z", str(teams[0].get("published_at") if teams else None))

    # H3-H12: every non-target identity / malformed row is rejected.
    rejected_present = [v for v in TEAMS_REJECTED if v in tvers]
    check("H3-8/21. Mac / VDI / Web / classic / mobile / government / gallatin / preview rows all rejected",
          rejected_present == [], str(rejected_present))
    check("H3. classic Teams version rejected", "2024.04.01.65" not in tvers)
    check("H4. web-only release rejected", "26183.4101.0007.0001" not in tvers)
    check("H5. iOS / Android mobile release rejected", "2026.02.01.06" not in tvers and "2024.40.01.07" not in tvers)
    check("H6. VDI release rejected", "26183.2201.0001.0001" not in tvers)
    check("H7/H21. public-preview ring row rejected; stable on same page accepted", "26120.9999.4700.0001" not in tvers and "26183.1903.4892.4448" in tvers)
    check("H8. targeted-release row rejected",
          T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
            "<table><tr><td>2026</td><td>July 08 (Targeted release)</td><td>26190.100.4900.7777</td></tr></table>") == [])
    check("H9. beta / test build rows rejected",
          T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
            "<table><tr><td>2026</td><td>July 08 (beta)</td><td>26190.100.4900.0001</td></tr>"
            "<tr><td>2026</td><td>July 09 test build</td><td>26191.100.4900.0002</td></tr></table>") == [])
    check("H10. service-feature announcement without a client version -> no record",
          T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
            "<p>New meeting features are rolling out.</p><table><tr><td>2026</td><td>July 01</td><td>Feature rollout</td></tr></table>") == [])
    check("H11. generic Microsoft 365 announcement page -> no Teams records",
          T("<h1>What's new in Microsoft 365</h1><table><tr><td>Version 2606 (Build 20131.20154)</td><td>July 2026</td></tr></table>") == [])
    check("H12. another Microsoft app version (Office build) is not a Teams version",
          T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
            "<table><tr><td>2026</td><td>July 01</td><td>20131.20154</td></tr></table>") == [])

    # H13-H18: version/date integrity.
    check("H13. exact version without a date rejected (undated row)", "26090.900.4500.0003" not in tvers)
    check("H14. a date with no exact Teams version rejected",
          T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
            "<table><tr><td>2026</td><td>July 01</td><td>latest</td></tr></table>") == [])
    check("H15. invalid calendar date (February 30) rejected", "26100.1000.4600.0002" not in tvers)
    check("H16. multiple conflicting versions in one row rejected",
          T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
            "<table><tr><td>2026</td><td>July 01</td><td>26190.100.4900.0001 26191.100.4900.0002</td></tr></table>") == [])
    check("H17. multiple conflicting dates in one row rejected",
          T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
            "<table><tr><td>2026</td><td>July 01</td><td>26190.100.4900.0001</td><td>August 15</td></tr></table>") == [])
    check("H18. a page-updated date in prose does not date a version row",
          T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
            "<p>Page updated October 2026.</p><table><tr><td>2026</td><td>July 01</td><td>26190.100.4900.0001</td></tr></table>")[0]["published_at"] == "2026-07-01T00:00:00Z")

    # H19: alternate official URLs -> one identity; transport failure fail-closed (fetch level).
    URL_A = TEAMS_URL
    URL_B = "https://learn.microsoft.com/en-us/officeupdates/teams-archive"
    def with_fetch(mapping, fn):
        orig = mso.fetch_text
        def fake(url, **_kw):
            if url not in mapping:
                raise RuntimeError("timeout")
            return SimpleNamespace(text=mapping[url], final_url=url)
        mso.fetch_text = fake
        try:
            return fn()
        finally:
            mso.fetch_text = orig
    two_url_src = {**teams_source(), "ingestion": {**teams_source()["ingestion"], "secondary_official_url": URL_B}}
    both = with_fetch({URL_A: TEAMS_HTML, URL_B: TEAMS_HTML}, lambda: mso.fetch(two_url_src, 50))
    check("H19. same version on two official URLs -> one identity (from the primary URL)",
          [r["version"] for r in both] == TEAMS_ACCEPTED and all(r["source_url"] == URL_A for r in both), str([(r["version"], r["source_url"]) for r in both]))
    raised = False
    try:
        with_fetch({}, lambda: mso.fetch(two_url_src, 50))
    except RuntimeError:
        raised = True
    check("H19b. all official URLs failing transport -> fetch raises (fail-closed)", raised)

    # H20: same version with conflicting dates -> fail visibly (dropped, not first-wins).
    conflict = T("<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
                 "<table><tr><td>2026</td><td>July 01</td><td>26190.100.4900.0001</td></tr>"
                 "<tr><td>2026</td><td>August 15</td><td>26190.100.4900.0001</td></tr></table>")
    check("H20. same version with conflicting release dates fails visibly (no record)", conflict == [])

    # H22-25: run_source backfill / rerun / dry-run over the Teams parser.
    import tempfile
    from pathlib import Path as _P
    class _TeamsAdapter:
        @staticmethod
        def fetch(source, limit=3):
            return T(TEAMS_HTML, limit)
    teams_cfg = {"company_id": "microsoft", "product_id": "microsoft-teams", "company": "Microsoft",
                 "software": "Microsoft Teams", "public_category": "Workplace Critical",
                 "ingestion": {"adapter": "microsoft_office_updates", "parser_profile": "microsoft_teams_version_history",
                               "official_url": TEAMS_URL}}
    import patch_ingest
    orig_mod = patch_ingest.adapter_module
    patch_ingest.adapter_module = lambda name: _TeamsAdapter
    try:
        with tempfile.TemporaryDirectory() as td:
            a = SimpleNamespace(limit=1, output=_P(td) / "generated", overwrite_existing=False)
            a.output.mkdir(parents=True, exist_ok=True)
            st = {"schema_version": 1, "sources": {}, "seen": {}}
            r1 = patch_ingest.run_source(teams_cfg, a, st)
            r2 = patch_ingest.run_source(teams_cfg, a, st)
            names1 = [_P(p).name for p in r1["written"]]
            names2 = [_P(p).name for p in r2["written"]]
            check("H22/H23. rerun does not duplicate; backfill advances to a different record",
                  len(names1) == 1 and len(names2) == 1 and set(names1).isdisjoint(names2), str((names1, names2)))
            r3 = patch_ingest.run_source(teams_cfg, a, st)  # both in-window records now created
            check("H23b. backfill converges (no new records once the window is drained)", r3["created"] == 0, str(r3["created"]))
            files_before = sorted(f.name for f in a.output.glob("*.md"))
            # H25: dry-run writes nothing and mutates no state.
            st_dry = {"schema_version": 1, "sources": {}, "seen": {}}
            rd = patch_ingest.run_source(teams_cfg, a, st_dry, write=False)
            check("H25. dry-run creates zero files and marks zero seen-state",
                  rd.get("dry_run") is True and st_dry.get("sources", {}).get("microsoft-teams", {}).get("seen", []) == []
                  and sorted(f.name for f in a.output.glob("*.md")) == files_before, str(rd.get("dry_run")))
    finally:
        patch_ingest.adapter_module = orig_mod

    # H26: unrelated content / empty / landing -> zero records.
    check("H26. empty, landing, and non-Teams HTML all yield zero records",
          T("", 5) == [] and T(TEAMS_LANDING_HTML, 5) == [] and T(UPDATE_HISTORY_HTML, 5) == [])

    # H27: generated record derives official_only with zero reports and carries the identity.
    t0 = teams[0]
    front = build_front_matter(t0)
    check("H27. front matter is official_only with 0 reports",
          front["evidence_state"] == "official_only" and front["update_report_count"] == 0,
          str({k: front[k] for k in ("evidence_state", "update_report_count")}))
    check("H27b. record carries explicit single identity (New Teams / Windows / Public cloud)",
          t0.get("teams_edition") == "New Teams" and t0.get("target_platform") == "Windows"
          and str(t0.get("target_channel")).startswith("Public cloud")
          and t0.get("source_type") == "release_notes"
          and t0.get("capture_status") == "captured-from-official-microsoft-teams-version-history",
          str({k: t0.get(k) for k in ("teams_edition", "target_platform", "target_channel")}))
    blob = " ".join(str(t0.get(k, "")) for k in ("body", "official_summary", "title")).lower()
    check("H27c. record carries no consensus/community/report language",
          not any(term in blob for term in ("consensus", "users report", "community", "complaint", "severity")), blob[:120])
    check("Teams limit respected (limit=1 -> newest only)",
          [r["version"] for r in T(TEAMS_HTML, 1)] == ["26183.1903.4892.4448"], "limit=1")

    # --- Regression: adversarial identity-leak defects (must stay fail-closed) --
    _W = "<h2>Public cloud offerings</h2><h3>New Teams app version</h3><h4>Windows</h4>"
    _tbl = lambda rows: "<table><tr><th>Release year</th><th>Release date</th><th>Teams version</th></tr>" + rows + "</table>"
    _GOOD = "<tr><td>2026</td><td>July 01</td><td>26183.1903.4892.4448</td></tr>"
    def _v(h): return [r["version"] for r in T(h)]

    # D1/D3: a foreign platform/cloud/ring label in an UNTRACKED element (h5, p, div, caption)
    # must taint the zone so a stale Windows heading cannot leak the next table's foreign builds.
    check("D1. <h5>Mac</h5> delimiter does not leak the following Mac table",
          "26183.1901.4874.5228" not in _v(_W + _tbl(_GOOD) + "<h5>Mac</h5>" + _tbl("<tr><td>2026</td><td>July 01</td><td>26183.1901.4874.5228</td></tr>")))
    check("D1. <div>...GCC (Government) builds</div> delimiter does not leak a Government build",
          "26183.3333.3333.3333" not in _v(_W + _tbl(_GOOD) + "<div>Note: the following are GCC (Government) builds</div>" + _tbl("<tr><td>2026</td><td>July 01</td><td>26183.3333.3333.3333</td></tr>")))
    check("D1/D3. <p>Public preview (insider) builds:</p> delimiter does not leak an insider build",
          "26196.1000.5000.5000" not in _v(_W + _tbl(_GOOD) + "<p>Public preview (insider) builds:</p>" + _tbl("<tr><td>2026</td><td>July 01</td><td>26196.1000.5000.5000</td></tr>")))
    check("D3. a <caption>Insider</caption> on the table taints its rows",
          T(_W + "<table><caption>Insider</caption><tr><td>2026</td><td>July 01</td><td>26181.1000.4000.4000</td></tr></table>") == [])
    check("D1b. a benign <p>General availability builds.</p> intro does NOT drop the real table",
          _v(_W + "<p>General availability builds.</p>" + _tbl(_GOOD)) == ["26183.1903.4892.4448"])

    # D2: exact heading match + heading-level ring exclusion (no startswith over-match).
    check("D2. 'Public cloud offerings (Preview)' / '- Targeted release' / 'for Government' headings are rejected",
          all(T(h + "<h3>New Teams app version</h3><h4>Windows</h4>" + _tbl(_GOOD)) == [] for h in (
              "<h2>Public cloud offerings (Preview)</h2>",
              "<h2>Public cloud offerings - Targeted release</h2>",
              "<h2>Public cloud offerings for Government (GCC High)</h2>")))

    # D4: ring token exclusion runs on normalized cell text (survives &nbsp; / inline-tag splits).
    check("D4. 'Release&nbsp;candidate' ring token in a cell is excluded",
          T(_W + "<table><tr><td>2026</td><td>July 05</td><td>26183.6666.0001.0001</td><td>Release&nbsp;candidate</td></tr></table>") == [])

    # D5: two dates in a single cell -> ambiguous -> dropped.
    check("D5. two dates in one cell ('March 03 and March 17') -> no record",
          T(_W + "<table><tr><td>2026</td><td>March 03 and March 17</td><td>26183.1903.4892.4448</td></tr></table>") == [])

    # D6: rowspan-grouped 'Release year' -> the year carries forward (no false-negative drop).
    check("D6. rowspan year column carries forward so later rows still record",
          _v(_W + "<table><tr><th>Release year</th><th>Release date</th><th>New Teams version</th></tr>"
                  "<tr><td rowspan='2'>2026</td><td>July 01</td><td>26183.1903.4892.4448</td></tr>"
                  "<tr><td>June 17</td><td>26149.1205.4798.6437</td></tr></table>")
          == ["26183.1903.4892.4448", "26149.1205.4798.6437"])

    # --- Regression: second adversarial pass ----------------------------------
    # R2-D1: the row ring filter uses the separator-flexible regex, so hyphen/underscore/dot/
    # no-separator ring tokens in a cell are excluded (not just the single-space literal).
    check("R2-D1. separator-variant ring tokens in a cell are all excluded",
          all(T(_W + f"<table><tr><td>2026</td><td>June 05</td><td>26183.1903.4892.4448</td><td>{sep}</td></tr></table>") == []
              for sep in ("Release-candidate", "release_candidate", "test-build", "test.build", "pre release", "Pre-Release")))
    # R2-D2: the version must be a real YYDDD build, not just a 5-6 digit shape.
    check("R2-D2. shape-only look-alikes (6-digit / impossible day-of-year) are rejected",
          all(T(_W + f"<table><tr><td>2026</td><td>June 05</td><td>{bad}</td></tr></table>") == []
              for bad in ("123456.1.1.1", "999999.9.9.9", "26999.1.1.1", "26000.1.1.1", "26400.1.1.1")))
    check("R2-D2b. a genuine YYDDD build (26005 = day 5) is still accepted",
          _v(_W + "<table><tr><td>2026</td><td>January 05</td><td>26005.213.4315.4117</td></tr></table>") == ["26005.213.4315.4117"])
    # R2-D3: a benign sub-heading (h5/h6) must not clear a foreign taint.
    check("R2-D3. a benign <h5> after a foreign <p> label does not clear the taint",
          "26196.1000.5000.5000" not in _v(_W + _tbl(_GOOD) + "<p>Insider</p><h5>Details</h5>"
                                            + _tbl("<tr><td>2026</td><td>July 01</td><td>26196.1000.5000.5000</td></tr>")))
    # R2-D4: descriptive prose that merely mentions a foreign word must NOT taint the section.
    check("R2-D4. a descriptive sentence mentioning 'classic' does not drop genuine Windows builds",
          _v(_W + "<p>The new Teams app replaces the classic Teams app on Windows.</p>" + _tbl(_GOOD)) == ["26183.1903.4892.4448"])

    # --- Regression: third adversarial pass (table-anchored identity) ----------
    # Identity is never inherited across a table boundary: each emitting table must sit directly
    # under a fresh <h4>Windows</h4>. R3-D1: an orphan foreign table whose only marker is its own
    # header row cannot leak.
    check("R3-D1. an orphan foreign (GCC) table after the Windows table does not leak",
          "26201.1500.2500.3500" not in _v(_W + _tbl(_GOOD) + "<table><tr><th>GCC release year</th><th>GCC release date</th><th>GCC version</th></tr><tr><td>2026</td><td>July 20</td><td>26201.1500.2500.3500</td></tr></table>"))
    # R3-D2: a foreign table separated by prose or an uncaptured tag (span/header/...) cannot leak.
    check("R3-D2. a foreign table after descriptive prose / a <span> label does not leak",
          "26203.4444.5555.6666" not in _v(_W + _tbl(_GOOD) + "<p>The table below shows the release history for the iOS mobile version of the client.</p>" + _tbl("<tr><td>2026</td><td>July 22</td><td>26203.4444.5555.6666</td></tr>"))
          and "26202.1111.2222.3333" not in _v(_W + _tbl(_GOOD) + "<span>Government cloud (GCCH)</span>" + _tbl("<tr><td>2026</td><td>July 22</td><td>26202.1111.2222.3333</td></tr>")))
    # R3-D3: a ring sub-heading (h5/h6, incl. plural) disarms the following table.
    check("R3-D3. an <h5>Insiders</h5> sub-heading disarms the following table",
          "26204.7777.8888.9999" not in _v(_W + "<h5>Insiders</h5>" + _tbl("<tr><td>2026</td><td>July 01</td><td>26204.7777.8888.9999</td></tr>")))
    # R3-D4: inline ring tokens (RC / TAP / Dev / Nightly / Early Access / no-separator) in a
    # Windows-table cell are excluded.
    check("R3-D4. inline RC / TAP / Dev / Nightly / ReleaseCandidate / Early Access rows are excluded",
          all(T(_W + f"<table><tr><td>2026</td><td>July 01</td><td>26183.1903.4892.4448</td><td>{r}</td></tr></table>") == []
              for r in ("RC", "TAP", "Dev", "Nightly", "ReleaseCandidate", "Early Access")))
    # R3-D5: a year-group header row updates the carried year before any early continue, so no
    # build inherits a neighbouring year-group's year.
    check("R3-D5. year-group rows date each build with its OWN year (no off-by-a-year)",
          [(r["version"], r["published_at"]) for r in T(_W + "<table><tr><th>Release year</th><th>Release date</th><th>Teams version</th></tr>"
                  "<tr><td>2025</td><td>December 01</td><td>25335.1000.2000.3000</td></tr>"
                  "<tr><td>2026</td><td>January 05</td><td>26005.213.4315.4117</td></tr></table>")]
          == [("25335.1000.2000.3000", "2025-12-01T00:00:00Z"), ("26005.213.4315.4117", "2026-01-05T00:00:00Z")])
    # False-negative sanity: a benign caption and benign prose must NOT drop the real table.
    check("R3-FN. a benign caption / classic-mentioning prose keeps the genuine Windows build",
          _v(_W + "<table><caption>Windows release history</caption><tr><td>2026</td><td>July 01</td><td>26183.1903.4892.4448</td></tr></table>") == ["26183.1903.4892.4448"])

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
