"""The one transport for GitHub's REST API (api.github.com).

Every AUXSAYS request to api.github.com goes through `get_json`: the OBS, PowerPoint (OfficeDev) and
ComfyUI issue collectors, and the GitHub Releases official adapter. Before this module each of them
had its own transport. One was unpaced, one kept sending after GitHub refused it, and none read the
headers GitHub uses to say when a client may come back.

WHAT IT GUARANTEES, per process (one collection run or one official-ingestion run):

  * IDENTITY. A truthful User-Agent naming AUXSAYS and where to reach it. Never a browser string.
  * ORIGIN. Only https://api.github.com receives a request, and so only it can ever receive the
    token. Any other URL is refused before anything is sent.
  * PACING. Requests are serial and at least MIN_INTERVAL apart (2.1 s, under the 30 searches a
    minute GitHub allows an authenticated client).
  * A REFUSAL STOPS THE RUN. GitHub's rate-limit documentation says that after a 403 or 429 a client
    must wait for `retry-after` or `x-ratelimit-reset` and warns that continuing may ban the
    integration. A run lasts minutes and the wait can be an hour, so the first refusal ends all
    GitHub traffic for the rest of the process: every later call raises without sending anything.
    The time GitHub named (at least MIN_BACKOFF_SECONDS away) is recorded so health telemetry can
    say when GitHub will accept requests again.
  * THREE KINDS OF REFUSAL, told apart, because they mean different things to whoever reads the
    health row:
        rate_limited    429; or 403 with x-ratelimit-remaining 0, a retry-after header, or a body
                        that says a (secondary) rate limit was exceeded
        access_denied   401; or 403 whose body says the credentials or their permissions were refused
        http_403_error  any other 403 (GitHub refused for a reason it did not state)
    All three stop the run. Other failures (a 404, a 5xx, the network) are ordinary errors: they are
    reported, and the caller decides what an error means for its own collection.

WHAT IT DOES NOT DO. It never retries, never sleeps out a rate limit, and never decides whether a
collection is complete. A caller that stopped early must say so in its own health row; `stop_state`
gives it what it needs to say it.
"""
from __future__ import annotations

import email.utils
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_ORIGIN = "https://api.github.com"
USER_AGENT = "AUXSAYS-patch-evidence/1.0 (+https://auxsays.com)"
API_VERSION = "2022-11-28"
REQUEST_TIMEOUT = 30
MAX_BYTES = 2_000_000
ERROR_BODY_BYTES = 65_536
# Authenticated GitHub SEARCH allows 30 requests a minute. 2.1 s is about 28.6 a minute.
MIN_INTERVAL = 2.1
# GitHub's rule when a refusal names no time: wait at least a minute.
MIN_BACKOFF_SECONDS = 60

RATE_LIMITED = "rate_limited"
ACCESS_DENIED = "access_denied"
FORBIDDEN = "http_403_error"
OFF_ORIGIN = "off_origin_refused"
# Every reason that stops the run. A health row reporting one of these is `blocked`.
STOP_REASONS = frozenset({RATE_LIMITED, ACCESS_DENIED, FORBIDDEN})

# GitHub's own wording. "API rate limit exceeded for ..." (primary) and "You have exceeded a
# secondary rate limit ..." both contain "rate limit"; abuse-detection messages predate that name.
_RATE_LIMIT_BODY_RE = re.compile(r"rate[ -]?limit|abuse detection", re.I)
# What GitHub answers when the credentials, or what they are allowed to do, are the problem.
_ACCESS_DENIED_BODY_RE = re.compile(
    r"bad credentials|requires authentication|resource not accessible|must have (?:admin|push|read)"
    r"|forbids access via|saml|token (?:has )?expired|not authorized|insufficient (?:scope|permission)",
    re.I)

# The seams tests replace. Production never touches them. `_urlopen` None means urllib's own,
# looked up at call time.
_urlopen = None
_sleep = time.sleep
_monotonic = time.monotonic
_wall = time.time

_STATE: dict[str, Any] = {}


def reset_run_state() -> None:
    """Forget any stop and the request count. Called once per process start, and by tests."""
    _STATE.clear()
    _STATE.update({"stop": None, "requests_sent": 0, "last_at": None})


reset_run_state()


class GitHubError(Exception):
    """A GitHub API failure with a stable reason token for method health.

    `sent` is False when the request was refused HERE, before reaching GitHub: the run had
    already been stopped, or the URL was not GitHub's API origin.
    """

    def __init__(self, reason: str, *, status: int | None = None, retry_at: str = "",
                 sent: bool = True, endpoint_family: str = "github_api") -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.retry_at = retry_at
        self.sent = sent
        self.endpoint_family = endpoint_family


def error_reason(exc: Exception) -> str:
    if isinstance(exc, GitHubError):
        return exc.reason
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}_error"
    if isinstance(exc, urllib.error.URLError):
        return "network_unreachable"
    return type(exc).__name__


def is_stop(exc_or_reason: Any) -> bool:
    """True for a refusal that stops the run (rate limit, access denial, other 403)."""
    reason = exc_or_reason.reason if isinstance(exc_or_reason, GitHubError) else str(exc_or_reason or "")
    return reason in STOP_REASONS


def stop_state() -> dict[str, Any] | None:
    """The run's stop, or None: {reason, status, at, retry_at}. A copy; editing it changes nothing."""
    stop = _STATE.get("stop")
    return dict(stop) if stop else None


def requests_sent() -> int:
    """How many requests this process actually sent to api.github.com."""
    return int(_STATE.get("requests_sent") or 0)


def stop_note() -> str:
    """One sentence for a health row's notes, or "" when the run was not stopped."""
    stop = stop_state()
    if not stop:
        return ""
    when = f" GitHub named {stop['retry_at']} as the earliest retry." if stop.get("retry_at") else ""
    return (f"GitHub refused a request ({stop['reason']}, HTTP {stop['status']}), so no further "
            f"GitHub request was sent in this run.{when}")


def _token() -> str:
    """A read-only token when the environment offers one. Never required, never logged."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def on_api_origin(url: str) -> bool:
    """Exactly https://api.github.com (default port, no userinfo). Nothing else gets a request."""
    try:
        parts = urllib.parse.urlsplit(str(url or ""))
        port = parts.port
    except ValueError:
        return False
    return (parts.scheme == "https" and parts.hostname == "api.github.com"
            and port in (None, 443) and "@" not in parts.netloc)


def _header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    try:
        value = headers.get(name)
    except AttributeError:
        return ""
    if value is None and isinstance(headers, dict):
        lowered = name.lower()
        for key, val in headers.items():
            if str(key).lower() == lowered:
                value = val
                break
    return str(value or "").strip()


def classify_refusal(status: int | None, headers: Any, body: str) -> str | None:
    """The stop reason for an HTTP status, or None when the status is not a refusal."""
    if status == 429:
        return RATE_LIMITED
    if status == 401:
        return ACCESS_DENIED
    if status != 403:
        return None
    if _header(headers, "x-ratelimit-remaining") == "0" or _header(headers, "retry-after"):
        return RATE_LIMITED
    text = str(body or "")
    if _RATE_LIMIT_BODY_RE.search(text):
        return RATE_LIMITED
    if _ACCESS_DENIED_BODY_RE.search(text):
        return ACCESS_DENIED
    return FORBIDDEN


def retry_wait_seconds(headers: Any, *, now: float) -> float:
    """How long GitHub asked us to wait: retry-after, else x-ratelimit-reset when the budget is 0,
    and never less than MIN_BACKOFF_SECONDS (GitHub's rule when it names no time)."""
    wait: float | None = None
    retry_after = _header(headers, "retry-after")
    if retry_after:
        if retry_after.isdigit():
            wait = float(retry_after)
        else:
            try:
                when = email.utils.parsedate_to_datetime(retry_after)
                wait = when.timestamp() - now
            except (TypeError, ValueError):
                wait = None
    if wait is None and _header(headers, "x-ratelimit-remaining") == "0":
        reset = _header(headers, "x-ratelimit-reset")
        if reset.isdigit():
            wait = float(reset) - now
    return max(float(MIN_BACKOFF_SECONDS), float(wait or 0.0))


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _pace() -> None:
    last = _STATE.get("last_at")
    if last is not None:
        delta = _monotonic() - last
        if delta < MIN_INTERVAL:
            _sleep(MIN_INTERVAL - delta)
    _STATE["last_at"] = _monotonic()


def _budget():
    """The collection run's runtime-budget module when this process already loaded it (every
    collector run does), else None. Never imported from here: lib/ must not pull a collector package
    into the official ingestion lane, where no run budget exists."""
    return sys.modules.get("patch_collectors.runtime_budget")


_META_NAMES = {
    "link": "Link",
    "etag": "ETag",
    "x-ratelimit-limit": "X-RateLimit-Limit",
    "x-ratelimit-remaining": "X-RateLimit-Remaining",
    "x-ratelimit-reset": "X-RateLimit-Reset",
    "x-ratelimit-used": "X-RateLimit-Used",
    "x-ratelimit-resource": "X-RateLimit-Resource",
}


def _meta(headers: Any) -> dict[str, str]:
    """Response metadata callers may read. `Link` is ALWAYS present ("" when GitHub sent none), so a
    caller can tell "GitHub said there is no next page" from "nothing told me"."""
    out = {"Link": ""}
    try:
        items = list(headers.items())
    except AttributeError:
        items = []
    for key, value in items:
        name = _META_NAMES.get(str(key).lower())
        if name:
            out[name] = str(value)
    return out


_LINK_RE = re.compile(r"<([^>]+)>\s*;\s*rel=\"?([^\";,]+)\"?")


def links(meta: dict[str, Any]) -> dict[str, str]:
    """rel -> URL from a Link header."""
    return {rel: url for url, rel in _LINK_RE.findall(str((meta or {}).get("Link") or ""))}


def has_next_page(meta: dict[str, Any], payload: Any, *, page: int, per_page: int,
                  result_cap: int = 1000) -> bool:
    """Is there another page? Decided by GitHub's own pagination contract, never by page size.

    The Link header's rel="next" is the contract. A response the transport did not produce (a test
    double that supplies no headers) falls back to the payload's total_count. An empty page always
    ends the walk.
    """
    items = payload.get("items") if isinstance(payload, dict) else None
    if not items:
        return False
    if isinstance(meta, dict) and "Link" in meta:
        return "next" in links(meta)
    total = payload.get("total_count") if isinstance(payload, dict) else None
    if isinstance(total, int):
        return page * per_page < min(total, result_cap)
    return len(items) >= per_page


def get_json(url: str, *, endpoint_family: str = "github_api") -> tuple[Any, dict[str, str]]:
    """GET one api.github.com URL. Returns (parsed JSON, response metadata).

    Raises GitHubError. After the first refusal (STOP_REASONS) every later call in the process
    raises the same reason with `sent=False` and sends nothing.
    """
    if not on_api_origin(url):
        raise GitHubError(OFF_ORIGIN, sent=False, endpoint_family=endpoint_family)
    stop = _STATE.get("stop")
    if stop:
        raise GitHubError(stop["reason"], status=stop.get("status"), retry_at=stop.get("retry_at", ""),
                          sent=False, endpoint_family=endpoint_family)
    _pace()
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    })
    token = _token()
    if token:
        # Unredirected: urllib rebuilds a redirected request from the plain headers only, so the
        # token never follows a redirect, wherever it points.
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    rb = _budget()
    budget = rb.get_run_budget() if rb else None
    timeout = rb.request_timeout(budget, REQUEST_TIMEOUT) if rb else REQUEST_TIMEOUT
    _STATE["requests_sent"] = requests_sent() + 1
    try:
        with (_urlopen or urllib.request.urlopen)(request, timeout=timeout) as response:
            if rb:
                raw = rb.bounded_read(response, budget=budget, endpoint_family=endpoint_family,
                                      max_bytes=MAX_BYTES)
            else:
                raw = response.read(MAX_BYTES)
            meta = _meta(response.headers)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(ERROR_BODY_BYTES).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 -- the status alone still classifies
            body = ""
        reason = classify_refusal(exc.code, exc.headers, body)
        if reason:
            now = _wall()
            retry_at = _iso(now + retry_wait_seconds(exc.headers, now=now))
            _STATE["stop"] = {"reason": reason, "status": exc.code, "at": _iso(now),
                              "retry_at": retry_at}
            raise GitHubError(reason, status=exc.code, retry_at=retry_at,
                              endpoint_family=endpoint_family) from exc
        raise GitHubError(f"http_{exc.code}_error", status=exc.code,
                          endpoint_family=endpoint_family) from exc
    except urllib.error.URLError as exc:
        raise GitHubError("network_unreachable", endpoint_family=endpoint_family) from exc
    try:
        return json.loads(raw.decode("utf-8", "replace")), meta
    except ValueError as exc:
        raise GitHubError("payload_parse_failed", endpoint_family=endpoint_family) from exc
