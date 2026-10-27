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


# NOTES THAT COVER BOTH PLATFORMS, from installer evidence, never from prose. An article whose title
# names no platform is NOT thereby cross-platform -- 4K Capture Utility 1.7.16's untitled notes offer a
# Windows download only -- but Elgato's notes list their installers by file, and "Elgato Stream Deck
# 7.6.pkg" beside "Elgato Stream Deck 7.6.msi" is positive, version-specific evidence for both. Three
# conditions, each failing toward unknown:
#   * an installer counts only when its file is named for the TRACKED PRODUCT ("DemoPlugin 7.6.pkg" in a
#     troubleshooting note says nothing about Stream Deck 7.6);
#   * the macOS and Windows files must sit in one download block -- product installers with nothing but
#     LIST VOCABULARY in front of and between them: platform labels, architecture qualifiers, download
#     headings and list punctuation, the way Elgato lists them. A known-issue sentence that happens to
#     name both files is prose, not a download list; so is "(coming soon)" or "(withdrawn)" beside a
#     file, and "DemoPlugin for Stream Deck 7.6.pkg" is another product's file, not this one's;
#   * every product installer in the notes names the record's release; another version's file is
#     contradictory and labels nothing. "Names the release" is string equality, or, for two dotted-numeric
#     versions, equality once trailing ".0" components are dropped: the notes for "Stream Deck 7.1" list
#     "Elgato Stream Deck 7.1.0.pkg". Components compare as written ("7.01" is not "7.1") and nothing
#     here orders versions or touches a record's own version, so "Wave Link 3.1" and "Wave Link 3.1.0"
#     stay two records.
# Casual mentions of Windows or macOS in the text never count. Not read: an availability statement made
# in prose elsewhere ("the macOS download is temporarily unavailable") -- a listed file is taken as
# published.
_INSTALLER_EXTENSIONS = "pkg|dmg|msi|msix|exe"
_MACOS_INSTALLERS = {"pkg", "dmg"}
_WINDOWS_INSTALLERS = {"msi", "msix", "exe"}
_LIST_WORD = r"\b(?:macos|mac\s?os|mac|windows|download|downloads|links?|x64|arm64|intel|apple\s+silicon)\b"
_LIST_QUALIFIER = r"\((?:x64|x86|arm64|64-bit|32-bit|intel|apple\s+silicon|universal|macos|windows)\)"
_LIST_PUNCT = r"[,;:/|•·\-–—]"
_DOWNLOAD_BLOCK_GAP = re.compile(rf"(?:\s|{_LIST_PUNCT}|{_LIST_QUALIFIER}|{_LIST_WORD})*", re.I)
_LISTING_LEAD = re.compile(rf"(?:{_LIST_PUNCT}|{_LIST_QUALIFIER}|{_LIST_WORD})\s*$", re.I)


def _product_installers(body: str, terms: tuple[str, ...]) -> list[re.Match[str]]:
    """Installer files named for the product: one of its terms, then a version, then an extension."""
    names = [r"[\s_\-]*".join(re.escape(word) for word in str(term).split())
             for term in terms if str(term).strip()]
    if not names:
        return []
    artifact = re.compile(r"(?<![\w.])(?:" + "|".join(names) + r")[\s_\-]+(\d+(?:\.\d+)+)\.("
                          + _INSTALLER_EXTENSIONS + r")\b", re.I)
    return list(artifact.finditer(body or ""))


def _names_release(file_version: str, version: str) -> bool:
    """Whether an installer file's version is the record's release (see the rules above).

    The file's version is dotted-numeric by the pattern that found it, and only components that are
    exactly "0" are dropped, so a record version that is not dotted-numeric can match only by equality.
    """
    def trimmed(value: str) -> list[str]:
        parts = value.split(".")
        while len(parts) > 1 and parts[-1] == "0":
            parts.pop()
        return parts

    return trimmed(file_version) == trimmed(version)


def _listed(body: str, match: re.Match[str]) -> bool:
    """A file is LISTED when only list vocabulary, or the start of the notes, stands in front of it."""
    lead = body[:match.start()]
    return not lead.strip() or bool(_LISTING_LEAD.search(lead))


def joint_platform_downloads(body: str, version: str, terms: tuple[str, ...]) -> tuple[str, bool]:
    """-> ('windows_macos' or '', installers_seen).

    'windows_macos' only when every product installer in the notes is for THIS release and one download
    block of listed files holds both a macOS and a Windows file. `installers_seen` lets the caller count
    notes that carried the product's installers but did not establish joint coverage.
    """
    body = body or ""
    found = _product_installers(body, terms)
    if not found:
        return "", False
    if any(not _names_release(m.group(1), version) for m in found):
        return "", True
    listed = [m for m in found if _listed(body, m)]
    if not listed:
        return "", True
    blocks: list[set[str]] = [{listed[0].group(2).lower()}]
    for previous, current in zip(listed, listed[1:]):
        gap = body[previous.end():current.start()]
        if _DOWNLOAD_BLOCK_GAP.fullmatch(gap):
            blocks[-1].add(current.group(2).lower())
        else:
            blocks.append({current.group(2).lower()})
    both = any(kinds & _MACOS_INSTALLERS and kinds & _WINDOWS_INSTALLERS for kinds in blocks)
    return ("windows_macos" if both else ""), True


def notes_platform_for(title: str, body: str, version: str, terms: tuple[str, ...]) -> tuple[str, str]:
    """-> (platform, basis). The title token decides first; installers only where the title is silent."""
    platform = notes_platform_from_title(title)
    if platform:
        return platform, "title_token"
    if _platform_unrecognized(title):
        return "", ""
    joint, _seen = joint_platform_downloads(body, version, terms)
    return (joint, "installer_downloads") if joint else ("", "")


def _platform_unrecognized(title: str) -> bool:
    """A platform word the closed vocabulary did not resolve: counted, never guessed."""
    return bool(_PLATFORM_WORD.search(title or "")) and not notes_platform_from_title(title)


def _product_terms(source: dict[str, Any]) -> tuple[str, ...]:
    configured = (source.get("ingestion") or {}).get("product_terms")
    if isinstance(configured, list) and configured:
        return tuple(str(term).lower() for term in configured if str(term).strip())
    return (str(source.get("software") or source.get("product_id") or "").lower(),)


def _installer_names(source: dict[str, Any]) -> tuple[str, ...]:
    """The product's terms, each also with the vendor in front: Elgato names its files "Elgato Stream
    Deck 7.6.pkg", and a vendor word left between two files would split one download list in two."""
    terms = _product_terms(source)
    company = str(source.get("company") or "").strip().lower()
    return terms + tuple(f"{company} {term}" for term in terms if company)


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
    platform, basis = notes_platform_for(title, body, version, _installer_names(source))
    extra = ({"official_notes_platform": platform, "official_notes_platform_basis": basis}
             if platform else {})
    # Whether the article's notes were actually captured this time. "body" below falls back to the
    # title, so the writer cannot tell a real observation from a missing one by the body alone; only a
    # captured body may withdraw a label that rested on its installers. Never written to the record.
    if body:
        extra["official_notes_body_captured"] = True
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
    platform_downloads_unverified = 0
    for article, version, body in candidates:
        if per_version[version] > 1:
            continue
        title = str(article.get("title") or "")
        if _platform_unrecognized(title):
            platform_titles_unrecognized += 1
        elif not notes_platform_from_title(title):
            joint, installers_seen = joint_platform_downloads(body, version, _installer_names(source))
            if installers_seen and not joint:
                # Installers were listed but did not establish both platforms for this exact
                # version (one platform only, or another version's file): left unlabelled, counted.
                platform_downloads_unverified += 1
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
        platform_downloads_unverified=platform_downloads_unverified,
        accepted_total=len(records),
        returned=len(accepted),
        no_matching_articles=(len(records) == 0),
    )
    return accepted
