"""Shared Adobe Acrobat (Reader + Acrobat Pro) official release-notes adapter.

One config-driven adapter serves BOTH product identities (`adobe-acrobat-reader` and
`adobe-acrobat-pro`). Adobe Acrobat DC releases are versioned per DC track
(Continuous / Classic) and, by default, ship at the same DC version for both Acrobat
Reader and Acrobat (Pro). Attribution is therefore data-driven, not inferred:

- A release generates a record for a product ONLY when the source establishes that the
  release applies to that product. Default DC applicability is both Reader and Pro; an
  explicit "Reader only" / "Acrobat only" restriction in the release text narrows it.
  Reader-only and Pro-only notes never cross-contaminate.
- Continuous and Classic tracks are kept distinct; Windows and macOS are kept distinct.
- Fail closed: a release whose track, version, or release date cannot be established is
  skipped. A security advisory (APSB…) becomes a patch record ONLY when a concrete release
  identity (track + version + date) is established for it; a bare advisory number is stored
  as official security context, never inferred into a patch record on its own.
- Official ingestion only: never emits consensus/report fields, so write_update_record
  derives evidence_state=official_only.

The adapter exposes the standard `fetch(source, limit)` contract. Because the two product
sources point at the same official URL, the fetched HTML is memoized per-URL for the
lifetime of the process so a run never double-fetches the (slow) Adobe pages.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from lib.http import fetch_text
from lib.normalize import strip_tags, first_nonempty

# DC versions look like 24.005.20320 (Continuous) or 20.005.30748 (Classic 2020).
ACROBAT_VERSION_RE = re.compile(r"\b(\d{2}\.\d{3}\.\d{4,6})\b")
TRACK_RE = re.compile(r"\b(Continuous|Classic)\b", re.I)
PLATFORM_WIN_RE = re.compile(r"\b(Windows|Win32|Win64)\b", re.I)
PLATFORM_MAC_RE = re.compile(r"\b(macOS|Mac ?OS|Macintosh)\b", re.I)
APSB_RE = re.compile(r"\bAPSB\d{2}-\d{2,3}\b", re.I)
DATE_MONTH_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(20\d{2})",
    re.I,
)
DATE_ISO_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
}
# Headings (set the current track/platform section) or table rows / list items (a release).
SECTION_TOKEN_RE = re.compile(
    r"<h[1-6]\b[^>]*>(?P<heading>.*?)</h[1-6]>"
    r"|<tr\b[^>]*>(?P<row>.*?)</tr>"
    r"|<li\b[^>]*>(?P<li>.*?)</li>",
    re.I | re.S,
)

READER_ID = "adobe-acrobat-reader"
PRO_ID = "adobe-acrobat-pro"
DEFAULT_APPLICABILITY = (READER_ID, PRO_ID)
_PRODUCT_LABELS = {READER_ID: "Adobe Acrobat Reader", PRO_ID: "Adobe Acrobat Pro"}

# Process-lifetime fetch cache so the Reader and Pro sources (same URL) fetch once.
_FETCH_CACHE: dict[str, str] = {}


def _request_options(source: dict[str, Any]) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    request = ingestion.get("request", {}) or {}
    headers = request.get("headers") or {}
    return {
        "timeout": int(request.get("timeout_seconds") or 40),
        "retries": int(request.get("retries") or 2),
        "backoff_seconds": float(request.get("backoff_seconds") or 3.0),
        "max_bytes": int(request.get("max_bytes") or 1_500_000),
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
    match = DATE_MONTH_RE.search(text or "")
    if match:
        month = MONTHS.get(match.group(1).lower(), "01")
        return f"{match.group(3)}-{month}-{int(match.group(2)):02d}T00:00:00Z"
    iso = DATE_ISO_RE.search(text or "")
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}T00:00:00Z"
    return ""


def _platforms(text: str) -> str:
    win = bool(PLATFORM_WIN_RE.search(text))
    mac = bool(PLATFORM_MAC_RE.search(text))
    if win and not mac:
        return "Windows"
    if mac and not win:
        return "macOS"
    # DC releases target both desktop platforms unless the notes restrict to one.
    return "Windows, macOS"


def _applicability_for(text: str, configured: list[str]) -> list[str]:
    """Explicit, non-inferred applicability. Start from the configured/default set, then
    narrow only on an explicit single-product restriction in the release text."""
    base = [p for p in (configured or list(DEFAULT_APPLICABILITY)) if p in DEFAULT_APPLICABILITY]
    if not base:
        base = list(DEFAULT_APPLICABILITY)
    lowered = text.lower()
    reader_only = ("reader only" in lowered) or ("reader-only" in lowered)
    pro_only = ("acrobat only" in lowered or "acrobat pro only" in lowered
                or "acrobat-only" in lowered or "pro only" in lowered)
    if reader_only and not pro_only:
        return [READER_ID]
    if pro_only and not reader_only:
        return [PRO_ID]
    return base


def _record(
    source: dict[str, Any],
    source_url: str,
    product_id: str,
    version: str,
    track: str,
    platform: str,
    published: str,
    applicability: list[str],
    security_bulletin_id: str,
    security: bool,
) -> dict[str, Any]:
    software = _PRODUCT_LABELS.get(product_id, source.get("software") or "Adobe Acrobat")
    ingestion = source.get("ingestion", {}) or {}
    digest = hashlib.sha256(
        (source_url + product_id + version + track + platform).encode("utf-8")
    ).hexdigest()[:16]
    date_str = published[:10] if published else ""
    track_label = track.title()

    official_sources = []
    for label, url in (
        ("Adobe Acrobat release notes", ingestion.get("official_url")),
        ("Adobe Acrobat security bulletins", ingestion.get("secondary_official_url")),
    ):
        if isinstance(url, str) and url.strip():
            official_sources.append({
                "label": label,
                "url": url.strip(),
                "source_type": "security_advisory" if "security" in label.lower() else "release_notes",
                "trust_level": "official",
                "extraction_status": "summary_captured" if url.strip() == source_url else "reference_only",
            })

    applies_to_label = " + ".join(_PRODUCT_LABELS.get(p, p) for p in applicability)
    bulletin_clause = f" Security bulletin {security_bulletin_id}." if security_bulletin_id else ""
    body = (
        f"{software} {version} ({track_label} track, {platform})."
        + (f" Release date {date_str}." if date_str else "")
        + bulletin_clause
        + f" Official Adobe Acrobat release note; applies to {applies_to_label}."
    )
    official_summary = (
        f"Adobe released {software} {version} on the {track_label} track ({platform})"
        + (f" ({date_str})." if date_str else ".")
        + bulletin_clause
    )

    official_source_type = "security_advisory" if security and security_bulletin_id else "release_notes"

    record: dict[str, Any] = {
        "record_id": f"adobe:{product_id}:{track.lower()}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": product_id,
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
            "Adobe Acrobat updates are Adobe-managed (Creative Cloud / enterprise deployment); "
            "the release notes do not expose standalone installer/package size metadata."
        ),
        "body": body,
        "checksums_body": "",
        "summary": "",
        "source_type": official_source_type,
        "official_source_type": official_source_type,
        "official_note_status": "security_advisory_captured" if official_source_type == "security_advisory" else "release_notes_captured",
        "official_note_label": "Official Acrobat security advisory" if official_source_type == "security_advisory" else "Official Acrobat release notes",
        "official_sources": official_sources,
        "capture_status": "captured-from-official-adobe-acrobat-release-notes",
        "official_summary": official_summary,
        # Structured, non-inferred identity.
        "target_track": track_label,
        "target_platform": platform,
        "target_version": version,
        "applicability": applicability,
        "applies_to_label": applies_to_label,
    }
    if security_bulletin_id:
        record["security_bulletin_id"] = security_bulletin_id
    return record


def _records_from_acrobat_release_notes(
    source: dict[str, Any],
    source_url: str,
    html: str,
    limit: int,
    product_id: str,
) -> list[dict[str, Any]]:
    """Pure parser (no network): Adobe Acrobat DC release notes -> official-only records for
    ``product_id``. Only releases whose track + version + date are established, and whose
    applicability includes ``product_id``, are emitted. Returns [] on DOM-miss (no fabrication)."""
    html = html or ""
    ingestion = source.get("ingestion", {}) or {}
    configured = ingestion.get("applicability")
    configured = configured if isinstance(configured, list) else None

    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    current_track = ""
    current_platform = ""

    for token in SECTION_TOKEN_RE.finditer(html):
        heading = token.group("heading")
        if heading is not None:
            htext = re.sub(r"\s+", " ", strip_tags(heading)).strip()
            tmatch = TRACK_RE.search(htext)
            if tmatch:
                current_track = tmatch.group(1)
            if PLATFORM_WIN_RE.search(htext) or PLATFORM_MAC_RE.search(htext):
                current_platform = _platforms(htext)
            continue

        block = token.group("row") or token.group("li") or ""
        text = re.sub(r"\s+", " ", strip_tags(block)).strip()
        if not text:
            continue
        vmatch = ACROBAT_VERSION_RE.search(text)
        if not vmatch:
            continue
        version = vmatch.group(1)

        track = (TRACK_RE.search(text).group(1) if TRACK_RE.search(text) else current_track)
        published = _date_from_text(text)
        # Fail closed: a release must establish track, version, and release date.
        if not track or not version or not published:
            continue

        key = (track.lower(), version)
        if key in seen:
            continue

        platform = _platforms(text) if (PLATFORM_WIN_RE.search(text) or PLATFORM_MAC_RE.search(text)) else (current_platform or "Windows, macOS")
        applicability = _applicability_for(text, configured)
        if product_id not in applicability:
            continue  # this release does not apply to the product this source drives

        apsb = APSB_RE.search(text)
        bulletin = apsb.group(0).upper() if apsb else ""
        security = bool(bulletin) or ("security" in text.lower())
        # Constraint: a security advisory becomes a record only with full release identity
        # (track+version+date already required above); a bare advisory number never does.

        seen.add(key)
        records.append(
            _record(source, source_url, product_id, version, track, platform, published,
                    applicability, bulletin, security)
        )
        if len(records) >= max(1, int(limit)):
            break

    return records


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    product_id = str(source.get("product_id") or "").strip()
    if product_id not in DEFAULT_APPLICABILITY:
        return []
    options = _request_options(source)
    candidates = _source_candidates(source)
    fetch_errors: list[str] = []

    for url in candidates:
        html = _FETCH_CACHE.get(url)
        final_url = url
        if html is None:
            try:
                result = fetch_text(url, **options)
            except Exception as exc:  # noqa: BLE001 - surface transport failures below
                fetch_errors.append(f"{url}: {exc}")
                continue
            html = result.text or ""
            final_url = result.final_url or url
            if not html.strip():
                fetch_errors.append(f"{url}: empty response")
                continue
            _FETCH_CACHE[url] = html
        records = _records_from_acrobat_release_notes(source, final_url, html, limit, product_id)
        if records:
            return records
        # Fetched OK but nothing parsed for this product: try the next official URL.

    # Every candidate failed transport -> raise so source health reflects it. A fetched-but-
    # unparseable page (or a page with no records for this product) returns [] (graceful).
    if candidates and len(fetch_errors) == len(candidates):
        raise RuntimeError("; ".join(fetch_errors[-2:]) or "adobe acrobat fetch failed")
    return []
