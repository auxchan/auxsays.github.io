"""Shared bounded-runtime framework for evidence collectors.

Production incident (run 31086662777): the scheduled collect step ran to the 240-min timeout and never
reached consensus/QA/writeback. Forensics: Acrobat/Reddit discovery is O(records x subreddits x endpoint
permutations) against wholesale-blocked endpoints, the subreddit listing was re-fetched once per record
(~130x), and -- decisively -- ``urllib.request.urlopen(timeout=30)`` bounds only per-``recv()``
inactivity, NOT total read wall-clock, so a single slow-drip / hung body read can stall indefinitely while
a between-request deadline check can never interrupt a thread blocked inside ``read()``.

This module provides the missing bounds:

* ``bounded_request`` -- a HARD per-request wall-clock transport (approach A): it reads the body in a loop
  against an explicit TOTAL monotonic deadline using ``read1`` (which returns after a single underlying
  socket read), regains control between chunks, enforces a strict byte cap, and CLOSES the response/socket
  when the total deadline expires. No worker threads or pools -- termination is intrinsic to the read loop,
  so nothing can linger. A slow-drip body that never reaches EOF and dribbles fast enough to defeat the
  socket inactivity timeout is still terminated at ``deadline (+ one read slice)``.
* ``RuntimeBudget`` -- a hierarchy of monotonic deadlines/counters: run-level collection deadline (so
  collection cannot consume the whole workflow step), per-collector deadline (with a reserved finalization
  tail for ownership validation + txn commit/rollback + bookkeeping), and per-method deadline + request
  cap + cumulative-backoff cap. ``request_deadline()`` yields ``min(per_request, remaining_method,
  remaining_collector_finalize)`` for every request.
* helpers: canonical-endpoint dedup/cache (version-invariant reuse, distinct from an allowed bounded
  retry), a bounded Retry-After policy, a terminal-health classifier, and a flushed, secret-scrubbed
  diagnostic emitter.

Ordinary source blocking (blocked/partial/no_results/broken/low_confidence) is a NORMAL method outcome:
callers catch ``MethodBudgetExhausted`` and return terminal method-health -- telemetry survives, the
collector commits. Only an emergency collector hard-deadline breach raises ``CollectorBudgetExhausted``,
which the runner turns into a rollback + fail-soft continue.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

_CHUNK = 65536


# --- config (env-overridable; defaults chosen from the forensic worst case) -------------------------
def _f(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class BudgetConfig:
    per_request_total: float = field(default_factory=lambda: _f("AUXSAYS_REQ_TOTAL_DEADLINE_SECONDS", 30.0))
    read_slice: float = field(default_factory=lambda: _f("AUXSAYS_REQ_READ_SLICE_SECONDS", 5.0))
    max_bytes: int = field(default_factory=lambda: _i("AUXSAYS_REQ_MAX_BYTES", 2_000_000))
    method_deadline: float = field(default_factory=lambda: _f("AUXSAYS_METHOD_DEADLINE_SECONDS", 180.0))
    collector_deadline: float = field(default_factory=lambda: _f("AUXSAYS_COLLECTOR_DEADLINE_SECONDS", 1200.0))
    collector_finalize_reserve: float = field(default_factory=lambda: _f("AUXSAYS_COLLECTOR_FINALIZE_RESERVE_SECONDS", 30.0))
    run_collection_deadline: float = field(default_factory=lambda: _f("AUXSAYS_RUN_COLLECTION_DEADLINE_SECONDS", 9000.0))
    max_requests_per_method: int = field(default_factory=lambda: _i("AUXSAYS_MAX_REQUESTS_PER_METHOD", 60))
    max_retries: int = field(default_factory=lambda: _i("AUXSAYS_REQ_MAX_RETRIES", 2))
    backoff_base: float = field(default_factory=lambda: _f("AUXSAYS_REQ_BACKOFF_SECONDS", 1.5))
    backoff_cap: float = field(default_factory=lambda: _f("AUXSAYS_REQ_BACKOFF_CAP_SECONDS", 20.0))
    max_cumulative_backoff: float = field(default_factory=lambda: _f("AUXSAYS_REQ_MAX_CUMULATIVE_BACKOFF_SECONDS", 45.0))
    request_pace: float = field(default_factory=lambda: _f("AUXSAYS_REDDIT_REQUEST_DELAY_SECONDS", 0.35))


# --- exceptions ------------------------------------------------------------------------------------
class BudgetError(Exception):
    def __init__(self, message: str, *, reason: str = "budget", health: str = "partial") -> None:
        super().__init__(message)
        self.reason = reason
        self.health = health


class RequestDeadlineExceeded(BudgetError):
    """A single request hit its hard total wall-clock deadline (e.g. a slow-drip/hung read)."""
    def __init__(self, endpoint_family: str, elapsed: float) -> None:
        super().__init__(f"request deadline exceeded ({endpoint_family}, {elapsed:.1f}s)",
                         reason="request_deadline", health="partial")
        self.endpoint_family = endpoint_family


class MethodBudgetExhausted(BudgetError):
    """A NORMAL method-level bound (deadline / request cap / cumulative backoff). The caller returns
    terminal method-health; it never propagates to the runner as a collector failure."""


class CollectorBudgetExhausted(BudgetError):
    """EMERGENCY: the collector blew past its hard deadline. The runner rolls the collector back and
    continues later collectors fail-soft."""
    def __init__(self, product_id: str) -> None:
        super().__init__(f"collector '{product_id}' exceeded its hard runtime deadline",
                         reason="collector_budget_exhausted", health="collector_budget_exhausted")
        self.product_id = product_id


# --- URL scrubbing (never log tokens/cookies/auth/sensitive query params or bodies) -----------------
_SENSITIVE = {"access_token", "token", "client_secret", "authorization", "bearer", "api_key",
              "apikey", "x-algolia-api-key", "session", "cookie", "password", "secret"}


def scrub_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url or "")
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        clean = urllib.parse.urlencode([(k, "[redacted]" if k.lower() in _SENSITIVE else v) for k, v in pairs])
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, clean, ""))
    except Exception:  # noqa: BLE001 -- diagnostics must never raise
        return "[unparseable-url]"


def emit(event: str, *, url: str | None = None, **fields: Any) -> None:
    """Flushed, secret-safe structured diagnostic. Only scrubbed URLs + scalar fields; never headers,
    cookies, bodies, or tokens."""
    payload: dict[str, Any] = {"event": event}
    if url is not None:
        payload["url"] = scrub_url(url)
    for key, value in fields.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            payload[key] = value
    # stderr keeps stdout a clean JSON summary; both streams are captured in CI logs. flush=True so a
    # timeout SIGKILL can never lose the tail (the dark-tail observability lesson from run 31086662777).
    print(f"[auxsays:runtime] {json.dumps(payload, sort_keys=True, ensure_ascii=True)}", file=sys.stderr, flush=True)


# --- the budget -----------------------------------------------------------------------------------
class RuntimeBudget:
    """Hierarchical monotonic deadlines. Clock is injectable for deterministic tests."""

    def __init__(self, cfg: BudgetConfig | None = None, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.cfg = cfg or BudgetConfig()
        self._clock = clock
        self._run_deadline_at = clock() + self.cfg.run_collection_deadline
        # per-collector
        self._collector_deadline_at = self._run_deadline_at
        self._collector_finalize_at = self._run_deadline_at
        self.product_id = ""
        self._invariant_cache: dict[str, Any] = {}
        # per-method
        self._method_deadline_at = self._run_deadline_at
        self._method_requests = 0
        self._method_backoff_total = 0.0
        self.method_id = ""

    def now(self) -> float:
        return self._clock()

    # run
    def remaining_run(self) -> float:
        return self._run_deadline_at - self._clock()

    def run_expired(self) -> bool:
        return self.remaining_run() <= 0

    # collector
    def start_collector(self, product_id: str) -> None:
        now = self._clock()
        self.product_id = product_id
        self._collector_deadline_at = min(now + self.cfg.collector_deadline, self._run_deadline_at)
        self._collector_finalize_at = self._collector_deadline_at - self.cfg.collector_finalize_reserve
        self._invariant_cache = {}

    def remaining_collector(self) -> float:
        return self._collector_deadline_at - self._clock()

    def remaining_collector_finalize(self) -> float:
        """Time left for DISCOVERY before the reserved finalization tail (ownership/commit/bookkeeping)."""
        return self._collector_finalize_at - self._clock()

    def collector_finalize_expired(self) -> bool:
        return self.remaining_collector_finalize() <= 0

    def collector_hard_expired(self) -> bool:
        return self.remaining_collector() <= 0

    def check_collector_hard(self) -> None:
        if self.collector_hard_expired():
            raise CollectorBudgetExhausted(self.product_id)

    # method
    def start_method(self, method_id: str) -> None:
        now = self._clock()
        self.method_id = method_id
        self._method_deadline_at = min(now + self.cfg.method_deadline, self._collector_finalize_at)
        self._method_requests = 0
        self._method_backoff_total = 0.0

    def remaining_method(self) -> float:
        return self._method_deadline_at - self._clock()

    def method_expired(self) -> bool:
        return self.remaining_method() <= 0

    def request_deadline(self) -> float:
        """Hard total wall-clock ceiling for the NEXT request: min(per-request, remaining method,
        remaining collector-finalize). Never negative-returned as usable time."""
        return min(self.cfg.per_request_total, self.remaining_method(), self.remaining_collector_finalize())

    def note_request(self) -> None:
        """Charge one request against the method; raise MethodBudgetExhausted (NORMAL) if a bound is hit."""
        if self.method_expired():
            raise MethodBudgetExhausted(f"method '{self.method_id}' deadline", reason="method_deadline", health="partial")
        if self.remaining_collector_finalize() <= 0:
            raise MethodBudgetExhausted(f"collector '{self.product_id}' finalize reserve", reason="collector_finalize", health="partial")
        self._method_requests += 1
        if self._method_requests > self.cfg.max_requests_per_method:
            raise MethodBudgetExhausted(f"method '{self.method_id}' request cap", reason="max_requests", health="partial")

    def note_backoff(self, seconds: float) -> float:
        """Return a sleep duration capped by the cumulative-backoff cap AND remaining method/collector
        time; raise MethodBudgetExhausted (NORMAL) if the cumulative cap is already spent."""
        if self._method_backoff_total >= self.cfg.max_cumulative_backoff:
            raise MethodBudgetExhausted(f"method '{self.method_id}' cumulative backoff cap", reason="backoff_cap", health="partial")
        allowed = min(seconds, self.cfg.backoff_cap,
                      self.cfg.max_cumulative_backoff - self._method_backoff_total,
                      max(0.0, self.remaining_method()),
                      max(0.0, self.remaining_collector_finalize()))
        allowed = max(0.0, allowed)
        self._method_backoff_total += allowed
        return allowed

    # version-invariant dedup/cache (per collector invocation; reset in start_collector)
    def cache_get(self, key: str) -> Any:
        return self._invariant_cache.get(key)

    def cache_has(self, key: str) -> bool:
        return key in self._invariant_cache

    def cache_put(self, key: str, value: Any) -> Any:
        self._invariant_cache[key] = value
        return value


# --- the hard-abort transport (approach A) ---------------------------------------------------------
@dataclass
class BoundedResponse:
    status: int
    headers: Any
    body: bytes
    truncated: bool = False


def _open(opener: Callable[..., Any] | None, req: urllib.request.Request, timeout: float) -> Any:
    if opener is not None:
        return opener(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def bounded_request(
    url: str,
    *,
    budget: RuntimeBudget,
    endpoint_family: str = "",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    method: str | None = None,
    max_bytes: int | None = None,
    read_slice: float | None = None,
    opener: Callable[..., Any] | None = None,
) -> BoundedResponse:
    """Perform ONE HTTP request under a HARD total wall-clock deadline. The body is read in a loop with
    ``read1`` against the deadline and CLOSED when it expires, so a slow-drip/hung read that never reaches
    EOF is still terminated at ``deadline (+ one read slice)`` -- no worker thread, nothing to linger.

    Returns a BoundedResponse (HTTP error statuses are returned, not raised, with a bounded error body).
    Raises RequestDeadlineExceeded when the total deadline is hit, and BudgetError('network') on a
    connect/transport failure.
    """
    cfg = budget.cfg
    max_bytes = cfg.max_bytes if max_bytes is None else max_bytes
    read_slice = cfg.read_slice if read_slice is None else read_slice
    total = budget.request_deadline()
    if total <= 0:
        raise RequestDeadlineExceeded(endpoint_family, 0.0)
    start = budget.now()

    def elapsed() -> float:
        return budget.now() - start

    def remaining() -> float:
        return total - elapsed()

    req = urllib.request.Request(url, headers=headers or {}, data=data, method=method)
    # Connect + headers, bounded by a read slice (or the whole deadline if smaller).
    try:
        resp = _open(opener, req, min(read_slice, total))
        err = False
    except urllib.error.HTTPError as exc:
        resp, err = exc, True
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise BudgetError(f"network_{type(exc).__name__}", reason="network", health="broken") from exc

    try:
        status = int(getattr(resp, "status", getattr(resp, "code", 200)) or 200)
        headers_obj = getattr(resp, "headers", None)
        buf = bytearray()
        truncated = False
        read1 = getattr(resp, "read1", None)
        while len(buf) < max_bytes:
            if remaining() <= 0:
                truncated = True
                raise RequestDeadlineExceeded(endpoint_family, elapsed())
            want = min(_CHUNK, max_bytes - len(buf))
            try:
                # read1 returns after a single underlying socket read (prompt on a slow drip); the socket
                # timeout (set at open) bounds each recv, and the deadline check bounds the total.
                chunk = read1(want) if read1 is not None else resp.read(1)
            except (socket.timeout, TimeoutError):
                if remaining() <= 0:
                    raise RequestDeadlineExceeded(endpoint_family, elapsed())
                continue
            except (urllib.error.URLError, OSError) as exc:
                raise BudgetError(f"network_{type(exc).__name__}", reason="network", health="broken") from exc
            if not chunk:
                break  # EOF
            buf += chunk
        else:
            truncated = True  # hit the byte cap
        return BoundedResponse(status=status, headers=headers_obj, body=bytes(buf), truncated=truncated)
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass


# --- retry / backoff / classification helpers ------------------------------------------------------
_TRANSIENT = frozenset({408, 429, 500, 502, 503, 504})


def is_transient(status: int | None, signature: str = "") -> bool:
    if status in _TRANSIENT:
        return True
    sig = (signature or "").lower()
    return "rate_limited" in sig or "network_" in sig


def parse_retry_after(headers: Any) -> float | None:
    """Seconds-form Retry-After only; the HTTP-date form is ignored (falls back to exponential backoff)."""
    if not headers:
        return None
    try:
        value = headers.get("Retry-After")
    except AttributeError:
        return None
    if value in (None, ""):
        return None
    try:
        return max(0.0, float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def backoff_delay(cfg: BudgetConfig, attempt: int, retry_after: float | None) -> float:
    if retry_after is not None and retry_after >= 0:
        return min(cfg.backoff_cap, retry_after)
    return min(cfg.backoff_cap, cfg.backoff_base * (2 ** attempt))


def classify_health(status: int | None, *, signature: str = "", candidate_count: int = 0) -> str:
    """Map a terminal request outcome to a method-health status."""
    sig = (signature or "").lower()
    if status in {401, 403} or "blocked" in sig or "challenge" in sig or "captcha" in sig:
        return "blocked"
    if status == 429 or "rate_limited" in sig:
        return "rate_limited"
    if "parse" in sig or "invalid_json" in sig or "broken" in sig:
        return "broken"
    if status and 200 <= status < 300:
        return "no_results" if candidate_count == 0 else "success"
    if sig.startswith("network_"):
        return "broken"
    return "no_results"
