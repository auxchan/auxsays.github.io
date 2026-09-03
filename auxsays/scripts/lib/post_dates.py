#!/usr/bin/env python3
"""When a report was WRITTEN -- not when its thread was last touched.

A feed's ``pubDate`` moves every time somebody replies. Microsoft Q&A bumps it, so a question
asked in November 2025 arrived carrying an August 2026 stamp, and the release window derived from
that stamp was nine months and five builds wrong. For Level 3 the window IS the entire claim, so a
date that means "last activity" quietly turns the one thing the layer asserts into a falsehood --
in the worst case placing a report on the page of a build that had not shipped when it was written.

Order of preference, strongest first:

1. JSON-LD ``mainEntity.dateCreated`` -- the question's own creation date, stated by the site.
   Tech Community serves this, and it is decisive: the surrounding page also carries the
   ``dateCreated`` of each *answer*, which is what a naive scrape picks up.
2. The earliest ``datetime=`` on the page. On a Q&A thread the question precedes every answer, so
   the minimum is the question. This can only ever move a report EARLIER, never later, so it
   cannot manufacture the future-dated placement described above.

No fallback to the feed date. A row whose original date cannot be established is refused rather
than published under a window that may be wrong.
"""
from __future__ import annotations

import json
import re

_LD_BLOCK_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                          re.S | re.I)
_DATETIME_ATTR_RE = re.compile(r'datetime=["\'](\d{4}-\d{2}-\d{2})')
_ISO_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _day(value) -> str:
    match = _ISO_DAY_RE.match(str(value or "").strip())
    return match.group(1) if match else ""


def _walk(node):
    """Yield every mapping in a JSON-LD document, which may be a bare object, a list or @graph."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def original_post_date_from_html(page_html: str) -> str:
    """The day the ORIGINAL post was written, as YYYY-MM-DD, or "" when it cannot be established."""
    html = str(page_html or "")
    if not html:
        return ""

    for block in _LD_BLOCK_RE.finditer(html):
        try:
            document = json.loads(block.group(1))
        except Exception:
            continue
        for node in _walk(document):
            main = node.get("mainEntity")
            if isinstance(main, dict):
                day = _day(main.get("dateCreated"))
                if day:
                    return day
        # A question served as the top-level object rather than under mainEntity.
        for node in _walk(document):
            if str(node.get("@type") or "").lower() in {"question", "discussionforumposting"}:
                day = _day(node.get("dateCreated") or node.get("datePublished"))
                if day:
                    return day

    stamps = sorted({d for d in _DATETIME_ATTR_RE.findall(html)})
    return stamps[0] if stamps else ""
