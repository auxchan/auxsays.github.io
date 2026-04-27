"""RSS/Atom adapter with conservative feed discovery."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import urljoin

from lib.http import fetch_text
from lib.normalize import normalize_date, strip_tags, first_nonempty

FEED_PATTERNS = [
    r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>',
    r'<a[^>]+href=["\'][^"\']*(?:rss|feed)[^"\']*["\'][^>]*>',
]

def _href(tag: str) -> str:
    match = re.search(r'href=["\']([^"\']+)["\']', tag, flags=re.I)
    return unescape(match.group(1)) if match else ""

def _discover_feed(source_url: str) -> str:
    html = fetch_text(source_url).text
    for pattern in FEED_PATTERNS:
        for tag in re.findall(pattern, html, flags=re.I | re.S):
            href = _href(tag)
            if href:
                return urljoin(source_url, href)
    # Conservative common fallbacks. Failed candidates are handled by the caller.
    candidates = [
        urljoin(source_url.rstrip("/") + "/", "feed/"),
        urljoin(source_url.rstrip("/") + "/", "feed.xml"),
        urljoin(source_url.rstrip("/") + "/", "rss.xml"),
    ]
    if "github.blog/changelog" in source_url:
        candidates.insert(0, "https://github.blog/changelog/feed/")
    return candidates[0]

def _children(elem):
    return list(elem)

def _local(tag: str) -> str:
    return tag.split("}", 1)[-1].lower()

def _text(elem, name: str) -> str:
    for child in _children(elem):
        if _local(child.tag) == name:
            return "".join(child.itertext()).strip()
    return ""

def _link(elem) -> str:
    # RSS link element
    rss_link = _text(elem, "link")
    if rss_link:
        return rss_link
    # Atom link href
    for child in _children(elem):
        if _local(child.tag) == "link" and child.attrib.get("href"):
            return child.attrib["href"]
    return ""

def _summary(elem) -> str:
    for name in ["content", "encoded", "summary", "description"]:
        value = _text(elem, name)
        if value:
            return strip_tags(value)
    return ""

def _items(root):
    if _local(root.tag) == "feed":
        return [child for child in _children(root) if _local(child.tag) == "entry"]
    channel = next((child for child in _children(root) if _local(child.tag) == "channel"), root)
    return [child for child in _children(channel) if _local(child.tag) == "item"]

def fetch(source: dict, limit: int = 3) -> list[dict]:
    ingestion = source.get("ingestion", {})
    feed_url = ingestion.get("feed_url") or _discover_feed(ingestion["official_url"])
    result = fetch_text(feed_url, headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    root = ET.fromstring(result.text)
    records = []
    for item in _items(root):
        title = first_nonempty(_text(item, "title"), "Untitled update")
        link = first_nonempty(_link(item), ingestion["official_url"])
        date = first_nonempty(_text(item, "pubdate"), _text(item, "published"), _text(item, "updated"), _text(item, "dc:date"))
        guid = first_nonempty(_text(item, "guid"), _text(item, "id"), link, title)
        body = _summary(item)
        records.append({
            "record_id": f"rss:{source['product_id']}:{guid}",
            "company_id": source["company_id"],
            "product_id": source["product_id"],
            "company": source["company"],
            "software": source["software"],
            "category": source.get("public_category"),
            "version": title,
            "title": title,
            "published_at": normalize_date(date),
            "source_url": link,
            "official_url": ingestion.get("official_url"),
            "download_url": "",
            "file_size": "",
            "file_size_note": "",
            "body": body or f"RSS item detected for {title}. Full body may require detail-page parsing in a later adapter revision.",
            "checksums_body": "",
            "summary": body,
            "source_type": "rss-feed",
            "capture_status": "captured-from-rss-feed",
        })
        if len(records) >= limit:
            break
    return records
