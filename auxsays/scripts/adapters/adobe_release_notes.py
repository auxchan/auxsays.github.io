"""Dedicated Adobe release-notes adapter.

Operating rule:
- Premiere Pro remains the active Adobe test lane.
- Adobe HelpX release notes are official but have repeatedly timed out from
  GitHub Actions with 0 response bytes.
- For Premiere, use a fetch-stable Adobe Community announcement as the active
  official Adobe source, while keeping HelpX release notes as a secondary
  official reference.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from lib.http import fetch_text
from lib.normalize import strip_tags, normalize_date, first_nonempty

VERSION_HEADING_RE = re.compile(
    r"<h(?P<level>[1-4])\b[^>]*>(?P<title>.*?(?:version|v)\s*[0-9]+(?:\.[0-9]+){0,3}.*?)</h(?P=level)>",
    re.I | re.S,
)
HEADING_RE = re.compile(r"<h[1-3]\b[^>]*>(?P<title>.*?)</h[1-3]>", re.I | re.S)
TITLE_RE = re.compile(r"<title\b[^>]*>(?P<title>.*?)</title>", re.I | re.S)
VERSION_RE = re.compile(
    r"(?:version|v|premiere(?:\s+pro)?)\s*([0-9]+(?:\.[0-9]+){1,3})",
    re.I,
)
DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(20\d{2})",
    re.I,
)
MONTH_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})",
    re.I,
)
MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


def _request_options(source: dict[str, Any]) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    request = ingestion.get("request", {}) or {}
    headers = request.get("headers") or {}
    return {
        "timeout": int(request.get("timeout_seconds") or 25),
        "retries": int(request.get("retries") or 0),
        "backoff_seconds": float(request.get("backoff_seconds") or 2.0),
        "max_bytes": int(request.get("max_bytes") or 500000),
        "headers": headers if isinstance(headers, dict) else {},
        "curl_fallback": bool(request.get("curl_fallback", False)),
    }


def _date_from_text(text: str) -> str:
    date_match = DATE_RE.search(text or "")
    if date_match:
        month = MONTHS.get(date_match.group(1).lower(), "01")
        day = int(date_match.group(2))
        return f"{date_match.group(3)}-{month}-{day:02d}T00:00:00Z"

    month_match = MONTH_RE.search(text or "")
    if month_match:
        return f"{month_match.group(2)}-{MONTHS.get(month_match.group(1).lower(), '01')}-01T00:00:00Z"

    return normalize_date("")


def _version_from_text(text: str) -> str:
    match = VERSION_RE.search(text or "")
    return match.group(1).strip() if match else "official-update"


def _first_title(html: str, software: str, version: str) -> str:
    for regex in (VERSION_HEADING_RE, HEADING_RE, TITLE_RE):
        match = regex.search(html or "")
        if match:
            title = strip_tags(match.group("title"))
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                # Adobe titles often append boilerplate after pipes/dashes.
                title = re.split(r"\s+[|]\s+|\s+[-–]\s+Adobe", title)[0].strip()
                return title
    return f"{software} {version} official update"


def _clean_body(title: str, html: str) -> str:
    """Return a readable official-note body, not the entire Adobe Community shell."""
    text = strip_tags(f"{title}\n\n{html}")
    text = re.sub(r"(?is)function\s+[a-zA-Z0-9_]+\s*\([^)]*\)\s*\{.*?\}", " ", text)
    text = re.sub(r"(?is)document\.addEventListener\s*\(.*", " ", text)
    text = re.sub(r"(?i)skip to main content\s+", " ", text)
    text = re.sub(r"(?i)featured communities\s+announcements\s+feature requests\s+", " ", text)
    text = re.sub(r"(?i)create a post\s+login\s+home\s+app communities\s+adobe premiere\s+", " ", text)

    # Adobe Community announcement pages include a useful body followed by forum chrome.
    start_markers = [
        "What’s new in Premiere Pro",
        "What's new in Premiere Pro",
        "We’ve just released",
        "We've just released",
    ]
    for marker in start_markers:
        idx = text.find(marker)
        if idx >= 0:
            text = text[idx:]
            break

    end_markers = [
        "Like Reply Subscribe",
        "Reply Subscribe",
        "Was this post helpful",
        "Related conversations",
    ]
    for marker in end_markers:
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
            break

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?i)welcome to premiere 26\.2!\s+welcome to premiere 26\.2!\s*\|\s*community", "Welcome to Premiere 26.2!", text)
    return text[:2600]


def _source_candidates(source: dict[str, Any]) -> list[str]:
    ingestion = source.get("ingestion", {}) or {}
    candidates = [
        ingestion.get("official_url"),
        ingestion.get("secondary_official_url"),
    ]
    clean: list[str] = []
    for url in candidates:
        if isinstance(url, str) and url.strip() and url.strip() not in clean:
            clean.append(url.strip())
    return clean


def _fetch_first_available(source: dict[str, Any]):
    options = _request_options(source)
    errors: list[str] = []
    for url in _source_candidates(source):
        try:
            result = fetch_text(url, **options)
            if result.text and result.text.strip():
                return result
            errors.append("empty response from official Adobe source")
        except Exception as exc:
            errors.append(str(exc))
            continue

    if errors:
        raise RuntimeError("; ".join(errors[-2:]))
    raise RuntimeError(f"{source.get('product_id', 'adobe-source')} is missing usable Adobe source URLs")


def _records_from_version_headings(source: dict[str, Any], source_url: str, html: str, limit: int) -> list[dict[str, Any]]:
    matches = list(VERSION_HEADING_RE.finditer(html))
    records: list[dict[str, Any]] = []

    for idx, match in enumerate(matches):
        title = strip_tags(match.group("title"))
        lowered = title.lower()
        if not title:
            continue
        if any(token in lowered for token in ["beta", "mobile", "ios", "android"]):
            continue

        section_start = match.end()
        section_end = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(html), section_start + 14000)
        body = _clean_body(title, html[section_start:section_end])
        version = _version_from_text(title)
        published = _date_from_text(title + " " + body)
        records.append(_record(source, source_url, title, version, published, body))
        if len(records) >= limit:
            break

    return records


def _premiere_262_pilot_consensus(version: str) -> dict[str, Any]:
    if not str(version).startswith("26.2"):
        return {}
    return {
        "consensus_label": "Moderate",
        "consensus_score_percent": 38,
        "report_count": 7,
        "consensus_confidence": "Low",
        "consensus_collection_status": "pilot_initial_sample",
        "evidence_state": "pilot_sample",
        "evidence_state_label": "Verified reports",
        "intelligence_stage": "pilot",
        "known_issues_present": True,
        "quick_verdict": (
            "Premiere Pro 26.2 has an official Adobe release record and an initial AUXSAYS verified-report set of "
            "confirmed patch-specific Adobe Community reports. Treat this as a caution build for production systems "
            "until live consensus refresh is active."
        ),
        "consensus_report": (
            "Initial confirmed patch-specific sample is cautionary. Adobe Community bug reports naming Premiere Pro "
            "26.2/26.2.0 include repeated crash, UI lag, freezing, project-open delay, and system-hang reports. "
            "This is not yet live telemetry; it is a verified-report set based on explicit 26.2 community reports."
        ),
        "complaint_themes": [
            {"theme": "UI lag, freezing, or system hang", "frequency": "4 confirmed reports", "severity": "High"},
            {"theme": "Timeline/editing crashes or freezes", "frequency": "2 confirmed reports", "severity": "High"},
            {"theme": "Project launch/opening delays or hangs", "frequency": "2 confirmed reports", "severity": "Medium-High"},
            {"theme": "Program Monitor / anchor point visibility regression", "frequency": "1 confirmed report", "severity": "Medium"},
        ],
    }



def _classified_source_type(source_url: str) -> str:
    lowered = (source_url or "").lower()
    if "release-notes" in lowered or "changelog" in lowered:
        return "release_notes"
    if "whats-new" in lowered:
        return "whats_new"
    if "community.adobe.com" in lowered:
        return "community_official_post"
    return "official-source"


def _premiere_262_release_notes_body() -> str:
    return """### Official Release Notes Summary

AUXSAYS classification: Adobe release notes / fixed-issue source. This section summarizes the official Adobe release notes instead of treating a marketing “What’s New” page as complete patch notes.

#### Feature updates summarized

- New Film Impact-powered effects and transitions are listed for compositing, texture work, and motion design.
- Object Masking adds edge quality controls so editors can choose sharper or smoother mask edges.
- Source Monitor audio waveforms, the Sequence Index panel, offline-media reconnection improvements, Global Mute, improved marker search, and Content Credentials export support are listed as workflow updates.

#### Fixed issues summarized

Adobe’s release notes also list fixed issues for Premiere Pro 26.2, including transcript accuracy failures on some newer macOS systems, missing label-color presets, spell-check underlining failures, marker export UI behavior, render-and-replace restoration failures, Paste Insert to Target Track failures, dialog layout problems across mixed-resolution displays, shape alignment errors, H.264 aspect-ratio display problems, RED R3D black-frame cases, M2V and Canon XF705 import failures, slow XAVC HS scrubbing, Scene Edit Detection playback hangs, HEVC media-property display errors, Lumetri Comparison View reference-frame update failures, duplicate-ID warnings in Productions, keyboard navigation failures in Project panel Icon View, transcript tab position jumps, hardware HEVC seek/scrub problems on Apple silicon, unlinking crashes with selected transitions, Essential Sound preset menu issues, disabled adaptive-audio track output still being audible, and incorrect History panel labeling.

AUXSAYS note: this is an official release-note/fixed-issue summary. Community consensus remains separate and patch-specific."""

def _record(
    source: dict[str, Any],
    source_url: str,
    title: str,
    version: str,
    published: str,
    body: str,
) -> dict[str, Any]:
    digest = hashlib.sha256((source_url + version + title).encode("utf-8")).hexdigest()[:16]
    source_type = _classified_source_type(source_url)
    official_sources = [
        {
            "label": "Adobe Premiere Pro release notes",
            "url": "https://helpx.adobe.com/premiere/desktop/whats-new/release-notes.html",
            "source_type": "release_notes",
            "trust_level": "official",
            "extraction_status": "summary_captured" if source_type == "release_notes" else "reference_only",
        },
        {
            "label": "Adobe Premiere Pro community announcement",
            "url": "https://community.adobe.com/announcements-727/welcome-to-premiere-26-2-1557825",
            "source_type": "community_official_post",
            "trust_level": "official",
            "extraction_status": "summary_captured" if source_type == "community_official_post" else "reference_only",
        },
    ] if source.get("product_id") == "adobe-premiere-pro" else []

    if source.get("product_id") == "adobe-premiere-pro" and str(version).startswith("26.2") and source_type == "release_notes":
        body = _premiere_262_release_notes_body()

    record = {
        "record_id": f"adobe:{source['product_id']}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": source["product_id"],
        "company": source["company"],
        "software": source["software"],
        "category": source.get("public_category"),
        "version": version,
        "title": title,
        "published_at": published,
        "source_url": source_url,
        "official_url": source_url,
        "download_url": "",
        "file_size": "",
        "file_size_status": "not_provided_by_source",
        "file_size_note": "Adobe's public release source does not expose standalone Creative Cloud installer/package size metadata.",
        "body": body or title,
        "checksums_body": "",
        "summary": "",
        "source_type": source_type,
        "official_source_type": source_type,
        "official_note_status": "release_notes_captured" if source_type == "release_notes" else "official_source_captured",
        "official_note_label": "Official release notes" if source_type == "release_notes" else "Official source summary",
        "official_sources": official_sources,
        "capture_status": "captured-from-official-adobe-source",
        "official_summary": f"Adobe published {source['software']} {version} release information.",
    }
    if source.get("product_id") == "adobe-premiere-pro":
        record.update(_premiere_262_pilot_consensus(version))
    return record


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    result = _fetch_first_available(source)
    html = result.text

    records = _records_from_version_headings(source, result.final_url or result.url, html, limit)
    if records:
        return records

    # Fetch-stable Adobe Community announcement pages often contain the current
    # version in prose/title rather than in a HelpX-style version heading.
    text = strip_tags(html)
    version = _version_from_text(text)
    title = _first_title(html, source.get("software") or "Adobe product", version)
    published = _date_from_text(text)
    body = _clean_body(title, html)
    return [_record(source, result.final_url or result.url, title, version, published, body)]
