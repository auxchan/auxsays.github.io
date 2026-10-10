"""OBS Studio official forum discovery: the second independent evidence family.

OBS had one real community source family -- obsproject/obs-studio GitHub Issues. The other slot,
`known_watchlist`, discovered nothing and only ever emitted `disabled`. This adds the OBS project's
OWN support forum, which is a genuinely different corpus: different platform, different authors,
and the place a non-technical user actually goes. A second GitHub Issues query would not have been
another family.

WHAT THE ROBOTS POLICY ALLOWS, measured at https://obsproject.com/robots.txt:
    allowed      /forum/list/<slug>.<id>/      subforum listings
                 /forum/threads/<slug>.<id>/   one specific thread
    DISALLOWED   /forum/search/  /forum/whats-new/  /forum/find-new/  /forum/posts/

So this ENUMERATES the three support subforums and never queries a search endpoint -- the same
conclusion the PowerPoint source-coverage sprint reached. And because a reply's canonical URL is
/forum/posts/<id>/, which is disallowed, this reads OPENING POSTS ONLY. That also happens to be
the safe reading: a reply must never inherit the thread author's version, and an opening post is
by construction the author's own statement about their own install.

THE DATE TRAP IS LIVE HERE. A 2013 thread renders three timestamps and the LAST is 2025 --
last activity, because someone replied. The feed is worse: it orders by activity. So the original
date is taken from the first <time> INSIDE the opening post's own <article>, never from the page
or the feed.

ACCEPTANCE IS NOT DECIDED HERE. A thread is shaped into the same {title, body, labels, created_at}
dict a GitHub issue presents, and handed to collect_obs_reports.evaluate_issue -- the one OBS
authority. This module discovers; it does not judge.
"""
from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

from . import runtime_budget as rb

FORUM_ROOT = "https://obsproject.com/forum"
SOURCE_TYPE = "obs_forum_thread"
SOURCE_NAME = "OBS Project Support Forum"
USER_AGENT = "Mozilla/5.0 (compatible; AUXSAYS/1.0; +https://auxsays.com)"
NEWLINE = chr(10)

# The three user-support subforums under the forum's own "OBS Studio Support" category. Node ids
# are part of the canonical URL, so they are pinned rather than scraped from the index each run.
# Development (19), General (31), Resources (23) and Archive (24) are deliberately excluded: the
# acceptance authority rejects developer-only reports anyway, and the rest are not defect reports.
SUPPORT_FORUMS = (
    ("windows-support", 32),
    ("mac-support", 33),
    ("linux-support", 34),
)

MAX_THREADS_PER_FORUM = 60

# Deliberate pacing, matching the convention the other enumerating collectors use. A bounded
# run issues up to ~180 thread requests, and natural latency already spaces them about a second
# apart -- but relying on that is relying on the forum being slow. This is a volunteer-run
# community server, so the floor is explicit.
_MIN_REQUEST_INTERVAL = 0.35
_last_request_at = 0.0


def _pace() -> None:
    global _last_request_at
    interval = max(0.0, float(os.getenv("AUXSAYS_OBS_FORUM_REQUEST_DELAY_SECONDS",
                                        str(_MIN_REQUEST_INTERVAL))))
    delta = time.monotonic() - _last_request_at
    if delta < interval:
        time.sleep(interval - delta)
    _last_request_at = time.monotonic()

_THREAD_HREF_RE = re.compile(
    r'href="(/forum/threads/[A-Za-z0-9%._-]+\.([0-9]+)/)"')
# The opening post. XenForo marks every post with data-content="post-<id>"; the FIRST one is the
# thread starter.
_FIRST_POST_RE = re.compile(
    r'<article[^>]*data-author="([^"]*)"[^>]*data-content="post-([0-9]+)"')
_TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
_BODY_RE = re.compile(
    r'<div class="bbWrapper">(.*?)</div>', re.S)
_TITLE_RE = re.compile(
    r'<h1[^>]*class="p-title-value"[^>]*>(.*?)</h1>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_BODY_START_RE = re.compile(r'<div class="bbWrapper">')


class ForumUnavailable(RuntimeError):
    """The forum could not be reached or returned something unusable."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _fetch(url: str, timeout: int = 25) -> str:
    _pace()
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        # A CI-only 403 on another source turned out to be the Accept header, not the runner IP.
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise ForumUnavailable(f"http_{exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ForumUnavailable(f"url_error_{type(exc.reason).__name__}") from exc
    except TimeoutError as exc:
        raise ForumUnavailable("timeout") from exc
    except OSError as exc:
        raise ForumUnavailable(f"os_error_{type(exc).__name__}") from exc
    return raw.decode("utf-8", errors="replace")


def _slice_balanced_div(html: str, start: int) -> str:
    """Return the inner HTML of the <div> whose opening tag ends at `start`.

    A naive `(.*?)</div>` stops at the first nested close, so a post containing a quote or a
    spoiler would be truncated. Balancing matters for a different reason too: the quote has to be
    present in the slice before it can be stripped out deliberately.
    """
    depth = 1
    index = start
    length = len(html)
    while index < length and depth > 0:
        opening = html.find("<div", index)
        closing = html.find("</div>", index)
        if closing == -1:
            return html[start:]
        if opening != -1 and opening < closing:
            depth += 1
            index = opening + 4
            continue
        depth -= 1
        index = closing + 6
    return html[start:max(start, index - 6)]


def _strip_blockquotes(html: str) -> str:
    """Remove quoted blocks, nesting included.

    A non-greedy `<blockquote[^>]*>.*?</blockquote>` is wrong here and iterating it does not
    help: on a nested quote the first pass matches the OUTER open tag through the INNER close,
    so it consumes the outer's opening tag and leaves the outer's own trailing text behind with
    nothing left to match it. XenForo nests quotes routinely ("A said: B said: ..."), and the
    text left behind is another member's version claim. So the span is balanced instead.

    An unbalanced quote drops everything from its opening tag onward. That loses some of the
    author's own words, which is the right direction to fail: keeping a stranger's version would
    attribute their install to this author.
    """
    out = html
    lowered = out.lower()
    for _ in range(12):
        start = lowered.find("<blockquote")
        if start == -1:
            return out
        depth = 0
        index = start
        end = None
        while index < len(out):
            nxt_open = lowered.find("<blockquote", index)
            nxt_close = lowered.find("</blockquote>", index)
            if nxt_close == -1:
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                index = nxt_open + len("<blockquote")
                continue
            depth -= 1
            index = nxt_close + len("</blockquote>")
            if depth == 0:
                end = index
                break
        if end is None:
            return out[:start]
        out = out[:start] + " " + out[end:]
        lowered = out.lower()
    return out


def _text(html: str) -> str:
    out = html.replace("<br />", NEWLINE).replace("<br/>", NEWLINE).replace("<br>", NEWLINE)
    out = out.replace("</p>", NEWLINE).replace("</li>", NEWLINE)
    out = _TAG_RE.sub(" ", out)
    for entity, plain in (
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", chr(34)),
        ("&#039;", chr(39)), ("&#39;", chr(39)), ("&nbsp;", " "), ("&hellip;", "..."),
    ):
        out = out.replace(entity, plain)
    return _WS_RE.sub(" ", out).strip()


_ARTICLE_TAG_RE = re.compile(r'<article[^>]*data-content="post-[0-9]+"[^>]*>')
_AUTHOR_RE = re.compile(r'data-author="([^"]*)"')
_POST_ID_RE = re.compile(r'data-content="post-([0-9]+)"')


def thread_url(path: str) -> str:
    return "https://obsproject.com" + path


_STICKY_GROUP_RE = re.compile(
    r'<div class="structItemContainer-group structItemContainer-group--sticky"[^>]*>')


def sticky_thread_paths(html: str) -> set[str]:
    """Thread paths pinned to the top of a subforum listing.

    XenForo groups them in their own container, so this is a structural fact about the listing
    rather than a guess from the title.
    """
    match = _STICKY_GROUP_RE.search(html)
    if not match:
        return set()
    inner = _slice_balanced_div(html, match.end())
    return {hit.group(1) for hit in _THREAD_HREF_RE.finditer(inner)}


def list_thread_paths(html: str, include_sticky: bool = False) -> list[str]:
    """Thread paths from a subforum listing, in listing order, de-duplicated.

    Listing order is activity order, so this is NOT chronological -- it is only a work list. The
    date that decides anything comes from the thread's own opening post.

    STICKIES ARE EXCLUDED. A pinned thread is a staff advice guide or a rules notice, not one
    user's report, and it sits on page 1 of every subforum forever -- so enumeration meets them
    first, every run. They are also the one shape that defeats the acceptance authority on
    vocabulary alone: "Dropped frames/disconnecting/lag? Read this first!" contains three
    concrete-issue terms and describes nobody's install. This is a DISCOVERY decision, which is
    where it belongs -- methods may discover differently, but they may not judge differently, so
    nothing about acceptance changes for the threads that do get through.
    """
    excluded = set() if include_sticky else sticky_thread_paths(html)
    seen: set[str] = set()
    paths: list[str] = []
    for match in _THREAD_HREF_RE.finditer(html):
        path = match.group(1)
        if path in seen or path in excluded:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def parse_opening_post(html: str) -> dict[str, Any] | None:
    """Shape a thread page into the dict the OBS acceptance authority consumes.

    OPENING POST ONLY, for two reasons that happen to agree. A reply's canonical URL is
    /forum/posts/<id>/, which robots.txt disallows, so a reply could not be cited as a specific
    report URL anyway. And a reply must never inherit the thread author's version -- reading only
    the first post makes that structural rather than a rule someone has to remember.

    Returns None when the page has no post, no title or no timestamp; a missing date must not fail
    open into "no date known", because the authority's release-date gate would then pass by
    default.
    """
    title_match = _TITLE_RE.search(html)
    article_match = _ARTICLE_TAG_RE.search(html)
    if not title_match or not article_match:
        return None

    article_tag = article_match.group(0)
    author_match = _AUTHOR_RE.search(article_tag)
    post_id_match = _POST_ID_RE.search(article_tag)
    if not post_id_match:
        return None

    # The opening post's OWN extent: from its article tag to the next post's. Searching the rest
    # of the page instead would read a REPLY whenever the opening post lacks the element being
    # looked for -- its date if the <time> markup moves, its body if the bbWrapper class changes.
    # Both failures are silent and both attribute another author's words to this one, so the
    # boundary is enforced here rather than trusted to the markup staying still. The thread's
    # LAST <time> is last-activity: measured live, a 2013 thread renders 2013, 2013, 2025.
    tail = html[article_match.end():]
    next_post = _ARTICLE_TAG_RE.search(tail)
    own = tail[:next_post.start()] if next_post else tail

    time_match = _TIME_RE.search(own)
    if not time_match:
        return None

    body = ""
    body_start = _BODY_START_RE.search(own)
    if body_start:
        inner = _slice_balanced_div(own, body_start.end())
        # Strip quoted blocks BEFORE reading the text. A quote carries another author's words,
        # and a version inside one is that author's claim about their install, not this one's.
        body = _text(_strip_blockquotes(inner))

    return {
        "title": _text(title_match.group(1)),
        "body": body,
        "labels": [],
        "created_at": time_match.group(1),
        "author": author_match.group(1) if author_match else "",
        "post_id": post_id_match.group(1),
    }


# One thread pool per process, not per version. A thread is fetched once and then evaluated
# against every tracked version offline -- otherwise 16 versions x 3 forums would re-fetch the
# same pages 16 times. This mirrors what the GitHub method gets for free from a server-side
# version query; here the query is not available (robots disallows /forum/search/), so the
# listing is enumerated and the filtering happens locally.
_POOL: list[dict[str, Any]] | None = None
_POOL_ERROR: str | None = None
_POOL_STATS: dict[str, int] = {}


def reset_pool() -> None:
    """Drop the cached pool. For tests, and for a second run inside one process."""
    global _POOL, _POOL_ERROR
    _POOL = None
    _POOL_ERROR = None
    _POOL_STATS.clear()


def _listing_urls(slug: str, node_id: int, pages: int) -> list[str]:
    base = f"{FORUM_ROOT}/list/{slug}.{node_id}/"
    return [base] + [f"{base}page-{page}" for page in range(2, max(1, pages) + 1)]


def build_pool(max_threads_per_forum: int = MAX_THREADS_PER_FORUM,
               listing_pages: int = 3,
               fetch=_fetch) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Enumerate the support subforums and parse each thread's opening post.

    Raises ForumUnavailable only when NO listing could be read at all. A partial pool is
    returned with its own counters so the caller can report `partial` honestly rather than
    claiming success -- a source whose extractor maps nothing must not read as healthy.
    """
    stats = {"listings_requested": 0, "listings_failed": 0, "threads_requested": 0,
             "threads_failed": 0, "threads_unparsed": 0, "threads_bodyless": 0}
    paths: list[str] = []
    for slug, node_id in SUPPORT_FORUMS:
        found = 0
        for url in _listing_urls(slug, node_id, listing_pages):
            if found >= max_threads_per_forum:
                break
            budget = rb.get_run_budget()
            if budget is not None and budget.collector_finalize_expired():
                rb.emit("obs_forum_budget_stop", reason="listing_enumeration")
                break
            stats["listings_requested"] += 1
            try:
                html = fetch(url)
            except ForumUnavailable:
                stats["listings_failed"] += 1
                continue
            for path in list_thread_paths(html):
                if found >= max_threads_per_forum:
                    break
                if path not in paths:
                    paths.append(path)
                    found += 1

    if stats["listings_requested"] and stats["listings_failed"] == stats["listings_requested"]:
        raise ForumUnavailable("all_listings_failed")

    pool: list[dict[str, Any]] = []
    for path in paths:
        budget = rb.get_run_budget()
        if budget is not None and budget.collector_finalize_expired():
            rb.emit("obs_forum_budget_stop", reason="thread_fetch")
            break
        stats["threads_requested"] += 1
        try:
            html = fetch(thread_url(path))
        except ForumUnavailable:
            stats["threads_failed"] += 1
            continue
        post = parse_opening_post(html)
        if post is None:
            stats["threads_unparsed"] += 1
            continue
        post["source_url"] = thread_url(path)
        post["thread_path"] = path
        # A post that parsed but carries no body text is the signature of a bbWrapper markup
        # change. It is kept -- a title can legitimately carry the whole report -- but it is
        # COUNTED, because a family that quietly degrades to titles only would otherwise keep
        # reporting success while its recall collapsed.
        if not str(post.get("body") or "").strip():
            stats["threads_bodyless"] += 1
        pool.append(post)
    stats["threads_in_pool"] = len(pool)
    return pool, stats


def get_pool(max_threads_per_forum: int = MAX_THREADS_PER_FORUM,
             listing_pages: int = 3,
             fetch=_fetch) -> tuple[list[dict[str, Any]], dict[str, int], str | None]:
    """The cached thread pool as (pool, stats, error_reason).

    `error_reason` is set only when the forum could not be reached at all; the caller reports
    `blocked` for that and must not silently treat it as an empty forum.
    """
    global _POOL, _POOL_ERROR
    if _POOL is None and _POOL_ERROR is None:
        try:
            pool, stats = build_pool(max_threads_per_forum, listing_pages, fetch)
        except ForumUnavailable as exc:
            _POOL = []
            _POOL_ERROR = exc.reason
            _POOL_STATS.clear()
        else:
            _POOL = pool
            _POOL_STATS.clear()
            _POOL_STATS.update(stats)
    return list(_POOL or []), dict(_POOL_STATS), _POOL_ERROR


_THREAD_ID_RE = re.compile(
    r'^/forum/threads/(?:[^/]*\.)?([0-9]+)/?$')


def thread_id(path: str) -> str | None:
    """The numeric thread id from a thread path, or None when it cannot be determined.

    The id is the stable part of the URL -- XenForo keeps a thread reachable at its numeric id
    even when the title slug is edited -- and it is also what makes the two URL shapes the same
    thread: /forum/threads/<slug>.<id>/ and /forum/threads/<id>/ both resolve here. Taking the
    text after the last dot instead returned the WHOLE path for the slugless shape, which built a
    row id containing slashes and let one thread land twice.

    Returns None rather than guessing. An evidence row whose identity was invented is worse than
    a report that was not counted.
    """
    match = _THREAD_ID_RE.match(str(path or "").strip())
    return match.group(1) if match else None


def row_identity(version: str, post: dict[str, Any], slugger) -> dict[str, str] | None:
    """The source identity a forum report contributes to an evidence row, or None.

    None means the thread path carried no resolvable id, so the caller must refuse the candidate
    instead of storing a row that cannot be matched back to its thread.
    """
    found = thread_id(post.get("thread_path") or "")
    if not found:
        return None
    thread_id_value = found
    return {
        "row_id": f"obs-studio-{slugger(version)}-obs-forum-thread-{thread_id_value}",
        "source_type": SOURCE_TYPE,
        "source_name": SOURCE_NAME,
        "source_url": str(post.get("source_url") or ""),
    }
