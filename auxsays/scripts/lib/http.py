"""HTTP helpers for low-frequency official-source ingestion."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

USER_AGENT = "AUXSAYS Patch Ingest/1.0 (+https://auxsays.com)"

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
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra:
        headers.update(extra)
    return headers

def fetch_text(url: str, timeout: int = 30, headers: dict[str, str] | None = None) -> FetchResult:
    req = urllib.request.Request(url, headers=_headers(headers))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
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
        raise RuntimeError(f"HTTP {exc.code} while fetching {url}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network failure while fetching {url}: {exc}") from exc

def fetch_json(url: str, timeout: int = 30) -> Any:
    result = fetch_text(url, timeout=timeout, headers={"Accept": "application/vnd.github+json, application/json"})
    return json.loads(result.text)
