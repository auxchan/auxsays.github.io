from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .security import sanitize_url, validate_url


@dataclass(frozen=True)
class RetrievedArtifact:
    body: bytes
    content_type: str
    final_url: str
    retrieved_time: str
    attempts: int
    elapsed_ms: int


class RequestBudget:
    """In-process source request budget; source registry remains the reviewed authority."""

    def __init__(self, *, max_per_day: int, max_per_10_seconds: int):
        self.max_per_day = max_per_day
        self.max_per_10_seconds = max_per_10_seconds
        self.day: deque[float] = deque()
        self.window: deque[float] = deque()

    def record(self, instant: float | None = None) -> None:
        now = time.time() if instant is None else instant
        while self.day and self.day[0] <= now - 86400:
            self.day.popleft()
        while self.window and self.window[0] <= now - 10:
            self.window.popleft()
        if len(self.day) >= self.max_per_day or len(self.window) >= self.max_per_10_seconds:
            raise RuntimeError("reviewed source request budget exhausted")
        self.day.append(now)
        self.window.append(now)


class BoundedRetriever:
    def __init__(self, *, timeout_seconds: float = 20, max_bytes: int = 8_000_000, max_redirects: int = 3, max_attempts: int = 3, sleeper: Callable[[float], None] = time.sleep):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.max_attempts = max_attempts
        self.sleeper = sleeper

    def fetch(self, url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None, expected_types: tuple[str, ...]) -> RetrievedArtifact:
        validate_url(url)
        safe_headers = {"User-Agent": "AUXSAYS-Systems-Monitor/0.1 (+https://auxsays.com)"}
        safe_headers.update(headers or {})
        last_error: Exception | None = None
        started = time.monotonic()
        for attempt in range(1, self.max_attempts + 1):
            try:
                artifact = self._request(url, method, body, safe_headers, expected_types)
                return RetrievedArtifact(artifact[0], artifact[1], artifact[2], datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), attempt, round((time.monotonic() - started) * 1000))
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    break
                retry_after = None
                if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
                    raw_retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    if raw_retry_after and raw_retry_after.isdigit():
                        retry_after = min(int(raw_retry_after), 60)
                self.sleeper(retry_after if retry_after is not None else min(2 ** (attempt - 1), 4))
        raise RuntimeError(f"bounded retrieval failed after {self.max_attempts} attempts for {sanitize_url(url)}: {type(last_error).__name__}") from last_error

    def _request(self, url: str, method: str, body: bytes | None, headers: dict[str, str], expected_types: tuple[str, ...]) -> tuple[bytes, str, str]:
        current = url
        for redirects in range(self.max_redirects + 1):
            validate_url(current)
            request = urllib.request.Request(current, data=body, headers=headers, method=method)
            opener = urllib.request.build_opener(_NoRedirect())
            try:
                response = opener.open(request, timeout=self.timeout_seconds)
            except urllib.error.HTTPError as exc:
                if exc.code not in {301, 302, 303, 307, 308}:
                    raise
                if redirects >= self.max_redirects:
                    raise RuntimeError("redirect limit exceeded") from exc
                location = exc.headers.get("Location")
                if not location:
                    raise RuntimeError("redirect missing location") from exc
                current = urllib.parse.urljoin(current, location)
                validate_url(current)
                if exc.code == 303:
                    method, body = "GET", None
                continue
            with response:
                content_type = response.headers.get_content_type().lower()
                if content_type not in expected_types:
                    raise ValueError(f"unexpected content type: {content_type}")
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > self.max_bytes:
                    raise ValueError("response exceeds configured size bound")
                payload = response.read(self.max_bytes + 1)
                if len(payload) > self.max_bytes:
                    raise ValueError("response exceeds configured size bound")
                return payload, content_type, sanitize_url(current)
        raise RuntimeError("unreachable redirect state")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def bls_request_body(series_ids: list[str], start_year: int, end_year: int) -> bytes:
    if not 1 <= len(series_ids) <= 25 or not 0 <= end_year - start_year <= 9:
        raise ValueError("BLS unregistered request scope exceeds reviewed limits")
    return json.dumps({"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)}, separators=(",", ":")).encode("utf-8")
