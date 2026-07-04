"""Shared, product-agnostic Reddit evidence discovery.

Adapted from the DaVinci collector's proven Reddit transport / parse / fallback
logic and generalized so any product collector can discover candidate user
reports from one or more subreddits.

This module ONLY discovers and normalizes candidate posts into the shared
candidate shape (parent_title / report_title / report_text / source_url /
source_date / source_type / source_name). It never accepts, counts, or gates
anything on its own — every product collector still applies its own deterministic
acceptance gates (exact version, product context, concrete issue, specific URL,
date) downstream via row_from_candidate / apply_acceptance_gates. More discovery,
same gates.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError

from .base import date_part

REDDIT_USER_AGENT = os.getenv(
    "AUXSAYS_REDDIT_USER_AGENT",
    "script:com.auxsays.patch-intelligence:v1.0 (by /u/auxsays)",
)
JSON_HEADERS = {
    "Accept": "application/json, text/plain;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "close",
    "User-Agent": REDDIT_USER_AGENT,
}
FEED_HEADERS = {
    "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9, text/plain;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "close",
    "User-Agent": REDDIT_USER_AGENT,
}
DEFAULT_SOURCE_TYPE = "reddit_community_report"


class SourceAccessError(RuntimeError):
    def __init__(
        self,
        reason: str,
        *,
        status: int | None = None,
        content_type: str = "",
        blocked_signature: str = "",
        endpoint_family: str = "",
        headers_strategy: str = "",
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.content_type = content_type
        self.blocked_signature = blocked_signature
        self.endpoint_family = endpoint_family
        self.headers_strategy = headers_strategy


def error_reason(exc: Exception) -> str:
    if isinstance(exc, SourceAccessError):
        return exc.reason
    return type(exc).__name__


# --- URL builders (subreddit-parameterized) ---------------------------------

def search_url(subreddit: str) -> str:
    return f"https://www.reddit.com/r/{subreddit}/search.json"


def old_search_url(subreddit: str) -> str:
    return f"https://old.reddit.com/r/{subreddit}/search.json"


def listing_url(subreddit: str) -> str:
    return f"https://www.reddit.com/r/{subreddit}/new.json"


def old_listing_url(subreddit: str) -> str:
    return f"https://old.reddit.com/r/{subreddit}/new.json"


GLOBAL_SEARCH = "https://www.reddit.com/search.json"


def search_rss_url(subreddit: str) -> str:
    return f"https://www.reddit.com/r/{subreddit}/search.rss"


def old_search_rss_url(subreddit: str) -> str:
    return f"https://old.reddit.com/r/{subreddit}/search.rss"


def new_rss_url(subreddit: str) -> str:
    return f"https://www.reddit.com/r/{subreddit}/new/.rss"


def old_new_rss_url(subreddit: str) -> str:
    return f"https://old.reddit.com/r/{subreddit}/new/.rss"


# --- diagnostics / pacing (product-agnostic) --------------------------------

def extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    if not match:
        return ""
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()


def clean_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def reddit_headers_strategy(headers: dict[str, str]) -> str:
    strategy = "reddit_descriptive_ua_json"
    if headers.get("Authorization"):
        strategy += "+bearer"
    return strategy


def reddit_diagnostics_enabled() -> bool:
    value = os.getenv("AUXSAYS_REDDIT_DIAGNOSTICS")
    if value is not None:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true"


def sanitize_diagnostic_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    sensitive = {"access_token", "token", "client_secret", "authorization", "bearer"}
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    clean_query = urllib.parse.urlencode([
        (key, "[redacted]" if key.lower() in sensitive else value)
        for key, value in query_pairs
    ])
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, clean_query, ""))


def blocked_signature(text: str, *, status: int | None, content_type: str, headers: dict[str, str] | None = None) -> str:
    lowered = (text or "").lower()
    header_text = " ".join(f"{key}:{value}" for key, value in (headers or {}).items()).lower()
    if status == 429 or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "cf-ray" in header_text or "cloudflare" in lowered or "checking your browser" in lowered:
        return "cloudflare_or_browser_challenge"
    if status == 403:
        return "blocked"
    if "blocked" in lowered and "text/html" in content_type.lower():
        return "blocked"
    if "login" in lowered and "reddit" in lowered:
        return "login_or_auth_challenge"
    if "captcha" in lowered:
        return "captcha_challenge"
    if "text/html" in content_type.lower() and "application/json" not in content_type.lower():
        title = extract_title(text)
        return f"html_response:{title[:60]}" if title else "html_response"
    if not text:
        return "empty_body"
    return "none"


def emit_reddit_fetch_diagnostic(
    *,
    url: str,
    endpoint_family: str,
    status: int | None,
    content_type: str,
    signature: str,
    headers_strategy: str,
    parsed_as_feed: bool | None = None,
    candidate_count: int | None = None,
) -> None:
    if not reddit_diagnostics_enabled():
        return
    payload = {
        "event": "reddit_fetch",
        "url": sanitize_diagnostic_url(url),
        "endpoint_family": endpoint_family,
        "http_status": status,
        "content_type": content_type,
        "blocked_signature": signature,
        "headers_strategy": headers_strategy,
    }
    if parsed_as_feed is not None:
        payload["parsed_as_feed"] = parsed_as_feed
    if candidate_count is not None:
        payload["candidate_count"] = candidate_count
    print(f"[auxsays:diagnostic] {json.dumps(payload, sort_keys=True, ensure_ascii=True)}")


def reddit_request_delay() -> float:
    try:
        return max(0.0, float(os.getenv("AUXSAYS_REDDIT_REQUEST_DELAY_SECONDS", "0.35")))
    except ValueError:
        return 0.35


def pace_reddit_request() -> None:
    delay = reddit_request_delay()
    if delay > 0:
        time.sleep(delay)


def with_raw_json(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key == "raw_json" for key, _value in pairs):
        pairs.append(("raw_json", "1"))
    query = urllib.parse.urlencode(pairs)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


# --- transport (product-agnostic) -------------------------------------------

def request_json(url: str, *, endpoint_family: str = "reddit_json") -> Any:
    headers = dict(JSON_HEADERS)
    token = os.getenv("REDDIT_BEARER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers_strategy = reddit_headers_strategy(headers)
    request_url = with_raw_json(url)
    request = urllib.request.Request(request_url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            content_type = response.headers.get("content-type", "")
            status = int(getattr(response, "status", 200) or 200)
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            signature = blocked_signature(text[:4000], status=status, content_type=content_type, headers=dict(response.headers.items()))
            emit_reddit_fetch_diagnostic(
                url=request_url,
                endpoint_family=endpoint_family,
                status=status,
                content_type=content_type,
                signature=signature,
                headers_strategy=headers_strategy,
            )
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise SourceAccessError(
                    f"json_decode_failed:{type(exc).__name__}",
                    status=status,
                    content_type=content_type,
                    blocked_signature=signature,
                    endpoint_family=endpoint_family,
                    headers_strategy=headers_strategy,
                ) from exc
    except HTTPError as exc:
        body = exc.read(8000).decode("utf-8", errors="replace")
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        signature = blocked_signature(body, status=exc.code, content_type=content_type, headers=dict(exc.headers.items()) if exc.headers else {})
        emit_reddit_fetch_diagnostic(
            url=request_url,
            endpoint_family=endpoint_family,
            status=exc.code,
            content_type=content_type,
            signature=signature,
            headers_strategy=headers_strategy,
        )
        raise SourceAccessError(
            f"http_{exc.code}_{exc.reason}",
            status=exc.code,
            content_type=content_type,
            blocked_signature=signature,
            endpoint_family=endpoint_family,
            headers_strategy=headers_strategy,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        emit_reddit_fetch_diagnostic(
            url=request_url,
            endpoint_family=endpoint_family,
            status=None,
            content_type="",
            signature=type(exc).__name__,
            headers_strategy=headers_strategy,
        )
        raise SourceAccessError(
            f"network_{type(exc).__name__}",
            endpoint_family=endpoint_family,
            blocked_signature=type(exc).__name__,
            headers_strategy=headers_strategy,
        ) from exc


def reddit_failure_summary(failures: list[dict[str, Any]]) -> str:
    pieces: list[str] = []
    for failure in failures:
        family = str(failure.get("endpoint_family") or "reddit_json")
        reason = str(failure.get("reason") or "fetch_failed")
        signature = str(failure.get("blocked_signature") or "")
        piece = f"{family}={reason}"
        if signature and signature != "none":
            piece += f":{signature}"
        pieces.append(piece)
    return "all_reddit_endpoint_attempts_failed[" + ";".join(pieces[:4]) + "]"


def request_reddit_json_with_fallback(attempts: list[tuple[str, str]]) -> Any:
    failures: list[dict[str, Any]] = []
    for endpoint_family, url in attempts:
        try:
            payload = request_json(url, endpoint_family=endpoint_family)
            pace_reddit_request()
            return payload
        except SourceAccessError as exc:
            failures.append({
                "endpoint_family": endpoint_family,
                "reason": exc.reason,
                "status": exc.status,
                "content_type": exc.content_type,
                "blocked_signature": exc.blocked_signature,
            })
            pace_reddit_request()
            continue
    raise SourceAccessError(reddit_failure_summary(failures), status=failures[0].get("status") if failures else None)


def request_reddit_feed(url: str, *, endpoint_family: str, source_type: str, source_name: str) -> list[dict[str, Any]]:
    headers = dict(FEED_HEADERS)
    headers_strategy = "reddit_descriptive_ua_feed"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(1_000_000)
            content_type = response.headers.get("content-type", "")
            status = int(getattr(response, "status", 200) or 200)
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            candidates = reddit_feed_candidates(text, source_type=source_type, source_name=source_name)
            signature = blocked_signature(text[:4000], status=status, content_type=content_type, headers=dict(response.headers.items()))
            emit_reddit_fetch_diagnostic(
                url=url,
                endpoint_family=endpoint_family,
                status=status,
                content_type=content_type,
                signature=signature,
                headers_strategy=headers_strategy,
                parsed_as_feed=True,
                candidate_count=len(candidates),
            )
            return candidates
    except HTTPError as exc:
        body = exc.read(8000).decode("utf-8", errors="replace")
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        signature = blocked_signature(body, status=exc.code, content_type=content_type, headers=dict(exc.headers.items()) if exc.headers else {})
        emit_reddit_fetch_diagnostic(
            url=url,
            endpoint_family=endpoint_family,
            status=exc.code,
            content_type=content_type,
            signature=signature,
            headers_strategy=headers_strategy,
            parsed_as_feed=False,
            candidate_count=0,
        )
        raise SourceAccessError(
            f"http_{exc.code}_{exc.reason}",
            status=exc.code,
            content_type=content_type,
            blocked_signature=signature,
            endpoint_family=endpoint_family,
            headers_strategy=headers_strategy,
        ) from exc
    except ET.ParseError as exc:
        emit_reddit_fetch_diagnostic(
            url=url,
            endpoint_family=endpoint_family,
            status=None,
            content_type="",
            signature=f"feed_parse_failed:{type(exc).__name__}",
            headers_strategy=headers_strategy,
            parsed_as_feed=False,
            candidate_count=0,
        )
        raise SourceAccessError(
            f"feed_parse_failed:{type(exc).__name__}",
            endpoint_family=endpoint_family,
            blocked_signature=type(exc).__name__,
            headers_strategy=headers_strategy,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        emit_reddit_fetch_diagnostic(
            url=url,
            endpoint_family=endpoint_family,
            status=None,
            content_type="",
            signature=type(exc).__name__,
            headers_strategy=headers_strategy,
            parsed_as_feed=False,
            candidate_count=0,
        )
        raise SourceAccessError(
            f"network_{type(exc).__name__}",
            endpoint_family=endpoint_family,
            blocked_signature=type(exc).__name__,
            headers_strategy=headers_strategy,
        ) from exc


# --- candidate mappers (source_type / source_name parameterized) ------------

def reddit_candidate(data: dict[str, Any], *, source_type: str, source_name: str) -> dict[str, Any]:
    created = data.get("created_utc")
    source_date = ""
    if isinstance(created, (int, float)):
        source_date = datetime.fromtimestamp(float(created), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    permalink = str(data.get("permalink") or "")
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": f"https://www.reddit.com{permalink}" if permalink.startswith("/") else str(data.get("url") or ""),
        "parent_title": str(data.get("title") or ""),
        "report_title": str(data.get("title") or ""),
        "report_text": " ".join([str(data.get("title") or ""), str(data.get("selftext") or "")]).strip(),
        "source_date": source_date,
    }


def reddit_feed_candidates(text: str, *, source_type: str, source_name: str) -> list[dict[str, Any]]:
    root = ET.fromstring(text)
    candidates: list[dict[str, Any]] = []
    if root.tag.endswith("feed"):
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            candidate = reddit_atom_entry_candidate(entry, source_type=source_type, source_name=source_name)
            if candidate:
                candidates.append(candidate)
        return candidates
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            candidate = reddit_rss_item_candidate(item, source_type=source_type, source_name=source_name)
            if candidate:
                candidates.append(candidate)
    return candidates


def reddit_atom_entry_candidate(entry: ET.Element, *, source_type: str, source_name: str) -> dict[str, Any] | None:
    title = xml_child_text(entry, "title")
    url = atom_entry_link(entry)
    if not reddit_source_url_is_usable(url):
        return None
    summary = xml_child_text(entry, "summary") or xml_child_text(entry, "content")
    source_date = xml_child_text(entry, "published") or xml_child_text(entry, "updated")
    text = clean_html(" ".join([title, summary]).strip())
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": canonical_reddit_url(url),
        "parent_title": title,
        "report_title": title,
        "report_text": text[:4000],
        "source_date": source_date,
    }


def reddit_rss_item_candidate(item: ET.Element, *, source_type: str, source_name: str) -> dict[str, Any] | None:
    title = xml_child_text(item, "title")
    url = xml_child_text(item, "link")
    if not reddit_source_url_is_usable(url):
        return None
    description = xml_child_text(item, "description")
    source_date = normalize_feed_date(xml_child_text(item, "pubDate") or xml_child_text(item, "dc:date"))
    text = clean_html(" ".join([title, description]).strip())
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": canonical_reddit_url(url),
        "parent_title": title,
        "report_title": title,
        "report_text": text[:4000],
        "source_date": source_date,
    }


def xml_child_text(parent: ET.Element, tag_name: str) -> str:
    if ":" in tag_name:
        tag_name = tag_name.split(":", 1)[1]
    for child in list(parent):
        if child.tag.split("}", 1)[-1] == tag_name:
            return "".join(child.itertext()).strip()
    return ""


def atom_entry_link(entry: ET.Element) -> str:
    fallback = ""
    for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
        href = str(link.attrib.get("href") or "").strip()
        rel = str(link.attrib.get("rel") or "alternate").strip()
        if not href:
            continue
        if rel == "alternate":
            return href
        fallback = fallback or href
    return fallback


def reddit_source_url_is_usable(url: str) -> bool:
    parsed = urllib.parse.urlsplit(str(url or ""))
    return "reddit.com" in parsed.netloc.lower() and "/comments/" in parsed.path.lower()


def canonical_reddit_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    host = "www.reddit.com" if "reddit.com" in parsed.netloc.lower() else parsed.netloc
    return urllib.parse.urlunsplit(("https", host, parsed.path, "", ""))


def normalize_feed_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# --- attempt builders (subreddit-parameterized) -----------------------------

def _search_attempts(subreddit: str, query: str, params: dict[str, str]) -> list[tuple[str, str]]:
    attempts: list[tuple[str, str]] = []
    encoded = urllib.parse.urlencode(params)
    token = os.getenv("REDDIT_BEARER_TOKEN")
    if token:
        attempts.append(("reddit_search_oauth", f"https://oauth.reddit.com/r/{subreddit}/search?{encoded}"))
    global_params = dict(params)
    global_params.pop("restrict_sr", None)
    global_params["q"] = f"subreddit:{subreddit} {query}"
    attempts.extend([
        ("reddit_search_www_json", f"{search_url(subreddit)}?{encoded}"),
        ("reddit_search_old_json", f"{old_search_url(subreddit)}?{encoded}"),
        ("reddit_search_global_json", f"{GLOBAL_SEARCH}?{urllib.parse.urlencode(global_params)}"),
    ])
    return attempts


def _listing_attempts(subreddit: str, params: dict[str, str]) -> list[tuple[str, str]]:
    encoded = urllib.parse.urlencode(params)
    attempts: list[tuple[str, str]] = []
    token = os.getenv("REDDIT_BEARER_TOKEN")
    if token:
        attempts.append(("reddit_listing_oauth", f"https://oauth.reddit.com/r/{subreddit}/new?{encoded}"))
    attempts.extend([
        ("reddit_listing_www_json", f"{listing_url(subreddit)}?{encoded}"),
        ("reddit_listing_old_json", f"{old_listing_url(subreddit)}?{encoded}"),
    ])
    return attempts


def _search_feed_attempts(subreddit: str, query: str) -> list[tuple[str, str]]:
    params = {"q": query, "restrict_sr": "1", "sort": "new", "t": "year"}
    encoded = urllib.parse.urlencode(params)
    return [
        ("reddit_search_www_atom", f"{search_rss_url(subreddit)}?{encoded}"),
        ("reddit_search_old_atom", f"{old_search_rss_url(subreddit)}?{encoded}"),
    ]


def _listing_feed_attempts(subreddit: str) -> list[tuple[str, str]]:
    return [
        ("reddit_new_www_atom", new_rss_url(subreddit)),
        ("reddit_new_old_atom", old_new_rss_url(subreddit)),
    ]


# --- orchestration ----------------------------------------------------------

def _candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join([
        str(candidate.get("parent_title") or ""),
        str(candidate.get("report_title") or ""),
        str(candidate.get("report_text") or ""),
    ]).lower()


def _matches_hint(candidate: dict[str, Any], hints: list[str]) -> bool:
    if not hints:
        return True
    text = _candidate_text(candidate)
    return any(hint in text for hint in hints)


def _add(results: list[dict[str, Any]], seen: set[str], candidate: dict[str, Any]) -> None:
    url = str(candidate.get("source_url") or "").strip().rstrip("/").lower()
    if not url or url in seen:
        return
    seen.add(url)
    results.append(candidate)


def collect_reddit_candidates(
    *,
    subreddits: Any,
    queries: list[str],
    context: Any,
    errors: list[dict[str, Any]],
    source_type: str = DEFAULT_SOURCE_TYPE,
    version_hints: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Discover candidate user-report posts across one or more subreddits.

    Runs JSON search (per query, paginated) -> JSON new listing -> RSS/Atom feed
    fallback for each subreddit, de-duplicating by canonical post URL. Fetch
    failures are appended to ``errors`` (never raised) so the caller's method
    health becomes ``blocked``/``partial`` instead of crashing. Returned
    candidates are unfiltered discovery rows; the caller still applies exact
    version / product / issue / URL / date gates.
    """
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    hints = [str(h or "").strip().lower() for h in (version_hints or []) if str(h or "").strip()]
    for raw_sub in list(subreddits or []):
        subreddit = str(raw_sub or "").strip().strip("/")
        if not subreddit:
            continue
        source_name = f"r/{subreddit}"
        _collect_search(subreddit, queries, context, errors, results, seen, source_type, source_name)
        _collect_listing(subreddit, context, errors, results, seen, source_type, source_name, hints)
        _collect_feed(subreddit, queries, context, errors, results, seen, source_type, source_name, hints)
    return results


def _collect_search(
    subreddit: str,
    queries: list[str],
    context: Any,
    errors: list[dict[str, Any]],
    results: list[dict[str, Any]],
    seen: set[str],
    source_type: str,
    source_name: str,
) -> None:
    seen_queries: set[str] = set()
    consecutive_failures = 0
    for query in queries:
        key = str(query or "").strip().lower()
        if not key or key in seen_queries:
            continue
        seen_queries.add(key)
        after: str | None = None
        for _page in range(max(1, int(getattr(context, "max_pages", 1) or 1))):
            params = {"q": query, "restrict_sr": "1", "sort": "new", "t": "year", "limit": "50"}
            if after:
                params["after"] = after
            try:
                payload = request_reddit_json_with_fallback(_search_attempts(subreddit, query, params))
            except Exception as exc:
                errors.append({
                    "query": query,
                    "source_url": f"{search_url(subreddit)}?{urllib.parse.urlencode(params)}",
                    "reason": f"reddit_search_fetch_failed:{error_reason(exc)}",
                })
                consecutive_failures += 1
                break
            consecutive_failures = 0
            children = (((payload or {}).get("data") or {}).get("children") or [])
            for child in children:
                data = child.get("data") if isinstance(child, dict) else None
                if isinstance(data, dict):
                    _add(results, seen, reddit_candidate(data, source_type=source_type, source_name=source_name))
            after = ((payload or {}).get("data") or {}).get("after")
            if not after:
                break
        if consecutive_failures >= 3:
            break


def _collect_listing(
    subreddit: str,
    context: Any,
    errors: list[dict[str, Any]],
    results: list[dict[str, Any]],
    seen: set[str],
    source_type: str,
    source_name: str,
    hints: list[str],
) -> None:
    since = getattr(context, "since", None)
    after: str | None = None
    for _page in range(max(1, int(getattr(context, "max_pages", 1) or 1))):
        params = {"limit": "100"}
        if after:
            params["after"] = after
        try:
            payload = request_reddit_json_with_fallback(_listing_attempts(subreddit, params))
        except Exception as exc:
            errors.append({
                "source_url": f"{listing_url(subreddit)}?{urllib.parse.urlencode(params)}",
                "reason": f"reddit_listing_fetch_failed:{error_reason(exc)}",
            })
            break
        children = (((payload or {}).get("data") or {}).get("children") or [])
        for child in children:
            data = child.get("data") if isinstance(child, dict) else None
            if not isinstance(data, dict):
                continue
            candidate = reddit_candidate(data, source_type=source_type, source_name=source_name)
            if since and candidate.get("source_date") and date_part(candidate.get("source_date")) < since:
                continue
            if not _matches_hint(candidate, hints):
                continue
            _add(results, seen, candidate)
        after = ((payload or {}).get("data") or {}).get("after")
        if not after:
            break


def _collect_feed(
    subreddit: str,
    queries: list[str],
    context: Any,
    errors: list[dict[str, Any]],
    results: list[dict[str, Any]],
    seen: set[str],
    source_type: str,
    source_name: str,
    hints: list[str],
) -> None:
    since = getattr(context, "since", None)
    attempts: list[tuple[str, str]] = []
    for query in queries[:6]:
        attempts.extend(_search_feed_attempts(subreddit, query))
    attempts.extend(_listing_feed_attempts(subreddit))
    for family, url in attempts:
        try:
            feed_candidates = request_reddit_feed(url, endpoint_family=family, source_type=source_type, source_name=source_name)
        except Exception as exc:
            errors.append({
                "source_url": url,
                "reason": f"reddit_feed_fetch_failed:{error_reason(exc)}",
            })
            continue
        for candidate in feed_candidates:
            if since and candidate.get("source_date") and date_part(candidate.get("source_date")) < since:
                continue
            if not _matches_hint(candidate, hints):
                continue
            _add(results, seen, candidate)
