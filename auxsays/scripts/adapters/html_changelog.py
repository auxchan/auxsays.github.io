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
# Feeds and downloadable assets are never changelog ENTRIES, whatever path they sit under.
FEED_OR_ASSET_RE = re.compile(r"\.(xml|rss|atom|json|zip|pdf|dmg|exe|pkg|png|jpe?g|svg)$", re.I)
ADOBE_VERSION_HEADING_RE = re.compile(r"<h(?P<level>[2-4])\b[^>]*>(?P<title>.*?(?:version|v)\s*[0-9]+(?:\.[0-9]+){0,3}.*?)</h(?P=level)>", re.I | re.S)
ADOBE_VERSION_RE = re.compile(r"(?:version|v)\s*([0-9]+(?:\.[0-9]+){0,3})", re.I)
ADOBE_MONTH_RE = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})", re.I)
MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
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


def _title_from_html(html: str) -> str:
    for pattern in [r"<h1[^>]*>(.*?)</h1>", r"<h2[^>]*>(.*?)</h2>", r"<title[^>]*>(.*?)</title>"]:
        m = re.search(pattern, html, flags=re.I | re.S)
        if m:
            title = strip_tags(m.group(1))
            title = re.sub(r"\s+[|–-]\s+Netlify\s*$", "", title, flags=re.I).strip()
            return title
    return "Official changelog update"


def _date_from_html(html: str) -> str:
    text = strip_tags(html[:8000])
    m = DATE_RE.search(text)
    return normalize_date(m.group(1) if m else "")


def _body_from_html(html: str) -> str:
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


def _adobe_month_year_to_date(title: str) -> str:
    m = ADOBE_MONTH_RE.search(title or "")
    if not m:
        return normalize_date("")
    month = MONTHS.get(m.group(1).lower(), "01")
    return f"{m.group(2)}-{month}-01T00:00:00Z"


def _adobe_version_from_title(title: str) -> str:
    m = ADOBE_VERSION_RE.search(title or "")
    return m.group(1).strip() if m else first_nonempty(title, "official-update")


def _fetch_adobe_release_notes(source: dict, limit: int = 3) -> list[dict]:
    ingestion = source.get("ingestion", {})
    source_url = ingestion["official_url"]
    html = fetch_text(source_url, **_fetch_options(source)).text
    matches = list(ADOBE_VERSION_HEADING_RE.finditer(html))
    records = []

    for idx, match in enumerate(matches):
        title = strip_tags(match.group("title"))
        lowered = title.lower()
        if not title or "version" not in lowered:
            continue
        if any(token in lowered for token in ["beta", "mobile", "ios", "android"]):
            continue

        section_start = match.end()
        section_end = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(html), section_start + 18000)
        section_html = html[section_start:section_end]
        body = strip_tags(f"{title}\n\n{section_html}")[:7000]
        version = _adobe_version_from_title(title)
        published = _adobe_month_year_to_date(title)
        digest = hashlib.sha256((source_url + version + title).encode("utf-8")).hexdigest()[:16]
        records.append({
            "record_id": f"html:{source['product_id']}:{version}:{digest}",
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
            "file_size_note": "Adobe installer metadata is not exposed on the public release notes page.",
            "body": body or title,
            "checksums_body": "",
            "summary": "",
            "source_type": "html-changelog",
            "capture_status": "captured-from-official-adobe-release-notes",
            "official_summary": f"Adobe published {source['software']} {version} release notes.",
        })
        if len(records) >= limit:
            break
    return records


def _is_generic_changelog_detail_url(source_url: str, absolute: str, text: str) -> bool:
    parsed_source = urlparse(source_url)
    parsed = urlparse(absolute)
    if parsed.netloc and parsed_source.netloc and parsed.netloc.lower() != parsed_source.netloc.lower():
        return False
    path = parsed.path
    if GENERIC_EXCLUDE_RE.search(path):
        return False
    haystack = (path + " " + text).lower()
    return any(token in haystack for token in ["/changelog/", "/release-notes/", "/releases/"])


def _candidate_links(source: dict, source_url: str, html: str) -> list[str]:
    ingestion = source.get("ingestion", {})
    profile = ingestion.get("parser_profile") or "generic"
    links: list[str] = []
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, flags=re.I | re.S):
        href, text = m.group(1), strip_tags(m.group(2))
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        absolute = urljoin(source_url, href)
        keep = _is_netlify_detail_url(absolute) if profile == "netlify_changelog" else _is_generic_changelog_detail_url(source_url, absolute, text)
        if keep and absolute.rstrip("/") != source_url.rstrip("/") and absolute not in links:
            links.append(absolute)
    return links[:10]


def _entry_key(url: str) -> str:
    """A URL reduced to the page it identifies: no query, no fragment, no trailing slash."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


def _family_links(source_url: str, html: str) -> list[str]:
    """Links on the listing that look like changelog/release ENTRIES for this same site.

    This is the loose, shape-only question -- "does this page still publish entries?" -- asked
    independently of whether the configured profile can map them. It is the generic rule every
    html_changelog source already trusts to find its own entries, so it cannot invent upstream
    content that the adapter would not otherwise consider.
    """
    base = _entry_key(source_url)
    found: list[str] = []
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, flags=re.I | re.S):
        href, text = m.group(1), strip_tags(m.group(2))
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        absolute = urljoin(source_url, href)
        # A feed is not an entry. Netlify's listing links /changelog/feed.xml, and counting it
        # would let a page whose ONLY changelog link is its own feed claim upstream content.
        if FEED_OR_ASSET_RE.search(urlparse(absolute).path):
            continue
        # `?page=2` and `#top` are the SAME page, so they are navigation, not entries. Comparing
        # raw URLs let a listing that has published nothing yet point at its own pagination and
        # claim upstream content -- which would call a brand-new source broken on its first check.
        key = _entry_key(absolute)
        if (_is_generic_changelog_detail_url(source_url, absolute, text)
                and key != base and key not in found):
            found.append(key)
    return found


def changelog_probe(source: dict, source_url: str, listing: str, matched: list[str]) -> dict:
    """Structural evidence about THIS listing: entries present, versus entries mapped.

    `extraction_mismatch` says the page still publishes entries and the configured extractor maps
    none of them. That is Netlify exactly: the changelog moved to slug-only URLs, and
    NETLIFY_DETAIL_RE still demands /changelog/YYYY/M/D/slug/, so every entry is invisible to it
    while the fetch keeps succeeding.

    It cannot fire for a `generic` profile, because there the family test IS the candidate test --
    if the generic rule finds no entries, there is nothing claimed to be present. That is the
    intended asymmetry: the signal only reports a profile narrower than the page it is aimed at.
    """
    family = _family_links(source_url, listing)
    return {
        "upstream_candidates": len(family),
        "matched_candidates": len(matched),
        "extraction_mismatch": bool(family) and not matched,
    }


def fetch(source: dict, limit: int = 3, probe: dict | None = None) -> list[dict]:
    ingestion = source.get("ingestion", {})
    profile = ingestion.get("parser_profile") or "generic"
    if profile.startswith("adobe_") and profile.endswith("_release_notes"):
        # Heading-driven, not link-driven: there is no candidate-link population to compare
        # against, so this path reports no signal and keeps the tolerance path.
        return _fetch_adobe_release_notes(source, limit=limit)

    source_url = ingestion["official_url"]
    listing = fetch_text(source_url, **_fetch_options(source)).text
    links = _candidate_links(source, source_url, listing)
    if probe is not None:
        probe.update(changelog_probe(source, source_url, listing, links))

    if not links:
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
        detail = fetch_text(link, **_fetch_options(source)).text
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
