#!/usr/bin/env python3
"""Microsoft Tech Community discussions, enumerated by sitemap.

WHY THIS EXISTS, AND WHY A PRIOR AUDIT WAS WRONG. An earlier AUXSAYS audit concluded Tech Community
was "structurally unusable: there is NO PowerPoint board at all". The board half of that is still
true -- the legacy PowerPoint board URL 301s to a category path that then 302s onward, and there is
no dedicated PowerPoint board today. The conclusion drawn from it was not: PowerPoint discussions
are simply DISPERSED across general boards rather than absent, and the sitemaps expose them.
Measured: 621 board sitemaps, and `microsoft-365` alone carries 272 PowerPoint threads, all
HTTP 200 and server-rendered.

Two further corrections to that audit, both measured:
  * the "302 into SSO" is the NOT-FOUND handler, not an auth wall -- a deliberately bogus category
    produces the identical redirect chain as a real one.
  * "621 sitemaps, zero PowerPoint" is true of sitemap NAMES only. At content level those sitemaps
    hold hundreds of thousands of URLs, and the PowerPoint threads are in there.

ENUMERATION IS BY SITEMAP, AND ONLY BY SITEMAP. Board pagination silently lies: ?page=2 returns the
same thread ids as ?page=1, and the on-site search returns the same ids for pages 1-3. Every
sitemap URL carries a <lastmod>, so the corpus is date-enumerable -- which is the one thing needed.

DISCUSSIONS ONLY. `/blog/` paths are Microsoft writing about its own product; official announcements
are not user consensus and are excluded here at discovery rather than argued about later.
"""
from __future__ import annotations

import gzip
import re
import time
import urllib.error
import urllib.request
from typing import Any

BASE = "https://techcommunity.microsoft.com"
SITEMAP_INDEX = f"{BASE}/sitemap.xml"
DEFAULT_SOURCE_TYPE = "microsoft_tech_community"
DEFAULT_SOURCE_NAME = "Microsoft Tech Community"
ENDPOINT_FAMILY = "techcommunity_sitemap"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AUXSAYS-patch-evidence/1.0 (+https://auxsays.com)")
REQUEST_TIMEOUT = 45
MAX_BYTES = 12_000_000
_MIN_REQUEST_INTERVAL = 0.35
_last_request_at = 0.0

# The boards that actually carry PowerPoint discussions, chosen by MEASURED yield rather than by
# name. Walking all 621 sitemaps per run would cost hundreds of multi-megabyte fetches to reach the
# same handful of threads.  (sitemap basename, measured PowerPoint thread count)
# Ranked by ALL-TIME volume, but SELECTED on recent yield -- those are different orders, and using
# the first as a proxy for the second is what a measured-once list gets wrong. `sharepoint_general`
# and `onedriveforbusiness` are small archives that nonetheless carried the only two PowerPoint
# discussions in the most recent window, while three of the largest boards carried none.
# (sitemap basename, measured all-time PowerPoint discussions, measured recent ones)
POWERPOINT_BOARDS: tuple[tuple[str, int], ...] = (
    ("sitemap_microsoft-365.xml.gz", 272),
    ("sitemap_microsoft365insider.xml.gz", 112),
    ("sitemap_microsoftteams.xml.gz", 85),
    ("sitemap_sharepoint_general.xml.gz", 47),
    ("sitemap_microsoft365copilot.xml.gz", 39),
    ("sitemap_microsoft365apps.xml.gz", 27),
    ("sitemap_1_excelgeneral.xml.gz", 25),
    ("sitemap_onedriveforbusiness.xml.gz", 8),
    ("sitemap_microsoft-learn-for-educators.xml.gz", 1),
    ("sitemap_drivingadoption.xml.gz", 1),
)

POWERPOINT_URL_RE = re.compile(r"powerpoint|pptx|/ppt\b", re.I)
# Only user-authored threads. A blog post is the vendor talking about itself.
DISCUSSION_PATH_RE = re.compile(r"/(discussions|forum|t5)/", re.I)
_URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.S)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LASTMOD_RE = re.compile(r"<lastmod>(\d{4}-\d{2}-\d{2})")


class TechCommunityError(Exception):
    """Transport failure carrying a stable reason token for method health."""

    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.endpoint_family = ENDPOINT_FAMILY


def error_reason(exc: Exception) -> str:
    if isinstance(exc, TechCommunityError):
        return exc.reason
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}_error"
    if isinstance(exc, urllib.error.URLError):
        return "network_unreachable"
    return type(exc).__name__


def _pace() -> None:
    global _last_request_at
    delta = time.monotonic() - _last_request_at
    if delta < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - delta)
    _last_request_at = time.monotonic()


def fetch(url: str) -> str:
    """Fetch and decode. The .gz sitemaps are sometimes served already decompressed, so the
    gzip magic number decides rather than the file extension."""
    _pace()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/xml,text/html"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read(MAX_BYTES)
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 503):
            raise TechCommunityError("rate_limited", status=exc.code) from exc
        raise TechCommunityError(f"http_{exc.code}_error", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise TechCommunityError("network_unreachable") from exc
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            raise TechCommunityError("sitemap_decompress_failed") from exc
    return raw.decode("utf-8", "replace")


def board_sitemap_url(basename: str) -> str:
    return f"{BASE}/{basename}"


def powerpoint_threads(sitemap_xml: str, *, since: str) -> list[dict[str, str]]:
    """PowerPoint DISCUSSION urls from one board sitemap, filtered to the window.

    A thread with no <lastmod> is skipped rather than assumed recent: an undated entry would
    otherwise be hydrated on every run forever.
    """
    rows: list[dict[str, str]] = []
    for block in _URL_BLOCK_RE.findall(sitemap_xml):
        loc = _LOC_RE.search(block)
        if not loc:
            continue
        url = loc.group(1).strip()
        if not POWERPOINT_URL_RE.search(url) or not DISCUSSION_PATH_RE.search(url):
            continue
        stamp = _LASTMOD_RE.search(block)
        if not stamp or stamp.group(1) < since:
            continue
        rows.append({"source_url": url, "date": stamp.group(1)})
    return rows


def enumerate_boards(*, since: str, errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Every recent PowerPoint discussion across the measured boards, de-duplicated by URL."""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for basename, _yield in POWERPOINT_BOARDS:
        url = board_sitemap_url(basename)
        try:
            xml = fetch(url)
        except Exception as exc:  # noqa: BLE001 - recorded for method health
            errors.append({"source_url": url, "reason": error_reason(exc)})
            continue
        for row in powerpoint_threads(xml, since=since):
            key = row["source_url"].rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({**row, "board": basename})
    return rows


def thread_candidate(url: str, *, date: str, page_html: str, source_type: str,
                     source_name: str) -> dict[str, Any] | None:
    """One thread page -> one candidate built from the OPENING POST only.

    The JSON-LD QAPage carries the whole thread including every reply. Only `mainEntity` is read:
    replies belong to other people, and folding them in would let another participant's build
    become this reporter's patch identity.
    """
    import json  # noqa: PLC0415

    title = ""
    body = ""
    for match in re.finditer(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', page_html, re.S):
        try:
            data = json.loads(match.group(1))
        except ValueError:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict) or node.get("@type") != "QAPage":
                continue
            main = node.get("mainEntity") or {}
            if isinstance(main, dict):
                title = str(main.get("name") or "").strip()
                body = re.sub(r"<[^>]+>", " ", str(main.get("text") or ""))
                body = " ".join(body.split())
        if title or body:
            break
    if not title:
        meta = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page_html)
        title = meta.group(1).strip() if meta else ""
    if not title and not body:
        return None
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": url.rstrip("/"),
        "parent_title": title,
        "report_title": title,
        "report_text": " ".join(x for x in (title, body) if x)[:6000],
        "source_date": date,
    }
