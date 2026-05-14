"""Blackmagic Design support-download official update adapter.

This adapter uses Blackmagic's public support downloads JSON model instead of
scraping the JavaScript-rendered support UI. It captures official version
availability from a durable vendor endpoint and leaves community risk evidence
to the shared evidence collection pipeline.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from typing import Any

from lib.http import USER_AGENT
from lib.normalize import first_nonempty
from lib.normalize_davinci_version import normalize_davinci_version

DEFAULT_DOWNLOAD_URL = "https://www.blackmagicdesign.com/event/davinciresolvedownload"
DEFAULT_SUPPORT_URL = "https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion"


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    ingestion = source.get("ingestion", {}) or {}
    api_url = ingestion.get("api_url") or "https://www.blackmagicdesign.com/api/support/us/downloads.json"
    include_prereleases = bool(ingestion.get("include_prereleases"))
    records: list[dict[str, Any]] = []
    seen_versions: set[str] = set()

    payload = _fetch_json(api_url, timeout=int((ingestion.get("request") or {}).get("timeout_seconds") or 30))
    downloads = payload.get("downloads") if isinstance(payload, dict) else []
    if not isinstance(downloads, list):
        raise ValueError("Blackmagic downloads payload is missing a downloads list")

    for item in sorted(downloads, key=_sort_key, reverse=True):
        if not _is_davinci_resolve_download(item):
            continue
        normalized = _normalized_version(item)
        if normalized.get("rejected"):
            continue
        if normalized.get("is_beta") and not include_prereleases:
            continue
        version = str(normalized.get("canonical_update_version") or "").strip()
        if not version or version in seen_versions:
            continue
        seen_versions.add(version)
        records.append(_record_from_download(source, item, version, normalized, api_url))
        if len(records) >= limit:
            break
    return records


def _fetch_json(url: str, *, timeout: int) -> Any:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain;q=0.8, */*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return json.loads(raw.decode(charset, errors="replace"))


def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
    numeric = item.get("numericDate")
    try:
        numeric_date = int(numeric or 0)
    except (TypeError, ValueError):
        numeric_date = 0
    return (numeric_date, str(item.get("name") or ""))


def _is_davinci_resolve_download(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    if "davinci-resolve-and-fusion" not in (item.get("relatedFamilies") or []):
        return False
    haystack = " ".join([
        str(item.get("name") or ""),
        str(item.get("releaseNotesTitle") or ""),
        _download_titles(item),
    ]).lower()
    if "fusion studio" in haystack or "fairlight live" in haystack:
        return False
    return "davinci resolve" in haystack


def _download_titles(item: dict[str, Any]) -> str:
    titles: list[str] = []
    urls = item.get("urls") or {}
    if isinstance(urls, dict):
        for platform_downloads in urls.values():
            if not isinstance(platform_downloads, list):
                continue
            for download in platform_downloads:
                if isinstance(download, dict):
                    titles.append(str(download.get("downloadTitle") or ""))
    return " ".join(titles)


def _normalized_version(item: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        item.get("name"),
        item.get("releaseNotesTitle"),
        *_platform_download_titles(item),
    ]
    for candidate in candidates:
        result = normalize_davinci_version(str(candidate or ""))
        if not result.get("rejected"):
            return result
    return normalize_davinci_version("")


def _platform_download_titles(item: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    urls = item.get("urls") or {}
    if isinstance(urls, dict):
        for platform_downloads in urls.values():
            if isinstance(platform_downloads, list):
                titles.extend(str(row.get("downloadTitle") or "") for row in platform_downloads if isinstance(row, dict))
    return titles


def _record_from_download(
    source: dict[str, Any],
    item: dict[str, Any],
    version: str,
    normalized: dict[str, Any],
    api_url: str,
) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    support_url = ingestion.get("official_url") or DEFAULT_SUPPORT_URL
    download_url = ingestion.get("download_url") or DEFAULT_DOWNLOAD_URL
    title = str(item.get("name") or item.get("releaseNotesTitle") or f"DaVinci Resolve {version}").strip()
    body = _official_body(item, version, normalized, support_url, api_url)
    published_at = _published_at(item)
    channel = "Public beta" if normalized.get("is_beta") else "Stable"

    return {
        "record_id": f"blackmagic-support:{source['product_id']}:{version}:{item.get('id') or title}",
        "company_id": source["company_id"],
        "product_id": source["product_id"],
        "company": source["company"],
        "software": source["software"],
        "category": source.get("public_category"),
        "version": version,
        "title": title,
        "published_at": published_at,
        "source_url": support_url,
        "official_url": support_url,
        "official_patch_notes_source_url": support_url,
        "download_url": download_url,
        "file_size": "",
        "file_size_note": "Blackmagic support-download metadata does not expose installer file size.",
        "file_size_status": "not_provided_by_source",
        "body": body,
        "checksums_body": "",
        "summary": str(item.get("desc") or "").strip(),
        "source_type": "download_portal",
        "official_source_type": "download_portal",
        "official_note_status": "official_source_captured",
        "official_note_label": "Official download portal entry",
        "capture_status": "captured-from-official-blackmagic-support-api",
        "official_summary": f"Blackmagic Design lists {title} in its official support downloads feed.",
        "release_channel_label": channel,
        "update_channel_label": channel,
        "official_source_classification_note": (
            "Blackmagic's support downloads API is treated as an official download-portal source. "
            "It confirms version availability and summary text; community evidence remains separate."
        ),
        "official_sources": [
            {
                "label": "Blackmagic support downloads",
                "url": support_url,
                "source_type": "download_portal",
                "trust_level": "official",
                "extraction_status": "summary_captured",
            },
            {
                "label": "Blackmagic support downloads JSON",
                "url": api_url,
                "source_type": "vendor_api",
                "trust_level": "official",
                "extraction_status": "version_metadata_captured",
            },
        ],
    }


def _official_body(item: dict[str, Any], version: str, normalized: dict[str, Any], support_url: str, api_url: str) -> str:
    title = str(item.get("name") or item.get("releaseNotesTitle") or f"DaVinci Resolve {version}").strip()
    desc = str(item.get("desc") or "").strip()
    platforms = ", ".join(str(platform) for platform in (item.get("platforms") or []) if platform)
    channel = "Public beta" if normalized.get("is_beta") else "Stable"
    lines = [
        f"Official Blackmagic support-download entry: {title}",
        f"Channel: {channel}",
        f"Release date: {_date_label(item)}",
    ]
    if platforms:
        lines.append(f"Platforms listed: {platforms}")
    if desc:
        lines.extend(["", desc])
    lines.extend([
        "",
        f"Official support page: {support_url}",
        f"Official metadata endpoint: {api_url}",
        "",
        "AUXSAYS note: this is official download-portal metadata, not broad community consensus.",
    ])
    return "\n".join(lines).strip()


def _published_at(item: dict[str, Any]) -> str:
    numeric = item.get("numericDate")
    try:
        if numeric:
            parsed = datetime.fromtimestamp(int(numeric) / 1000, tz=timezone.utc)
            return parsed.date().isoformat() + "T00:00:00Z"
    except (TypeError, ValueError, OSError, OverflowError):
        pass

    text = str(item.get("date") or "").strip()
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3})\s+(20\d{2})", text)
    if match:
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month = months.get(match.group(2).lower())
        if month:
            return datetime(int(match.group(3)), month, int(match.group(1)), tzinfo=timezone.utc).date().isoformat() + "T00:00:00Z"
    return ""


def _date_label(item: dict[str, Any]) -> str:
    published = _published_at(item)
    if published:
        return published[:10]
    return first_nonempty(item.get("date"), "Not provided by source")
