#!/usr/bin/env python3
"""Open-web discovery: a federated search that finds report URLs the enumerators never reach.

WHY. Every other AUXSAYS lane WALKS a community it already knows -- a Q&A tag, a sitemap, an API
listing. A human hunting PowerPoint complaints does something different: they ASK, with words, and
get back pages nobody configured. This lane is that, autonomously.

WHY NOT A GENERAL WEB INDEX. Measured, not assumed:
  * duckduckgo html -- robots.txt permits it, but after a handful of automated queries it serves an
    interactive bot challenge ("select all squares containing a duck"). Defeating bot detection is
    not something AUXSAYS will do, so it cannot be a production dependency.
  * mojeek -- robots.txt says `Disallow: /search`.
  * marginalia -- robots.txt says `Disallow: /search`.
  * brave api -- answers HTTP 402/422 without a paid key; a lane that stops when an account runs
    dry is not autonomous.
Every general index is therefore either forbidden, gated, or paid. Rather than pretend otherwise,
this lane federates the search endpoints AUXSAYS is actually permitted to query, and asks them the
WIDE question set a human would type.

HOW IT DIFFERS FROM THE NATIVE LANES. The native lanes enumerate: tag pages by recency, sitemaps by
lastmod, issues by label. They are bounded by WHERE they look. This one is bounded by WHAT IT ASKS,
so it reaches threads outside a recency window, outside an enumerated tag, and outside a sitemap --
including archives no walk would ever page back to.

A SNIPPET IS NEVER EVIDENCE. Search output is used for ONE thing: producing candidate URLs. Titles
and summaries are discarded immediately. The original page is fetched, hydrated and classified by
the same unchanged gates as every other lane, or the candidate is dropped.
"""
from __future__ import annotations

import html as html_module
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_SOURCE_TYPE = "open_web_discovery"
ENDPOINT_FAMILY = "open_web_search"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
REQUEST_TIMEOUT = 25
MAX_BYTES = 1_500_000
_MIN_REQUEST_INTERVAL = 1.1          # general indexes throttle far harder than product APIs
_last_request_at = 0.0

# Hosts this repo can actually fetch and attribute. The value is the source_type the resulting
# evidence row carries, so a report found by search is indistinguishable downstream from the same
# report found by its native lane -- which is what makes cross-lane de-duplication work.
SUPPORTED_HOSTS: tuple[tuple[str, str], ...] = (
    ("learn.microsoft.com/en-us/answers/questions/", "microsoft_learn_qna"),
    ("learn.microsoft.com/answers/questions/", "microsoft_learn_qna"),
    ("techcommunity.microsoft.com/discussions/", "microsoft_tech_community"),
    ("superuser.com/questions/", "stack_exchange_question"),
    ("stackoverflow.com/questions/", "stack_exchange_question"),
    ("github.com/OfficeDev/office-js/issues/", "github_officedev_issue"),
)

# Hosts that are real discussion venues but that AUXSAYS must not ingest, listed so the telemetry
# can say WHY a result was dropped instead of silently losing it.
KNOWN_UNINGESTABLE: tuple[str, ...] = (
    "reddit.com", "answers.microsoft.com", "quora.com", "facebook.com", "x.com", "twitter.com",
)


class OpenWebError(Exception):
    """Transport failure carrying a stable reason token for method health."""

    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.endpoint_family = ENDPOINT_FAMILY


def error_reason(exc: Exception) -> str:
    # Provider adapters raise their OWN error types. Reading `.reason` off any of them keeps the
    # health row specific ("rate_limited") instead of collapsing to a class name that says nothing.
    reason = getattr(exc, "reason", "")
    if reason:
        return str(reason)
    if isinstance(exc, OpenWebError):
        return exc.reason
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}_error"
    if isinstance(exc, urllib.error.URLError):
        return "network_unreachable"
    return type(exc).__name__


def _pace() -> None:
    global _last_request_at
    delta = time.monotonic() - _last_request_at
    if delta < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - delta)
    _last_request_at = time.monotonic()


def _fetch(url: str) -> str:
    _pace()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.read(MAX_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 503):
            raise OpenWebError("rate_limited", status=exc.code) from exc
        raise OpenWebError(f"http_{exc.code}_error", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise OpenWebError("network_unreachable") from exc


# --------------------------------------------------------------------------- providers
# Each provider is a permitted, keyless search endpoint that this repo already talks to in
# production. They are asked the WIDE question set, which is what separates this lane from the
# enumerators: those are bounded by where they look, this one by what it asks.


def search_learn_qna(query: str) -> list[str]:
    """Microsoft Learn search. Returns question URLs only; titles and summaries are discarded."""
    from . import microsoft_learn_qna_source as learn_qna  # noqa: PLC0415

    _pace()
    url = learn_qna.learn_qna_search_url(query)
    _status, _ctype, body = learn_qna._fetch_feed_text(url)
    return [f"https://learn.microsoft.com/en-us/answers/questions/{qid}/"
            for qid in dict.fromkeys(re.findall(r"/answers/questions/(\d+)/", body))]


def search_stack_exchange(query: str) -> list[str]:
    """Super User and Stack Overflow, via the keyless official API."""
    from . import stack_exchange_source as se  # noqa: PLC0415

    urls: list[str] = []
    for site in ("superuser", "stackoverflow"):
        _pace()
        payload = se.request_json(se.search_advanced_url(site, query=query))
        for item in (payload.get("items") or []):
            if isinstance(item, dict) and item.get("question_id"):
                urls.append(se.question_url(site, item["question_id"]))
    return urls


def search_github(query: str) -> list[str]:
    """OfficeDev issues, via the GitHub search API."""
    from . import github_officedev_source as gh  # noqa: PLC0415

    _pace()
    scoped = query if "repo:" in query else f"repo:{gh.REPO} {query}"
    items, _telemetry = gh.collect_officedev_candidates(queries=[scoped], errors=[],
                                                        max_requests=1)
    return [str(item.get("source_url") or "") for item in items]


PROVIDERS: tuple[tuple[str, Any], ...] = (
    ("learn_qna_search", search_learn_qna),
    ("stack_exchange_search", search_stack_exchange),
    ("github_search", search_github),
)


# --------------------------------------------------------------------------- URL handling
_TRACKING_PARAMS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                    "ref", "referrer", "src", "spm", "fbclid", "gclid")


def canonical_url(url: str) -> str:
    """One canonical spelling per report, so a search hit and a native hit are the same row.

    Strips tracking parameters, fragments, the locale segment Microsoft varies per visitor, and a
    trailing slash. Without this the same thread found by two routes becomes two evidence rows.
    """
    text = html_module.unescape(str(url or "").strip())
    if not text.startswith("http"):
        return ""
    parts = urllib.parse.urlsplit(text)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query)
             if k.lower() not in _TRACKING_PARAMS]
    path = parts.path
    # learn.microsoft.com serves the same thread under every locale; the native lane stores en-us.
    path = re.sub(r"^/[a-z]{2}-[a-z]{2}/answers/", "/en-us/answers/", path, flags=re.I)
    cleaned = urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path,
                                       urllib.parse.urlencode(query), ""))
    return cleaned.rstrip("/")


def identify_source(url: str) -> tuple[str, str]:
    """(source_type, disposition) for a discovered URL.

    disposition is "supported", "uningestable" for a known venue with no adapter, or "unsupported".
    """
    lowered = canonical_url(url).lower()
    if not lowered:
        return "", "unsupported"
    for marker, source_type in SUPPORTED_HOSTS:
        if marker.lower() in lowered:
            return source_type, "supported"
    for host in KNOWN_UNINGESTABLE:
        if host in lowered:
            return "", "uningestable"
    return "", "unsupported"


# --------------------------------------------------------------------------- query building
PRODUCT_TERMS = ("PowerPoint", "Microsoft PowerPoint")
UPDATE_TERMS = ("after update", "after updating Office", "after PowerPoint update",
                "since the latest update", "update broke", "stopped working after update")
SYMPTOM_TERMS = ("crash", "freeze", "not responding", "cannot save", "cannot open",
                 "slideshow", "export PDF", "images missing", "video", "fonts",
                 "animation", "hyperlink", "Copilot", "add-in", "slow")
# Restricting to hosts we can hydrate keeps the index working for us rather than returning pages
# that would only be recorded as skipped.
SITE_SCOPES = ("site:learn.microsoft.com", "site:superuser.com",
               "site:techcommunity.microsoft.com", "")


def build_queries(*, version: str = "", build: str = "", max_queries: int = 12) -> list[str]:
    """A bounded, deterministic query set for one patch window.

    Deliberately NOT a Cartesian product: that produces hundreds of near-identical searches and
    the index returns the same pages for most of them. Identity-bearing queries come first because
    they are the only ones that can yield a Tier-1 report; the symptom families follow.
    """
    queries: list[str] = []
    if build:
        queries.append(f'PowerPoint "{build}"')
        queries.append(f'PowerPoint "{build}" problem')
    if version:
        queries.append(f'PowerPoint "Version {version}" after update')
        queries.append(f'PowerPoint {version} crash OR freeze OR "not responding"')
    for update_term in UPDATE_TERMS[:3]:
        for scope in SITE_SCOPES[:2]:
            queries.append(f'PowerPoint {update_term} {scope}'.strip())
    for symptom in SYMPTOM_TERMS[:4]:
        queries.append(f'PowerPoint {symptom} after Office update')
    seen: set[str] = set()
    ordered: list[str] = []
    for query in queries:
        key = " ".join(query.split()).lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(" ".join(query.split()))
    return ordered[:max_queries]


# --------------------------------------------------------------------------- discovery
def discover_urls(queries: list[str], *, errors: list[dict[str, Any]],
                  max_requests: int = 14) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Run the query set across providers and return canonical, de-duplicated candidate URLs.

    Only the URL survives. Titles and summaries produced by the index are never returned, so there
    is no path by which a snippet becomes evidence.
    """
    found: dict[str, dict[str, str]] = {}
    telemetry = {"queries": 0, "requests": 0, "raw_results": 0,
                 "supported": 0, "uningestable": 0, "unsupported": 0,
                 "providers_ok": [], "providers_failed": []}
    requests_made = 0
    for query in queries:
        if requests_made >= max_requests:
            errors.append({"source_url": ENDPOINT_FAMILY,
                           "reason": f"request_budget_exhausted_after_{requests_made}"})
            break
        telemetry["queries"] += 1
        for provider_name, provider in PROVIDERS:
            if requests_made >= max_requests:
                break
            requests_made += 1
            telemetry["requests"] = requests_made
            try:
                hits = provider(query)
            except Exception as exc:  # noqa: BLE001 - recorded for method health
                errors.append({"source_url": f"{ENDPOINT_FAMILY}:{provider_name}",
                               "reason": error_reason(exc)})
                if provider_name not in telemetry["providers_failed"]:
                    telemetry["providers_failed"].append(provider_name)
                continue
            if provider_name not in telemetry["providers_ok"]:
                telemetry["providers_ok"].append(provider_name)
            telemetry["raw_results"] += len(hits)
            for hit in hits:
                url = canonical_url(hit)
                if not url:
                    continue
                source_type, disposition = identify_source(url)
                if disposition != "supported":
                    telemetry[disposition] += 1
                    continue
                if url in found:
                    continue
                found[url] = {"source_url": url, "source_type": source_type,
                              "discovered_by": provider_name, "matched_query": query}
                telemetry["supported"] += 1
            # Every provider is asked every query. They are not fallbacks for one another --
            # they index DIFFERENT corpora, so stopping at the first that answers would silently
            # drop Stack Exchange and GitHub whenever Learn happened to return something.
    return list(found.values()), telemetry


_CANONICAL_LINK_RE = re.compile(
    r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"|<meta[^>]+property="og:url"[^>]+content="([^"]+)"',
    re.I)


def canonical_from_page(page_html: str, fallback: str = "") -> str:
    """The URL the PAGE says it is.

    A search result gives an id-only URL; the native lanes store the slugged form. Two spellings of
    one thread would become two evidence rows, so the page's own canonical link decides -- it is
    the only spelling both routes can agree on without either guessing.
    """
    found = _CANONICAL_LINK_RE.search(page_html or "")
    if found:
        declared = found.group(1) or found.group(2) or ""
        if declared.startswith("http"):
            return canonical_url(declared)
    return canonical_url(fallback)
