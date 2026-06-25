"""Elgato Help Center release-note adapter.

This is official-source ingestion only. Elgato Help Center articles can prove
that a vendor release exists and describe official changes, but they are not
community reports and must not create consensus evidence.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse, urlunparse

from lib.http import fetch_text
from lib.normalize import strip_tags, normalize_date

ARTICLE_PATH = "/hc/en-us/articles/"
ARTICLE_BODY_RE = re.compile(
    r"<(?P<tag>div|section|article)\b(?=[^>]*class=[\"'][^\"']*\barticle-body\b)[^>]*>(?P<body>.*?)</(?P=tag)>",
    re.I | re.S,
)
ANCHOR_RE = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>", re.I | re.S)
TITLE_PATTERNS = (
    r"<h1\b[^>]*>(?P<title>.*?)</h1>",
    r"<title\b[^>]*>(?P<title>.*?)</title>",
)
TIME_RE = re.compile(r"<time\b[^>]*datetime=[\"'](?P<date>[^\"']+)[\"'][^>]*>", re.I | re.S)
META_DATE_RE = re.compile(
    r"<meta\b[^>]*(?:property|name)=[\"'](?:article:published_time|date|pubdate|dc\.date)[\"'][^>]*content=[\"'](?P<date>[^\"']+)[\"'][^>]*>",
    re.I | re.S,
)
VISIBLE_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}",
    re.I,
)

PRODUCT_TERMS = {
    "elgato-stream-deck": ("stream deck",),
    "elgato-wave-link": ("wave link",),
    "elgato-camera-hub": ("camera hub",),
    "elgato-4k-capture-utility": ("4k capture utility", "4k capture"),
}


def _fetch_options(source: dict) -> dict:
    ingestion = source.get("ingestion", {}) or {}
    request = ingestion.get("request", {}) or {}
    headers = request.get("headers") or {}
    return {
        "timeout": int(request.get("timeout_seconds") or ingestion.get("timeout_seconds") or 30),
        "retries": int(request.get("retries") or ingestion.get("retries") or 0),
        "backoff_seconds": float(request.get("backoff_seconds") or ingestion.get("backoff_seconds") or 2),
        "max_bytes": int(request.get("max_bytes") or ingestion.get("max_bytes") or 0) or None,
        "headers": headers if isinstance(headers, dict) else {},
    }


def _clean_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def _is_elgato_article_url(section_url: str, candidate: str) -> bool:
    section = urlparse(section_url)
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != section.netloc.lower():
        return False
    if ARTICLE_PATH not in parsed.path:
        return False
    lowered = parsed.path.lower()
    return not any(part in lowered for part in ("/search", "/sections", "/categories"))


def _article_links(section_url: str, html: str, limit: int) -> list[str]:
    links: list[str] = []
    for match in ANCHOR_RE.finditer(html or ""):
        href = (match.group(1) or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:")):
            continue
        absolute = _clean_url(urljoin(section_url, href))
        if _is_elgato_article_url(section_url, absolute) and absolute not in links:
            links.append(absolute)
        if len(links) >= max(1, limit) * 4:
            break
    return links


def _title_from_html(html: str) -> str:
    for pattern in TITLE_PATTERNS:
        match = re.search(pattern, html or "", flags=re.I | re.S)
        if match:
            title = strip_tags(match.group("title"))
            title = re.sub(r"\s+[|]\s+Elgato.*$", "", title, flags=re.I).strip()
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                return title
    return ""


def _body_from_html(html: str) -> str:
    for pattern in (ARTICLE_BODY_RE, re.compile(r"<article\b[^>]*>(?P<body>.*?)</article>", re.I | re.S), re.compile(r"<main\b[^>]*>(?P<body>.*?)</main>", re.I | re.S)):
        match = pattern.search(html or "")
        if match:
            body = strip_tags(match.group("body"))
            body = re.sub(r"\s+", " ", body).strip()
            if body:
                return body[:7000]
    body = strip_tags(html or "")
    return re.sub(r"\s+", " ", body).strip()[:7000]


def _date_from_html(html: str) -> str:
    for regex in (TIME_RE, META_DATE_RE):
        match = regex.search(html or "")
        if match:
            return normalize_date(match.group("date"))
    text = strip_tags(html or "")
    match = VISIBLE_DATE_RE.search(text)
    return normalize_date(match.group(0) if match else "")


def _product_matches(source: dict, title: str, body: str) -> bool:
    product_id = str(source.get("product_id") or "").strip()
    terms = PRODUCT_TERMS.get(product_id, (str(source.get("software") or product_id).lower(),))
    haystack = f"{title}\n{body}".lower()
    return any(term in haystack for term in terms)


def _version_from_pattern(source: dict, title: str, body: str) -> str:
    pattern = ((source.get("ingestion") or {}).get("version_pattern") or "").strip()
    if not pattern:
        return ""
    regex = re.compile(pattern, re.I | re.M)
    candidates = [title.strip()]
    candidates.extend(line.strip() for line in (body or "").splitlines() if line.strip())
    candidates.append(re.sub(r"\s+", " ", body or "").strip())
    for candidate in candidates:
        match = regex.search(candidate)
        if match:
            if "version" in match.groupdict():
                return match.group("version").strip()
            return match.group(1).strip()
    return ""


def _record(source: dict, article_url: str, title: str, version: str, published: str, body: str) -> dict:
    digest = hashlib.sha256((article_url + version + title).encode("utf-8")).hexdigest()[:16]
    return {
        "record_id": f"help-center:{source['product_id']}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": source["product_id"],
        "company": source["company"],
        "software": source["software"],
        "category": source.get("public_category"),
        "version": version,
        "title": title,
        "published_at": published,
        "source_url": article_url,
        "official_url": (source.get("ingestion") or {}).get("official_url") or article_url,
        "download_url": "",
        "file_size": "",
        "file_size_note": "Elgato installer metadata is not exposed on the public release-note article.",
        "body": body or title,
        "checksums_body": "",
        "summary": "",
        "source_type": "help_center_release_notes",
        "capture_status": "captured-from-official-elgato-help-center",
        "official_summary": f"Elgato published {source['software']} {version} release notes.",
    }


def fetch(source: dict, limit: int = 3) -> list[dict]:
    ingestion = source.get("ingestion", {}) or {}
    section_url = ingestion["official_url"]
    section = fetch_text(section_url, **_fetch_options(source)).text
    links = _article_links(section_url, section, limit)

    records: list[dict] = []
    for article_url in links:
        html = fetch_text(article_url, **_fetch_options(source)).text
        title = _title_from_html(html)
        body = _body_from_html(html)
        if not title or not _product_matches(source, title, body):
            continue
        version = _version_from_pattern(source, title, body)
        if not version:
            continue
        records.append(_record(source, article_url, title, version, _date_from_html(html), body))
        if len(records) >= limit:
            break
    return records
