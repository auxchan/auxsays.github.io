#!/usr/bin/env python3
"""Refuse to publish a site whose indexing signals contradict each other (G39).

WHY. Four publication defects reached production unnoticed because nothing read the built pages the
way a search engine does: 17 patch pages published "&#39;" and "&amp;" inside their structured data,
one page's source asked for noindex and its HTML never said so (it sat in the sitemap, canonical to
itself), and a stored title carried mojibake. This gate reads the exact bytes about to be served.
It does not, and cannot, say whether Google indexes a page: that needs Search Console data.

WHAT IT CHECKS, on the built site. ERROR blocks the deploy; WARN is printed and never blocks.
  SITEMAP   ERROR  every sitemap <loc> is an https://auxsays.com URL, listed once, served by a built
                   file, and (for a page) that page's single canonical names exactly that URL. A
                   sitemap URL that robots.txt disallows is an error too: the two files disagree.
  CANONICAL ERROR  no page carries more than one canonical link; every canonical is an absolute
                   https://auxsays.com URL that a built file serves.
  ROBOTS    ERROR  no page carries conflicting robots directives (index and noindex, or two robots
                   tags that disagree); no noindex page is listed in the sitemap; every page whose
                   source front matter sets an explicit `robots:` policy renders exactly that policy;
                   no page renders a robots directive its source did not ask for (an accidental
                   noindex de-lists a page silently). Header directives (X-Robots-Tag) cannot be set
                   on GitHub Pages and are a live-verification step, not a build check.
  JSONLD    ERROR  every application/ld+json block parses; no string in a patch page's block
                   (_includes/patch-search-meta.html, which this repository writes) carries an HTML
                   entity (a <script> element is raw text, so "&amp;" there is five characters, not
                   "&"); and that block states the page's own title, description and canonical URL.
                   A page with no block is fine: structured data is not required where a page needs none.
            WARN   an HTML entity in a block the site-wide SEO tag wrote (jekyll-seo-tag escapes the
                   title before it builds its JSON-LD, so any page title with "&" or an apostrophe gets
                   one). None does today; an editorial title must not be able to stop every deploy,
                   so it is reported for a template fix instead.
  HUBS      ERROR  every live-consensus patch page (its verdict box certified live) is linked by a
                   plain <a href> from its product hub page, read up to the crawl window.
            WARN   ... and from its company hub page (a company hub may summarise; the product
                   tracker is the page that must list it).
  MOJIBAKE  WARN   a title, description, h1 or JSON-LD value carrying the UTF-8-read-as-cp1252
                   pattern ("â€™"). Heuristic, so it never blocks: a source may publish such text.

Not every page must be indexable, and not every page needs structured data: an explicit noindex
policy is honoured, and only a contradiction is refused.

Run:  python auxsays/scripts/ci/verify_publication_hygiene.py --site auxsays/_site [--source auxsays]
Exit: 0 clean (warnings allowed), 1 an error, 2 the site directory is unusable.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import yaml

# Run as a bare script (the deploy) or imported as ci.verify_publication_hygiene (the tests): either way
# the crawl window, the URL rules and the link reader are the feed gate's, so "a crawlable link" means
# one thing on this site.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.verify_feed_discovery import CRAWL_WINDOW_BYTES, SITE_HOST, Site, site_path  # noqa: E402

ORIGIN = f"https://{SITE_HOST}"
SITE_TITLE_SUFFIX = " | AUXSAYS"
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

HEAD_END_RE = re.compile(r"</head\s*>", re.I)
CANONICAL_RE = re.compile(r"<link\b[^>]*\brel=[\"']canonical[\"'][^>]*>", re.I)
HREF_RE = re.compile(r"\bhref=[\"']([^\"']*)[\"']", re.I)
ROBOTS_META_RE = re.compile(r"<meta\b[^>]*\bname=[\"'](robots|googlebot)[\"'][^>]*>", re.I)
CONTENT_RE = re.compile(r"\bcontent=[\"']([^\"']*)[\"']", re.I)
JSONLD_RE = re.compile(r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script\s*>", re.I | re.S)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
DESCRIPTION_RE = re.compile(r"<meta name=\"description\" content=\"(.*?)\"", re.S)
H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
BODY_CLASS_RE = re.compile(r"<body class=\"aux-page ([^\"]*)\"")
LIVE_BOX = 'class="update-decision-box update-decision-box--live"'
PATCH_SEARCH_MARKER = "<!-- Patch page search metadata"
# An HTML character reference, named or numeric. Inside JSON-LD it is never decoded.
ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6});")
# UTF-8 bytes read as cp1252: a lead byte (0xE2 for typographic punctuation such as the curly quote and the
# dash, 0xC2/0xC3 for Latin-1 letters and the no-break space) followed by continuation bytes 0x80-0xBF,
# each shown as its cp1252 character. Built from byte values so no editor can decode it into the very text
# it looks for.
_CONT = "[" + re.escape(bytes(range(0x80, 0xC0)).decode("cp1252", errors="ignore")) + "]"
MOJIBAKE_RE = re.compile(chr(0xE2) + _CONT + _CONT + "|[" + chr(0xC2) + chr(0xC3) + "]" + _CONT)
# Source directories that hold no published page front matter (or are build output).
SOURCE_SKIP = {"_site", "_includes", "_layouts", "_data", "_plugins", "_sass", "scripts", "tools", "vendor",
               "node_modules", ".jekyll-cache", ".bundle", "assets", "systems-monitor"}
MAX_REPORTED = 25


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def _fold(value):  # noqa: ANN001, ANN202
    """Whitespace folded the way _text folds a page title, so a value comparison is like for like.

    The include writes the same text into <title> and into the JSON-LD, unfolded; the title is read
    through _text, which folds a no-break space or a doubled space. Folding only that side refused a
    correct page whose stored title holds one (the ingest lane writes U+00A0 from vendor text)."""
    return " ".join(value.split()) if isinstance(value, str) else value


def _directives(content: str) -> set[str]:
    return {d.strip().lower() for d in (content or "").split(",") if d.strip()}


def _index_state(directives: set[str]) -> str | None:
    """'noindex', 'index' or None (the directive says nothing about indexing)."""
    if "noindex" in directives or "none" in directives:
        return "noindex"
    if "index" in directives or "all" in directives:
        return "index"
    return None


class Page:
    """What one built HTML file says to a crawler: its head signals and its structured data."""

    def __init__(self, url: str, path: Path) -> None:
        self.url = url
        raw = path.read_text(encoding="utf-8", errors="replace")
        m = HEAD_END_RE.search(raw)
        head = raw[: m.start()] if m else raw[:200_000]
        self.canonicals = [html.unescape(h.group(1)) for tag in CANONICAL_RE.findall(head)
                           for h in [HREF_RE.search(tag)] if h]
        self.canonical_tags = len(CANONICAL_RE.findall(head))
        self.robots = [(name.lower(), _directives(html.unescape(c.group(1)) if c else ""))
                       for tag, name in ((t.group(0), t.group(1)) for t in ROBOTS_META_RE.finditer(head))
                       for c in [CONTENT_RE.search(tag)]]
        self.jsonld = JSONLD_RE.findall(raw)
        self.titles = [_text(t) for t in TITLE_RE.findall(head)]
        self.descriptions = [html.unescape(d) for d in DESCRIPTION_RE.findall(head)]
        body = BODY_CLASS_RE.search(raw)
        self.layout = body.group(1).strip() if body else ""
        self.is_patch_meta = PATCH_SEARCH_MARKER in head
        self.live = LIVE_BOX in raw
        h1 = H1_RE.search(raw[m.end():] if m else raw)
        self.h1 = _text(h1.group(1)) if h1 else ""

    def index_states(self) -> set[str]:
        return {s for _, d in self.robots for s in [_index_state(d)] if s}

    def robots_policy(self) -> str:
        """The page's robots directives as one normalised string ('' when it states none)."""
        merged = sorted({d for _, ds in self.robots for d in ds})
        return ",".join(merged)


def built_pages(site: Path) -> dict[str, Path]:
    """Every built HTML file by the site URL that serves it (a directory URL for index.html)."""
    out: dict[str, Path] = {}
    for f in site.rglob("*.html"):
        rel = f.relative_to(site).as_posix()
        if rel.startswith("assets/"):
            continue
        if f.name == "index.html":
            parent = rel[: -len("index.html")]
            out["/" + parent] = f
        else:
            out["/" + rel] = f
    return out


def _url_path(url: str) -> str | None:
    """The site path of an absolute auxsays.com URL, or None if it is not one."""
    u = urlparse(url)
    if u.scheme != "https" or u.netloc != SITE_HOST or u.query or u.fragment:
        return None
    return u.path or "/"


def sitemap_urls(site: Path) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    f = site / "sitemap.xml"
    if not f.is_file():
        return [], ["SITEMAP sitemap.xml is missing from the built site"]
    try:
        root = ET.fromstring(f.read_bytes())
    except ET.ParseError as exc:
        return [], [f"SITEMAP sitemap.xml does not parse: {exc}"]
    locs = [(e.text or "").strip() for e in root.iter(f"{SITEMAP_NS}loc")]
    return locs, problems


def robots_txt_disallows(site: Path) -> list[str]:
    """The Disallow prefixes robots.txt applies to every crawler (User-agent: *)."""
    f = site / "robots.txt"
    if not f.is_file():
        return []
    prefixes: list[str] = []
    applies = False
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (x.strip() for x in line.split(":", 1))
        if key.lower() == "user-agent":
            applies = value == "*"
        elif key.lower() == "disallow" and applies and value:
            prefixes.append(value)
    return prefixes


def _front_matter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return None
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None
    try:
        data = yaml.load(m.group(1), Loader=yaml.SafeLoader)  # noqa: S506 -- SafeLoader
    except Exception:  # noqa: BLE001 -- a malformed record is QA's to report
        return None
    return data if isinstance(data, dict) else None


def explicit_robots_policies(source: Path | None) -> dict[str, str]:
    """{site URL: normalised directives} for every source page whose front matter sets `robots:`.

    Only an EXPLICIT field is a policy. Generated patch records never carry one, so the scan reads
    the text first and parses only files that mention the key."""
    policies: dict[str, str] = {}
    if source is None:
        return policies
    candidates: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(source):
        if Path(dirpath) == source:  # prune build output and non-page trees (vendor/bundle is large)
            dirnames[:] = [d for d in dirnames if d not in SOURCE_SKIP]
        candidates += [Path(dirpath) / n for n in filenames if n.endswith((".md", ".html"))]
    for f in sorted(candidates):
        rel = f.relative_to(source).parts
        if b"\nrobots:" not in f.read_bytes()[:20_000]:
            continue
        data = _front_matter(f)
        if not data or "robots" not in data:
            continue
        url = str(data.get("permalink") or "").strip()
        if not url:
            stem = "/".join(rel)[: -len(f.suffix)]
            url = "/" + (stem[: -len("index")] if stem.endswith("index") else stem + "/")
        policies[url] = ",".join(sorted(_directives(str(data.get("robots") or ""))))
    return policies


def _strings(value) -> list[str]:  # noqa: ANN001
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return [value] if isinstance(value, str) else []


def verify(site_dir: Path, source: Path | None) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict = {}
    files = built_pages(site_dir)
    pages = {url: Page(url, path) for url, path in files.items()}
    stats["pages"] = len(pages)

    # SITEMAP
    locs, found = sitemap_urls(site_dir)
    errors.extend(found)
    stats["sitemap_urls"] = len(locs)
    in_sitemap: set[str] = set()
    disallowed = robots_txt_disallows(site_dir)
    for loc in locs:
        path = _url_path(loc)
        if path is None:
            errors.append(f"SITEMAP {loc!r} is not an https://{SITE_HOST} URL")
            continue
        if path in in_sitemap:
            errors.append(f"SITEMAP {loc} is listed more than once")
            continue
        in_sitemap.add(path)
        if any(path.startswith(p) for p in disallowed):
            errors.append(f"SITEMAP {loc} is listed but robots.txt disallows it")
        page = pages.get(path)
        if page is None:
            if not (site_dir / path.lstrip("/")).is_file():
                errors.append(f"SITEMAP {loc} is listed but no built file serves it")
            continue
        if page.canonicals != [loc]:
            errors.append(f"SITEMAP {loc} is listed but its page's canonical is {page.canonicals!r}")

    # CANONICAL
    with_canonical = 0
    for url, page in sorted(pages.items()):
        if not page.canonical_tags:
            continue
        with_canonical += 1
        if page.canonical_tags > 1:
            errors.append(f"CANONICAL {url} carries {page.canonical_tags} canonical links")
        for target in page.canonicals:
            path = _url_path(target)
            if path is None:
                errors.append(f"CANONICAL {url} names {target!r}, not an absolute https://{SITE_HOST} URL")
            elif path not in pages and not (site_dir / path.lstrip("/")).is_file():
                errors.append(f"CANONICAL {url} names {target}, which no built file serves")
    stats["with_canonical"] = with_canonical

    # ROBOTS
    policies = explicit_robots_policies(source)
    stats["explicit_policies"] = len(policies)
    noindex = 0
    for url, page in sorted(pages.items()):
        states = page.index_states()
        if len(states) > 1:
            errors.append(f"ROBOTS {url} carries conflicting robots directives {page.robots!r}")
        if "noindex" in states:
            noindex += 1
            if url in in_sitemap:
                errors.append(f"ROBOTS {url} renders noindex but the sitemap lists it")
        rendered = page.robots_policy()
        if source is not None and url not in policies and rendered:
            errors.append(f"ROBOTS {url} renders robots {rendered!r} but its source sets no robots policy")
    for url, policy in sorted(policies.items()):
        page = pages.get(url)
        if page is None:
            errors.append(f"ROBOTS the source sets robots {policy!r} for {url}, which is not a built page")
        elif page.robots_policy() != policy:
            errors.append(f"ROBOTS {url}: its source sets robots {policy!r}, the page renders "
                          f"{page.robots_policy() or 'none'!r}")
    stats["noindex_pages"] = noindex

    # JSONLD
    blocks = parsed_ok = 0
    entity_pages: list[str] = []
    for url, page in sorted(pages.items()):
        docs = []
        for raw in page.jsonld:
            blocks += 1
            try:
                docs.append(json.loads(raw))
                parsed_ok += 1
            except ValueError as exc:
                errors.append(f"JSONLD {url} has a block that does not parse: {exc}")
        leaked = sorted({m for d in docs for s in _strings(d) for m in ENTITY_RE.findall(s)})
        if leaked:
            entity_pages.append(url)
            if page.is_patch_meta:
                errors.append(f"JSONLD {url} carries HTML entities {leaked[:4]!r} in its structured data")
            else:
                warnings.append(f"JSONLD {url} carries HTML entities {leaked[:4]!r} in the SEO tag's structured "
                                f"data (its title is escaped before the JSON is built)")
        if page.is_patch_meta:
            web = [d for d in docs if isinstance(d, dict) and d.get("@type") == "WebPage"]
            title = page.titles[0][: -len(SITE_TITLE_SUFFIX)] if page.titles and page.titles[0].endswith(
                SITE_TITLE_SUFFIX) else None
            want = {"headline": title, "description": page.descriptions[0] if page.descriptions else None,
                    "url": page.canonicals[0] if page.canonicals else None}
            if len(web) != 1:
                errors.append(f"JSONLD {url} is a patch page with {len(web)} WebPage blocks, not 1")
            else:
                wrong = {k: (web[0].get(k), v) for k, v in want.items() if _fold(web[0].get(k)) != _fold(v)}
                if wrong:
                    errors.append(f"JSONLD {url} states values its page does not: "
                                  + "; ".join(f"{k} {got!r} vs page {exp!r}" for k, (got, exp) in wrong.items()))
        for s in [*page.titles, *page.descriptions, page.h1, *(s for d in docs for s in _strings(d))]:
            if s and MOJIBAKE_RE.search(s):
                warnings.append(f"MOJIBAKE {url}: {MOJIBAKE_RE.search(s).group(0)!r} in {s[:90]!r}")
                break
    stats.update(jsonld_blocks=blocks, jsonld_parsed=parsed_ok, jsonld_entity_pages=len(entity_pages))

    # HUBS
    site = Site(site_dir)
    live = sorted(url for url, page in pages.items() if page.live and page.layout == "aux-update")
    hub_ok = 0
    for url in live:
        hubs = {"aux-patch-product": [], "aux-patch-company": []}
        for link in site.links(url):
            target = pages.get(link)
            if target is not None and target.layout in hubs and link not in hubs[target.layout]:
                hubs[target.layout].append(link)
        products = hubs["aux-patch-product"]
        if not products:
            errors.append(f"HUBS live page {url} links no product hub page")
        for hub in products:
            if url not in site.links(hub):
                errors.append(f"HUBS live page {url} is not linked from its product hub {hub} "
                              f"(read up to {CRAWL_WINDOW_BYTES:,} bytes)")
        for hub in hubs["aux-patch-company"]:
            if url not in site.links(hub):
                warnings.append(f"HUBS live page {url} is not linked from its company hub {hub}")
        if products and all(url in site.links(h) for h in products):
            hub_ok += 1
    stats.update(live_pages=len(live), live_linked_from_product_hub=hub_ok, live_urls=live)
    return errors, warnings, stats


def _report(kind: str, items: list[str]) -> None:
    for item in items[:MAX_REPORTED]:
        print(f"{kind} {item}")
    if len(items) > MAX_REPORTED:
        print(f"{kind} ... and {len(items) - MAX_REPORTED} more")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--site", required=True, type=Path, help="the built site directory")
    ap.add_argument("--source", type=Path, default=None,
                    help="the Jekyll source (for explicit robots policies); default: the site's parent")
    args = ap.parse_args(argv)
    site_dir = args.site
    if not (site_dir / "index.html").is_file():
        print(f"verify_publication_hygiene: {site_dir} has no index.html", file=sys.stderr)
        return 2
    source = args.source if args.source is not None else site_dir.resolve().parent
    if not (source / "_config.yml").is_file():
        source = None
    started = time.monotonic()
    errors, warnings, stats = verify(site_dir, source)
    print(f"pages {stats['pages']}; sitemap URLs {stats['sitemap_urls']}; pages with a canonical "
          f"{stats['with_canonical']}; noindex pages {stats['noindex_pages']}; explicit robots policies "
          f"{stats['explicit_policies'] if source is not None else 'not checked (no source)'}")
    print(f"JSON-LD blocks {stats['jsonld_blocks']}, parsed {stats['jsonld_parsed']}, pages with HTML entities "
          f"{stats['jsonld_entity_pages']}")
    print(f"live-consensus pages {stats['live_pages']}; linked from their product hub "
          f"{stats['live_linked_from_product_hub']}")
    _report("WARN", warnings)
    _report("FAIL", errors)
    print(f"verify_publication_hygiene: {time.monotonic() - started:.1f}s")
    if errors:
        print(f"verify_publication_hygiene: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"verify_publication_hygiene: clean ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
