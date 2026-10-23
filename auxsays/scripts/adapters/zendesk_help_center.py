"""Reusable Zendesk Help Center release-note adapter (official-source ingestion only).

Vendors that host release notes on a Zendesk Help Center (help.<vendor>.com/hc/...)
expose the same documented anonymous JSON API:

    https://<host>/api/v2/help_center/<locale>/sections/<section_id>/articles.json

One paginated JSON request per section replaces per-article HTML scraping, so the
adapter gets exact article titles, ISO release dates (``created_at``), draft flags,
section scoping, and the full article body without depending on any theme DOM.

Everything vendor-specific stays in source configuration:

- ``ingestion.official_url``     the human section page (also the record's official_url);
  its host/locale/section id determine the API endpoint unless ``ingestion.api_url``
  explicitly overrides it (same host required).
- ``ingestion.version_pattern``  anchored regex extracting the exact version from the
  article TITLE (named group ``version`` or group 1). No version -> no record.
- ``ingestion.product_terms``    lowercase phrases, at least one of which must appear in
  the article title/body (defaults to the source's software name).

Zendesk Help Center articles prove that a vendor release exists and describe official
changes; they are never community reports and must not create consensus evidence. The
adapter emits official-record fields only — no report/consensus/evidence keys.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from typing import Any
from urllib.parse import urlparse

from lib.http import fetch_text
from lib.normalize import normalize_date, strip_tags

# Hard bound on paginated list requests per run. Zendesk serves up to 100 articles per
# page, so 5 pages cover 500 release notes — far beyond any real release-note section
# (Elgato's largest holds 56). More pages than this means a broken/looping paginator,
# which is surfaced as truncated pagination, never silently swept past.
MAX_PAGES = 5

# Articles per page requested from the API (Zendesk caps per_page at 100).
PER_PAGE = 100

# Byte cap per list response. A 100-article page observed in production is ~300 KB;
# 4 MB keeps a runaway response bounded while never truncating a legitimate page
# (a truncated page fails JSON parsing loudly and books the source as failing).
MAX_RESPONSE_BYTES = 4_000_000

# Body text cap per record, matching the prior help-center adapter's bound.
MAX_BODY_CHARS = 7000

SECTION_PATH_RE = re.compile(r"^/hc/(?P<locale>[a-z]{2}(?:-[a-z0-9]+)?)/sections/(?P<section_id>\d+)", re.I)
API_PATH_MARKER = "/api/v2/help_center/"


def _fetch_options(source: dict[str, Any]) -> dict[str, Any]:
    ingestion = source.get("ingestion", {}) or {}
    request = ingestion.get("request", {}) or {}
    headers = request.get("headers") or {}
    return {
        "timeout": int(request.get("timeout_seconds") or ingestion.get("timeout_seconds") or 30),
        "retries": int(request.get("retries") or ingestion.get("retries") or 0),
        "backoff_seconds": float(request.get("backoff_seconds") or ingestion.get("backoff_seconds") or 2),
        "max_bytes": int(request.get("max_bytes") or ingestion.get("max_bytes") or 0) or MAX_RESPONSE_BYTES,
        "headers": headers if isinstance(headers, dict) else {},
    }


def _section_identity(source: dict[str, Any]) -> tuple[str, str, int]:
    """Parse (host, locale, section_id) from the configured section page URL.

    The section page URL is required config (it is also the record's official_url), and
    its Zendesk-standard shape carries everything needed to derive the API endpoint, so
    the four coordinates can never drift apart in configuration.
    """
    official_url = str((source.get("ingestion") or {}).get("official_url") or "")
    parsed = urlparse(official_url)
    match = SECTION_PATH_RE.match(parsed.path or "")
    if parsed.scheme != "https" or not parsed.netloc or not match:
        raise RuntimeError(
            f"{source.get('product_id')}: ingestion.official_url must be a Zendesk Help Center "
            f"section URL (https://<host>/hc/<locale>/sections/<id>-...), got {official_url!r}"
        )
    return parsed.netloc.lower(), match.group("locale").lower(), int(match.group("section_id"))


def _list_url(source: dict[str, Any], host: str, locale: str, section_id: int) -> str:
    explicit = str((source.get("ingestion") or {}).get("api_url") or "").strip()
    if explicit:
        parsed = urlparse(explicit)
        if parsed.netloc.lower() != host or API_PATH_MARKER not in (parsed.path or ""):
            raise RuntimeError(
                f"{source.get('product_id')}: ingestion.api_url must live on {host} under "
                f"{API_PATH_MARKER}, got {explicit!r}"
            )
        return explicit
    return (
        f"https://{host}{API_PATH_MARKER}{locale}/sections/{section_id}/articles.json"
        f"?per_page={PER_PAGE}&sort_by=created_at&sort_order=desc"
    )


def _next_page_url(payload: dict[str, Any], host: str) -> str:
    """The next list page, followed only when it stays on the same host and API path."""
    next_page = str(payload.get("next_page") or "").strip()
    if not next_page:
        return ""
    parsed = urlparse(next_page)
    if parsed.scheme != "https" or parsed.netloc.lower() != host or API_PATH_MARKER not in (parsed.path or ""):
        return ""
    return next_page


def _version_from_title(source: dict[str, Any], title: str) -> str:
    pattern = str((source.get("ingestion") or {}).get("version_pattern") or "").strip()
    if not pattern:
        raise RuntimeError(f"{source.get('product_id')}: ingestion.version_pattern is required")
    match = re.compile(pattern, re.I).search(title or "")
    if not match:
        return ""
    if "version" in match.groupdict():
        return (match.group("version") or "").strip()
    return (match.group(1) or "").strip()


# WHICH PLATFORM AN ARTICLE'S NOTES COVER, from its TITLE only. Elgato publishes some versions'
# notes per platform, and an article titled "Elgato Wave Link 2.0.9 Release Notes (macOS)" covers
# the macOS notes -- which says nothing about whether 2.0.9 exists elsewhere, so the record states
# whose notes it holds and claims no more. Across every Elgato article observed the platform is
# written exactly "(Windows)" or "(macOS)", so this is a closed vocabulary: no aliases, and never the
# body, which routinely names both systems (a Windows-only article lists x64 and arm64; Stream Deck
# notes mention macOS fixes). Exactly one match labels the record; none or both label nothing.
_NOTES_PLATFORM_TOKENS = {"(windows)": "windows", "(macos)": "macos"}
_PLATFORM_WORD = re.compile(r"\b(?:windows|mac ?os|os ?x|mac)\b", re.I)


def notes_platform_from_title(title: str) -> str:
    """'windows' or 'macos' when the title names exactly one platform in the known form, else ''."""
    lowered = (title or "").lower()
    found = {platform for token, platform in _NOTES_PLATFORM_TOKENS.items() if token in lowered}
    return found.pop() if len(found) == 1 else ""


def _platform_unrecognized(title: str) -> bool:
    """A platform word the closed vocabulary did not resolve: counted, never guessed."""
    return bool(_PLATFORM_WORD.search(title or "")) and not notes_platform_from_title(title)


def _product_terms(source: dict[str, Any]) -> tuple[str, ...]:
    configured = (source.get("ingestion") or {}).get("product_terms")
    if isinstance(configured, list) and configured:
        return tuple(str(term).lower() for term in configured if str(term).strip())
    return (str(source.get("software") or source.get("product_id") or "").lower(),)


def _body_text(article: dict[str, Any]) -> str:
    body = strip_tags(str(article.get("body") or ""))
    return re.sub(r"\s+", " ", body).strip()[:MAX_BODY_CHARS]


def _record(source: dict[str, Any], article: dict[str, Any], version: str, body: str) -> dict[str, Any]:
    article_url = str(article.get("html_url") or "")
    title = str(article.get("title") or "")
    digest = hashlib.sha256((article_url + version + title).encode("utf-8")).hexdigest()[:16]
    company = source["company"]
    software = source["software"]
    # `title` stays verbatim: it feeds record_id above, and a changed digest would make a
    # published record look unseen. The platform travels as its own field, and only when known --
    # an empty value would read to the writer as "no platform" and could wipe a real label.
    platform = notes_platform_from_title(title)
    extra = {"official_notes_platform": platform} if platform else {}
    return {
        **extra,
        "record_id": f"zendesk:{source['product_id']}:{version}:{digest}",
        "company_id": source["company_id"],
        "product_id": source["product_id"],
        "company": company,
        "software": software,
        "category": source.get("public_category"),
        "version": version,
        "title": title,
        "published_at": normalize_date(str(article.get("created_at") or "")),
        "source_url": article_url,
        "official_url": (source.get("ingestion") or {}).get("official_url") or article_url,
        "download_url": "",
        "file_size": "",
        "file_size_note": f"{company} installer metadata is not exposed on the public release-note article.",
        "body": body or title,
        "checksums_body": "",
        "summary": "",
        "source_type": str((source.get("ingestion") or {}).get("type") or "help_center_release_notes"),
        "capture_status": "captured-from-zendesk-help-center-api",
        "official_summary": f"{company} published {software} {version} release notes.",
    }


def _emit_diagnostics(source: dict[str, Any], **counts: object) -> None:
    """One structured, parseable stderr line per run.

    Distinguishes the outcomes an operator needs to tell apart: pages fetched, articles
    listed, and exactly why any listed article did not become a record (draft, wrong
    section/locale/domain, no version in title, product mismatch, missing date, the same
    article listed twice, or a version deferred because distinct articles claim it). A miss is a drop, never
    a fabricated record.
    """
    fields = " ".join(f"{key}={value}" for key, value in counts.items())
    print(f"[zendesk_help_center] product={source.get('product_id')} {fields}", file=sys.stderr)


def fetch(source: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    host, locale, section_id = _section_identity(source)
    options = _fetch_options(source)

    articles: list[dict[str, Any]] = []
    pages_fetched = 0
    visited: set[str] = set()
    url = _list_url(source, host, locale, section_id)
    pagination_truncated = False
    while url:
        if url in visited or pages_fetched >= MAX_PAGES:
            # A paginator that repeats itself or exceeds the page ceiling is broken or
            # abusive; stop and surface the truncation rather than looping.
            pagination_truncated = True
            break
        visited.add(url)
        payload = json.loads(fetch_text(url, **options).text)
        if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
            raise RuntimeError(f"{source.get('product_id')}: Zendesk articles response missing 'articles' list")
        pages_fetched += 1
        articles.extend(item for item in payload["articles"] if isinstance(item, dict))
        url = _next_page_url(payload, host)

    # Deterministic newest-first ordering regardless of endpoint sort parameters.
    articles.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)

    terms = _product_terms(source)
    records: list[dict[str, Any]] = []
    candidates: list[tuple[dict[str, Any], str, str]] = []
    seen_ids: set[Any] = set()
    duplicate_listings = 0
    drafts_skipped = 0
    outside_section = 0
    locale_mismatches = 0
    wrong_domain = 0
    title_version_misses = 0
    product_misses = 0
    date_misses = 0
    for article in articles:
        if article.get("draft"):
            drafts_skipped += 1
            continue
        if int(article.get("section_id") or 0) != section_id:
            outside_section += 1
            continue
        article_locale = str(article.get("locale") or "").lower()
        if article_locale and article_locale != locale:
            locale_mismatches += 1
            continue
        article_url = str(article.get("html_url") or "")
        if urlparse(article_url).netloc.lower() != host:
            wrong_domain += 1
            continue
        title = str(article.get("title") or "")
        version = _version_from_title(source, title)
        if not version:
            title_version_misses += 1
            continue
        body = _body_text(article)
        haystack = f"{title}\n{body}".lower()
        if not any(term in haystack for term in terms):
            product_misses += 1
            continue
        if not str(article.get("created_at") or "").strip():
            # The record filename and freshness fields key off the release date; Zendesk
            # always supplies created_at, so its absence means malformed data. Fail closed.
            date_misses += 1
            continue
        article_id = article.get("id")
        if article_id is not None and article_id in seen_ids:
            # The SAME article listed twice (a paginator that overlaps pages). That is one
            # article, not two candidates, so it must not make its version look ambiguous.
            duplicate_listings += 1
            continue
        if article_id is not None:
            seen_ids.add(article_id)
        candidates.append((article, version, body))

    # TWO DISTINCT ARTICLES FOR ONE VERSION ARE DEFERRED, NOT DECIDED. Elgato publishes separate
    # macOS and Windows release notes for the same version (Wave Link 3.4 has both, on the same
    # day; 10 Wave Link versions and 1 Camera Hub version do this). The first version of this
    # adapter kept the newest article and dropped the other, so Wave Link 3.4 would have published
    # as "Elgato Wave Link 3.4 (macOS) Release Notes" -- the macOS notes presented as THE notes for
    # 3.4, to Windows users included. A record carries one official_patch_notes_body, so it cannot
    # present both platforms' notes with each attributed to its own platform; choosing one silently
    # misstates the other. Until a record can hold separately attributed platform notes, the honest
    # outcome for an ambiguous version is no record, counted, rather than half a record.
    per_version: dict[str, int] = {}
    for _article, version, _body in candidates:
        per_version[version] = per_version.get(version, 0) + 1
    versions_deferred = sorted(v for v, n in per_version.items() if n > 1)
    platform_titles_unrecognized = 0
    for article, version, body in candidates:
        if per_version[version] > 1:
            continue
        if _platform_unrecognized(str(article.get("title") or "")):
            platform_titles_unrecognized += 1
        records.append(_record(source, article, version, body))

    accepted = records[: max(0, int(limit))]
    _emit_diagnostics(
        source,
        pages_fetched=pages_fetched,
        pagination_truncated=pagination_truncated,
        articles_listed=len(articles),
        drafts_skipped=drafts_skipped,
        outside_section=outside_section,
        locale_mismatches=locale_mismatches,
        wrong_domain=wrong_domain,
        title_version_misses=title_version_misses,
        product_misses=product_misses,
        date_misses=date_misses,
        duplicate_listings=duplicate_listings,
        versions_deferred=len(versions_deferred),
        articles_deferred=sum(per_version[v] for v in versions_deferred),
        platform_titles_unrecognized=platform_titles_unrecognized,
        accepted_total=len(records),
        returned=len(accepted),
        no_matching_articles=(len(records) == 0),
    )
    return accepted
