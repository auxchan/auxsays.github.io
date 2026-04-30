"""HTTP helpers for low-frequency official-source ingestion."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import subprocess
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


def _is_adobe_helpx(url: str) -> bool:
    return "helpx.adobe.com" in (url or "").lower()


def _safe_fetch_label(url: str) -> str:
    if _is_adobe_helpx(url):
        return "official Adobe source"
    return "official source"


def _curl_fetch_text(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
    max_bytes: int | None = None,
) -> FetchResult:
    """Fallback fetcher for brittle vendor pages in CI.

    Narrowly useful for Adobe HelpX pages that repeatedly timeout under
    urllib inside GitHub Actions while still loading in normal browsers.
    Raised errors avoid raw URLs in headlines because GitHub Actions auto-links
    them and makes diagnostics visually noisy.
    """
    merged_headers = _headers(headers)
    cmd = [
        "curl",
        "--location",
        "--silent",
        "--show-error",
        "--compressed",
        "--http1.1",
        "--max-time",
        str(max(5, int(timeout))),
        "--connect-timeout",
        str(min(10, max(5, int(timeout)))),
    ]
    for key, value in merged_headers.items():
        if key.lower() == "authorization":
            continue
        cmd.extend(["-H", f"{key}: {value}"])
    cmd.append(url)

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(10, int(timeout) + 5),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Timeout while fetching {_safe_fetch_label(url)} — curl fallback timed out") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"Fetch failed for {_safe_fetch_label(url)} — curl is unavailable in this environment") from exc

    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()[:300] or f"curl exited {proc.returncode}"
        raise RuntimeError(f"Fetch failed for {_safe_fetch_label(url)} — {detail}")

    raw = proc.stdout or b""
    if max_bytes and max_bytes > 0:
        raw = raw[:max_bytes]
    text = raw.decode("utf-8", errors="replace")
    return FetchResult(url=url, status=200, headers={}, text=text, final_url=url)


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
            last_exc = RuntimeError(f"HTTP {exc.code} while fetching {_safe_fetch_label(url)} — {body[:500]}")
            # Retrying hard 4xx usually wastes time. 408/429 can be transient.
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                break
        except urllib.error.URLError as exc:
            last_exc = RuntimeError(f"Network failure while fetching {_safe_fetch_label(url)} — {exc}")
        except TimeoutError as exc:
            last_exc = RuntimeError(f"Timeout while fetching {_safe_fetch_label(url)} — {exc}")

        if _is_adobe_helpx(url):
            try:
                return _curl_fetch_text(url, timeout=timeout, headers=headers, max_bytes=max_bytes)
            except Exception as curl_exc:
                last_exc = RuntimeError(f"{last_exc}; fallback failed — {curl_exc}") if last_exc else curl_exc

        if attempt < attempts - 1:
            time.sleep(float(backoff_seconds) * (attempt + 1))

    raise last_exc or RuntimeError(f"Failed to fetch {_safe_fetch_label(url)}")


def fetch_json(url: str, timeout: int = 30) -> Any:
    result = fetch_text(url, timeout=timeout, headers={"Accept": "application/vnd.github+json, application/json"})
    return json.loads(result.text)
