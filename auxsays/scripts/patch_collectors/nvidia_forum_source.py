"""NVIDIA GeForce forum: the two default views, read exactly the way the forum page reads them.

WHAT IS READ, AND WHY ONLY THAT (measured 2026-11-19, FORUM_MEASUREMENT / FORUM_CRITIC). The forum at
www.nvidia.com/en-us/geforce/forums/ is a JavaScript page; its content comes from the forum's API
host. For the two DEFAULT views a visitor sees, the page itself makes these calls and no others:

* a community's default view: its pinned topics and its 15 most recently active topics
  (``/communities/pinned`` and ``/communities/topics`` with sort=recent, page 1, size 15);
* a topic's default view: the topic (``/topics?id=T``), then its LATEST 25 top-level comments with
  the replies the API embeds (``/topics/comments`` page 1, anchored on the topic's own last comment,
  direction "+before" -- the call the page makes with no comment anchor and no page number).

Everything else is content the main site keeps away from crawlers, and the API serving the same
content does not change that: page 2 and later (``?commentPage=`` / ``?topicPage=``, which
www.nvidia.com's robots.txt disallows), the oldest-first sort, ``?comment=`` anchors into older
comments, reply expansion beyond the embedded replies, search, user pages and the all-communities
listing. ``permitted_request`` refuses every one of those BEFORE a request is made, and a test pins
it. The www.nvidia.com robots.txt is re-read every cycle and the www page each call stands for must
be allowed by it; the API host's own robots.txt is re-read too (measured 404, which RFC 9309 reads
as "no policy"; a 5xx or unreachable policy skips the cycle; a policy that appears is applied).

POLITENESS. One cycle per 12 hours whatever the lane's cron (the cadence is kept in the state file),
at most ``MAX_REQUESTS_PER_CYCLE`` requests spaced ``REQUEST_SPACING_SECONDS`` apart, an honest
client name, no login, no cookies, no retries. A thread whose last activity has not moved is not
re-read.

STOP RULES. HTTP 401/403/429/451, a bot challenge, an HTML page where JSON was expected or a body
refusing automated access raises ``AccessRefused``: the refusal is persisted in the state file and
the method stays suspended -- zero requests -- until a reviewed change sets
``ACCESS_REFUSAL_CLEARED_AT`` to a time after it that has passed (the same rule as the official
NVIDIA lane). A redirect is followed only to the host asked (lib.http ``redirect_hosts``, checked
before the hop is made); anything else is a ``SourceAuthorityStop`` with nothing sent there. A
response missing the fields identity rests on is a ``SchemaIntegrityStop``. None of these deletes a
stored row: a stored report stops counting only through audited withdrawal.

WHAT THE WINDOW CANNOT SEE. Only the latest 25 top-level comments of a thread are visible, and only
the replies the API embeds. ``compare_windows`` implements the coverage-gap contract (GPT G47 s2):
the last successful window's comment ids and creation times are kept, the next window is compared
with them, and a POSSIBLE gap is recorded with its reason. The number or content of unseen comments
is never inferred and never fetched: no page is ever read to repair a gap. None of this claims the
forum is monitored comprehensively.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lib.http import RedirectRefused, fetch_text
from patch_collectors import base

SOURCE_ID = "nvidia_geforce_forum"
API_HOST = "api-forums.nvidia.com"
WWW_HOST = "www.nvidia.com"
API_BASE = f"https://{API_HOST}/forums-api/1.0"
WWW_FORUM_PATH = "/en-us/geforce/forums"
ROBOTS_URLS = {WWW_HOST: f"https://{WWW_HOST}/robots.txt", API_HOST: f"https://{API_HOST}/robots.txt"}

# The communities whose default views are read: Game-Ready Drivers (13), where NVIDIA posts each Game
# Ready release's feedback thread, and Studio Drivers (39). Slugs are the forum's own (its slug
# generator over the community title), used only to name the www page a call stands for.
COMMUNITIES: tuple[tuple[int, str], ...] = ((13, "game-ready-drivers"), (39, "studio-drivers"))
# Staff feedback threads that were already unpinned or quiet when this collector was built, so a
# first cycle can still read their default view. Each is read like any other topic: its title must
# still qualify (staff author, exact version AND family) before it counts as patch-specific.
SEED_THREADS: tuple[tuple[int, int], ...] = ((13, 592433), (13, 592767))

COMMUNITY_PAGE_SIZE = 15
COMMENT_PAGE_SIZE = 25
MAX_REQUESTS_PER_CYCLE = 16
MAX_THREADS_PER_CYCLE = 5
MIN_CYCLE_INTERVAL = timedelta(hours=11, minutes=30)
REQUEST_SPACING_SECONDS = 4.0
TIMEOUT_SECONDS = 30
MAX_BYTES = 2_000_000
THREAD_RETENTION_DAYS = 45
MAX_STATE_THREADS = 40

USER_AGENT = "AUXSAYS-Patch-Evidence/1.0 (+https://auxsays.com; read-only, low rate)"
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
ACCESS_REFUSAL_CODES = frozenset({401, 403, 429, 451})
# Set ONLY by a reviewed change, to a time after a recorded refusal (ISO 8601, UTC). A future time
# clears nothing until it arrives, then clears that one refusal once.
ACCESS_REFUSAL_CLEARED_AT = ""

STATE_PATH = base.ROOT / "_data" / "nvidia_forum_state.json"
STATE_SCHEMA_VERSION = 1

# Carried in the state file for audit; never rendered on a page.
PROVENANCE = {
    "source_origin": "NVIDIA GeForce forum (user reports)",
    "collection_method": "forum default views",
    "collection_authorization": "owner risk acceptance; NVIDIA permission not established",
}

_REJECTION_RE = re.compile(
    r"access denied|forbidden|not authori[sz]ed|unauthori[sz]ed|too many requests|rate[\s-]*limit"
    r"|captcha|are you a robot|automated (?:access|requests?|traffic|queries)|request blocked"
    r"|you have been blocked", re.I)


class AccessRefused(RuntimeError):
    """The forum refused automated access. Persisted; the method stays suspended."""


class SchemaIntegrityStop(RuntimeError):
    """A response is not the shape this collector was built and tested against."""


class SourceAuthorityStop(RuntimeError):
    """A host or redirect this collector was not approved for."""


class RobotsStop(RuntimeError):
    """A robots policy disallows the view, or cannot be read: the cycle is skipped."""


class ForbiddenRequest(RuntimeError):
    """A request outside the two default views. Raised before anything is sent."""


class RequestBudgetExhausted(RuntimeError):
    """The per-cycle request ceiling was reached."""


class TransportError(RuntimeError):
    """Any other failed request (5xx, network). Not a refusal."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


# --- the forum's own slugs and page URLs ------------------------------------------------------------

def forum_slug(text: Any) -> str:
    """The forum page's own slug generator (SlugGenerator.generate(' ' + title)), reproduced."""
    value = re.sub(r"\s", "-", str(text or "").strip()).lower()
    value = re.sub(r"[^a-z0-9-]", "", value)[:100]
    return re.sub(r"-+", "-", value)


def www_topic_path(community_id: int, community_slug: str, topic_id: int, topic_slug: str = "") -> str:
    path = f"{WWW_FORUM_PATH}/{community_slug}/{int(community_id)}/{int(topic_id)}/"
    return path + (f"{topic_slug}/" if topic_slug else "")


def comment_url(community_id: int, community_slug: str, topic_id: int, topic_slug: str,
                comment_id: int) -> str:
    """The forum's own link to one comment (its `?comment=` route parameter). Stored for audit and
    shown as a link; never requested."""
    return (f"https://{WWW_HOST}{www_topic_path(community_id, community_slug, topic_id, topic_slug)}"
            f"?comment={int(comment_id)}")


# --- the request guard ------------------------------------------------------------------------------

def community_view_urls(community_id: int) -> tuple[str, str]:
    query = urllib.parse.urlencode([("id", int(community_id)), ("type", "all"), ("sort", "recent"),
                                    ("_page", 1), ("_pageSize", COMMUNITY_PAGE_SIZE),
                                    ("status", "default")])
    return (f"{API_BASE}/communities/pinned?{query}", f"{API_BASE}/communities/topics?{query}")


def topic_url(topic_id: int) -> str:
    return f"{API_BASE}/topics?" + urllib.parse.urlencode([("id", int(topic_id))])


def topic_comments_url(topic_id: int, last_comment_id: int) -> str:
    return f"{API_BASE}/topics/comments?" + urllib.parse.urlencode([
        ("id", int(topic_id)), ("_page", 1), ("_pageSize", COMMENT_PAGE_SIZE),
        ("_anchorValue", int(last_comment_id)), ("_anchorDirection", "+before"),
        ("_anchorOffset", 0), ("includeGhosted", 0)])


_COMMUNITY_QUERY = {"type": "all", "sort": "recent", "_page": "1",
                    "_pageSize": str(COMMUNITY_PAGE_SIZE), "status": "default"}
_COMMENTS_QUERY = {"_page": "1", "_pageSize": str(COMMENT_PAGE_SIZE), "_anchorDirection": "+before",
                   "_anchorOffset": "0", "includeGhosted": "0"}


def permitted_request(url: str, anchors: dict[int, int] | None = None) -> tuple[bool, str]:
    """Is this one of the default-view calls (or a robots file)? Returns (ok, reason).

    Exact shapes only: every parameter must be present with the default view's value and nothing
    may be added. `anchors` maps a topic id to the last comment id its own `/topics` response named
    in THIS cycle; a comments call anchored anywhere else is an anchor into older comments.
    """
    try:
        parts = urllib.parse.urlsplit(str(url or ""))
        port = parts.port
    except ValueError:
        return False, "unparseable_url"
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or port not in (None, 443) or parts.username or parts.password \
            or parts.fragment:
        return False, "not_plain_https"
    if host not in (WWW_HOST, API_HOST):
        return False, "host_not_approved"
    if parts.path == "/robots.txt":
        return (not parts.query, "robots_with_query" if parts.query else "")
    if host != API_HOST:
        return False, "www_page_not_requested"
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query = dict(pairs)
    if len(query) != len(pairs):
        return False, "duplicate_parameter"
    if re.search(r"page", parts.query, re.I) and ("_page" not in query or query.get("_page") != "1"):
        return False, "page_beyond_first"
    path = parts.path
    configured = {cid for cid, _slug in COMMUNITIES}
    if path in ("/forums-api/1.0/communities/pinned", "/forums-api/1.0/communities/topics"):
        cid = query.get("id", "")
        rest = {k: v for k, v in query.items() if k != "id"}
        if not cid.isdigit() or int(cid) not in configured:
            return False, "community_not_configured"
        if rest != _COMMUNITY_QUERY:
            return False, "community_view_not_default"
        return True, ""
    if path == "/forums-api/1.0/topics":
        if set(query) != {"id"} or not query["id"].isdigit():
            return False, "topic_view_not_default"
        return True, ""
    if path == "/forums-api/1.0/topics/comments":
        tid = query.get("id", "")
        anchor = query.get("_anchorValue", "")
        rest = {k: v for k, v in query.items() if k not in ("id", "_anchorValue")}
        if not tid.isdigit() or not anchor.isdigit() or rest != _COMMENTS_QUERY:
            return False, "comment_view_not_default"
        if (anchors or {}).get(int(tid)) != int(anchor):
            return False, "anchor_not_the_topics_last_comment"
        return True, ""
    return False, "endpoint_not_a_default_view"


# --- robots ------------------------------------------------------------------------------------------

@dataclass
class RobotsPolicy:
    """RFC 9309 groups for `*` (and for this client's own token, if a group names it)."""

    rules: list[tuple[bool, str]] = field(default_factory=list)
    status: str = "parsed"          # parsed | unavailable (4xx: no policy)

    def allows(self, path_and_query: str) -> bool:
        target = path_and_query or "/"
        best: tuple[int, bool] | None = None
        for allow, pattern in self.rules:
            if not pattern:
                continue
            if _robots_match(pattern, target):
                key = (len(pattern), allow)
                if best is None or key > best:
                    best = key
        return True if best is None else best[1]


def _robots_match(pattern: str, target: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.match(regex + ("$" if anchored else ""), target) is not None


def parse_robots(text: str, agent_token: str = "auxsays-patch-evidence") -> RobotsPolicy:
    groups: list[tuple[set[str], list[tuple[bool, str]]]] = []
    agents: set[str] = set()
    rules: list[tuple[bool, str]] = []
    in_rules = False
    for raw in str(text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = set(), [], False
            agents.add(value.lower())
        elif key in ("allow", "disallow"):
            in_rules = True
            rules.append((key == "allow", value))
    if agents:
        groups.append((agents, rules))
    own = [r for a, r in groups if any(tok != "*" and agent_token.startswith(tok) for tok in a)]
    chosen = own or [r for a, r in groups if "*" in a]
    return RobotsPolicy(rules=[rule for group in chosen for rule in group])


# --- transport ---------------------------------------------------------------------------------------

def _host(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""


def _sleep(seconds: float) -> None:      # replaced by tests
    time.sleep(seconds)


class Transport:
    """Every request of a cycle goes through here: guard, budget, spacing, redirect bound."""

    def __init__(self, state: dict[str, Any] | None, *, max_requests: int = MAX_REQUESTS_PER_CYCLE):
        self.state = state
        self.max_requests = max_requests
        self.requests: list[str] = []
        self.anchors: dict[int, int] = {}
        self._last = 0.0

    def remaining(self) -> int:
        return self.max_requests - len(self.requests)

    def _refusal(self, detail: str) -> AccessRefused:
        at = base.utc_now()
        if isinstance(self.state, dict):
            self.state["access_refused"] = {"at": at, "detail": detail}
        return AccessRefused(f"access refused by the NVIDIA forum ({detail}); collection is suspended "
                             "until a reviewed change clears it")

    def get(self, url: str) -> str:
        ok, reason = permitted_request(url, self.anchors)
        if not ok:
            raise ForbiddenRequest(f"refusing a request outside the default views ({reason})")
        if self.remaining() <= 0:
            raise RequestBudgetExhausted(f"request ceiling of {self.max_requests} reached")
        if self.requests:
            wait = REQUEST_SPACING_SECONDS - (time.monotonic() - self._last)
            if wait > 0:
                _sleep(wait)
        host = _host(url)
        self.requests.append(url)
        self._last = time.monotonic()
        try:
            result = fetch_text(url, timeout=TIMEOUT_SECONDS, headers=REQUEST_HEADERS, retries=0,
                                max_bytes=MAX_BYTES, redirect_hosts=frozenset({host}))
        except RedirectRefused as exc:
            raise SourceAuthorityStop(
                f"{host} redirected to {_host(exc.destination) or 'an unnamed destination'} "
                f"(HTTP {exc.code}); the redirect was not followed and nothing was sent there") from None
        except RuntimeError as exc:
            message = str(exc)
            code = re.search(r"\bHTTP (\d{3})\b", message)
            if code and int(code.group(1)) in ACCESS_REFUSAL_CODES:
                raise self._refusal(f"HTTP {code.group(1)}") from None
            if "Browser challenge" in message:
                raise self._refusal("bot challenge") from None
            raise TransportError(message[:200], int(code.group(1)) if code else None) from None
        if _host(result.final_url or url) != host:
            raise SourceAuthorityStop(f"{host} answered from {_host(result.final_url)}")
        return (result.text or "").lstrip("﻿")

    def get_json(self, url: str) -> dict[str, Any]:
        text = self.get(url).strip()
        if text.startswith("<"):
            raise self._refusal("an HTML page was returned where JSON was expected")
        try:
            payload = json.loads(text)
        except ValueError:
            if _REJECTION_RE.search(text[:4000]):
                raise self._refusal("the response refused automated access") from None
            raise SchemaIntegrityStop("a forum response does not parse as JSON") from None
        if not isinstance(payload, dict):
            raise SchemaIntegrityStop("a forum response is not a JSON object")
        if payload.get("success") is not True:
            if _REJECTION_RE.search(json.dumps(payload)[:4000]):
                raise self._refusal("the response refused automated access")
            raise SchemaIntegrityStop("a forum response reports success=false")
        return payload


def read_robots(transport: Transport) -> dict[str, RobotsPolicy]:
    """Both robots files, every cycle. A refusal raises AccessRefused; anything that leaves the
    policy unknown raises RobotsStop (skip the cycle)."""
    policies: dict[str, RobotsPolicy] = {}
    for host, url in ROBOTS_URLS.items():
        try:
            text = transport.get(url)
        except TransportError as exc:
            if host == API_HOST and exc.code is not None and 400 <= exc.code < 500:
                # Measured 2026-11-19: 404 with a JSON error body. RFC 9309 s2.3.1.3: unavailable,
                # i.e. no policy of its own. The www policy still governs the content (see below).
                policies[host] = RobotsPolicy(status="unavailable")
                continue
            raise RobotsStop(f"robots policy of {host} could not be read ({exc}); cycle skipped") from None
        if text.lstrip().startswith("<"):
            raise RobotsStop(f"robots policy of {host} came back as a web page; cycle skipped")
        policies[host] = parse_robots(text)
    return policies


def check_robots(policies: dict[str, RobotsPolicy], api_url: str, www_path: str) -> None:
    """The www page a call stands for must be allowed by www.nvidia.com's policy, and the call itself
    by the API host's own policy when it has one."""
    www = policies.get(WWW_HOST)
    if www is None or not www.allows(www_path):
        raise RobotsStop(f"www.nvidia.com robots.txt disallows {www_path}; cycle skipped")
    api = policies.get(API_HOST)
    parts = urllib.parse.urlsplit(api_url)
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    if api is not None and api.status == "parsed" and not api.allows(target):
        raise RobotsStop(f"{API_HOST} robots.txt disallows {parts.path}; cycle skipped")


# --- response shapes ---------------------------------------------------------------------------------

def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _require(condition: bool, where: str) -> None:
    if not condition:
        raise SchemaIntegrityStop(f"schema change: {where}")


def is_staff(user: Any) -> bool:
    return bool(isinstance(user, dict) and (user.get("aclactions") or {}).get("officialreply") is True)


def listing_topics(payload: dict[str, Any], where: str) -> list[dict[str, Any]]:
    data = payload.get("data")
    _require(isinstance(data, dict) and isinstance(data.get("topics"), list), f"{where} has no data.topics")
    out = []
    for topic in data["topics"]:
        _require(isinstance(topic, dict) and _int(topic.get("id")) is not None
                 and isinstance(topic.get("title"), str) and _int(topic.get("lastActivityStamp")) is not None
                 and isinstance(topic.get("user"), dict), f"{where} topic without id/title/lastActivityStamp/user")
        out.append(topic)
    return out


def topic_view(payload: dict[str, Any], topic_id: int) -> dict[str, Any]:
    data = payload.get("data")
    _require(isinstance(data, dict) and isinstance(data.get("topic"), dict), "topic has no data.topic")
    topic = data["topic"]
    _require(_int(topic.get("id")) == int(topic_id), "topic id differs from the one asked")
    _require(isinstance(topic.get("title"), str) and topic["title"].strip(), "topic has no title")
    _require(_int(topic.get("createdStamp")) is not None, "topic has no createdStamp")
    _require(_int(topic.get("lastActivityStamp")) is not None, "topic has no lastActivityStamp")
    _require(isinstance(topic.get("user"), dict), "topic has no user")
    last = topic.get("lastComment")
    _require(isinstance(last, dict) and _int(last.get("id")) is not None, "topic has no lastComment.id")
    communities = topic.get("communities")
    _require(isinstance(communities, list) and communities and isinstance(communities[0], dict)
             and _int(communities[0].get("id")) is not None and isinstance(communities[0].get("title"), str),
             "topic has no community")
    first = topic.get("firstComment")
    _require(isinstance(first, dict), "topic has no firstComment")
    return topic


def _comment_shape(comment: Any, where: str) -> None:
    _require(isinstance(comment, dict), f"{where} is not an object")
    _require(_int(comment.get("id")) is not None, f"{where} has no id")
    _require(_int(comment.get("createdStamp")) is not None, f"{where} has no createdStamp")
    _require(isinstance(comment.get("body"), str), f"{where} has no body")
    _require(isinstance(comment.get("user"), dict), f"{where} has no user")


def comments_view(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    data = payload.get("data")
    _require(isinstance(data, dict) and isinstance(data.get("comments"), list), "comments have no data.comments")
    pagination = payload.get("pagination")
    _require(isinstance(pagination, dict) and _int(pagination.get("_totalRows")) is not None,
             "comments have no pagination._totalRows")
    for comment in data["comments"]:
        _comment_shape(comment, "a comment")
        replies = comment.get("comments", [])
        _require(isinstance(replies, list), "a comment's embedded replies are not a list")
        for reply in replies:
            _comment_shape(reply, "an embedded reply")
    return data["comments"], int(pagination["_totalRows"])


def visible(comment: dict[str, Any]) -> bool:
    return (comment.get("isVisible", 1) == 1 and not comment.get("isGhosted")
            and str(comment.get("status") or "default") == "default")


# --- the coverage-gap contract (GPT G47 s2) ----------------------------------------------------------

def window_of(comments: list[dict[str, Any]]) -> list[list[int]]:
    """The window's identity: [comment id, creation time] for every visible top-level comment."""
    rows = {(int(c["id"]), int(c["createdStamp"])) for c in comments if visible(c)}
    return [list(item) for item in sorted(rows, key=lambda item: (-item[1], -item[0]))]


def compare_windows(previous: list[list[int]] | None, current: list[list[int]],
                    previous_total: int | None = None, current_total: int | None = None) -> list[str]:
    """Why comments MAY have been missed between two successful windows, or [] when nothing says so.

    Order-independent (only ids and creation times are compared, so a reordered response decides
    the same), edit-independent (an edit moves neither), and tie-aware. Never a count, never content.
    """
    if not previous:
        return []
    prev = {int(i): int(t) for i, t in previous}
    cur = {int(i): int(t) for i, t in current}
    if not cur:
        return ["window_now_empty"]
    newest_id = max(prev, key=lambda i: (prev[i], i))
    newest_at = prev[newest_id]
    oldest_seen = min(prev.values())
    cur_oldest = min(cur.values())
    reasons: list[str] = []
    overlap = set(prev) & set(cur)
    if not overlap and newest_id not in cur:
        reasons.append("no_overlap_and_previous_newest_gone")
    if newest_id not in cur and cur_oldest == newest_at:
        # Comments created in the same second as the last one seen sit on the boundary; which of
        # them slid out of the window cannot be told.
        reasons.append("boundary_timestamp_tie")
    late = [i for i, t in cur.items() if i not in prev and oldest_seen <= t <= newest_at]
    if late:
        # A comment created inside the span the last window covered, but not in it then: the
        # window is not purely arrival-ordered, so others like it may sit beyond it.
        reasons.append("comments_appeared_inside_previous_span")
    if previous_total is not None and current_total is not None:
        new_visible = len(set(cur) - set(prev))
        if current_total - previous_total > new_visible:
            reasons.append("more_new_comments_than_the_window_shows")
    return reasons


# --- state -------------------------------------------------------------------------------------------

def empty_state() -> dict[str, Any]:
    return {"schema_version": STATE_SCHEMA_VERSION, "source": SOURCE_ID, "provenance": dict(PROVENANCE),
            "last_cycle": {}, "threads": {}}


def load_state(path: Path | None = None) -> dict[str, Any]:
    target = path or STATE_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return empty_state()
    except ValueError as exc:
        raise SchemaIntegrityStop(f"the forum state file does not parse ({exc})") from None
    if not isinstance(data, dict) or data.get("schema_version") != STATE_SCHEMA_VERSION:
        raise SchemaIntegrityStop("the forum state file has an unknown schema")
    data.setdefault("threads", {})
    data.setdefault("last_cycle", {})
    data["provenance"] = dict(PROVENANCE)
    return data


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
    target = path or STATE_PATH
    text = json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    base.atomic_write_text(target, text)


def parse_instant(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def suspension(state: dict[str, Any], now: datetime | None = None,
               cleared_at: str | None = None) -> str:
    """The refusal still in force, or ''. A clearing time counts only when it is later than the
    refusal and not in the future (one clearing time clears one refusal, once)."""
    stored = state.get("access_refused")
    if not isinstance(stored, dict) or not stored.get("at"):
        return ""
    refused = parse_instant(stored.get("at"))
    cleared = parse_instant(ACCESS_REFUSAL_CLEARED_AT if cleared_at is None else cleared_at)
    current = now or datetime.now(timezone.utc)
    if refused is not None and cleared is not None and refused < cleared <= current:
        state.pop("access_refused", None)
        return ""
    return f"suspended since {str(stored.get('at'))[:10]}: {stored.get('detail') or 'refusal'}"


def cycle_due(state: dict[str, Any], now: datetime | None = None) -> bool:
    last = parse_instant((state.get("last_cycle") or {}).get("at"))
    current = now or datetime.now(timezone.utc)
    return last is None or current - last >= MIN_CYCLE_INTERVAL


def prune_threads(state: dict[str, Any], keep_versions: set[str], now: datetime | None = None) -> None:
    current = now or datetime.now(timezone.utc)
    horizon = (current - timedelta(days=THREAD_RETENTION_DAYS)).timestamp()
    threads = state.get("threads") or {}
    kept = {tid: entry for tid, entry in threads.items()
            if set(entry.get("title_versions") or []) & keep_versions
            and int(entry.get("last_activity") or horizon) >= horizon}
    ordered = sorted(kept.items(), key=lambda kv: -int(kv[1].get("last_activity") or 0))
    state["threads"] = dict(ordered[:MAX_STATE_THREADS])
