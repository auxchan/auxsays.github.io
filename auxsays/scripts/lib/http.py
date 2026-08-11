"""HTTP helpers for low-frequency official-source ingestion."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
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


# Hosts that may receive the GitHub token, as an EXACT netloc match. Derived from the only
# production callers that need GitHub authentication: fetch_json() for GitHub's REST API
# (github_releases adapter's ingestion.api_url and revalidate_consensus_evidence's
# issue/comment lookups). Deliberately NOT a substring test: "api.github.com.evil.example"
# and "github.com" must both fail. Vendor documentation fetches are never authenticated.
GITHUB_AUTH_HOSTS = frozenset({"api.github.com"})


def _netloc(url: str) -> str:
    """Lowercased host of a URL, port and credentials stripped. '' when unparseable."""
    try:
        host = urllib.parse.urlsplit(url).netloc.lower()
    except ValueError:
        return ""
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    if host.startswith("["):  # IPv6 literal
        return host.split("]", 1)[0] + "]"
    return host.split(":", 1)[0]


def _github_auth_allowed(url: str) -> bool:
    """True only for an exact approved-host match on an https URL."""
    try:
        scheme = urllib.parse.urlsplit(url).scheme.lower()
    except ValueError:
        return False
    return scheme == "https" and _netloc(url) in GITHUB_AUTH_HOSTS


def _strip_authorization(request: urllib.request.Request) -> None:
    for key in [k for k in request.headers if str(k).lower() == "authorization"]:
        del request.headers[key]
    for key in [k for k in request.unredirected_hdrs if str(k).lower() == "authorization"]:
        del request.unredirected_hdrs[key]


class _AuthStrippingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never forward the GitHub token off an approved host.

    Defence in depth. The token is attached with add_unredirected_header(), and urllib's
    HTTPRedirectHandler rebuilds the redirected request from req.headers only -- so an
    unredirected header is already not forwarded. This handler additionally strips any
    Authorization header from the redirected request whenever the new URL is not an
    approved host, so a future change that switches to a normal header cannot leak.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is not None and not _github_auth_allowed(newurl):
            _strip_authorization(new_request)
        return new_request


_OPENER = urllib.request.build_opener(_AuthStrippingRedirectHandler())


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Generic request headers. STRUCTURALLY INCAPABLE of carrying repository credentials.

    This builder used to take ``include_auth`` (defaulting to True) and read GITHUB_TOKEN, so
    every fetch_text/fetch_json call attached ``Authorization: Bearer $GITHUB_TOKEN`` whenever
    the variable was present -- and production workflows put it in the job environment. Vendor
    documentation, community and forum requests therefore received the repository token.

    Merely flipping that default would leave the primitive able to recreate the defect, so the
    parameter and the token read are GONE. This function cannot mint an Authorization header;
    it has no access to the token. Authentication lives only in fetch_text(), which knows the
    destination URL and can validate it (see _github_auth_allowed). A caller may still pass an
    explicit ``extra`` header, which is the caller's own value, never a credential this module
    fabricated.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
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
    # Generic curl stays credential-free: _headers() cannot mint one, and the argv builder
    # below additionally drops any Authorization a caller passed explicitly.
    request_headers = _headers(headers)
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
    authenticate: bool = False,
) -> FetchResult:
    """Fetch text with small, explicit reliability controls.

    `max_bytes` is useful for very large documentation pages where the parser
    only needs the first portion of the HTML. It reduces slow reads without
    pretending partial reads are a full-source capture.

    Adobe HelpX sometimes stalls from GitHub Actions before returning any body
    bytes. For Adobe URLs only, a narrow curl fallback can be enabled by the
    adapter/source config. This is not a generic scraping fallback.

    `authenticate` is a REQUEST, not a guarantee: the GitHub token is attached only when
    the destination is an approved host (GITHUB_AUTH_HOSTS, exact match, https). Every
    other destination -- vendor documentation, community, forum, anything config-driven --
    is fetched unauthenticated. The token is attached as an unredirected header and the
    opener strips Authorization on any redirect that leaves an approved host.
    """
    last_exc: Exception | None = None
    attempts = max(1, int(retries) + 1)
    send_auth = bool(authenticate) and _github_auth_allowed(url)

    for attempt in range(attempts):
        req = urllib.request.Request(url, headers=_headers(headers))
        if send_auth:
            token = os.getenv("GITHUB_TOKEN")
            if token:
                # Unredirected: urllib rebuilds a redirected request from req.headers only,
                # so this is never forwarded off the approved host.
                req.add_unredirected_header("Authorization", f"Bearer {token}")
        try:
            with _OPENER.open(req, timeout=timeout) as resp:
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
    """Fetch JSON. Authentication is requested but applies ONLY to approved GitHub hosts.

    This helper serves GitHub's REST API (higher authenticated rate limits). Because the
    URL is config-driven (``ingestion.api_url``), a non-GitHub destination must never be
    handed the token -- ``authenticate=True`` is a request that fetch_text validates
    against GITHUB_AUTH_HOSTS.
    """
    result = fetch_text(
        url,
        timeout=timeout,
        headers={"Accept": "application/vnd.github+json, application/json"},
        authenticate=True,
    )
    return json.loads(result.text)
