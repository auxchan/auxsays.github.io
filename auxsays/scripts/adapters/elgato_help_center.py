"""Elgato Help Center release-note adapter.

This is official-source ingestion only. Elgato Help Center articles can prove
that a vendor release exists and describe official changes, but they are not
community reports and must not create consensus evidence.
"""
from __future__ import annotations

import hashlib
import re
import sys
from urllib.parse import urljoin, urlparse, urlunparse

from lib.http import fetch_text
from lib.normalize import strip_tags, normalize_date

# Unlike parse-once adapters, this adapter fetches ONE HTTP page per discovered
# article, so its network cost scales with how many links it inspects. Two mechanisms
# bound and progress that cost:
#
# 1. BOUND (per run): the adapter enforces its OWN deterministic ceiling on article-
#    detail requests, independent of the caller's `limit`. Even if a caller passes
#    limit=200, at most ARTICLE_SCAN_CEILING article pages are fetched per run. Sources
#    also set ingestion.scan_limit (currently 8) to narrow the budget below this backstop.
#
# 2. PROGRESS (across runs): link DISCOVERY is cheap (regex over the already-fetched
#    section page, no HTTP), so the adapter discovers ALL current article links, then
#    spends its bounded detail-request budget only on links it has NOT already inspected,
#    tracked in a persisted per-source ledger (state["sources"][pid]["scan"]["inspected"]).
#    Successive runs therefore sweep forward across the whole section instead of forever
#    re-fetching the same prefix (which starves any match beyond the budget). Already-
#    inspected links (including already-ingested and non-matching ones) do not re-consume
#    the budget until the sweep completes and resets. A brand-new link at the front is
#    un-inspected, so it is picked up on the very next run. The ledger is keyed by URL, so
#    section reordering neither starves nor duplicates. When every current link has been
#    inspected the ledger resets for a fresh sweep (re-verifying content, bounded per run).
ARTICLE_SCAN_CEILING = 12

# Cap on links DISCOVERED from the section page per run (no HTTP — regex only). Bounds the
# inspected-URL ledger size; Elgato release-note sections list far fewer than this.
MAX_DISCOVERED_LINKS = 200

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


def _discover_article_links(section_url: str, html: str, cap: int) -> tuple[list[str], int]:
    """Discover article links from the section page (regex only, NO HTTP).

    Returns ``(retained, total_valid)``. Every distinct, same-domain, article-path link
    is counted (validated + deduplicated after query/fragment cleanup); the first ``cap``
    are retained for hydration. ``total_valid > cap`` means discovery was TRUNCATED, which
    the caller surfaces explicitly (never silently) so that (a) it is not reported as a
    complete section sweep and (b) links past the cap are visibly unreachable. Counting is
    bounded by the already-fetched, size-limited section HTML.
    """
    ceiling = max(1, int(cap))
    retained: list[str] = []
    seen: set[str] = set()
    total = 0
    for match in ANCHOR_RE.finditer(html or ""):
        href = (match.group(1) or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:")):
            continue
        absolute = _clean_url(urljoin(section_url, href))
        if not _is_elgato_article_url(section_url, absolute) or absolute in seen:
            continue
        seen.add(absolute)
        total += 1
        if len(retained) < ceiling:
            retained.append(absolute)
    return retained, total


def _article_links(section_url: str, html: str, max_links: int) -> list[str]:
    """Backward-compatible wrapper: the retained (bounded) article links only."""
    return _discover_article_links(section_url, html, max_links)[0]


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


def _emit_diagnostics(source: dict, **counts: object) -> None:
    """Emit a single structured, parseable diagnostics line to stderr.

    Distinguishes the outcomes an operator needs to tell apart: how many article
    pages were fetched, how many were accepted, whether the request ceiling was
    reached, and how many were dropped for request failure, parser/version miss, or
    product non-match. Never fabricates records; a miss is a drop, not an accept.
    """
    fields = " ".join(f"{key}={value}" for key, value in counts.items())
    print(f"[elgato_help_center] product={source.get('product_id')} {fields}", file=sys.stderr)


def _select_uninspected(links: list[str], inspected: list[str], budget: int, discovery_truncated: bool = False) -> tuple[list[str], bool, int]:
    """Choose up to ``budget`` links not yet in ``inspected`` (document order = newest first).

    Returns ``(selection, wrapped, pool_size)`` where ``pool_size`` is the number of links
    eligible this run. If every RETAINED link has been inspected AND discovery was complete
    (not truncated), the sweep is genuinely complete: reset (``wrapped=True``) and re-verify
    from the top. When discovery was TRUNCATED we must NOT reset — doing so would falsely
    claim a full-section sweep while links past the cap were never inspected — so the run
    idles (empty selection) and the caller surfaces ``discovery_truncated`` loudly instead.
    Bounds hold either way.
    """
    inspected_set = set(inspected)
    uninspected = [url for url in links if url not in inspected_set]
    wrapped = False
    if links and not uninspected and not discovery_truncated:
        uninspected = list(links)
        wrapped = True
    return uninspected[:budget], wrapped, len(uninspected)


def fetch(source: dict, limit: int = 3, scan_state: dict | None = None) -> list[dict]:
    ingestion = source.get("ingestion", {}) or {}
    section_url = ingestion["official_url"]

    # Bound article-detail requests deterministically: honour the caller's candidate
    # budget but never exceed the adapter's own ceiling, regardless of caller input.
    article_budget = min(max(1, int(limit)), ARTICLE_SCAN_CEILING)

    # One section-page request. A failure here propagates so the source is booked as
    # failing (transport error), unlike per-article failures which are isolated below.
    section = fetch_text(section_url, **_fetch_options(source)).text
    # Cheap discovery: valid, deduped article links in document order (no HTTP). If the page
    # advertises more than MAX_DISCOVERED_LINKS valid links, discovery is truncated — surfaced
    # explicitly below and never treated as a complete sweep.
    links, total_discovered = _discover_article_links(section_url, section, MAX_DISCOVERED_LINKS)
    discovery_truncated = total_discovered > MAX_DISCOVERED_LINKS

    # Spend the bounded detail-request budget on not-yet-inspected links so successive runs
    # sweep forward instead of re-fetching the same prefix. The ledger is keyed by URL.
    ledger = scan_state if isinstance(scan_state, dict) else {}
    inspected = list(ledger.get("inspected", []))
    selection, wrapped, pool_size = _select_uninspected(links, inspected, article_budget, discovery_truncated)

    records: list[dict] = []
    articles_fetched = 0
    request_failures = 0
    parser_misses = 0
    nonmatches = 0
    newly_inspected: list[str] = []
    for article_url in selection:
        if articles_fetched >= article_budget:
            break  # explicit request ceiling — never one fetch per discovered anchor
        try:
            html = fetch_text(article_url, **_fetch_options(source)).text
        except Exception:
            request_failures += 1
            continue  # transport failure: NOT marked inspected -> retried next run
        articles_fetched += 1
        newly_inspected.append(article_url)
        title = _title_from_html(html)
        body = _body_from_html(html)
        if not title or not _product_matches(source, title, body):
            nonmatches += 1
            continue
        version = _version_from_pattern(source, title, body)
        if not version:
            parser_misses += 1
            continue
        records.append(_record(source, article_url, title, version, _date_from_html(html), body))

    # STAGE the ledger advance under "pending_inspected"; the runner promotes it to
    # "inspected" only when the whole run succeeds (records written + state persisted).
    # A failed run therefore never advances the committed ledger, so its window is
    # re-fetched deterministically on restart (no candidate is skipped by a failure).
    # Most-recent-first, deduped, bounded. On a wrap the sweep restarts from just this
    # run's URLs. Only successfully-fetched URLs are recorded (request failures retry).
    if isinstance(scan_state, dict):
        base = [] if wrapped else inspected
        merged: list[str] = []
        seen_urls: set[str] = set()
        for url in newly_inspected + base:
            if url not in seen_urls:
                seen_urls.add(url)
                merged.append(url)
        scan_state["pending_inspected"] = merged[:MAX_DISCOVERED_LINKS]

    _emit_diagnostics(
        source,
        article_budget=article_budget,
        total_discovered=total_discovered,
        retained_count=len(links),
        discovery_truncated=discovery_truncated,
        links_found=len(links),
        candidate_pool=pool_size,
        selected=len(selection),
        articles_fetched=articles_fetched,
        accepted=len(records),
        ceiling_reached=(pool_size > article_budget),
        swept_reset=wrapped,
        no_matching_articles=(len(records) == 0),
        request_failures=request_failures,
        parser_misses=parser_misses,
        nonmatches=nonmatches,
        inspected_ledger=len(scan_state.get("pending_inspected", [])) if isinstance(scan_state, dict) else 0,
    )
    return records
