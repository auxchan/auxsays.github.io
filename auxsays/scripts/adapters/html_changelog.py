"""Conservative HTML changelog adapter.

This is intentionally narrow. It is safe enough for Netlify-style changelog pages
and should be expanded with source-specific parser profiles before enabling more
HTML sources.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin

from lib.http import fetch_text
from lib.normalize import strip_tags, normalize_date, first_nonempty

DATE_RE = re.compile(r"([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})")

def _title_from_html(html: str) -> str:
    for pattern in [r"<h1[^>]*>(.*?)</h1>", r"<h2[^>]*>(.*?)</h2>", r"<title[^>]*>(.*?)</title>"]:
        m = re.search(pattern, html, flags=re.I | re.S)
        if m:
            return strip_tags(m.group(1))
    return "Official changelog update"

def _date_from_html(html: str) -> str:
    m = DATE_RE.search(strip_tags(html[:6000]))
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

def _candidate_links(source_url: str, html: str) -> list[str]:
    links = []
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, flags=re.I | re.S):
        href, text = m.group(1), strip_tags(m.group(2))
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(source_url, href)
        haystack = (absolute + " " + text).lower()
        if "/changelog" in haystack or "/release" in haystack or "release notes" in haystack or "update" in haystack:
            if absolute not in links and absolute.rstrip("/") != source_url.rstrip("/"):
                links.append(absolute)
    return links[:10]

def fetch(source: dict, limit: int = 3) -> list[dict]:
    ingestion = source.get("ingestion", {})
    source_url = ingestion["official_url"]
    listing = fetch_text(source_url).text
    links = _candidate_links(source_url, listing)
    if not links:
        # Snapshot fallback: create one record for the page itself only if enabled.
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
