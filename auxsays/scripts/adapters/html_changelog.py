"""Conservative HTML changelog adapter.

This adapter intentionally avoids broad "any /changelog link" scraping. Source-specific
profiles can opt into narrow URL patterns so tag/archive pages do not become patch records.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse

from lib.http import fetch_text
from lib.normalize import strip_tags, normalize_date, first_nonempty

DATE_RE = re.compile(r"([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})")
NETLIFY_DETAIL_RE = re.compile(r"/changelog/\d{4}/\d{1,2}/\d{1,2}/[^/?#]+/?$", re.I)
GENERIC_EXCLUDE_RE = re.compile(r"/(tag|tags|category|categories|author|page|feed|rss|atom)/", re.I)


def _title_from_html(html: str) -> str:
    for pattern in [r"<h1[^>]*>(.*?)</h1>", r"<h2[^>]*>(.*?)</h2>", r"<title[^>]*>(.*?)</title>"]:
        m = re.search(pattern, html, flags=re.I | re.S)
        if m:
            title = strip_tags(m.group(1))
            # Remove common site suffixes without damaging product/version titles.
            title = re.sub(r"\s+[|–-]\s+Netlify\s*$", "", title, flags=re.I).strip()
            return title
    return "Official changelog update"


def _date_from_html(html: str) -> str:
    text = strip_tags(html[:8000])
    m = DATE_RE.search(text)
    return normalize_date(m.group(1) if m else "")


def _body_from_html(html: str) -> str:
    # Prefer main/article if present.
    for pattern in [r"<article\b[^>]*>(.*?)</article>", r"<main\b[^>]*>(.*?)</main>"]:
        m = re.search(pattern, html, flags=re.I | re.S)
        if m:
            text = strip_tags(m.group(1))
            if len(text) > 80:
                return text[:6000]
    return strip_tags(html)[:6000]


def _is_netlify_detail_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc.lower() not in {"www.netlify.com", "netlify.com"}:
        return False
    path = parsed.path.rstrip("/") + "/"
    return bool(NETLIFY_DETAIL_RE.search(path))


def _is_generic_changelog_detail_url(source_url: str, absolute: str, text: str) -> bool:
    parsed_source = urlparse(source_url)
    parsed = urlparse(absolute)
    if parsed.netloc and parsed_source.netloc and parsed.netloc.lower() != parsed_source.netloc.lower():
        return False
    path = parsed.path
    if GENERIC_EXCLUDE_RE.search(path):
        return False
    haystack = (path + " " + text).lower()
    if any(token in haystack for token in ["/changelog/", "/release-notes/", "/releases/"]):
        return True
    return False


def _candidate_links(source: dict, source_url: str, html: str) -> list[str]:
    ingestion = source.get("ingestion", {})
    profile = ingestion.get("parser_profile") or "generic"
    links: list[str] = []

    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, flags=re.I | re.S):
        href, text = m.group(1), strip_tags(m.group(2))
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        absolute = urljoin(source_url, href)

        if profile == "netlify_changelog":
            keep = _is_netlify_detail_url(absolute)
        else:
            keep = _is_generic_changelog_detail_url(source_url, absolute, text)

        if keep and absolute.rstrip("/") != source_url.rstrip("/") and absolute not in links:
            links.append(absolute)

    return links[:10]


def fetch(source: dict, limit: int = 3) -> list[dict]:
    ingestion = source.get("ingestion", {})
    source_url = ingestion["official_url"]
    listing = fetch_text(source_url).text
    links = _candidate_links(source, source_url, listing)

    if not links:
        # Do not create records from broad listing pages by default. A listing snapshot
        # is useful for state/debugging, but it is too noisy for public Patch records.
        if not ingestion.get("allow_listing_snapshot", False):
            return []
        digest = hashlib.sha256(listing.encode("utf-8", errors="ignore")).hexdigest()[:16]
        title = _title_from_html(listing)
        body = _body_from_html(listing)
        return [{
            "record_id": f"html:{source['product_id']}:{digest}",
            "company_id": source["company_id"],
            "product_id": source["product_id"],
            "company": source["company"],
            "software": source["software"],
            "category": source.get("public_category"),
            "version": title,
            "title": title,
            "published_at": _date_from_html(listing),
            "source_url": source_url,
            "official_url": source_url,
            "download_url": "",
            "file_size": "",
            "file_size_note": "",
            "body": body,
            "checksums_body": "",
            "summary": "",
            "source_type": "html-changelog-snapshot",
            "capture_status": "captured-from-official-html-snapshot",
        }][:limit]

    records = []
    for link in links:
        detail = fetch_text(link).text
        title = _title_from_html(detail)
        body = _body_from_html(detail)
        date = _date_from_html(detail)
        digest = hashlib.sha256((link + title + date).encode("utf-8")).hexdigest()[:16]
        records.append({
            "record_id": f"html:{source['product_id']}:{digest}",
            "company_id": source["company_id"],
            "product_id": source["product_id"],
            "company": source["company"],
            "software": source["software"],
            "category": source.get("public_category"),
            "version": first_nonempty(title, digest),
            "title": title,
            "published_at": date,
            "source_url": link,
            "official_url": source_url,
            "download_url": "",
            "file_size": "",
            "file_size_note": "",
            "body": body,
            "checksums_body": "",
            "summary": "",
            "source_type": "html-changelog",
            "capture_status": "captured-from-official-html",
        })
        if len(records) >= limit:
            break
    return records
