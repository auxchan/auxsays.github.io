"""Microsoft 365 / Office official update-notes adapter.

Conservative official-source ingestion for the Microsoft 365 Apps (Office) update
family on learn.microsoft.com/officeupdates. It parses the official "update history
by date" table (columns: Channel, Version, Build, Latest release date, Version
availability date, End of service) into official-only records for the mainstream
Current Channel.

Design rules:
- Official ingestion only. This adapter never emits consensus/report fields; every
  record stays official_only (report_count is left unset, so write_update_record
  derives evidence_state=official_only).
- Conservative: only real table rows that contain a bare version number AND a build
  number are turned into records. If the page structure does not match (DOM changed,
  landing page with no table, etc.) the adapter returns [] rather than fabricating a
  record.
- parser_profile dispatch keeps this file reusable across Office lanes without a new
  file: the Microsoft 365 Apps suite update-history table, the Microsoft Teams version
  history, and per-app (e.g. PowerPoint) release-note attribution each have a pure parser.
- App attribution is fail-closed and explicit: a version becomes a record for an individual
  app (PowerPoint) only when a feature/fixed-issue block names that app (word-boundary) or
  is explicitly all-Office-apps. Generic suite channel/build rows are never attributed to an
  individual app -- they stay on the Microsoft 365 Apps (shared servicing) page.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from lib.http import fetch_text
from lib.normalize import strip_tags, first_nonempty

ROW_RE = re.compile(r"<tr\b[^>]*>(?P<row>.*?)</tr>", re.I | re.S)
CELL_RE = re.compile(r"<t[dh]\b[^>]*>(?P<cell>.*?)</t[dh]>", re.I | re.S)
# Headings + rows in document order, so a parser can skip rows under a given section
# heading (e.g. "Public preview") without depending on the row text alone.
SECTION_RE = re.compile(
    r"<h[1-4]\b[^>]*>(?P<heading>.*?)</h[1-4]>|<tr\b[^>]*>(?P<row>.*?)</tr>",
    re.I | re.S,
)
VERSION_CELL_RE = re.compile(r"\d{3,4}")
BUILD_CELL_RE = re.compile(r"\d{3,6}\.\d{3,6}")
DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(20\d{2})",
    re.I,
)
# The Current Channel release-notes page prints a per-version date WITHOUT a year
# ("Version 2606: July 14"); the year is derived from the 4-digit YYMM version number.
NO_YEAR_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2})\b(?!\d|,\s*20\d{2})",
    re.I,
)
MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
}
# Mainstream monthly feature channel. Preview/insider/enterprise variants are skipped
# so version numbers stay 1:1 with a single record (no canonical-URL collisions).
DEFAULT_CHANNEL = "Current Channel"
EXCLUDE_CHANNEL_TOKENS = ("preview", "insider", "beta")

# Microsoft Teams version-history table rows are
# [Release year | Release date ("July 01") | Teams version | SlimCore version (3-part)].
#
# The teams-app-versioning page is NOT a single list: it is a hierarchy of DISTINCT product
# identities -- cloud (Public / Government / Sovereign-Gallatin) x app (New Teams / Classic
# Teams) x platform (Windows / Mac / Web / VDI / Mobile), each with its own version stream.
# The SAME calendar release ships different build numbers per platform (e.g. Public New Teams
# Windows 26183.1903.4892.4448 vs Mac 26183.1901.4874.5228), so a record must be scoped to a
# SINGLE identity or it misreports a user's patch state. This adapter tracks exactly one:
# the mainstream New Teams desktop client for Windows in the Public cloud. Every other
# section is rejected (see _records_from_teams_version_history).
#
# New Teams desktop builds use a 5-digit "YYDDD" first component (e.g. 26183.1903.4892.4448).
# That distinguishes them from the classic-Teams / Web "YYYY.WW.dd.n" 4-digit-year format and
# from the 3-part SlimCore value -- a secondary guard; the section hierarchy is primary.
TEAMS_VERSION_RE = re.compile(r"\d{5}\.\d{1,6}\.\d{1,6}\.\d{1,6}")
TEAMS_YEAR_RE = re.compile(r"20\d{2}")
TEAMS_MONTH_DAY_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2})\b",
    re.I,
)
# The single tracked identity, matched EXACTLY (not startswith) against the page's h2/h3/h4
# heading hierarchy, so a ring/edition qualifier ("Public cloud offerings (Preview)") never
# passes as the production Public-cloud section.
TEAMS_CLOUD_HEADINGS = ("public cloud", "public cloud offerings")  # h2
TEAMS_TYPE_HEADING = "new teams app version"                       # h3: reject Classic Teams
TEAMS_PLATFORM_HEADING = "windows"                                 # h4 (exact): reject Mac /
                                                                  #   Web / VDI / Mobile and the
                                                                  #   government "Windows (GCC...)"
# Table-anchored tokenizer: headings h1-h6 (to arm/disarm the target identity) and whole
# <table> blocks (each parsed only when it sits directly under a freshly declared target
# <h4>Windows</h4>). Identity is therefore never inherited across a table boundary, so an
# orphan foreign table, a table after prose, or one under an h5/h6 ring sub-heading cannot
# leak. Rows and caption within an armed table are parsed with the helpers below.
TEAMS_TOKEN_RE = re.compile(
    r"<(?P<htag>h[1-6])\b[^>]*>(?P<heading>.*?)</h[1-6]>"
    r"|<table\b[^>]*>(?P<table>.*?)</table>",
    re.I | re.S,
)
TEAMS_ROW_RE = re.compile(r"<tr\b[^>]*>(?P<row>.*?)</tr>", re.I | re.S)
TEAMS_CAPTION_RE = re.compile(r"<caption\b[^>]*>(?P<cap>.*?)</caption>", re.I | re.S)
# A platform / cloud / edition / release-ring label that means "this is NOT the tracked
# Public-cloud New-Teams Windows-stable identity". Used as a defence-in-depth check on an
# armed table's caption and on each row's normalised cell text (so an inline ring row inside
# the production table is dropped). Separators are a class and family suffixes are optional so
# "release-candidate", "Insiders", "Previews", "ReleaseCandidate", "RC", "TAP", "Dev/Nightly
# ring", etc. are all caught after tag/entity normalisation.
TEAMS_FOREIGN_SECTION_RE = re.compile(
    r"\b(?:mac(?:os)?|web|browser|vdi|mobile|ios|android|linux|"
    r"gcc|gcch|dod|government|gallatin|sovereign|classic|"
    r"preview(?:s)?|insider(?:s)?|beta(?:s)?|targeted|"
    r"release[\s._-]*candidate|test[\s._-]*build|pre[\s._-]*release|canary|"
    r"nightly|dev|tap|rc|early[\s._-]*access|ring)\b",
    re.I,
)

# --- App attribution (per-app release notes) ---------------------------------
# Microsoft 365 Apps release notes describe features/fixed issues per version. A change
# is attributed to a specific app ONLY when that app is named explicitly, or the entry is
# explicitly all-Office-apps. Generic suite channel/build rows are never attributed to an
# individual app (they stay on the Microsoft 365 Apps page).
OFFICE_APP_NAMES = (
    "powerpoint", "word", "excel", "outlook", "onenote",
    "access", "publisher", "visio", "project", "teams", "onedrive",
)
# Per-version section heading, e.g. "<h2>Version 2606 (Build 20131.20154)</h2>".
APP_VERSION_HEADING_RE = re.compile(
    r"<h[1-4]\b[^>]*>[^<]*?\bversion\s+(?P<ver>\d{3,4})\b[^<]*?</h[1-4]>", re.I
)
# "Build 20131.20154" inside a section (the precise identity; a bare marketing version is
# never enough on its own).
BUILD_IN_TEXT_RE = re.compile(r"build\s+(\d{3,6}\.\d{3,6})", re.I)
# Feature / fixed-issue blocks within a version section.
BLOCK_RE = re.compile(r"<(?:li|p)\b[^>]*>(?P<block>.*?)</(?:li|p)>", re.I | re.S)
# Explicit "applies to every Office app" phrasing -> a per-app record is allowed, with the
# suite id carried in the applicability list alongside the app id.
SUITEWIDE_APPLICABILITY_RE = re.compile(
    r"\b(all (microsoft 365 )?apps|all office apps|across (the )?(microsoft 365|office) apps"
    r"|every (microsoft 365|office) app|microsoft 365 apps suite)\b",
    re.I,
)


def _request_options(source: dict[str, Any]) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    request = ingestion.get("request", {}) or {}
    headers = request.get("headers") or {}
    return {
        "timeout": int(request.get("timeout_seconds") or 30),
        "retries": int(request.get("retries") or 1),
        "backoff_seconds": float(request.get("backoff_seconds") or 2.0),
        "max_bytes": int(request.get("max_bytes") or 900000),
        "headers": headers if isinstance(headers, dict) else {},
    }


def _source_candidates(source: dict[str, Any]) -> list[str]:
    ingestion = source.get("ingestion", {}) or {}
    clean: list[str] = []
    for url in (ingestion.get("official_url"), ingestion.get("secondary_official_url")):
        if isinstance(url, str) and url.strip() and url.strip() not in clean:
            clean.append(url.strip())
    return clean


def _iso_date(year: int, month: int, day: int) -> str:
    """ISO datetime string for a REAL calendar date, else "" — rejects impossible day/month
    combinations (e.g. day 40, February 30) instead of emitting a fabricated date."""
    try:
        return date(year, month, day).isoformat() + "T00:00:00Z"
    except ValueError:
        return ""


def _date_from_text(text: str) -> str:
    """Return an ISO date if the text contains a valid 'Month DD, YYYY' date, else "".

    Note: this deliberately returns "" (not normalize_date("")) on no match, because
    normalize_date defaults to now() — which would let a non-date table cell win the
    per-row date scan. An impossible day/month (e.g. "March 40, 2026") is also rejected.
    """
    match = DATE_RE.search(text or "")
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month:
            return _iso_date(int(match.group(3)), int(month), int(match.group(2)))
    return ""


def _release_date(section_text: str, version: str) -> str:
    """Official release date for a version section, fail-closed.

    Prefers a full 'Month DD, YYYY' date. Falls back to 'Month DD' plus the year DERIVED from
    the 4-digit YYMM version number, because the Current Channel page prints the per-version
    date without a year ("Version 2606: July 14"). A release month earlier than the version's
    own month means the calendar year rolled over (e.g. Version 2512 shipping in January).
    Returns "" (reject) when neither a full date nor a 'Month DD' + a 4-digit YYMM version can
    be established -- this never fabricates a date."""
    full = _date_from_text(section_text)
    if full:
        return full
    if not re.fullmatch(r"\d{4}", version or ""):
        return ""
    match = NO_YEAR_DATE_RE.search(section_text or "")
    if not match:
        return ""
    month = MONTHS.get(match.group(1).lower())
    if not month:
        return ""
    day = int(match.group(2))
    version_year, version_month = 2000 + int(version[:2]), int(version[2:])
    if not 1 <= version_month <= 12:
        return ""  # malformed YYMM version (no such month) -> cannot anchor the year
    year = version_year + 1 if int(month) < version_month else version_year
    return _iso_date(year, int(month), day)


def _row_cells(row_html: str) -> list[str]:
    return [re.sub(r"\s+", " ", strip_tags(c.group("cell"))).strip() for c in CELL_RE.finditer(row_html)]


def _record(
    source: dict[str, Any],
    source_url: str,
    channel: str,
    version: str,
    build: str,
    published: str,
) -> dict[str, Any]:
    digest = hashlib.sha256((source_url + version + build + channel).encode("utf-8")).hexdigest()[:16]
    ingestion = source.get("ingestion", {}) or {}
    version_label = f"Version {version} (Build {build})"
    date_str = published[:10] if published else ""
    software = source["software"]

    official_sources = []
    for label, url in (
        ("Microsoft 365 Apps update history", ingestion.get("official_url")),
        ("Microsoft 365 Apps release notes", ingestion.get("secondary_official_url")),
    ):
        if isinstance(url, str) and url.strip():
            official_sources.append({
                "label": label,
                "url": url.strip(),
                "source_type": "release_notes",
                "trust_level": "official",
                "extraction_status": "summary_captured" if url.strip() == source_url else "reference_only",
            })

    body = (
        f"{software} {version_label} on the {channel}."
        + (f" Latest release date {date_str}." if date_str else "")
        + " This is the official Microsoft 365 Apps update-history entry"
        " (learn.microsoft.com/officeupdates). Per-version security and feature update"
        " details are published in the Microsoft 365 Apps release notes."
    )
    official_summary = (
        f"Microsoft released {software} {version_label} on the {channel}"
        + (f" ({date_str})." if date_str else ".")
    )

    return {
        "record_id": f"microsoft:{source['product_id']}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": source["product_id"],
        "company": source["company"],
        "software": software,
        "category": source.get("public_category"),
        "version": version,
        "title": first_nonempty(f"{software} {version_label}", f"{software} Version {version}"),
        "published_at": published,
        "source_url": source_url,
        "official_url": source_url,
        "download_url": "",
        "file_size": "",
        "file_size_status": "not_provided_by_source",
        "file_size_note": (
            "Microsoft 365 Apps updates are Click-to-Run managed; the public update "
            "history does not expose standalone installer/package size metadata."
        ),
        "body": body,
        "checksums_body": "",
        "summary": "",
        "source_type": "release_notes",
        "official_source_type": "release_notes",
        "official_note_status": "release_notes_captured",
        "official_note_label": "Official update history",
        "official_sources": official_sources,
        "capture_status": "captured-from-official-microsoft365-update-history",
        "official_summary": official_summary,
    }


def _records_from_office_release_notes(
    source: dict[str, Any],
    source_url: str,
    html: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Pure parser (no network): update-history table rows -> official-only records.

    Returns [] when no conservative version+build row is found so a DOM change never
    yields a fabricated record.
    """
    html = html or ""
    ingestion = source.get("ingestion", {}) or {}
    target_channel = str(ingestion.get("channel") or DEFAULT_CHANNEL).strip().lower()

    records: list[dict[str, Any]] = []
    seen_versions: set[str] = set()

    for row in ROW_RE.finditer(html):
        cells = _row_cells(row.group("row"))
        if len(cells) < 4:
            continue

        channel = cells[0]
        lowered_channel = channel.lower()
        if lowered_channel != target_channel:
            continue
        if any(token in lowered_channel for token in EXCLUDE_CHANNEL_TOKENS):
            continue

        version = next((c for c in cells if VERSION_CELL_RE.fullmatch(c)), "")
        build = next((c for c in cells if BUILD_CELL_RE.fullmatch(c)), "")
        if not version or not build or version in seen_versions:
            continue

        published = ""
        for cell in cells:
            candidate = _date_from_text(cell)
            if candidate:
                published = candidate
                break

        seen_versions.add(version)
        records.append(_record(source, source_url, channel, version, build, published))
        if len(records) >= max(1, int(limit)):
            break

    return records


def _is_new_teams_windows_build(version: str) -> bool:
    """True only for a real new-Teams desktop build number: the first component is a YYDDD
    stamp (2-digit year + day-of-year 001-366), e.g. 26183 -> 2026, day 183. Rejects shape-only
    look-alikes such as a day-of-year of 000/400/999 that pass the digit-count regex."""
    first = version.split(".", 1)[0]
    if len(first) != 5:
        return False
    return 1 <= int(first[2:]) <= 366


def _teams_published(year: str, month_day: re.Match | None) -> str:
    """Combine the Teams table's split 'Release year' + 'Month DD' cells into a CALENDAR-
    VALIDATED ISO date, else "". Rejects an impossible day/month (e.g. February 30) instead of
    emitting a fabricated timestamp, and returns "" when either cell is missing (fail closed)."""
    if not year or month_day is None:
        return ""
    month = MONTHS.get(month_day.group(1).lower())
    if not month:
        return ""
    return _iso_date(int(year), int(month), int(month_day.group(2)))


def _teams_record(
    source: dict[str, Any],
    source_url: str,
    version: str,
    published: str,
) -> dict[str, Any]:
    digest = hashlib.sha256((source_url + version).encode("utf-8")).hexdigest()[:16]
    ingestion = source.get("ingestion", {}) or {}
    software = source["software"]
    date_str = published[:10] if published else ""

    official_sources = []
    for label, url in (
        ("Microsoft Teams version history", ingestion.get("official_url")),
        ("What's new in Microsoft Teams", ingestion.get("secondary_official_url")),
    ):
        if isinstance(url, str) and url.strip():
            official_sources.append({
                "label": label,
                "url": url.strip(),
                "source_type": "release_notes",
                "trust_level": "official",
                "extraction_status": "summary_captured" if url.strip() == source_url else "reference_only",
            })

    # Single, explicit, non-inferred identity (New Teams desktop, Windows, Public cloud).
    identity_label = "New Teams (Windows, Public cloud)"
    body = (
        f"{software} {identity_label} version {version}."
        + (f" Release date {date_str}." if date_str else "")
        + " This is the official Microsoft Teams version-history entry for the New Teams"
        " desktop client on Windows (Public cloud)"
        " (learn.microsoft.com/officeupdates/teams-app-versioning)."
    )
    official_summary = (
        f"Microsoft released {software} {identity_label} version {version}"
        + (f" ({date_str})." if date_str else ".")
    )

    return {
        "record_id": f"microsoft:{source['product_id']}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": source["product_id"],
        "company": source["company"],
        "software": software,
        "category": source.get("public_category"),
        "version": version,
        "title": first_nonempty(f"{software} {version}", software),
        "published_at": published,
        "source_url": source_url,
        "official_url": source_url,
        "download_url": "",
        "file_size": "",
        "file_size_status": "not_provided_by_source",
        "file_size_note": (
            "Microsoft Teams updates are Microsoft-managed (auto-update); the public version "
            "history does not expose standalone installer/package size metadata."
        ),
        "body": body,
        "checksums_body": "",
        "summary": "",
        "source_type": "release_notes",
        "official_source_type": "release_notes",
        "official_note_status": "release_notes_captured",
        "official_note_label": "Official version history",
        "official_sources": official_sources,
        "capture_status": "captured-from-official-microsoft-teams-version-history",
        "official_summary": official_summary,
        # Structured, non-inferred identity so a record never conflates platforms/clouds/editions.
        "teams_edition": "New Teams",
        "target_platform": "Windows",
        "target_channel": "Public cloud (Production)",
        "target_version": version,
        "applicability": [source["product_id"]],
    }


def _records_from_teams_version_history(
    source: dict[str, Any],
    source_url: str,
    html: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Pure parser (no network): Teams version-history -> official-only records for a SINGLE
    identity (New Teams desktop, Windows, Public cloud). Fail-closed and TABLE-ANCHORED.

    The page interleaves many distinct identities (cloud x New/Classic x platform), each its
    own <table>. Identity is NEVER inherited across a table boundary: a table's rows are parsed
    only when it sits directly under a freshly declared target heading chain
    (Public cloud -> New Teams app version -> Windows). Any other heading -- a different
    platform h4, a new h2/h3 section, or a sub-heading (h5/h6 such as "Insiders" / "Dev ring"),
    and every already-consumed table -- disarms, so a Mac / Web / VDI / Mobile / Government /
    Sovereign / Classic / preview table can never leak, even when its only marker is its own
    header row or when prose separates it from the Windows table. Within the armed Windows
    table a record is emitted only when the row establishes:

    - exactly one valid new-Teams Windows build (5-digit YYDDD; >1 -> ambiguous, skip);
    - a calendar-VALID release date from the split 'Release year' + 'Month DD' cells (the year
      carries forward across rowspan-grouped rows); undated / impossible-date rows are rejected;
    - no inline ring/platform marker (checked on the table caption and each row's cell text).

    A version that appears with more than one distinct release date fails visibly (dropped).
    Returns [] when no qualifying row matches.
    """
    html = html or ""
    cap = max(1, int(limit))
    h2 = h3 = h4 = ""
    armed = False                               # a fresh target <h4>Windows</h4> declared and
                                                # not yet consumed by a table
    order: list[str] = []                       # versions in page order (newest first)
    dates_by_version: dict[str, set[str]] = {}  # version -> distinct release dates seen

    def _identity_is_target() -> bool:
        return (h2 in TEAMS_CLOUD_HEADINGS
                and h3 == TEAMS_TYPE_HEADING
                and h4 == TEAMS_PLATFORM_HEADING)

    for match in TEAMS_TOKEN_RE.finditer(html):
        htag = match.group("htag")
        if htag is not None:
            text = re.sub(r"\s+", " ", strip_tags(match.group("heading"))).strip().lower()
            level = htag.lower()
            if level in ("h1", "h2"):
                h2, h3, h4 = (text if level == "h2" else ""), "", ""
            elif level == "h3":
                h3, h4 = text, ""
            elif level == "h4":
                h4 = text
            # A table is trusted ONLY directly under a fresh target <h4>Windows</h4>; any other
            # heading (incl. an h5/h6 ring sub-heading) disarms so nothing is inherited.
            armed = (level == "h4" and _identity_is_target())
            continue

        # A <table>...</table> unit.
        if not armed:
            continue
        armed = False  # identity is consumed by this table, never inherited by a later one
        table_html = match.group("table") or ""
        cap_m = TEAMS_CAPTION_RE.search(table_html)
        if cap_m and TEAMS_FOREIGN_SECTION_RE.search(
                re.sub(r"\s+", " ", strip_tags(cap_m.group("cap"))).strip().lower()):
            continue  # a foreign/ring table caption -> skip the whole table

        current_year = ""  # 'Release year' carried across rowspan-grouped rows within THIS table
        for row_match in TEAMS_ROW_RE.finditer(table_html):
            cells = _row_cells(row_match.group("row"))
            if not cells:
                continue
            # Update the carried year at the TOP of the row (a year-group header row updates it
            # before any early continue) so no build inherits a neighbouring year-group's year.
            row_year = next((c for c in cells if TEAMS_YEAR_RE.fullmatch(c)), "")
            if row_year:
                current_year = row_year
            joined = " ".join(cells).lower()
            if TEAMS_FOREIGN_SECTION_RE.search(joined):
                continue  # inline ring/platform marker in the row's own (normalised) text

            versions = {c for c in cells if TEAMS_VERSION_RE.fullmatch(c) and _is_new_teams_windows_build(c)}
            if len(versions) != 1:
                continue  # zero -> not a valid new-Teams Windows build; >1 -> ambiguous
            version = next(iter(versions))

            month_days = [m for c in cells for m in TEAMS_MONTH_DAY_RE.finditer(c)]
            distinct_md = {(m.group(1).lower(), m.group(2)) for m in month_days}
            if len(distinct_md) > 1:
                continue  # more than one distinct date in the row -> ambiguous, fail closed
            published = _teams_published(current_year, month_days[0] if month_days else None)
            if not published:
                continue  # fail closed: undated or impossible-date row is never emitted

            if version not in dates_by_version:
                order.append(version)
            dates_by_version.setdefault(version, set()).add(published)

    records: list[dict[str, Any]] = []
    for version in order:
        dates = dates_by_version[version]
        if len(dates) != 1:
            continue  # same version, conflicting release dates -> fail visibly (drop, don't guess)
        records.append(_teams_record(source, source_url, version, next(iter(dates))))
        if len(records) >= cap:
            break
    return records


def _target_app(source: dict[str, Any]) -> str:
    ingestion = source.get("ingestion", {}) or {}
    app = str(ingestion.get("target_app") or "").strip().lower()
    if app:
        return app
    # Fall back to the last product_id segment, e.g. microsoft-powerpoint -> powerpoint.
    return str(source.get("product_id") or "").split("-")[-1].strip().lower()


def _app_record(
    source: dict[str, Any],
    source_url: str,
    channel: str,
    version: str,
    build: str,
    published: str,
    target_app: str,
    entries: list[str],
    applies_suitewide: bool,
) -> dict[str, Any]:
    digest = hashlib.sha256((source_url + version + build + target_app).encode("utf-8")).hexdigest()[:16]
    ingestion = source.get("ingestion", {}) or {}
    software = source["software"]
    version_label = f"Version {version} (Build {build})"
    date_str = published[:10] if published else ""
    product_id = source["product_id"]

    # Explicit, auditable applicability. A suite-wide entry additionally lists the shared
    # servicing product so the common source identity is preserved (never blind duplication).
    applicability = [product_id]
    if applies_suitewide and "microsoft-365-apps" not in applicability:
        applicability.append("microsoft-365-apps")
    applies_to_label = software + (" + Microsoft 365 Apps (suite-wide)" if applies_suitewide else "")

    official_sources = []
    for label, url in (
        (f"{software} release notes", ingestion.get("official_url")),
        ("Microsoft 365 Apps update history", ingestion.get("secondary_official_url")),
    ):
        if isinstance(url, str) and url.strip():
            official_sources.append({
                "label": label,
                "url": url.strip(),
                "source_type": "release_notes",
                "trust_level": "official",
                "extraction_status": "summary_captured" if url.strip() == source_url else "reference_only",
            })

    joined = " ".join(entries)[:1200]
    scope = "an all-apps (suite-wide) change" if applies_suitewide else f"a {software}-specific change"
    body = (
        f"{software} {version_label} on the {channel}"
        + (f" (release date {date_str})." if date_str else ".")
        + f" Official Microsoft 365 Apps release notes attribute {scope} to this version"
        f" for {software}: {joined}"
    )
    official_summary = (
        f"Microsoft 365 Apps release notes attribute a {software} change to {version_label}"
        + (f" on the {channel} ({date_str})." if date_str else f" on the {channel}.")
    )

    return {
        "record_id": f"microsoft:{product_id}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": product_id,
        "company": source["company"],
        "software": software,
        "category": source.get("public_category"),
        "version": version,
        "title": first_nonempty(f"{software} {version_label}", f"{software} Version {version}"),
        "published_at": published,
        "source_url": source_url,
        "official_url": source_url,
        "download_url": "",
        "file_size": "",
        "file_size_status": "not_provided_by_source",
        "file_size_note": (
            "Microsoft 365 Apps updates are Click-to-Run managed; per-app release notes do "
            "not expose standalone installer/package size metadata."
        ),
        "body": body,
        "checksums_body": "",
        "summary": "",
        "source_type": "release_notes",
        "official_source_type": "release_notes",
        "official_note_status": "release_notes_captured",
        "official_note_label": f"Official {software} release notes",
        "official_sources": official_sources,
        "capture_status": "captured-from-official-microsoft365-app-release-notes",
        "official_summary": official_summary,
        # Structured, precise identity (never keyed by a vague marketing version alone).
        "target_channel": channel,
        "target_build": build,
        "target_app_version": version,
        # Explicit applicability list + label (auditable; suite-wide items carry the suite id).
        "applicability": applicability,
        "applies_to_label": applies_to_label,
    }


def _records_from_office_app_release_notes(
    source: dict[str, Any],
    source_url: str,
    html: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Pure parser (no network): Microsoft 365 Apps per-version release notes -> app-attributed
    official-only records.

    A version is turned into a record for the target app ONLY when a feature / fixed-issue
    block in that version's section explicitly names the app (word-boundary) or is explicitly
    all-Office-apps. Blocks that name only other apps, and generic channel/build rows with no
    app attribution, never produce a record for this app. Fail closed: a version whose exact
    version AND build cannot be established is skipped; returns [] on DOM-miss (never fabricates).
    """
    html = html or ""
    ingestion = source.get("ingestion", {}) or {}
    channel = str(ingestion.get("channel") or DEFAULT_CHANNEL).strip()
    target_app = _target_app(source)
    if not target_app:
        return []
    app_word = re.compile(rf"(?<![A-Za-z]){re.escape(target_app)}(?![A-Za-z])", re.I)

    heads = list(APP_VERSION_HEADING_RE.finditer(html))
    records: list[dict[str, Any]] = []
    seen_versions: set[str] = set()

    for i, match in enumerate(heads):
        version = match.group("ver")
        if not version or version in seen_versions:
            continue
        section = html[match.start(): heads[i + 1].start() if i + 1 < len(heads) else len(html)]

        build_match = BUILD_IN_TEXT_RE.search(section)
        build = build_match.group(1) if build_match else ""
        if not build:
            continue  # fail closed: require the precise build, not just a marketing version

        published = _release_date(re.sub(r"\s+", " ", strip_tags(section)), version)
        if not published:
            continue  # fail closed: require the official release date (every record must carry one)

        entries: list[str] = []
        applies_suitewide = False
        for block in BLOCK_RE.finditer(section):
            text = re.sub(r"\s+", " ", strip_tags(block.group("block"))).strip()
            if not text:
                continue
            if SUITEWIDE_APPLICABILITY_RE.search(text):
                entries.append(text)
                applies_suitewide = True
            elif app_word.search(text):
                entries.append(text)
            # Blocks that name only other Office apps (or no app) are not attributed here.

        if not entries:
            continue  # no explicit target-app / suite-wide attribution in this version

        seen_versions.add(version)
        records.append(
            _app_record(source, source_url, channel, version, build, published, target_app, entries, applies_suitewide)
        )
        if len(records) >= max(1, int(limit)):
            break

    return records


# parser_profile -> pure parser. The M365 Apps / generic profiles use the suite update-history
# table parser; the PowerPoint (per-app) profile uses the app-attribution release-notes parser;
# Teams uses the version-history table parser. Unknown profiles are not dispatched (fetch returns []).
_PROFILE_PARSERS = {
    "microsoft_365_apps_update_history": _records_from_office_release_notes,
    "microsoft_365_powerpoint_release_notes": _records_from_office_app_release_notes,
    "microsoft_office_app_release_notes": _records_from_office_app_release_notes,
    "microsoft_office_release_notes": _records_from_office_release_notes,
    "generic": _records_from_office_release_notes,
    "": _records_from_office_release_notes,
    "microsoft_teams_version_history": _records_from_teams_version_history,
}


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    ingestion = source.get("ingestion", {}) or {}
    profile = str(ingestion.get("parser_profile") or "").strip()
    parser = _PROFILE_PARSERS.get(profile)
    if parser is None:
        # Unsupported parser_profile (e.g. a future lane not yet implemented).
        return []

    options = _request_options(source)
    candidates = _source_candidates(source)
    fetch_errors: list[str] = []

    for url in candidates:
        try:
            result = fetch_text(url, **options)
        except Exception as exc:  # noqa: BLE001 - surface transport failures below
            fetch_errors.append(f"{url}: {exc}")
            continue
        html = result.text or ""
        if not html.strip():
            fetch_errors.append(f"{url}: empty response")
            continue
        records = parser(source, result.final_url or url, html, limit)
        if records:
            return records
        # Fetched OK but no version row matched: try the next official URL rather than
        # emitting a snapshot/bad record.

    # Every candidate URL failed to fetch -> surface as a transport error so source
    # health reflects it. Fetched-but-unparseable pages return [] (graceful).
    if candidates and len(fetch_errors) == len(candidates):
        raise RuntimeError("; ".join(fetch_errors[-2:]) or "microsoft office updates fetch failed")
    return []
