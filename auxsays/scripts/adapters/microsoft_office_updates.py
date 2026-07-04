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
- parser_profile dispatch keeps this file reusable: future Office lanes (e.g.
  Microsoft Teams version history) can be added as a new branch without a new file.
  Only the Microsoft 365 Apps / PowerPoint release profiles are implemented in this
  sprint; other profiles return [].
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from lib.http import fetch_text
from lib.normalize import strip_tags, first_nonempty

ROW_RE = re.compile(r"<tr\b[^>]*>(?P<row>.*?)</tr>", re.I | re.S)
CELL_RE = re.compile(r"<t[dh]\b[^>]*>(?P<cell>.*?)</t[dh]>", re.I | re.S)
VERSION_CELL_RE = re.compile(r"\d{3,4}")
BUILD_CELL_RE = re.compile(r"\d{3,6}\.\d{3,6}")
DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(20\d{2})",
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

# parser_profiles this adapter can parse today (Office update-history family).
SUPPORTED_PROFILES = {
    "microsoft_365_apps_update_history",
    "microsoft_365_powerpoint_release_notes",
    "microsoft_office_release_notes",
    "generic",
    "",
}


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


def _date_from_text(text: str) -> str:
    """Return an ISO date if the text contains a 'Month DD, YYYY' date, else "".

    Note: this deliberately returns "" (not normalize_date("")) on no match, because
    normalize_date defaults to now() — which would let a non-date table cell win the
    per-row date scan.
    """
    match = DATE_RE.search(text or "")
    if match:
        month = MONTHS.get(match.group(1).lower(), "01")
        day = int(match.group(2))
        return f"{match.group(3)}-{month}-{day:02d}T00:00:00Z"
    return ""


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


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    ingestion = source.get("ingestion", {}) or {}
    profile = str(ingestion.get("parser_profile") or "").strip()
    if profile not in SUPPORTED_PROFILES:
        # Reserved for future Office lanes (e.g. microsoft_teams_version_history).
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
        records = _records_from_office_release_notes(source, result.final_url or url, html, limit)
        if records:
            return records
        # Fetched successfully but no conservative version row matched: try the next
        # official URL rather than emitting a snapshot/bad record.

    # Every candidate URL failed to fetch -> surface as a transport error so source
    # health reflects it. Fetched-but-unparseable pages return [] (graceful).
    if candidates and len(fetch_errors) == len(candidates):
        raise RuntimeError("; ".join(fetch_errors[-2:]) or "microsoft office updates fetch failed")
    return []
