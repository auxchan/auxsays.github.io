#!/usr/bin/env python3
"""Microsoft Q&A PowerPoint TAG-FEED enumeration -- a community inventory, not a search box.

WHY THIS EXISTS. The existing Learn Q&A method asks the site's search endpoint a fixed set of
questions. Search recall is whatever the index decides to return for those phrasings, so a report
is only ever as findable as the words its author happened to use. Microsoft Q&A also publishes the
PowerPoint communities themselves as browsable, paginated, server-rendered inventories -- measured
at 12,969 questions in "For home | Windows" alone -- and those can be walked in creation/activity
order without asking any search engine anything. That is a genuinely independent discovery path:
it enumerates the corpus rather than querying it.

WHAT IT DOES AND DOES NOT DO. It ONLY discovers and normalizes candidates. It performs no
acceptance decision: every candidate goes through the same unchanged PowerPoint authority as every
other method, so broader discovery never becomes looser acceptance.

TWO-STAGE BY DESIGN, because the two stages have very different costs. Stage one walks tag pages
(one request per 20 questions) and keeps only what is inside the release window AND reads as a
concrete problem. Stage two hydrates just those, one request each. Without the filter a single
run would fetch thousands of pages to find a handful of reports.

DISCOVERY IS BROAD, ACCEPTANCE STAYS STRICT. A candidate is admitted here on a recent date plus a
concrete PowerPoint symptom -- deliberately NOT on an exact build, because the build is very often
absent from the title and body and arrives only when a moderator asks and the reporter answers.
Hydration keeps the whole thread available so the existing same-author context resolution can find
that later reply. Nothing is counted until the unchanged authority proves exact patch identity.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE = "https://learn.microsoft.com"
TAGS_INDEX = f"{BASE}/en-us/answers/tags/"
DEFAULT_SOURCE_TYPE = "microsoft_learn_qna"
DEFAULT_SOURCE_NAME = "Microsoft Learn Q&A"
ENDPOINT_FAMILY = "learn_qna_tag_feed"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AUXSAYS-patch-evidence/1.0 (+https://auxsays.com)")
REQUEST_TIMEOUT = 30
MAX_BYTES = 3_000_000
_MIN_REQUEST_INTERVAL = 0.35
_last_request_at = 0.0

# The PowerPoint communities, enumerated from the tag index rather than guessed. Ordered by measured
# question volume so a bounded run always spends its budget on the biggest inventories first.
# (tag_id, slug, public label, measured question count at time of enumeration)
POWERPOINT_TAGS: tuple[tuple[str, str, str, int], ...] = (
    ("1464", "m365-office-office-powerpoint-home-platform-windows", "PowerPoint for home, Windows", 12969),
    ("363", "m365-office-office-powerpoint-business-platform-windows", "PowerPoint for business, Windows", 2805),
    ("1277", "m365-office-office-powerpoint-business-macos", "PowerPoint for business, macOS", 819),
    ("1165", "m365-office-office-powerpoint-home-macos", "PowerPoint for home, macOS", 670),
    ("1272", "m365-office-office-powerpoint-education-platform-windows", "PowerPoint for education, Windows", 658),
    ("1268", "m365-office-office-powerpoint-education-macos", "PowerPoint for education, macOS", 332),
    ("1297", "m365-office-office-powerpoint-business-unknown-platform", "PowerPoint for business", 237),
    ("1424", "m365-office-office-powerpoint-unknown-routing-unknown-platform", "PowerPoint", 152),
    ("1253", "m365-office-office-powerpoint-education-unknown-platform", "PowerPoint for education", 121),
    ("1199", "m365-office-office-powerpoint-home-unknown-platform", "PowerPoint for home", 100),
    ("1310", "m365-insider-office-powerpoint-platform-windows", "Microsoft 365 Insider PowerPoint, Windows", 27),
)

# Mobile tags are deliberately excluded: a Click-to-Run desktop build cannot be the patch identity
# of an iOS or Android report, so enumerating them spends requests on candidates the authority is
# structurally certain to refuse.
EXCLUDED_TAGS: tuple[tuple[str, str], ...] = (
    ("1419", "home-ios"), ("1294", "home-android"), ("1509", "education-android"),
    ("1557", "business-ios"), ("1204", "business-android"), ("1441", "unknown-routing-android"),
    ("1388", "insider-ios"),
)

_QUESTION_LINK_RE = re.compile(r'href="(/en-us/answers/questions/(\d+)/([^"?#]*))["?#]')
_TITLE_ATTR_RE = re.compile(r'<a[^>]+href="/en-us/answers/questions/\d+/[^"]*"[^>]*>(.*?)</a>', re.S)
# Each card carries TWO <local-time> elements, labelled "asked" and "answered", and both sit AFTER
# the card's question link. They are matched by label and joined to the nearest PRECEDING link, so
# the two dates can never be swapped and a card missing one still keeps the other.
_STAMP_RE = re.compile(r'(asked|answered)\s*<local-time[^>]*datetime="(\d{4}-\d{2}-\d{2})')


class QnaTagError(Exception):
    """Transport failure carrying a stable reason token for method health."""

    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.endpoint_family = ENDPOINT_FAMILY


def error_reason(exc: Exception) -> str:
    if isinstance(exc, QnaTagError):
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
    _pace()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            final = response.geturl()
            raw = response.read(MAX_BYTES)
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 503):
            raise QnaTagError("rate_limited", status=exc.code) from exc
        raise QnaTagError(f"http_{exc.code}_error", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise QnaTagError("network_unreachable") from exc
    # A retired or renamed tag does not 404 -- it redirects to the tag index with a disclaimer. That
    # is a silent zero-result lane unless it is named, so it becomes an explicit reason.
    if "disclaimer=tag-not-found" in final:
        raise QnaTagError("tag_not_found", status=200)
    return raw.decode("utf-8", "replace")


def tag_page_url(slug: str, tag_id: str, page: int) -> str:
    base = f"{BASE}/en-us/answers/tags/{tag_id}/{slug}/"
    return base if page <= 1 else f"{base}?page={page}"


def question_url(question_id: str, slug: str = "") -> str:
    """The question URL in the SAME canonical form the RSS lane stores.

    Both lanes discover the same threads, and de-duplication is by URL string. A trailing slash
    here and none there would make one report look like two, so the shared canonicaliser owns the
    form rather than each source module guessing at it.
    """
    from .microsoft_learn_qna_source import canonical_learn_qna_url  # noqa: PLC0415 - avoids a cycle

    return canonical_learn_qna_url(f"{BASE}/en-us/answers/questions/{question_id}/{slug}")


def parse_tag_page(html: str) -> list[dict[str, str]]:
    """One tag page -> the questions it lists, with the date the page shows for each.

    `asked` is the creation date and `date` is the most recent activity, so a window sweep can use
    whichever the caller means by "recent". A stamp is joined to the nearest PRECEDING question
    link; a card with no stamp keeps an empty string rather than borrowing its neighbour's, because
    a wrong date silently moves a report into or out of a release window.
    """
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _QUESTION_LINK_RE.finditer(html):
        path, qid, slug = match.group(1), match.group(2), match.group(3)
        if qid in seen:
            continue
        seen.add(qid)
        links.append({"question_id": qid, "slug": slug, "path": path,
                      "offset": match.start(), "asked": "", "date": ""})
    titles = [" ".join(re.sub(r"<[^>]+>", " ", t).split()) for t in _TITLE_ATTR_RE.findall(html)]
    for index, row in enumerate(links):
        row["title"] = titles[index] if index < len(titles) else ""
    offsets = [row["offset"] for row in links]
    for stamp in _STAMP_RE.finditer(html):
        label, day = stamp.group(1), stamp.group(2)
        owner = -1
        for index, offset in enumerate(offsets):
            if offset < stamp.start():
                owner = index
            else:
                break
        if owner < 0:
            continue
        row = links[owner]
        if label == "asked" and not row["asked"]:
            row["asked"] = day
        if day > row["date"]:
            row["date"] = day
    for row in links:
        row.pop("offset", None)
    return links


def enumerate_tag(tag_id: str, slug: str, *, since: str, max_pages: int,
                  errors: list[dict[str, Any]]) -> tuple[list[dict[str, str]], int]:
    """Walk one tag newest-first and stop once the page falls entirely before `since`.

    Returns (rows, pages_fetched). Stopping on the first fully-old page is what keeps this bounded:
    the listing is ordered by recent activity, so everything past that point is older still.
    """
    rows: list[dict[str, str]] = []
    pages = 0
    for page in range(1, max_pages + 1):
        url = tag_page_url(slug, tag_id, page)
        try:
            html = fetch(url)
        except Exception as exc:  # noqa: BLE001 - recorded for method health
            errors.append({"source_url": url, "reason": error_reason(exc)})
            break
        pages += 1
        found = parse_tag_page(html)
        if not found:
            break
        for row in found:
            row["tag_id"] = tag_id
            row["tag_slug"] = slug
        rows.extend(found)
        dated = [r["date"] for r in found if r.get("date")]
        if dated and max(dated) < since:
            break
    return rows, pages


def question_candidate(question_id: str, slug: str, *, title: str, date: str,
                       page_html: str, source_type: str, source_name: str,
                       parse_thread) -> dict[str, Any] | None:
    """One hydrated question -> one candidate, or None when the page yields no usable text.

    `report_text` is the ORIGINAL POSTER's own opening text only. Answers and comments are
    deliberately not folded in: a question is one author's report, and merging an answerer's words
    would let a stranger's build become the asker's patch identity. Same-author follow-ups are the
    separate, already-proven concern of lib/context_resolution, which re-reads this same thread.
    """
    url = question_url(question_id, slug)
    thread = parse_thread(url, page_html)
    opening = ""
    author_id = ""
    if getattr(thread, "ok", False):
        for segment in thread.segments:
            if segment.segment_type == "question":
                opening = str(segment.segment_text or "").strip()
                author_id = str(segment.author_id or "").strip()
                break
    heading = title.strip()
    if not heading and not opening:
        return None
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": url,
        "parent_title": heading,
        "report_title": heading,
        "report_text": " ".join(x for x in (heading, opening) if x)[:6000],
        "source_date": date,
        "qna_question_id": question_id,
        "qna_author_id": author_id,
    }
