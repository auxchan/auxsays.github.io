"""Shared, product-agnostic Microsoft Learn Q&A search-RSS evidence discovery.

Microsoft Learn Q&A (`learn.microsoft.com/answers`) exposes a clean, unauthenticated
search RSS API that can be driven by an exact query term (a KB number or OS build), so
discovery is keyword-anchored and CI-reliable — no login, no HTML scraping, no AI.

This module ONLY discovers and normalizes candidate question threads into the shared
candidate shape (parent_title / report_title / report_text / source_url / source_date /
source_type / source_name). It never accepts, counts, or gates anything — every product
collector still applies its own deterministic acceptance gates (exact KB/build identity,
concrete issue, specific URL, date) downstream. More discovery, same gates.

Determinism / safety:
- Only specific Learn Q&A question URLs (``/answers/questions/<id>/...``) become candidates;
  generic Learn search/category/docs URLs are dropped via base.source_url_is_specific.
- Fetch/parse/empty states are surfaced explicitly (blocked / broken / no_results) so a
  product collector's method health is honest instead of crashing.
"""
from __future__ import annotations

import html
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError

from .base import date_part, source_url_is_specific

LEARN_QNA_RSS_ENDPOINT = "https://learn.microsoft.com/api/search/rss"
DEFAULT_SOURCE_TYPE = "microsoft_learn_qna"
DEFAULT_SOURCE_NAME = "Microsoft Learn Q&A"
ENDPOINT_FAMILY = "learn_qna_search_rss"

LEARN_QNA_USER_AGENT = os.getenv(
    "AUXSAYS_LEARN_QNA_USER_AGENT",
    "script:com.auxsays.patch-intelligence:v1.0 (+https://auxsays.com)",
)
FEED_HEADERS = {
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, text/plain;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "close",
    "User-Agent": LEARN_QNA_USER_AGENT,
}


class LearnQnaAccessError(RuntimeError):
    """Raised for transport/HTTP/parse failures. ``signature`` classifies the failure
    ("blocked" for auth/403/429/challenge, "broken" for parser/schema, "network" for
    unreachable) so the collector can map it to honest method health."""

    def __init__(self, reason: str, *, status: int | None = None, content_type: str = "", signature: str = "", endpoint_family: str = ENDPOINT_FAMILY) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.content_type = content_type
        self.signature = signature
        self.endpoint_family = endpoint_family


def error_reason(exc: Exception) -> str:
    return exc.reason if isinstance(exc, LearnQnaAccessError) else type(exc).__name__


# --- URL + query builders ----------------------------------------------------

def learn_qna_search_url(query: str) -> str:
    """Build a Microsoft Learn Q&A search-RSS URL for an exact query term.

    The ``$filter=category eq 'QnA'`` facet scopes to Q&A; a known Learn bug means it is
    not always fully respected, so callers still re-check each item is a specific Q&A
    question URL (base.source_url_is_specific).
    """
    params = {
        "search": query,
        "locale": "en-us",
        "facet": "category",
        "$filter": "category eq 'QnA'",
    }
    return f"{LEARN_QNA_RSS_ENDPOINT}?{urllib.parse.urlencode(params)}"


# --- text / date helpers -----------------------------------------------------

def clean_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", text or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def xml_child_text(parent: ET.Element, tag_name: str) -> str:
    if ":" in tag_name:
        tag_name = tag_name.split(":", 1)[1]
    for child in list(parent):
        if child.tag.split("}", 1)[-1] == tag_name:
            return "".join(child.itertext()).strip()
    return ""


def normalize_feed_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return date_part(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_learn_qna_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    return urllib.parse.urlunsplit(("https", host, parsed.path.rstrip("/"), "", ""))


def blocked_signature(text: str, *, status: int | None, content_type: str) -> str:
    lowered = (text or "").lower()
    if status in {401, 403}:
        return "blocked"
    if status == 429 or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "captcha" in lowered:
        return "captcha_challenge"
    if "access denied" in lowered or "request blocked" in lowered or "forbidden" in lowered:
        return "blocked"
    if "checking your browser" in lowered or "cloudflare" in lowered:
        return "browser_challenge"
    if "sign in" in lowered and "microsoft account" in lowered:
        return "login_or_auth_challenge"
    if not text:
        return "empty_body"
    if content_type and "html" in content_type.lower() and "xml" not in content_type.lower():
        return "html_response"
    return "none"


# --- transport (single testable seam) ----------------------------------------

def _fetch_feed_text(url: str, *, timeout: int = 30, max_bytes: int = 1_500_000) -> tuple[int, str, str]:
    """Fetch raw RSS text. Returns (status, content_type, text) on a 2xx response; raises
    LearnQnaAccessError on any HTTP/network failure. Tests monkeypatch THIS function."""
    request = urllib.request.Request(url, headers=FEED_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes)
            status = int(getattr(response, "status", 200) or 200)
            content_type = response.headers.get("content-type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            return status, content_type, raw.decode(charset, errors="replace")
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read(8000).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        signature = blocked_signature(body, status=exc.code, content_type=content_type)
        raise LearnQnaAccessError(
            f"http_{exc.code}_{signature}",
            status=exc.code,
            content_type=content_type,
            signature="blocked" if signature not in {"none", "empty_body"} or exc.code in {401, 403, 429} else "broken",
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise LearnQnaAccessError(f"network_{type(exc).__name__}", signature="network") from exc


# --- parsing -----------------------------------------------------------------

def parse_learn_qna_rss(text: str, *, source_type: str = DEFAULT_SOURCE_TYPE, source_name: str = DEFAULT_SOURCE_NAME) -> list[dict[str, Any]]:
    """Pure RSS 2.0 parser: search-RSS text -> candidate dicts. Raises ET.ParseError on
    malformed XML. Only specific Q&A question URLs survive."""
    root = ET.fromstring(text)
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall(".//item")
    candidates: list[dict[str, Any]] = []
    for item in items:
        candidate = learn_qna_item_candidate(item, source_type=source_type, source_name=source_name)
        if candidate:
            candidates.append(candidate)
    return candidates


def learn_qna_item_candidate(item: ET.Element, *, source_type: str, source_name: str) -> dict[str, Any] | None:
    title = xml_child_text(item, "title")
    link = xml_child_text(item, "link")
    canonical = canonical_learn_qna_url(link)
    # Only specific Learn Q&A question threads; generic search/category/docs URLs are dropped.
    if not canonical or not source_url_is_specific(canonical):
        return None
    description = xml_child_text(item, "description")
    source_date = normalize_feed_date(xml_child_text(item, "pubDate") or xml_child_text(item, "dc:date"))
    report_text = clean_html(" ".join([title, description]).strip())
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": canonical,
        "parent_title": title,
        "report_title": title,
        "report_text": report_text[:6000],
        "source_date": source_date,
    }


def request_learn_qna_feed(query: str, *, source_type: str = DEFAULT_SOURCE_TYPE, source_name: str = DEFAULT_SOURCE_NAME) -> list[dict[str, Any]]:
    """Fetch + parse one exact-term search. Raises LearnQnaAccessError (blocked/broken/
    network) on failure; returns [] when the feed is reachable but empty."""
    url = learn_qna_search_url(query)
    status, content_type, text = _fetch_feed_text(url)
    signature = blocked_signature(text[:4000], status=status, content_type=content_type)
    if signature not in {"none", "empty_body"}:
        raise LearnQnaAccessError(f"blocked:{signature}", status=status, content_type=content_type, signature="blocked")
    try:
        return parse_learn_qna_rss(text, source_type=source_type, source_name=source_name)
    except ET.ParseError as exc:
        raise LearnQnaAccessError(f"feed_parse_failed:{type(exc).__name__}", status=status, content_type=content_type, signature="broken") from exc


# --- pacing ------------------------------------------------------------------

learn_qna_sleep = time.sleep


def learn_qna_request_delay() -> float:
    try:
        return max(0.0, float(os.getenv("AUXSAYS_LEARN_QNA_REQUEST_DELAY_SECONDS", "0.35")))
    except ValueError:
        return 0.35


def pace_learn_qna_request() -> None:
    delay = learn_qna_request_delay()
    if delay > 0:
        learn_qna_sleep(delay)


# --- orchestration -----------------------------------------------------------

def collect_learn_qna_candidates(
    *,
    queries: list[str],
    context: Any,
    errors: list[dict[str, Any]],
    source_type: str = DEFAULT_SOURCE_TYPE,
    source_name: str = DEFAULT_SOURCE_NAME,
) -> list[dict[str, Any]]:
    """Discover candidate Learn Q&A question threads for a set of exact query terms.

    Runs one search-RSS request per query, de-duplicating by canonical question URL.
    Fetch failures are appended to ``errors`` (never raised) so the caller's method health
    becomes ``blocked``/``partial`` instead of crashing. Returned candidates are unfiltered
    discovery rows; the caller still applies exact KB/build identity, concrete-issue,
    specific-URL, and date gates.
    """
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_queries: set[str] = set()
    for raw_query in queries or []:
        query = str(raw_query or "").strip()
        key = query.lower()
        if not query or key in seen_queries:
            continue
        seen_queries.add(key)
        try:
            candidates = request_learn_qna_feed(query, source_type=source_type, source_name=source_name)
        except LearnQnaAccessError as exc:
            errors.append({
                "query": query,
                "source_url": learn_qna_search_url(query),
                "reason": f"learn_qna_search_fetch_failed:{exc.reason}",
                "blocked_signature": exc.signature,
            })
            pace_learn_qna_request()
            continue
        since = getattr(context, "since", None)
        for candidate in candidates:
            url = str(candidate.get("source_url") or "").strip().rstrip("/").lower()
            if not url or url in seen:
                continue
            if since and candidate.get("source_date") and date_part(candidate.get("source_date")) < since:
                continue
            seen.add(url)
            candidate = {**candidate, "matched_query": query}
            results.append(candidate)
        pace_learn_qna_request()
    return results
