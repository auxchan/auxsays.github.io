#!/usr/bin/env python3
"""Stack Exchange (Super User, Stack Overflow) question discovery for AUXSAYS.

WHY THIS SOURCE. PowerPoint had exactly one active discovery method (Microsoft Learn Q&A), and the
live PowerPoint pages showed one accepted report in total. Stack Exchange carries genuine
post-update PowerPoint reports that name an exact Click-to-Run build in the question body -- for
example a slideshow-annotation report on Build 20228.20124 that AUXSAYS could never see because
nothing fetched this site.

TRANSPORT. The official API at api.stackexchange.com/2.3, unauthenticated. Verified reachable from
CI-like environments; the plain HTML page returns 403 to a scripted user agent, so the API is the
only viable transport. A keyless client gets a per-day quota (300 at time of writing) and the
response carries ``quota_remaining``; the collector reports it as telemetry and stops early rather
than burning the budget.

WHAT THIS MODULE DOES AND DOES NOT DO. It ONLY discovers and normalizes candidate questions into
the shared candidate shape. It performs no acceptance decision: every candidate goes through the
same unchanged PowerPoint authority as Learn Q&A, so discovery diversity never becomes acceptance
divergence.

ATTRIBUTION SAFETY -- the load-bearing design choice. ``report_text`` is built from the QUESTION
title and QUESTION body only. Answers and comments are deliberately NOT concatenated into it, even
though the API can return them in the same call. A question is one author's report; folding an
answerer's text in would let a stranger's build become the asker's patch identity, which is exactly
the cross-participant borrowing AUXSAYS forbids. Same-author follow-up resolution is the separate,
already-existing concern of lib/context_resolution.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

API_BASE = "https://api.stackexchange.com/2.3"
DEFAULT_SOURCE_TYPE = "stack_exchange_question"
DEFAULT_SOURCE_NAME = "Stack Exchange"
ENDPOINT_FAMILY = "stack_exchange_api"

# Built-in filter that adds the question body to the default field set. Preferred over a generated
# custom filter id: `withbody` is documented and stable, and the body is all this module reads.
BODY_FILTER = "withbody"

SITE_NAMES = {
    "superuser": "Super User",
    "stackoverflow": "Stack Overflow",
}

USER_AGENT = "AUXSAYS-patch-evidence/1.0 (+https://auxsays.com)"
REQUEST_TIMEOUT = 30
MAX_BYTES = 2_000_000
PAGE_SIZE = 50
_MIN_REQUEST_INTERVAL = 0.4
_last_request_at = 0.0


class StackExchangeError(Exception):
    """Transport failure, carrying a stable reason token for method health."""

    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.endpoint_family = ENDPOINT_FAMILY


def error_reason(exc: Exception) -> str:
    if isinstance(exc, StackExchangeError):
        return exc.reason
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}_error"
    if isinstance(exc, urllib.error.URLError):
        return "network_unreachable"
    return type(exc).__name__


def clean_html(text: str) -> str:
    """Strip tags and collapse whitespace. The API returns rendered HTML bodies."""
    import re
    without = re.sub(r"(?is)<(script|style).*?</\1>|<[^>]+>", " ", text or "")
    return " ".join(unescape(without).split())


def question_url(site: str, question_id: Any) -> str:
    host = "superuser.com" if site == "superuser" else "stackoverflow.com"
    return f"https://{host}/questions/{question_id}"


def _pace() -> None:
    """Space requests. The API throttles aggressively on burst and answers with `backoff`."""
    global _last_request_at
    delta = time.monotonic() - _last_request_at
    if delta < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - delta)
    _last_request_at = time.monotonic()


def request_json(url: str) -> dict[str, Any]:
    _pace()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read(MAX_BYTES)
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        # 429/503 are throttling, not breakage. Naming them distinctly keeps method health honest:
        # "rate_limited" is a transient capacity signal, while http_4xx would read as a broken
        # endpoint and hide the fact that the source is fine and simply needs to be asked slower.
        if exc.code in (429, 503):
            raise StackExchangeError("rate_limited", status=exc.code) from exc
        raise StackExchangeError(f"http_{exc.code}_error", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise StackExchangeError("network_unreachable") from exc
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        raise StackExchangeError("payload_parse_failed", status=status) from exc
    if not isinstance(payload, dict):
        raise StackExchangeError("payload_not_object", status=status)
    if payload.get("error_id") or payload.get("error_name"):
        raise StackExchangeError(f"api_error_{payload.get('error_id') or 'unknown'}", status=status)
    return payload


def _api_url(path: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    return f"{API_BASE}/{path}?{query}"


def search_advanced_url(site: str, *, query: str = "", tagged: str = "", from_date: int | None = None) -> str:
    return _api_url("search/advanced", {
        "site": site,
        "q": query,
        "tagged": tagged,
        "fromdate": from_date,
        "sort": "creation",
        "order": "desc",
        "pagesize": PAGE_SIZE,
        "filter": BODY_FILTER,
    })


def item_candidate(item: dict[str, Any], *, site: str, source_type: str,
                   source_name: str) -> dict[str, Any] | None:
    """One API question -> one candidate, or None when it is not usable.

    `report_text` is the question's OWN title and body. Answers/comments are never folded in; see
    the module docstring on attribution safety.
    """
    question_id = item.get("question_id")
    if not question_id:
        return None
    link = str(item.get("link") or question_url(site, question_id))
    title = clean_html(str(item.get("title") or ""))
    body = clean_html(str(item.get("body") or ""))
    if not title and not body:
        return None
    created = item.get("creation_date")
    try:
        source_date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(created))) if created else ""
    except (TypeError, ValueError, OSError):
        source_date = ""
    report_text = " ".join(x for x in (title, body) if x)
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": link,
        "parent_title": title,
        "report_title": title,
        "report_text": report_text[:6000],
        "source_date": source_date,
        "stack_exchange_site": site,
        "stack_exchange_question_id": str(question_id),
        "stack_exchange_owner_id": str((item.get("owner") or {}).get("user_id") or ""),
    }


def collect_stack_exchange_candidates(
    *,
    sites: list[str],
    queries: list[str],
    tags_by_site: dict[str, str] | None,
    errors: list[dict[str, Any]],
    from_date: int | None = None,
    max_requests: int = 8,
    source_type: str = DEFAULT_SOURCE_TYPE,
) -> list[dict[str, Any]]:
    """Discover candidate questions across the given sites.

    Two routes are issued per site, because they fail differently: a TAG route finds PowerPoint
    questions whose author never wrote a build (recall), and a TEXT route finds a specific build
    token wherever it was written (precision). Neither alone is sufficient -- the calibration case
    is reachable by both, but most real questions only ever surface through one.
    """
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    requests_made = 0
    quota_remaining: int | None = None

    for site in sites:
        source_name = SITE_NAMES.get(site, site)
        routes: list[tuple[str, dict[str, Any]]] = []
        # Each site has its OWN tag ("microsoft-powerpoint" on Super User, "powerpoint" on Stack
        # Overflow). Sending one site's tag to the other returns nothing and still costs a request.
        site_tag = (tags_by_site or {}).get(site, "")
        if site_tag:
            routes.append(("tag", {"tagged": site_tag}))
        for query in queries:
            routes.append(("text", {"query": query}))

        for _route, params in routes:
            if requests_made >= max_requests:
                errors.append({"source_url": API_BASE,
                               "reason": f"request_budget_exhausted_after_{requests_made}"})
                return candidates
            url = search_advanced_url(site, from_date=from_date, **params)
            payload = None
            for attempt in range(3):
                # The budget bounds HTTP ATTEMPTS, not successes and not routes. Counting only
                # successful payloads let a 429 storm make 3 calls per route while the counter stayed
                # at zero -- measured at 18 calls against a declared budget of 4, on a keyless
                # ~300/day quota shared by every AUXSAYS run from this IP.
                if requests_made >= max_requests:
                    errors.append({"source_url": API_BASE,
                                   "reason": f"request_budget_exhausted_after_{requests_made}"})
                    return candidates
                requests_made += 1
                try:
                    payload = request_json(url)
                    break
                except StackExchangeError as exc:
                    if exc.reason == "rate_limited" and attempt < 2:
                        time.sleep(2 ** attempt * 3)      # 3s, 6s -- bounded, never a busy loop
                        continue
                    errors.append({"source_url": url, "reason": exc.reason})
                    break
                except Exception as exc:  # noqa: BLE001 - reason recorded for method health
                    errors.append({"source_url": url, "reason": error_reason(exc)})
                    break
            if payload is None:
                continue
            remaining = payload.get("quota_remaining")
            if isinstance(remaining, int):
                quota_remaining = remaining
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                candidate = item_candidate(item, site=site, source_type=source_type,
                                           source_name=source_name)
                if not candidate:
                    continue
                key = candidate["source_url"].rstrip("/").lower()
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)

    if quota_remaining is not None and quota_remaining <= 10:
        errors.append({"source_url": API_BASE, "reason": f"quota_low_{quota_remaining}"})
    return candidates
