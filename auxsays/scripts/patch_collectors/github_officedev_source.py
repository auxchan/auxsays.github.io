#!/usr/bin/env python3
"""OfficeDev GitHub issue discovery for PowerPoint patch evidence.

WHY THIS SOURCE. PowerPoint had one active discovery method and one accepted report in total.
`OfficeDev/office-js` is Microsoft's public issue tracker for the Office JavaScript platform, and
its issue template asks reporters for exactly the fields AUXSAYS needs:

    * Host [Excel, Word, PowerPoint, etc.]: PowerPoint
    * Office version number: web: 16.0.20329.45605; desktop: Version 2607 Build 16.0.20228.20124

TRANSPORT. The public REST/Search API, never HTML. Search is DISCOVERY ONLY -- a search hit is not
evidence; the issue is fetched and adjudicated by the unchanged PowerPoint authority.

TWO MEASURED FACTS drive the query design:
  * a bare build token finds nothing. `repo:OfficeDev/office-js "20228.20124"` returns 0 results,
    while `"16.0.20228.20124"` returns 6 including the calibration issue -- GitHub's tokenizer does
    not match the dotted fragment, so build-first search MUST use the full 16.0.<build> form.
  * unauthenticated search allows only 10 requests/minute, so a token is used when the environment
    offers one and the query budget stays small either way.

THE STRUCTURED FIELDS ARE THE POINT. `Host:` is a far stronger product signal than the word
PowerPoint appearing somewhere, and an issue whose Host is Excel stays Excel however often it
mentions PowerPoint. The version line routinely names BOTH a web and a desktop build; AUXSAYS
tracks Click-to-Run desktop patches, so only the desktop segment is read. Taking whichever token
appeared first would have attributed a web build to a desktop patch.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_BASE = "https://api.github.com"
REPO = "OfficeDev/office-js"
DEFAULT_SOURCE_TYPE = "github_officedev_issue"
DEFAULT_SOURCE_NAME = "OfficeDev office-js"
ENDPOINT_FAMILY = "github_officedev_issues"

USER_AGENT = "AUXSAYS-patch-evidence/1.0 (+https://auxsays.com)"
REQUEST_TIMEOUT = 30
MAX_BYTES = 2_000_000
# Authenticated GitHub SEARCH is 30 requests/minute. 0.8s paced at 75/min, and the real merged run
# drained "rate remaining" by 4 per record until two records came back `blocked`. 2.1s is 28/min.
_MIN_INTERVAL = 2.1
_last_at = 0.0

# `* Host [Excel, Word, PowerPoint, etc.]: PowerPoint`  (the bracketed list is part of the template)
HOST_FIELD_RE = re.compile(r"^\s*[*\-]?\s*Host\b[^:\n]*:\s*(.+)$", re.I | re.M)
# `* Office version number: web: 16.0.20329.45605; desktop: Version 2607 Build 16.0.20228.20124`
VERSION_FIELD_RE = re.compile(r"^\s*[*\-]?\s*Office\s+version(?:\s+number)?\b[^:\n]*:\s*(.+)$", re.I | re.M)
PLATFORM_FIELD_RE = re.compile(r"^\s*[*\-]?\s*Platform\b[^:\n]*:\s*(.+)$", re.I | re.M)

_HOST_WORD_RE = re.compile(r"\b(powerpoint|excel|word|outlook|onenote|access|project|visio)\b", re.I)
# The desktop half of a version line. Anything after a `web:` marker belongs to Office on the web,
# which is not a Click-to-Run patch and must never supply a desktop build.
_DESKTOP_SEGMENT_RE = re.compile(r"desktop\s*:\s*(.+?)(?:;|$)", re.I)
_WEB_SEGMENT_RE = re.compile(r"web\s*:\s*(.+?)(?:;|$)", re.I)
# "web:" is only ONE of the ways a reporter marks a web build. Keying the guard on that exact form
# let "web 16.0...", "Office on the web 16.0...", "web version 16.0..." and "Web - 16.0..." through
# as if they were desktop builds, which would attribute a WEB build to a Click-to-Run desktop patch.
# The word alone is the marker, and it also truncates a desktop segment that runs on into a web one
# ("desktop: ..., web: ..."), which the ";"-only terminator did not stop.
_WEB_MARKER_RE = re.compile(r"\bweb\b", re.I)


class GitHubError(Exception):
    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.endpoint_family = ENDPOINT_FAMILY


def error_reason(exc: Exception) -> str:
    if isinstance(exc, GitHubError):
        return exc.reason
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}_error"
    if isinstance(exc, urllib.error.URLError):
        return "network_unreachable"
    return type(exc).__name__


def _token() -> str:
    """A read-only token when the environment offers one. Never required, never logged."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _pace() -> None:
    global _last_at
    delta = time.monotonic() - _last_at
    if delta < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - delta)
    _last_at = time.monotonic()


def request_json(url: str) -> tuple[Any, dict[str, str]]:
    _pace()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read(MAX_BYTES)
            meta = {k: v for k, v in response.headers.items()
                    if k.lower().startswith("x-ratelimit")}
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise GitHubError("rate_limited", status=exc.code) from exc
        raise GitHubError(f"http_{exc.code}_error", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise GitHubError("network_unreachable") from exc
    try:
        return json.loads(raw.decode("utf-8", "replace")), meta
    except ValueError as exc:
        raise GitHubError("payload_parse_failed") from exc


def declared_host(body: str) -> str:
    """The template's declared Host, lowercased, or "" when the field is absent/ambiguous.

    Only the FIRST application named on the Host line counts. The template's own placeholder text
    ("[Excel, Word, PowerPoint, etc.]") is stripped by the field regex, so a reporter who left the
    placeholder in place yields the first real word they typed after the colon.
    """
    match = HOST_FIELD_RE.search(body or "")
    if not match:
        return ""
    words = _HOST_WORD_RE.findall(match.group(1))
    return words[0].lower() if words else ""


def desktop_version_text(body: str) -> str:
    """The DESKTOP portion of the Office version field.

    Reporters commonly give both, e.g. "web: 16.0.20329.45605; desktop: Version 2607 Build
    16.0.20228.20124". Returning the whole line would put a web build in front of the desktop one
    and attribute the wrong patch, so the desktop segment is isolated; when the line names a web
    build and no desktop marker, nothing is returned rather than guessing.
    """
    match = VERSION_FIELD_RE.search(body or "")
    if not match:
        return ""
    line = match.group(1).strip()
    desktop = _DESKTOP_SEGMENT_RE.search(line)
    if desktop:
        segment = desktop.group(1).strip()
        web = _WEB_MARKER_RE.search(segment)
        return (segment[:web.start()] if web else segment).strip()
    if _WEB_MARKER_RE.search(line):
        return ""       # web build named anywhere and no desktop marker: not a Click-to-Run patch
    return line         # a single unlabelled version is taken as stated


def issue_report_text(issue: dict[str, Any]) -> str:
    """The reporter's OWN text: title, body, and the desktop version field promoted to the front.

    Comments are never folded in -- a maintainer's or another user's build must not become the
    reporter's patch identity. The desktop version is repeated because the acceptance authority
    reads free text, and the structured field is the trustworthy statement of it.
    """
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    desktop = desktop_version_text(body)
    host = declared_host(body)
    lead = []
    if host:
        lead.append(f"Host: {host}")
    if desktop:
        # Emitted RAW. Build semantics -- including Office's 16.0.<build> full form -- belong to
        # lib.build_claims and the PowerPoint collector that consumes it; duplicating a build regex
        # here is exactly the two-copies-of-the-token drift that primitive exists to prevent.
        lead.append(f"Office desktop version: {desktop}")
    return " ".join([*lead, title, body])[:6000]


def search_url(query: str, per_page: int = 25) -> str:
    return f"{API_BASE}/search/issues?" + urllib.parse.urlencode({
        "q": query, "per_page": per_page, "sort": "created", "order": "desc"})


def issue_candidate(issue: dict[str, Any], *, source_type: str, source_name: str) -> dict[str, Any] | None:
    number = issue.get("number")
    if not number:
        return None
    if issue.get("pull_request"):
        return None                     # a PR is not a user report
    body = str(issue.get("body") or "")
    host = declared_host(body)
    # A declared Host that is not PowerPoint is authoritative: the issue stays that product's, no
    # matter how often PowerPoint appears elsewhere in the text.
    if host and host != "powerpoint":
        return None
    user = issue.get("user") or {}
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": str(issue.get("html_url") or f"https://github.com/{REPO}/issues/{number}"),
        "parent_title": str(issue.get("title") or ""),
        "report_title": str(issue.get("title") or ""),
        "report_text": issue_report_text(issue),
        "source_date": str(issue.get("created_at") or ""),
        "github_repo": REPO,
        "github_issue_number": str(number),
        "github_author_login": str(user.get("login") or ""),
        "github_author_id": str(user.get("id") or ""),
        "github_declared_host": host,
        # Emitted as its own field so the collector can canonicalise the DESKTOP build alone,
        # without touching any web build that shares the same version line.
        "github_desktop_version": desktop_version_text(body),
        "github_updated_at": str(issue.get("updated_at") or ""),
    }


def collect_officedev_candidates(
    *,
    queries: list[str],
    errors: list[dict[str, Any]],
    max_requests: int = 6,
    source_type: str = DEFAULT_SOURCE_TYPE,
    source_name: str = DEFAULT_SOURCE_NAME,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Discover candidate issues. Returns (candidates, telemetry).

    Dedupe identity is repository + issue number: the same issue found by a build query and by a
    symptom query is ONE candidate, never two. Discovery routes are not evidence.
    """
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    telemetry = {"queries": 0, "requests": 0, "issues_discovered": 0,
                 "rate_remaining": "", "rate_limit": ""}
    for query in queries:
        if telemetry["requests"] >= max_requests:
            errors.append({"source_url": API_BASE,
                           "reason": f"request_budget_exhausted_after_{telemetry['requests']}"})
            break
        telemetry["queries"] += 1
        try:
            payload, meta = request_json(search_url(query))
        except Exception as exc:  # noqa: BLE001 - reason recorded for method health
            errors.append({"source_url": API_BASE, "reason": error_reason(exc)})
            continue
        telemetry["requests"] += 1
        telemetry["rate_remaining"] = meta.get("X-RateLimit-Remaining", "")
        telemetry["rate_limit"] = meta.get("X-RateLimit-Limit", "")
        items = payload.get("items") if isinstance(payload, dict) else None
        for issue in items or []:
            if not isinstance(issue, dict):
                continue
            telemetry["issues_discovered"] += 1
            key = f"{REPO}#{issue.get('number')}"
            if key in seen:
                continue
            candidate = issue_candidate(issue, source_type=source_type, source_name=source_name)
            if not candidate:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates, telemetry
