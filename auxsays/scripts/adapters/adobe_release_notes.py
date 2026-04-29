"""Dedicated Adobe release-notes adapter.

Adobe HelpX pages are slower and more brittle from GitHub Actions than the
other currently enabled sources. This adapter keeps Adobe handling explicit so
we can tune it without making the generic HTML changelog adapter slower or more
fragile.

Current operating rule:
- Premiere Pro is the active Adobe test lane.
- Other Adobe products can stay visible on the site while their ingestion rows
  remain staged until the dedicated adapter proves reliable.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from lib.http import fetch_text
from lib.normalize import strip_tags, normalize_date, first_nonempty

VERSION_HEADING_RE = re.compile(
    r"<h(?P<level>[2-4])\b[^>]*>(?P<title>.*?(?:version|v)\s*[0-9]+(?:\.[0-9]+){0,3}.*?)</h(?P=level)>",
    re.I | re.S,
)
VERSION_RE = re.compile(r"(?:version|v)\s*([0-9]+(?:\.[0-9]+){0,3})", re.I)
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
        # Keep Adobe bounded. Longer timeouts already proved expensive without
        # solving HelpX fetch stability in Actions.
        "timeout": int(request.get("timeout_seconds") or 30),
        "retries": int(request.get("retries") or 1),
        "backoff_seconds": float(request.get("backoff_seconds") or 2.5),
        "max_bytes": int(request.get("max_bytes") or 750000),
        "headers": headers if isinstance(headers, dict) else {},
    }


def _month_year_to_date(text: str) -> str:
    match = MONTH_RE.search(text or "")
    if not match:
        return normalize_date("")
    return f"{match.group(2)}-{MONTHS.get(match.group(1).lower(), '01')}-01T00:00:00Z"


def _version_from_title(title: str) -> str:
    match = VERSION_RE.search(title or "")
    return match.group(1).strip() if match else first_nonempty(title, "official-update")


def _clean_body(title: str, section_html: str) -> str:
    text = strip_tags(f"{title}\n\n{section_html}")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:7000]


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    ingestion = source.get("ingestion", {}) or {}
    source_url = ingestion.get("official_url")
    if not source_url:
        raise RuntimeError(f"{source.get('product_id', 'adobe-source')} is missing ingestion.official_url")

    result = fetch_text(source_url, **_request_options(source))
    html = result.text
    matches = list(VERSION_HEADING_RE.finditer(html))
    records: list[dict[str, Any]] = []

    for idx, match in enumerate(matches):
        title = strip_tags(match.group("title"))
        lowered = title.lower()
        if not title or "version" not in lowered:
            continue
        # Avoid mobile/beta sections unless that product lane is explicitly added later.
        if any(token in lowered for token in ["beta", "mobile", "ios", "android"]):
            continue

        section_start = match.end()
        section_end = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(html), section_start + 14000)
        body = _clean_body(title, html[section_start:section_end])
        version = _version_from_title(title)
        published = _month_year_to_date(title)
        digest = hashlib.sha256((source_url + version + title).encode("utf-8")).hexdigest()[:16]
        records.append({
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
            "file_size_note": "Adobe public release notes do not expose installer/package size metadata.",
            "body": body or title,
            "checksums_body": "",
            "summary": "",
            "source_type": "adobe-release-notes",
            "capture_status": "captured-from-official-adobe-release-notes",
            "official_summary": f"Adobe published {source['software']} {version} release notes.",
        })
        if len(records) >= limit:
            break

    return records
