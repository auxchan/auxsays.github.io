"""HTTP helpers for low-frequency official-source ingestion."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# Identify AUXSAYS but use a browser-like UA shape. Some vendor documentation
# pages treat minimal script UAs more harshly than normal browser requests.
USER_AGENT = (
    "Mozilla/5.0 (compatible; AUXSAYS-Patch-Ingest/1.1; +https://auxsays.com; "
    "official-source-check) AppleWebKit/537.36"
)

@dataclass
class FetchResult:
    url: str
    status: int
    headers: dict[str, str]
    text: str
    final_url: str


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra:
        headers.update({str(k): str(v) for k, v in extra.items() if v is not None})
    return headers


def _read_response(resp, max_bytes: int | None = None) -> bytes:
    if max_bytes and max_bytes > 0:
        return resp.read(max_bytes)
    return resp.read()


def fetch_text(
    url: str,
    timeout: int = 30,
    headers: dict[str, str] | None = None,
    *,
    retries: int = 0,
    backoff_seconds: float = 2.0,
    max_bytes: int | None = None,
) -> FetchResult:
    """Fetch text with small, explicit reliability controls.

    `max_bytes` is useful for very large documentation pages where the parser
    only needs the first portion of the HTML. It reduces slow reads without
    pretending partial reads are a full-source capture.
    """
    last_exc: Exception | None = None
    attempts = max(1, int(retries) + 1)

    for attempt in range(attempts):
        req = urllib.request.Request(url, headers=_headers(headers))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = _read_response(resp, max_bytes=max_bytes)
                charset = resp.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                return FetchResult(
                    url=url,
                    status=getattr(resp, "status", 200),
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    text=text,
                    final_url=resp.geturl(),
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_exc = RuntimeError(f"HTTP {exc.code} while fetching official source URL [{url}] — {body[:500]}")
            # Retrying hard 4xx usually wastes time. 408/429 can be transient.
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                break
        except urllib.error.URLError as exc:
            last_exc = RuntimeError(f"Network failure while fetching official source URL [{url}] — {exc}")
        except TimeoutError as exc:
            last_exc = RuntimeError(f"Timeout while fetching official source URL [{url}] — {exc}")

        if attempt < attempts - 1:
            time.sleep(float(backoff_seconds) * (attempt + 1))

    raise last_exc or RuntimeError(f"Failed to fetch official source URL [{url}]")


def fetch_json(url: str, timeout: int = 30) -> Any:
    result = fetch_text(url, timeout=timeout, headers={"Accept": "application/vnd.github+json, application/json"})
    return json.loads(result.text)
