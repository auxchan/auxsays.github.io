#!/usr/bin/env python3
"""Windows 11 Forum (elevenforum.com) discovery: opening posts only, listing-walked, hard-capped.

SHIPPED DISABLED. Nothing in this module runs unless ``microsoft_windows`` is told to
(``AUXSAYS_ENABLE_WINDOWS_ELEVENFORUM_DISCOVERY`` exactly ``true``), and the shared ownership
manifest still refuses its identities on a write. See the ENGINEERING_LEDGER entry for the
activation blocker.

WHAT IT DOES. Walks three approved support listings, hydrates the threads whose TITLE already carries
a patch cue, and turns each thread's OPENING POST into one candidate. Candidates are offered to the
UNCHANGED Windows acceptance authority (``microsoft_windows.evaluate_candidates``); this module
decides nothing about what counts.

WHY LISTINGS AND NOT THE PUBLISHED RSS FEED. Measured on 2026-11-04, same three categories:
  * every ``/questions/<category>/index.rss`` returned HTTP 200 but carries only 15 items, so three
    requests reach 45 threads and there is no second page;
  * ``<pubDate>`` is LAST ACTIVITY, not the post date (a 2021 sticky was stamped 2026-11-04), so the
    feed cannot supply the original post date either; the date still has to come from the thread's
    JSON-LD ``datePublished``;
  * ``content:encoded`` is a truncated preview of the first post, so it is not a substitute for the
    hydrated opening post.
The feed is the simpler request but reaches about a third of the depth and removes none of the
hydrations. The listing walk (3 categories x up to 3 pages, 9 requests) reaches about 130 threads and
exposes the pinned/sticky flag and last-activity time that the title prefilter and the window use.
ONE approach is shipped; the feed is not a second path.

DATES. A listing time is last activity and is used for exactly one thing: skipping a thread whose
LAST activity is older than the window, because a thread cannot have been posted after its last
activity. It is never a post date. The post date is the JSON-LD ``datePublished`` of the opening post;
a thread that does not carry a valid one yields no candidate, with no fallback to a listing time.

OPENING POST ONLY. The page's JSON-LD is a ``WebPage`` whose ``mainEntity`` is a
``DiscussionForumPosting`` for the first post (the earlier recon note called it a QAPage; the live
pages say otherwise, and a ``QAPage``/``Question`` wrapper is accepted too). Replies are never read,
because folding a stranger's build into the reporter's text is how a report lands on the wrong patch.

POLITENESS, ENFORCED BELOW THE LOOPS. ``Session.get`` refuses any URL outside the approved shapes
(so /search/, /members/ and /whats-new/ are unreachable by construction), refuses the 10th listing
request and the 41st hydration, and sleeps so consecutive requests are at least 1.5 s apart. Those
checks sit in the one function every request goes through rather than in the loops that call it, so a
future caller cannot spend more than the budget by forgetting a counter.

NEVER BYPASS A CHALLENGE. HTTP 403, 401, 429, 503 and a 200 whose body is a bot-check page are
classified ``blocked`` and discovery STOPS; it does not retry, rotate headers or try another host.
"""
from __future__ import annotations

import difflib
import html as html_lib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

BASE = "https://www.elevenforum.com"
HOST = "www.elevenforum.com"
DEFAULT_SOURCE_TYPE = "elevenforum_thread"
DEFAULT_SOURCE_NAME = "Windows 11 Forum"
ENDPOINT_FAMILY = "elevenforum_listing"

# --- the approved request budget (GPT Decision 2). Change these only with the decision. -------------
APPROVED_LISTINGS: tuple[str, ...] = ("install-update-activate", "general-support", "bsod")
MAX_LISTING_PAGES = 3
MAX_LISTING_REQUESTS = len(APPROVED_LISTINGS) * MAX_LISTING_PAGES
MAX_HYDRATIONS = 40
MAX_REQUESTS_PER_CYCLE = MAX_LISTING_REQUESTS + MAX_HYDRATIONS
MIN_REQUEST_INTERVAL = 1.5
# Three refused hydrations in a row is a block, not bad luck; stop rather than keep asking.
MAX_CONSECUTIVE_BLOCKED = 3
DEFAULT_WINDOW_DAYS = 45

# Store a short excerpt and the link, not the post. The acceptance authority reads this text.
EXCERPT_CHARS = 2000
REQUEST_TIMEOUT = 30
MAX_BYTES = 1_500_000
# The forum opened in mid 2021; a date before this is a parsing accident, not a post.
EARLIEST_PLAUSIBLE_POST = "2021-01-01"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AUXSAYS-patch-evidence/1.0 (+https://auxsays.com)")
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# robots.txt (measured 2026-11-04) disallows /search/, /members/, /whats-new/ for every agent. The
# allow-list below is the positive form: only these two URL shapes can ever be requested.
_LISTING_PATH_RE = re.compile(
    r"^/questions/(?P<cat>" + "|".join(re.escape(c) for c in APPROVED_LISTINGS) + r")/"
    r"(?:page-(?P<page>[1-9]))?$")
_THREAD_PATH_RE = re.compile(r"^/t/(?P<slug>[a-z0-9][a-z0-9-]*)\.(?P<id>\d{1,9})/?$")

BLOCKED_REASONS = frozenset({"http_401_blocked", "http_403_blocked", "challenge_page", "rate_limited"})

CHALLENGE_MARKERS = (
    "just a moment", "checking your browser", "attention required", "cf-browser-verification",
    "challenge-platform", "enable javascript and cookies to continue", "verify you are human",
)

# The cheap first stage: a title that already says it is about a patch. Same vocabulary the Windows
# authority itself keys on (a KB, an OS build, a feature train) plus the word "update".
TITLE_CUE_RE = re.compile(
    r"\bKB\s?\d{6,7}\b|(?<!\d)2\d{4}\.\d{3,5}(?!\d)|\b2\dH[12]\b|\bupdat\w*|\bpatch\w*",
    re.I)

ACCEPTED_POST_TYPES = frozenset({"DiscussionForumPosting", "Question"})


class ElevenForumError(Exception):
    """Transport or policy failure carrying a stable reason token for method health."""

    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.endpoint_family = ENDPOINT_FAMILY


def error_reason(exc: Exception) -> str:
    if isinstance(exc, ElevenForumError):
        return exc.reason
    if isinstance(exc, urllib.error.URLError):
        return "network_unreachable"
    return type(exc).__name__


# --- URL policy --------------------------------------------------------------------------------

def listing_url(category: str, page: int) -> str:
    if category not in APPROVED_LISTINGS:
        raise ElevenForumError("listing_not_approved")
    if not 1 <= page <= MAX_LISTING_PAGES:
        raise ElevenForumError("listing_page_out_of_budget")
    suffix = "" if page == 1 else f"page-{page}"
    return f"{BASE}/questions/{category}/{suffix}"


def classify_url(url: str) -> str:
    """'listing', 'thread', or '' (not requestable). Positive allow-list; everything else refused."""
    parts = urllib.parse.urlsplit(str(url or "").strip())
    if parts.scheme != "https" or parts.netloc.lower() != HOST or parts.query or parts.fragment:
        return ""
    # A listing is one of the three categories at pages 1..MAX_LISTING_PAGES.
    match = _LISTING_PATH_RE.match(parts.path)
    if match:
        page = match.group("page")
        return "listing" if page is None or 1 <= int(page) <= MAX_LISTING_PAGES else ""
    if _THREAD_PATH_RE.match(parts.path):
        return "thread"
    return ""


def thread_id_of(url: str) -> str:
    match = _THREAD_PATH_RE.match(urllib.parse.urlsplit(str(url or "").strip()).path)
    return match.group("id") if match else ""


def canonical_thread_url(url: str) -> str:
    """https://www.elevenforum.com/t/<slug>.<id> with no trailing slash, or '' if not a thread."""
    parts = urllib.parse.urlsplit(str(url or "").strip())
    if parts.scheme not in {"http", "https"} or parts.netloc.lower() not in {HOST, "elevenforum.com"}:
        return ""
    match = _THREAD_PATH_RE.match(parts.path)
    if not match:
        return ""
    return f"{BASE}/t/{match.group('slug')}.{match.group('id')}"


# --- response classification -------------------------------------------------------------------

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def classify_response(status: int, body: str) -> str | None:
    """None when the response is usable, else a stable reason token.

    A 200 can be a challenge page, so the body is inspected. A genuine XenForo page announces itself
    (``<html id="XF"``), and a user's post that merely contains the words "just a moment" must not be
    read as a challenge, so a marker counts only in the <title>, or in a page that is not XenForo.
    """
    lowered = (body or "")[:20000].lower()
    title_match = _TITLE_RE.search(body or "")
    title = (title_match.group(1) if title_match else "").lower()
    challenged = any(m in title for m in CHALLENGE_MARKERS) or (
        'id="xf"' not in lowered and any(m in lowered for m in CHALLENGE_MARKERS))
    if status == 403:
        return "challenge_page" if challenged else "http_403_blocked"
    if status == 401:
        return "http_401_blocked"
    if status in (429, 503):
        return "challenge_page" if challenged else "rate_limited"
    if status >= 400:
        return f"http_{status}_error"
    if challenged:
        return "challenge_page"
    return None


Transport = Callable[[str], "tuple[int, str]"]


def urllib_transport(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=dict(REQUEST_HEADERS))
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # noqa: S310
            raw = response.read(MAX_BYTES)
            return int(response.status), raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read(200_000)
        except Exception:  # noqa: BLE001
            raw = b""
        return int(exc.code), raw.decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise ElevenForumError("network_unreachable") from exc
    except TimeoutError as exc:
        raise ElevenForumError("timeout") from exc


class Session:
    """Every request this adapter makes goes through ``get``. Caps and pacing live here."""

    def __init__(self, transport: Transport | None = None, *,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 min_interval: float = MIN_REQUEST_INTERVAL) -> None:
        self._transport = transport or urllib_transport
        self._clock = clock
        self._sleep = sleep
        self.min_interval = min_interval
        self._last_at: float | None = None
        self.requested: list[str] = []
        self.gaps: list[float] = []
        self.counts = {"listing": 0, "thread": 0}

    @property
    def total_requests(self) -> int:
        return self.counts["listing"] + self.counts["thread"]

    def get(self, url: str) -> str:
        kind = classify_url(url)
        if not kind:
            raise ElevenForumError("url_not_allowed")
        cap = MAX_LISTING_REQUESTS if kind == "listing" else MAX_HYDRATIONS
        if self.counts[kind] >= cap:
            raise ElevenForumError("request_budget_exhausted")
        now = self._clock()
        if self._last_at is not None:
            wait = self.min_interval - (now - self._last_at)
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
            self.gaps.append(now - self._last_at)
        self._last_at = now
        self.counts[kind] += 1
        self.requested.append(url)
        status, body = self._transport(url)
        reason = classify_response(int(status), body)
        if reason:
            raise ElevenForumError(reason, status=int(status))
        return body


# --- listing parsing ---------------------------------------------------------------------------

_ITEM_SPLIT = '<div class="structItem structItem--thread'
_TITLE_LINK_RE = re.compile(
    r'class="structItem-title"[^>]*>.*?<a href="(?P<href>/t/[^"]+)"[^>]*>(?P<title>.*?)</a>', re.S)
_LATEST_RE = re.compile(r'structItem-latestDate[^>]*datetime="(?P<dt>[^"]+)"')


def _iso_date(value: str) -> str:
    """YYYY-MM-DD of an ISO/XenForo datetime, '' if it does not parse."""
    text = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return ""
    try:
        datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return ""
    return match.group(0)


def parse_listing(page_html: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in (page_html or "").split(_ITEM_SPLIT)[1:]:
        link = _TITLE_LINK_RE.search(block)
        if not link:
            continue
        url = canonical_thread_url(urllib.parse.urljoin(BASE, link.group("href")))
        if not url:
            continue
        latest = _LATEST_RE.search(block)
        rows.append({
            "source_url": url,
            "thread_id": thread_id_of(url),
            "title": " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", link.group("title"))).split()),
            "sticky": "structItem-status--sticky" in block,
            # LAST ACTIVITY. Used only to skip threads that went quiet before the window.
            "last_activity": _iso_date(latest.group("dt")) if latest else "",
        })
    return rows


def title_has_patch_cue(title: str) -> bool:
    return bool(TITLE_CUE_RE.search(title or ""))


# --- opening-post parsing ----------------------------------------------------------------------

_LDJSON_RE = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$")


def valid_post_date(value: Any, *, today: str) -> str:
    """YYYY-MM-DD of a well-formed ISO datePublished inside the plausible range, else ''."""
    text = str(value or "").strip()
    if not _ISO_RE.match(text):
        return ""
    day = _iso_date(text)
    if not day:
        return ""
    if day < EARLIEST_PLAUSIBLE_POST:
        return ""
    limit = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    return "" if day > limit else day


def _posting_nodes(blocks: list[Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def visit(node: Any, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(node, list):
            for item in node:
                visit(item, depth + 1)
            return
        if not isinstance(node, dict):
            return
        graph = node.get("@graph")
        if isinstance(graph, list):
            visit(graph, depth + 1)
        main = node.get("mainEntity")
        if isinstance(main, dict) and main.get("@type") in ACCEPTED_POST_TYPES:
            found.append(main)
        elif node.get("@type") in ACCEPTED_POST_TYPES and "mainEntity" not in node:
            found.append(node)

    visit(blocks)
    return found


def parse_thread(url: str, page_html: str, *, today: str | None = None) -> tuple[dict[str, Any] | None, str]:
    """One thread page -> (candidate, '') or (None, reason). Deterministic and fail-closed.

    The candidate is built from the OPENING POST only (the JSON-LD ``mainEntity``); replies are not
    read. The post date is the opening post's ``datePublished``; with none valid there is NO candidate.
    """
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    want_id = thread_id_of(url)
    if not want_id:
        return None, "not_a_thread_url"
    blocks: list[Any] = []
    for match in _LDJSON_RE.finditer(page_html or ""):
        try:
            blocks.append(json.loads(match.group(1)))
        except ValueError:
            continue
    if not blocks:
        return None, "no_json_ld"
    posts = _posting_nodes(blocks)
    if not posts:
        return None, "no_opening_post_node"
    post = posts[0]
    claimed = canonical_thread_url(str(post.get("url") or post.get("@id") or ""))
    if not claimed or thread_id_of(claimed) != want_id:
        # The JSON-LD must describe the thread that was requested. A mismatch is a different page.
        return None, "thread_url_mismatch"
    day = valid_post_date(post.get("datePublished"), today=today)
    if not day:
        return None, "no_valid_date_published"
    title = " ".join(html_lib.unescape(str(post.get("headline") or post.get("name") or "")).split())
    raw_body = str(post.get("text") or post.get("articleBody") or "")
    body = " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", raw_body)).split())
    if not body:
        # A title is a headline, not a report: no opening-post text, no candidate.
        return None, "no_opening_post_text"
    return {
        "source_type": DEFAULT_SOURCE_TYPE,
        "source_name": DEFAULT_SOURCE_NAME,
        "source_url": claimed,
        "parent_title": title,
        "report_title": title,
        "report_text": " ".join(x for x in (title, body) if x)[:EXCERPT_CHARS],
        "source_date": day,
        "original_post_date": day,
        "thread_id": want_id,
    }, ""


# --- duplicate candidates (annotation only) ----------------------------------------------------

def normalized_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower()).split())


def text_similarity(a: str, b: str) -> float:
    na, nb = normalized_text(a)[:800], normalized_text(b)[:800]
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb, autojunk=False).ratio()


def duplicate_candidates(candidates: list[dict[str, Any]], references: list[dict[str, str]],
                         *, threshold: float = 0.9) -> list[dict[str, Any]]:
    """Cross-source text SIMILARITY, reported as a duplicate CANDIDATE and nothing more.

    Highly similar text is not proof of one report (a templated question, a quoted post, one person
    posting in two places for two different patches are all possible), so this function only
    returns annotations. It never removes or changes a candidate; the shared one-report-one-patch
    claims map, keyed on URL, remains the only thing that refuses a row.
    """
    out: list[dict[str, Any]] = []
    for cand in candidates:
        for ref in references:
            score = text_similarity(cand.get("report_text", ""), ref.get("text", ""))
            if score >= threshold:
                out.append({"source_url": cand.get("source_url", ""),
                            "similar_to": ref.get("source_url", ""), "similarity": round(score, 3),
                            "conclusive": False})
    return out


# --- discovery ---------------------------------------------------------------------------------

@dataclass
class Discovery:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    rejected_threads: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    telemetry: dict[str, Any] = field(default_factory=dict)


def default_since(days: int = DEFAULT_WINDOW_DAYS) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(1, days))).strftime("%Y-%m-%d")


def discover(session: Session, *, since: str, today: str | None = None,
             should_stop: Callable[[], bool] | None = None) -> Discovery:
    """Walk the approved listings, then hydrate the newest patch-titled threads. Bounded throughout."""
    result = Discovery()
    errors = result.errors
    listed: list[dict[str, Any]] = []
    listing_ok = 0
    listing_errors = 0
    blocked = False
    abort_reason = ""

    for category in APPROVED_LISTINGS:
        if blocked:
            break
        for page in range(1, MAX_LISTING_PAGES + 1):
            url = listing_url(category, page)
            try:
                body = session.get(url)
            except ElevenForumError as exc:
                listing_errors += 1
                errors.append({"source_url": url, "reason": exc.reason})
                if exc.reason in BLOCKED_REASONS:
                    blocked, abort_reason = True, exc.reason
                break  # a failed page ends this category; a blocked one ends everything
            listing_ok += 1
            rows = parse_listing(body)
            listed.extend(rows)
            live = [r for r in rows if not r["sticky"]]
            # Pages run newest-activity first. When every unpinned thread on a page went quiet before
            # the window, the next page cannot hold anything inside it.
            if not live or all(r["last_activity"] and r["last_activity"] < since for r in live):
                break

    seen: set[str] = set()
    eligible: list[dict[str, Any]] = []
    skipped = {"sticky": 0, "outside_window": 0, "no_title_cue": 0, "duplicate_thread": 0}
    for row in listed:
        if row["sticky"]:
            skipped["sticky"] += 1
            continue
        if row["last_activity"] and row["last_activity"] < since:
            skipped["outside_window"] += 1
            continue
        if not title_has_patch_cue(row["title"]):
            skipped["no_title_cue"] += 1
            continue
        if row["thread_id"] in seen:
            skipped["duplicate_thread"] += 1
            continue
        seen.add(row["thread_id"])
        eligible.append(row)
    eligible.sort(key=lambda r: (r["last_activity"], int(r["thread_id"])), reverse=True)
    capped = len(eligible) > MAX_HYDRATIONS
    to_hydrate = eligible[:MAX_HYDRATIONS]

    attempted = hydration_errors = consecutive_blocked = 0
    stopped_early = False
    if not blocked:
        for row in to_hydrate:
            if should_stop is not None and should_stop():
                stopped_early, abort_reason = True, "run_budget_expired"
                break
            attempted += 1
            try:
                page = session.get(row["source_url"])
            except ElevenForumError as exc:
                hydration_errors += 1
                errors.append({"source_url": row["source_url"], "reason": exc.reason})
                if exc.reason in BLOCKED_REASONS:
                    consecutive_blocked += 1
                    if consecutive_blocked >= MAX_CONSECUTIVE_BLOCKED:
                        blocked, abort_reason = True, exc.reason
                        break
                else:
                    consecutive_blocked = 0
                continue
            consecutive_blocked = 0
            candidate, reason = parse_thread(row["source_url"], page, today=today)
            if candidate is None:
                result.rejected_threads.append({"source_url": row["source_url"], "reason": reason})
                continue
            result.candidates.append(candidate)

    result.telemetry = {
        "listing_requests": session.counts["listing"],
        "listing_ok": listing_ok,
        "listing_errors": listing_errors,
        "listed": len(listed),
        "eligible": len(eligible),
        "skipped": skipped,
        "attempted": attempted,
        "hydration_requests": session.counts["thread"],
        "hydration_errors": hydration_errors,
        "hydrated": len(result.candidates),
        "unparseable": len(result.rejected_threads),
        # By design the cap leaves eligible threads unread; that is recall, not degradation.
        "capped": capped,
        "blocked": blocked,
        "aborted": bool(blocked or stopped_early),
        "abort_reason": abort_reason,
        "total_requests": session.total_requests,
    }
    return result
