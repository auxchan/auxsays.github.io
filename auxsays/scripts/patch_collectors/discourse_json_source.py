"""Shared, product-agnostic Discourse JSON evidence discovery.

Discourse forums (community.openai.com, forum.figma.com, and many vendor communities)
expose the same documented anonymous JSON search endpoint::

    https://<forum-host>/search.json?q=<exact term>

so discovery is keyword-anchored (an exact patch version or patch title) and
CI-reliable — no login, no HTML scraping, no AI.

This module ONLY discovers and normalizes candidate posts into the shared candidate
shape (parent_title / report_title / report_text / source_url / source_date /
source_type / source_name / matched_query). It never accepts, counts, or gates
anything — every product collector still applies its own deterministic acceptance
gates (exact-version identity, concrete issue, specific URL, date) downstream via
``base.apply_acceptance_gates``. More discovery, same gates: discovery can never set
``counted=true`` or fabricate consensus.

No product collector registers this method yet; adding one is a separate, explicit
activation decision per product.

Determinism / safety:
- Only specific Discourse topic URLs (``/t/<slug>/<topic_id>[/<post_number>]``) become
  candidates; search pages, categories, and hostless payload rows are dropped.
- One bounded transient retry per request (408/429/5xx) honouring a bounded seconds-form
  Retry-After via the shared runtime-budget backoff policy; hard 4xx never retries.
- Every request is charged to the active RuntimeBudget (``note_request``) and its body
  read is total-wall-clock- and byte-bounded (``bounded_read``), so a slow-drip response
  or a runaway payload can never stall a collector past its deadline.
- Fetch/parse/empty states are surfaced explicitly (blocked / rate_limited / broken /
  network) so a product collector's method health is honest instead of crashing.
"""
from __future__ import annotations

from . import runtime_budget as rb

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError

DEFAULT_SOURCE_TYPE = "discourse_forum_report"
ENDPOINT_FAMILY = "discourse_json"

# Bytes allowed per search response body. Live Discourse search pages run ~60 KB; the
# cap bounds a runaway body without truncating a legitimate response (a truncated body
# fails JSON parsing loudly and is classified broken, never silently half-parsed).
MAX_RESPONSE_BYTES = 1_500_000

# One bounded retry for transient statuses only; everything else fails terminally.
MAX_TRANSIENT_RETRIES = 1

REPORT_TEXT_CAP = 6000

DISCOURSE_USER_AGENT = os.getenv(
    "AUXSAYS_DISCOURSE_USER_AGENT",
    "script:com.auxsays.patch-intelligence:v1.0 (+https://auxsays.com)",
)
REQUEST_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "close",
    "User-Agent": DISCOURSE_USER_AGENT,
}


class DiscourseAccessError(RuntimeError):
    """Raised for transport/HTTP/parse failures. ``signature`` classifies the failure
    ("blocked" for auth/403/challenge, "rate_limited" for 429, "broken" for
    parser/schema, "network" for unreachable) so the collector can map it to honest
    method health."""

    def __init__(self, reason: str, *, status: int | None = None, signature: str = "", endpoint_family: str = ENDPOINT_FAMILY) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.signature = signature
        self.endpoint_family = endpoint_family


def error_reason(exc: Exception) -> str:
    return exc.reason if isinstance(exc, DiscourseAccessError) else type(exc).__name__


# --- URL + query builders ----------------------------------------------------

def forum_base(base_url: str) -> str:
    """Normalize a configured forum base URL to ``https://<host>`` (path-less)."""
    parsed = urllib.parse.urlsplit(str(base_url or "").strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise DiscourseAccessError(f"invalid_forum_base:{base_url!r}", signature="broken")
    return f"https://{parsed.netloc.lower()}"


def discourse_search_url(base_url: str, query: str) -> str:
    return f"{forum_base(base_url)}/search.json?{urllib.parse.urlencode({'q': query})}"


def topic_url(base_url: str, topic: dict[str, Any], post_number: int) -> str:
    """The canonical, specific topic/post URL — the only URL shape emitted."""
    topic_id = topic.get("id")
    slug = str(topic.get("slug") or "").strip()
    if not isinstance(topic_id, int) or topic_id <= 0 or not slug:
        return ""
    url = f"{forum_base(base_url)}/t/{slug}/{topic_id}"
    if isinstance(post_number, int) and post_number > 1:
        url = f"{url}/{post_number}"
    return url


# --- text / date helpers -----------------------------------------------------

def clean_text(text: str) -> str:
    text = re.sub(r"(?s)<[^>]+>", " ", str(text or ""))
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_discourse_date(value: str) -> str:
    """Discourse timestamps are ISO 8601 (e.g. ``2026-08-10T19:04:42.600Z``); normalize
    to a second-precision UTC ``...Z`` string, or return '' when unparseable."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def blocked_signature(text: str, *, status: int | None) -> str:
    lowered = (text or "")[:4000].lower()
    if status in {401, 403}:
        return "blocked"
    if status == 429 or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "captcha" in lowered:
        return "captcha_challenge"
    if "checking your browser" in lowered or "cloudflare" in lowered:
        return "browser_challenge"
    if "access denied" in lowered or "request blocked" in lowered:
        return "blocked"
    return "none"


# --- transport (single testable seam) ----------------------------------------

def _fetch_json_text(url: str, *, timeout: int = 30, max_bytes: int = MAX_RESPONSE_BYTES) -> tuple[int, str]:
    """Fetch raw JSON text for ONE request. Returns (status, text) on a 2xx response;
    raises DiscourseAccessError on any HTTP/network failure. Tests monkeypatch THIS
    function. The body read is total-wall-clock- and byte-bounded by the active
    RuntimeBudget (plain bounded read when no budget is set)."""
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=rb.request_timeout(rb.get_run_budget(), timeout)) as response:
            raw = rb.bounded_read(response, budget=rb.get_run_budget(), endpoint_family=ENDPOINT_FAMILY, max_bytes=max_bytes)
            status = int(getattr(response, "status", 200) or 200)
            charset = response.headers.get_content_charset() or "utf-8"
            return status, raw.decode(charset, errors="replace")
    except HTTPError as exc:
        body = ""
        retry_after = rb.parse_retry_after(exc.headers)
        try:
            body = exc.read(8000).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        signature = blocked_signature(body, status=exc.code)
        if signature in {"none"}:
            signature = "rate_limited" if exc.code == 429 else ("blocked" if exc.code in {401, 403} else "broken")
        error = DiscourseAccessError(f"http_{exc.code}_{signature}", status=exc.code, signature=signature)
        error.retry_after = retry_after  # bounded later by backoff_delay/note_backoff
        raise error from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise DiscourseAccessError(f"network_{type(exc).__name__}", signature="network") from exc


def request_search_json(base_url: str, query: str, *, timeout: int = 30) -> dict[str, Any]:
    """One search request with at most ONE bounded transient retry (408/429/5xx),
    honouring a bounded seconds-form Retry-After. Charges every attempt to the active
    RuntimeBudget; a method budget bound raises MethodBudgetExhausted (NORMAL — the
    caller books terminal method health). Raises DiscourseAccessError on terminal
    transport/HTTP/parse failure; returns the parsed payload dict otherwise."""
    url = discourse_search_url(base_url, query)
    budget = rb.get_run_budget()
    attempt = 0
    while True:
        if budget is not None:
            budget.note_request()
        try:
            status, text = _fetch_json_text(url, timeout=timeout)
            break
        except DiscourseAccessError as exc:
            transient = rb.is_transient(exc.status, exc.signature if exc.signature == "rate_limited" else "")
            if not transient or attempt >= MAX_TRANSIENT_RETRIES:
                raise
            cfg = budget.cfg if budget is not None else rb.BudgetConfig()
            delay = rb.backoff_delay(cfg, attempt, getattr(exc, "retry_after", None))
            if budget is not None:
                delay = budget.note_backoff(delay)
            else:
                delay = rb.budget_capped_sleep(delay, None)
            if delay > 0:
                discourse_sleep(delay)
            attempt += 1
    signature = blocked_signature(text, status=status)
    if signature != "none":
        raise DiscourseAccessError(f"blocked:{signature}", status=status, signature="blocked" if signature != "rate_limited" else "rate_limited")
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise DiscourseAccessError(f"json_parse_failed:{type(exc).__name__}", status=status, signature="broken") from exc
    if not isinstance(payload, dict):
        raise DiscourseAccessError("json_shape_unexpected:not_object", status=status, signature="broken")
    return payload


# --- parsing -----------------------------------------------------------------

def search_candidates(base_url: str, payload: dict[str, Any], *, source_type: str = DEFAULT_SOURCE_TYPE, source_name: str = "") -> list[dict[str, Any]]:
    """Pure parser: a /search.json payload -> candidate dicts (no network, no gating).

    Posts are joined to their topics for the parent title and the canonical specific
    URL; a post whose topic is missing from the payload is dropped (never a fabricated
    parent), as is any row that cannot form a specific ``/t/<slug>/<id>`` URL.
    """
    host_name = source_name or urllib.parse.urlsplit(forum_base(base_url)).netloc
    topics_by_id: dict[int, dict[str, Any]] = {}
    for topic in payload.get("topics") or []:
        if isinstance(topic, dict) and isinstance(topic.get("id"), int):
            topics_by_id[topic["id"]] = topic
    candidates: list[dict[str, Any]] = []
    for post in payload.get("posts") or []:
        if not isinstance(post, dict):
            continue
        topic = topics_by_id.get(post.get("topic_id"))
        if not isinstance(topic, dict):
            continue
        post_number = post.get("post_number") if isinstance(post.get("post_number"), int) else 1
        url = topic_url(base_url, topic, post_number)
        if not url:
            continue
        parent_title = clean_text(topic.get("title") or "")
        blurb = clean_text(post.get("blurb") or "")
        report_text = " ".join(part for part in (parent_title, blurb) if part).strip()
        candidates.append({
            "source_type": source_type,
            "source_name": host_name,
            "source_url": url,
            "parent_title": parent_title,
            "report_title": parent_title,
            "report_text": report_text[:REPORT_TEXT_CAP],
            "source_date": normalize_discourse_date(str(post.get("created_at") or "")),
        })
    return candidates


# --- pacing ------------------------------------------------------------------

discourse_sleep = time.sleep


def discourse_request_delay() -> float:
    try:
        return max(0.0, float(os.getenv("AUXSAYS_DISCOURSE_REQUEST_DELAY_SECONDS", "0.35")))
    except ValueError:
        return 0.35


def pace_discourse_request() -> None:
    delay = rb.budget_capped_sleep(discourse_request_delay(), rb.get_run_budget())
    if delay > 0:
        discourse_sleep(delay)


# --- orchestration -----------------------------------------------------------

def collect_discourse_candidates(
    *,
    base_url: str,
    queries: list[str],
    context: Any = None,
    errors: list[dict[str, Any]],
    source_type: str = DEFAULT_SOURCE_TYPE,
    source_name: str = "",
) -> list[dict[str, Any]]:
    """Discover candidate Discourse posts for a set of exact query terms.

    Runs one bounded search request per distinct query, de-duplicating candidates by
    canonical post URL. Fetch/parse failures are appended to ``errors`` (never raised)
    so the caller's method health becomes blocked/partial instead of crashing; only a
    RuntimeBudget bound (MethodBudgetExhausted) propagates, which the caller already
    books as terminal method health. Returned candidates are unfiltered discovery rows;
    the caller still applies exact-version identity, concrete-issue, specific-URL, and
    date gates. ``context.since`` (YYYY-MM-DD), when present, drops older candidates.
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
            payload = request_search_json(base_url, query)
        except DiscourseAccessError as exc:
            errors.append({
                "query": query,
                "source_url": discourse_search_url(base_url, query),
                "reason": f"discourse_search_fetch_failed:{exc.reason}",
                "blocked_signature": exc.signature,
            })
            pace_discourse_request()
            continue
        since = getattr(context, "since", None)
        for candidate in search_candidates(base_url, payload, source_type=source_type, source_name=source_name):
            url = str(candidate.get("source_url") or "").strip().rstrip("/").lower()
            if not url or url in seen:
                continue
            if since and candidate.get("source_date") and candidate["source_date"][:10] < since:
                continue
            seen.add(url)
            results.append({**candidate, "matched_query": query})
        pace_discourse_request()
    return results
