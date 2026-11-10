#!/usr/bin/env python3
"""Refuse to publish a Patch Feed that is too heavy to read, or a patch page a crawler cannot reach.

WHY. /updates/ used to print every tracked patch as a full card on one page: 1,535 cards and
4,295,549 bytes on 2026-11-10, growing by a few hundred records a month. Googlebot reads the first
2 MB of an HTML response, so 819 of the feed's 1,535 patch links -- and its whole archive -- sat past
what it reads. The feed is now paged (_plugins/patch_feed_pages.rb, _layouts/aux-updates.html).
This gate keeps it that way on the exact bytes about to be served.

WHAT IT CHECKS, on the built site:
  BUDGET   every feed page (/updates/ and each /updates/page/N/ its pager reaches) is at most
           FEED_PAGE_BUDGET_BYTES. Half the 2 MB window, so a page can double before it nears it.
  PAGER    every feed page is reached from /updates/ by plain <a href> links, every pager link
           resolves to a built page, and no built /updates/page/N/ is left out (an orphan page).
  STAMP    every feed page's pager carries the same build stamp (data-feed-build). The feed
           controls search another page only when its stamp matches their own page's
           (assets/js/auxsays.js, loadFeedPages), so a page with none, or with another build's,
           would leave every search from it on that one page.
  COVERAGE every patch page the feed lists is linked from exactly one feed page's cards, and every
           feed card links a real patch page. "Listed" = every patch page except a record whose
           front matter says `feed_hidden: true`, which the feed deliberately omits.
  REACH    every patch page is reached from / by crawlable <a href> links within MAX_HOPS hops,
           reading each page only up to the Googlebot window -- independent of whether the reach
           comes through the feed or through the product trackers.

A link counts only as an <a href> in the served HTML, read up to CRAWL_WINDOW_BYTES. A link that
exists only through script, a data attribute or past the window is not a link here, because it is
not one for a crawler.

Patch pages are found in the BUILT site by their layout (`<body class="aux-page aux-update">`,
emitted by _layouts/aux-base.html for every record), not from the source tree, so the check judges
what is actually published.

Run:  python auxsays/scripts/ci/verify_feed_discovery.py --site auxsays/_site [--source auxsays]
Exit: 0 clean, 1 a budget, pager, stamp, coverage or reach failure, 2 the site directory is unusable.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

FEED_PAGE_BUDGET_BYTES = 1_000_000
# Googlebot fetches the first 2 MB of an HTML response, headers included. 1 KiB is kept for the
# response headers (about 690 bytes measured on auxsays.com).
CRAWL_WINDOW_BYTES = 2 * 1024 * 1024 - 1024
MAX_HOPS = 3
FEED_URL = "/updates/"
FEED_PAGE_RE = re.compile(r"/updates/page/(\d+)/")
PATCH_BODY_RE = re.compile(rb'<body class="aux-page aux-update"')
SITE_HOST = "auxsays.com"


class _Anchors(HTMLParser):
    """Every <a href>, which of them are a feed card's identity link, and the pager's build stamp."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.card_hrefs: list[str] = []
        self.feed_builds: list[str] = []
        self._card_depth = 0
        self._depth = 0

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        a = dict(attrs)
        if tag == "nav" and "data-feed-pages" in a:
            self.feed_builds.append(a.get("data-feed-build") or "")
        if tag == "article":
            self._depth += 1
            if "patch-card" in (a.get("class") or "").split():
                self._card_depth = self._depth
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
            if self._card_depth and "patch-identity" in (a.get("class") or "").split():
                self.card_hrefs.append(a["href"])

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag == "article":
            if self._depth == self._card_depth:
                self._card_depth = 0
            self._depth -= 1


def site_path(href: str, base: str) -> str | None:
    """The site-relative directory URL an <a href> points to, or None if it leaves the site."""
    if href.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
        return None
    u = urlparse(urljoin(f"https://{SITE_HOST}{base}", href))
    if u.scheme not in ("http", "https") or (u.netloc and u.netloc != SITE_HOST):
        return None
    path = u.path or "/"
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return path


class Site:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._parsed: dict[str, _Anchors] = {}

    def file_of(self, url: str) -> Path | None:
        p = self.root / url.lstrip("/")
        if url.endswith("/"):
            p = p / "index.html"
        return p if p.is_file() else None

    def anchors(self, url: str) -> _Anchors:
        if url not in self._parsed:
            parser = _Anchors()
            f = self.file_of(url)
            if f is not None and f.suffix == ".html":
                parser.feed(f.read_bytes()[:CRAWL_WINDOW_BYTES].decode("utf-8", "ignore"))
                parser.close()
            self._parsed[url] = parser
        return self._parsed[url]

    def links(self, url: str) -> list[str]:
        out = []
        for href in self.anchors(url).hrefs:
            p = site_path(href, url)
            if p is not None:
                out.append(p)
        return out

    def patch_pages(self) -> set[str]:
        found = set()
        for f in self.root.rglob("index.html"):
            if PATCH_BODY_RE.search(f.read_bytes()):
                rel = f.parent.relative_to(self.root).as_posix()
                found.add("/" if rel == "." else f"/{rel}/")
        return found


def feed_hidden_urls(source: Path | None) -> set[str]:
    """Permalinks of records the feed omits on purpose (`feed_hidden: true` in front matter)."""
    hidden: set[str] = set()
    if source is None:
        return hidden
    for f in (source / "updates").rglob("*.md"):
        text = f.read_text(encoding="utf-8", errors="replace")
        if "feed_hidden" not in text or not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            data = yaml.load(parts[1], Loader=yaml.SafeLoader)  # noqa: S506 -- SafeLoader
        except Exception:  # noqa: BLE001 -- a malformed record is QA's to report; it is not exempt
            continue
        if isinstance(data, dict) and data.get("feed_hidden") is True and data.get("permalink"):
            hidden.add(str(data["permalink"]))
    return hidden


def verify(site_dir: Path, source: Path | None) -> tuple[list[str], dict]:
    site = Site(site_dir)
    problems: list[str] = []
    stats: dict = {}

    # PAGER: the feed pages a crawler reaches from /updates/ through plain links.
    feed_pages = [FEED_URL]
    i = 0
    while i < len(feed_pages):
        for link in site.links(feed_pages[i]):
            if FEED_PAGE_RE.fullmatch(link) and link not in feed_pages:
                if site.file_of(link) is None:
                    problems.append(f"PAGER {feed_pages[i]} links {link}, which is not a built page")
                    continue
                feed_pages.append(link)
        i += 1
    built_pages = {"/" + p.parent.relative_to(site_dir).as_posix() + "/"
                   for p in (site_dir / "updates" / "page").glob("*/index.html")} if (site_dir / "updates" / "page").is_dir() else set()
    for orphan in sorted(built_pages - set(feed_pages)):
        problems.append(f"PAGER {orphan} is built but no feed page links it")
    stats["feed_pages"] = len(feed_pages)

    # STAMP: the pages of one build, each saying so. A single-page feed has no pager and fetches nothing.
    if len(feed_pages) > 1:
        stamps = {p: (site.anchors(p).feed_builds or [""])[0] for p in feed_pages}
        first = stamps[FEED_URL]
        for p, stamp in stamps.items():
            if not stamp:
                problems.append(f"STAMP {p} has no build stamp on its pager (data-feed-build): the feed "
                                f"controls would search it alone")
            elif first and stamp != first:
                problems.append(f"STAMP {p} is stamped {stamp!r} but {FEED_URL} {first!r}: feed pages of two builds")

    # BUDGET
    sizes = {p: site.file_of(p).stat().st_size for p in feed_pages}
    for p, size in sizes.items():
        if size > FEED_PAGE_BUDGET_BYTES:
            problems.append(f"BUDGET {p} is {size:,} bytes, over the {FEED_PAGE_BUDGET_BYTES:,}-byte feed page budget")
    stats["largest_feed_page"] = max(sizes.items(), key=lambda kv: kv[1])
    stats["feed_bytes_total"] = sum(sizes.values())

    # COVERAGE
    patches = site.patch_pages()
    hidden = feed_hidden_urls(source)
    listed = patches - hidden
    seen: dict[str, list[str]] = {}
    for p in feed_pages:
        cards = [site_path(h, p) for h in site.anchors(p).card_hrefs]
        if not cards:
            problems.append(f"COVERAGE {p} carries no patch card")
        for c in cards:
            seen.setdefault(c, []).append(p)
    unlinked = sorted(listed - set(seen))
    for url in unlinked[:20]:
        problems.append(f"COVERAGE {url} is listed by the feed but no feed page links it")
    if len(unlinked) > 20:
        problems.append(f"COVERAGE ... and {len(unlinked) - 20} more unlinked patch pages")
    for url, where in sorted(seen.items()):
        if url not in patches:
            problems.append(f"COVERAGE a feed card on {where[0]} links {url}, which is not a patch page")
        elif len(where) > 1:
            problems.append(f"COVERAGE {url} is on {len(where)} feed pages: {', '.join(where)}")
    stats["patch_pages"] = len(patches)
    stats["feed_hidden"] = len(hidden & patches)
    stats["linked_by_feed"] = len(listed & set(seen))

    # REACH: breadth-first from the homepage over crawlable links.
    dist = {"/": 0}
    queue = deque(["/"])
    while queue:
        u = queue.popleft()
        if dist[u] >= MAX_HOPS:
            continue
        for v in site.links(u):
            if v not in dist and site.file_of(v) is not None:
                dist[v] = dist[u] + 1
                queue.append(v)
    unreached = sorted(patches - set(dist))
    for url in unreached[:20]:
        problems.append(f"REACH {url} is not reached from / within {MAX_HOPS} crawlable hops")
    if len(unreached) > 20:
        problems.append(f"REACH ... and {len(unreached) - 20} more unreached patch pages")
    stats["reached"] = len(patches & set(dist))
    stats["max_hops"] = max((dist[u] for u in patches if u in dist), default=0)
    return problems, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--site", required=True, type=Path, help="the built site directory")
    ap.add_argument("--source", type=Path, default=None,
                    help="the Jekyll source (for feed_hidden records); default: the site's parent")
    args = ap.parse_args(argv)
    site_dir = args.site
    if not (site_dir / "index.html").is_file() or not (site_dir / "updates" / "index.html").is_file():
        print(f"verify_feed_discovery: {site_dir} has no index.html or updates/index.html", file=sys.stderr)
        return 2
    source = args.source if args.source is not None else site_dir.resolve().parent
    if not (source / "updates").is_dir():
        source = None
    problems, stats = verify(site_dir, source)
    largest_url, largest = stats["largest_feed_page"]
    print(f"feed pages {stats['feed_pages']}; largest {largest_url} {largest:,} B of {FEED_PAGE_BUDGET_BYTES:,}; "
          f"all feed pages {stats['feed_bytes_total']:,} B")
    print(f"patch pages {stats['patch_pages']}; feed-hidden {stats['feed_hidden']}; linked by the feed "
          f"{stats['linked_by_feed']}; reached from / {stats['reached']} within {MAX_HOPS} hops "
          f"(max {stats['max_hops']})")
    for p in problems:
        print(f"FAIL {p}")
    if problems:
        print(f"verify_feed_discovery: {len(problems)} problem(s)")
        return 1
    print("verify_feed_discovery: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
