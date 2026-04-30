"""HTTP helpers for low-frequency official-source ingestion."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# Identify AUXSAYS but use a browser-like UA shape. Some vendor documentation
# pages treat minimal script UAs more harshly than normal browser requests.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "AUXSAYS-Patch-Ingest/1.2 (+https://auxsays.com)"
)


@dataclass
class FetchResult:
    url: str
    status: int
    headers: dict[str, str]
    text: str
    final_url: str


def _headers(extra: dict[str, str] | None = None, *, include_auth: bool = True) -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token and include_auth:
        headers["Authorization"] = f"Bearer {token}"
    if extra:
        headers.update({str(k): str(v) for k, v in extra.items() if v is not None})
    return headers


def _read_response(resp, max_bytes: int | None = None) -> bytes:
    if max_bytes and max_bytes > 0:
        return resp.read(max_bytes)
    return resp.read()


def _domain(url: str) -> str:
    return url.split("/")[2].lower() if "://" in url else ""


def _friendly_source_name(url: str) -> str:
    host = _domain(url)
    if "adobe.com" in host:
        return "official Adobe source"
    if "github.com" in host or "api.github.com" in host:
        return "official GitHub source"
    return "official source"


def _format_fetch_error(kind: str, url: str, detail: object | str) -> RuntimeError:
    # Do not include the raw URL in the headline. GitHub Actions auto-links URLs
    # and can make separators look like part of the URL. The URL remains in
    # structured source data and source-health rows.
    return RuntimeError(f"{kind} while fetching {_friendly_source_name(url)} — {detail}")


def _curl_fetch_text(
    url: str,
    timeout: int,
    headers: dict[str, str] | None,
    *,
    max_bytes: int | None = None,
) -> FetchResult:
    request_headers = _headers(headers, include_auth=False)
    cmd = [
        "curl",
        "--location",
        "--silent",
        "--show-error",
        "--fail-with-body",
        "--compressed",
        "--http1.1",
        "--ipv4",
        "--connect-timeout",
        str(min(10, max(5, int(timeout)))),
        "--max-time",
        str(max(10, int(timeout))),
        "--user-agent",
        USER_AGENT,
    ]

    if max_bytes and max_bytes > 0:
        cmd.extend(["--range", f"0-{max_bytes - 1}"])

    for key, value in request_headers.items():
        if key.lower() == "authorization":
            continue
        cmd.extend(["--header", f"{key}: {value}"])

    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=False, timeout=max(15, int(timeout) + 5))

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        if "Operation timed out" in stderr or proc.returncode == 28:
            raise _format_fetch_error("Timeout", url, stderr or "curl operation timed out")
        raise _format_fetch_error("Fetch failed", url, f"curl exit {proc.returncode}: {stderr[:500]}")

    raw = proc.stdout or b""
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
    curl_fallback: bool | None = None,
) -> FetchResult:
    """Fetch text with small, explicit reliability controls.

    `max_bytes` is useful for very large documentation pages where the parser
    only needs the first portion of the HTML. It reduces slow reads without
    pretending partial reads are a full-source capture.

    Adobe HelpX sometimes stalls from GitHub Actions before returning any body
    bytes. For Adobe URLs only, a narrow curl fallback can be enabled by the
    adapter/source config. This is not a generic scraping fallback.
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
            last_exc = _format_fetch_error(f"HTTP {exc.code}", url, body[:500])
            # Retrying hard 4xx usually wastes time. 408/429 can be transient.
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                break
        except urllib.error.URLError as exc:
            last_exc = _format_fetch_error("Network failure", url, exc)
        except TimeoutError as exc:
            last_exc = _format_fetch_error("Timeout", url, exc)

        if attempt < attempts - 1:
            time.sleep(float(backoff_seconds) * (attempt + 1))

    should_curl = bool(curl_fallback) or ("adobe.com" in _domain(url) and bool(curl_fallback))
    if should_curl:
        try:
            return _curl_fetch_text(url, timeout=timeout, headers=headers, max_bytes=max_bytes)
        except Exception as curl_exc:
            if last_exc:
                raise RuntimeError(f"{last_exc}; fallback failed — {curl_exc}") from curl_exc
            raise

    raise last_exc or _format_fetch_error("Failed", url, "unknown fetch failure")


def fetch_json(url: str, timeout: int = 30) -> Any:
    result = fetch_text(url, timeout=timeout, headers={"Accept": "application/vnd.github+json, application/json"})
    return json.loads(result.text)
