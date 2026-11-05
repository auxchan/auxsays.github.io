#!/usr/bin/env python3
"""Deterministic source-SEGMENT extraction for community threads (R2 attribution correction).

WHY THIS EXISTS. A thread is not one report. It is an authored question plus authored replies, and
those authors are different people making different claims about different machines. Reading a
build from "somewhere on the page" and attaching it to the original poster invents a fact nobody
stated: the OP never said they were on that build, a stranger did. Attribution has to be scoped to
the segment that actually made the claim.

WHAT WAS MEASURED (not assumed). learn.microsoft.com/answers question pages are server-rendered and
embed a schema.org ``QAPage`` block as ``<script type="application/ld+json">``. Probed live against
the three real PowerPoint 2607 calibration threads, that block deterministically yields:

  question  -> id, name (title), text (HTML body), author, authorId          [no timestamp field]
  answers   -> id, text, author, authorId, authorRole, updatedAt, url        [in acceptedAnswer,
               suggestedAnswer and moderatorRecommendedAnswers buckets]

Confirmed absent: comments are NOT present in the structured data and carry no ``data-comment-id``
in the markup, so comments are deliberately NOT modelled -- an unmodelled segment is honest, a
guessed one is not. The question segment carries no timestamp of its own; callers that need one
supply it from the discovery candidate rather than inventing it here.

Answer permalinks (``/en-us/answers/a/<id>``) are stable but do NOT satisfy the repo's existing
``source_url_is_specific`` gate for learn.microsoft.com, which requires ``/answers/questions/<id>``.
Rather than weaken that gate, a segment is addressed by the platform-supported anchor on the thread
URL itself (``.../questions/<qid>/<slug>#answer-<aid>``) -- the id attribute is really in the page.
That URL is specific under the UNCHANGED gate, and it does not collide with the thread URL under the
collector's dedup key (which lowercases and strips a trailing slash, but keeps the fragment).

MACHINE-GENERATED SEGMENTS. Learn Q&A now publishes first-party "AI answer" replies under a
sentinel author id. AUXSAYS doctrine forbids AI in the production intelligence path, so a
machine-generated segment can never become AUXSAYS evidence. Detection is fail-closed: anything
matching the sentinel id, or an author name that reads as a machine byline, is flagged and excluded.
"""
from __future__ import annotations

import html as _html
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

# --- parse status vocabulary -------------------------------------------------
PARSE_OK = "ok"
PARSE_NO_STRUCTURED_DATA = "no_structured_data"
PARSE_UNEXPECTED_SHAPE = "unexpected_shape"

SEGMENT_QUESTION = "question"
SEGMENT_ANSWER = "answer"
SEGMENT_COMMENT = "comment"

# Learn Q&A publishes its first-party generated replies under this fixed author id.
MACHINE_AUTHOR_IDS = frozenset({"a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1"})
# Byline forms that read as machine-generated. Matched case-insensitively on the whole name.
MACHINE_AUTHOR_NAMES = frozenset({"ai answer", "ai-generated answer", "ai assistant", "copilot"})

_LDJSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
_QUESTION_ID_RE = re.compile(r"/answers/questions/(\d+)", re.I)
_ANSWER_BUCKETS = ("acceptedAnswer", "suggestedAnswer", "moderatorRecommendedAnswers")
_MACHINE_NAME_RE = re.compile(r"(ai|bot|assistant)[\s\-_]?(answer|reply|bot|response)?")


def strip_html(value: str) -> str:
    """HTML -> whitespace-NORMALIZED plain text. Not a byte-exact slice of the source."""
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ",
                  value or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def is_machine_generated(author_name: str, author_id: str) -> bool:
    """Fail-closed: an unrecognised byline that reads as a machine is treated as one."""
    if str(author_id or "").strip().lower() in MACHINE_AUTHOR_IDS:
        return True
    name = str(author_name or "").strip().lower()
    if name in MACHINE_AUTHOR_NAMES:
        return True
    return bool(_MACHINE_NAME_RE.fullmatch(name))


def learn_qna_question_id(url: str) -> str:
    match = _QUESTION_ID_RE.search(str(url or ""))
    return match.group(1) if match else ""


# --- canonical Learn report identity (AUX-078) ---------------------------------------------------
#
# WHY. A Learn Q&A question URL carries a title SLUG after the question id, and the slug follows the
# title: when a title is edited (a "(SOLVED)" prefix, a reworded month, a translated first draft) a
# later feed hit arrives under a new slug. Every dedup key in the Learn path was the slugged URL, so
# the same report passed every guard a second time and was counted twice on one patch. The question
# id never changes. It is the identity; the slug is decoration.
#
# THE TWO FORMATS, RECONCILED.
#   * ``SourceSegment.segment_key`` is ``<qid>:<type>:<id>`` with type question / answer / comment.
#     It needs the PARSED thread, so only segment-aware code has it (context resolution).
#   * ``learn_report_key(url)`` is derived from the URL alone, because that is all a stored row keeps
#     (rows carry no segment type and no segment id). It is ``learn:`` followed by the same three
#     slots, read from the URL:
#
#       stored URL form                     learn_report_key                 the segment it can be
#       .../questions/<q>/<slug>            learn:<q>:question:<q>           the question  (= learn: + segment_key)
#       .../questions/<q>/<slug>#comment-<c> learn:<q>:comment:<c>           comment <c>   (= learn: + segment_key)
#       .../questions/<q>/<slug>#answer-<i>  learn:<q>:reply:<i>             answer <i> OR comment <i>
#
#     ``reply`` is deliberate: ``anchor_url`` writes ``#answer-<id>`` for comments too (Teams stores
#     every reply segment that way), so a URL CANNOT tell an answer from a comment and the key does
#     not pretend to. Two consequences, both conservative: one comment stored once as ``#answer-<c>``
#     and once as ``#comment-<c>`` keeps two keys (no producer writes ``#comment-`` today), and an
#     answer and a comment that shared one numeric id would share a key -- exactly as their identical
#     URLs already did before this key existed.
#
# WHO CAN DISTINGUISH WHAT. Segment-aware sites (context resolution's receipts, Teams segment
# discovery, the orchestrator's reply harvest) hold the segment object and could tell an answer from
# a comment, but every dedup decision compares a candidate against something that is only a URL --
# a stored row, a claim, a persisted seen-set -- so every dedup site keys on the URL form, and the
# precise ``segment_key`` stays what it was: the receipt key for context resolution.
#
# SAFETY PROPERTY. Two URLs share a key only if they name the same question id AND the same anchor.
# What it merges that the old key kept apart is ONLY the slug, the locale segment, the scheme, the
# host's case, a query string and a trailing slash. It never merges two question ids, a question with
# one of its replies, or two replies of one thread. Anything it does not recognise -- another host,
# another path shape, an unknown fragment -- returns "" and the caller keeps its historical key byte
# for byte, so a URL this parser does not understand can never collapse into another report.
LEARN_REPORT_KEY_PREFIX = "learn:"
SEGMENT_REPLY_ANCHOR = "reply"
_LEARN_QNA_HOST = "learn.microsoft.com"
_LEARN_QUESTION_PATH_RE = re.compile(
    r"/(?:[a-z]{2}-[a-z]{2}/)?answers/questions/(\d+)(?:/[^/]*)?/?", re.I)
_ANSWER_ANCHOR_RE = re.compile(r"answer-(\d+)", re.I)
_COMMENT_ANCHOR_RE = re.compile(r"comment-(\d+)", re.I)


def learn_report_key(url: str) -> str:
    """Canonical identity of one Microsoft Learn Q&A report, from its URL; "" when not one.

    See the block comment above for the format, the reconciliation with ``segment_key`` and the
    safety property. Callers use ``learn_report_key(url) or <their historical key>``."""
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or parts.netloc.lower() != _LEARN_QNA_HOST:
        return ""
    path = _LEARN_QUESTION_PATH_RE.fullmatch(parts.path)
    if not path:
        return ""
    qid = path.group(1)
    fragment = parts.fragment.strip()
    if not fragment:
        return f"{LEARN_REPORT_KEY_PREFIX}{qid}:{SEGMENT_QUESTION}:{qid}"
    answer = _ANSWER_ANCHOR_RE.fullmatch(fragment)
    if answer:
        return f"{LEARN_REPORT_KEY_PREFIX}{qid}:{SEGMENT_REPLY_ANCHOR}:{answer.group(1)}"
    comment = _COMMENT_ANCHOR_RE.fullmatch(fragment)
    if comment:
        return f"{LEARN_REPORT_KEY_PREFIX}{qid}:{SEGMENT_COMMENT}:{comment.group(1)}"
    return ""


def report_url_key(url: str) -> str:
    """The dedup identity of a report URL: the canonical Learn key for a Learn Q&A URL, otherwise
    the historical normalised URL (strip, trailing slash, lowercase), byte for byte.

    Idempotent: a key is its own key, so a set of keys can be re-keyed safely (a persisted seen-set
    written before this function existed is re-keyed on restore without changing any later entry)."""
    return learn_report_key(url) or str(url or "").strip().rstrip("/").lower()


@dataclass(frozen=True)
class SourceSegment:
    """One authored unit of a thread. The unit attribution is allowed to be scoped to."""

    thread_url: str
    segment_type: str
    segment_id: str
    segment_url: str
    segment_text: str
    author_name: str = ""
    author_id: str = ""
    author_role: str = ""
    segment_date: str = ""
    machine_generated: bool = False

    @property
    def segment_key(self) -> str:
        """Deterministic canonical identity. Thread URL alone is NOT sufficient once resolution is
        segment-scoped -- two segments of one thread must never share a receipt."""
        thread = learn_qna_question_id(self.thread_url) or self.thread_url
        return f"{thread}:{self.segment_type}:{self.segment_id}"

    def as_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["segment_key"] = self.segment_key
        return data


@dataclass
class ThreadSegments:
    """The parsed thread. ``parse_status`` is honest about failure rather than returning nothing."""

    thread_url: str = ""
    thread_id: str = ""
    parse_status: str = PARSE_NO_STRUCTURED_DATA
    detail: str = ""
    segments: list[SourceSegment] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.parse_status == PARSE_OK and bool(self.segments)

    def question(self) -> SourceSegment | None:
        for seg in self.segments:
            if seg.segment_type == SEGMENT_QUESTION:
                return seg
        return None

    def answers(self) -> list[SourceSegment]:
        return [s for s in self.segments if s.segment_type == SEGMENT_ANSWER]

    def by_key(self, segment_key: str) -> SourceSegment | None:
        for seg in self.segments:
            if seg.segment_key == segment_key:
                return seg
        return None


def anchor_url(thread_url: str, segment: SourceSegment) -> str:
    """Address a segment via the platform-supported ``#answer-<id>`` anchor on the thread URL.

    Keeps ``source_url_is_specific`` satisfied without changing it, and stays distinct from the
    thread URL under the collector's canonical dedup key."""
    base = str(thread_url or "").split("#", 1)[0]
    if segment.segment_type == SEGMENT_QUESTION or not segment.segment_id:
        return base
    return f"{base}#answer-{segment.segment_id}"


def parse_learn_qna_thread(thread_url: str, page_html: str) -> ThreadSegments:
    """Parse a Learn Q&A thread page into authored segments. Fail-closed on any surprise."""
    parsed = ThreadSegments(thread_url=str(thread_url or ""),
                            thread_id=learn_qna_question_id(thread_url))

    payload: dict[str, Any] | None = None
    for raw in _LDJSON_RE.findall(page_html or ""):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if isinstance(data, list):
            data = next((d for d in data if isinstance(d, dict)
                         and str(d.get("@type", "")).lower() == "qapage"), None)
        if isinstance(data, dict) and str(data.get("@type", "")).lower() == "qapage":
            payload = data
            break
    if payload is None:
        parsed.detail = "no schema.org QAPage ld+json block on the page"
        return parsed

    question = payload.get("mainEntity")
    if not isinstance(question, dict) or str(question.get("@type", "")).lower() != "question":
        parsed.parse_status = PARSE_UNEXPECTED_SHAPE
        parsed.detail = "QAPage mainEntity is not a Question"
        return parsed

    qid = str(question.get("id") or parsed.thread_id or "").strip()
    q_author = str(question.get("author") or "")
    q_author_id = str(question.get("authorId") or "")
    base_url = str(thread_url or "").split("#", 1)[0]
    segments = [SourceSegment(
        thread_url=parsed.thread_url, segment_type=SEGMENT_QUESTION, segment_id=qid,
        segment_url=base_url,
        segment_text=strip_html(f"{question.get('name') or ''} {question.get('text') or ''}"),
        author_name=q_author, author_id=q_author_id,
        author_role=str(question.get("authorRole") or ""),
        # The QAPage block carries no question timestamp; callers supply the discovery date.
        segment_date="",
        machine_generated=is_machine_generated(q_author, q_author_id),
    )]

    for bucket in _ANSWER_BUCKETS:
        for answer in (question.get(bucket) or []):
            if not isinstance(answer, dict):
                continue
            aid = str(answer.get("id") or "").strip()
            if not aid:
                continue
            author = str(answer.get("author") or "")
            author_id = str(answer.get("authorId") or "")
            segments.append(SourceSegment(
                thread_url=parsed.thread_url, segment_type=SEGMENT_ANSWER, segment_id=aid,
                segment_url=f"{base_url}#answer-{aid}",
                segment_text=strip_html(answer.get("text") or ""),
                author_name=author, author_id=author_id,
                author_role=str(answer.get("authorRole") or ""),
                segment_date=str(answer.get("updatedAt") or ""),
                machine_generated=is_machine_generated(author, author_id),
            ))

    segments.extend(parse_comment_segments(page_html, thread_url=parsed.thread_url, base_url=base_url))

    parsed.parse_status = PARSE_OK
    parsed.segments = segments
    parsed.detail = f"{len(segments)} segments"
    return parsed


# Comments are NOT in the schema.org block -- verified live: the ld+json QAPage carries the question
# and its answer buckets only, while the build a reporter supplies when asked ("The build is current
# channel 2607 20228.20124") appears solely in comment markup. They were previously left unmodelled
# on the grounds that comments carried no stable id; the markup does in fact expose one, together
# with the author's GUID:
#
#     data-test-id="comment-2758987"        ... the comment's own id
#     /en-us/users/na/?userid=<guid>        ... that comment's author
#
# The author GUID is what makes this safe. On the calibration thread the question author is
# 4bf12226-06e6-4d29-81dd-92bb3ba0d634 and the comment stating the build carries the SAME guid,
# while the three other comments carry two different ones. Same-author enrichment and cross-author
# refusal are therefore both decidable from the markup, with no inference.
# The marker locates a comment; it does NOT delimit one. An earlier form ended each block at the
# next marker or \Z, which made the LAST comment absorb every remaining byte of the page -- measured
# at 45,496 characters of footer, nav and "related questions" rail attributed to one author, and an
# answer rendered between two comments absorbed into the preceding one. Foreign text attributed to a
# reporter is exactly what segment scoping exists to prevent, so a comment is now bounded by its OWN
# <li> element, found by depth-tracking so a nested list inside a comment does not end it early.
_COMMENT_MARKER_RE = re.compile(r'data-test-id="comment-(\d+)"')
_LI_TAG_RE = re.compile(r'<(/?)li\b', re.I)


def _comment_block(html: str, start: int, hard_stop: int) -> str:
    """Text of the comment whose marker sits at `start`, bounded by its own </li>.

    Falls back to `hard_stop` (the next marker, or end of document) only when the element is
    unterminated. Never returns more than `hard_stop`, so a missing </li> cannot resurrect the
    absorb-the-rest-of-the-page behaviour.
    """
    depth = 0
    for tag in _LI_TAG_RE.finditer(html, start, hard_stop):
        if tag.group(1):                      # </li>
            if depth == 0:
                return html[start:tag.start()]
            depth -= 1
        else:                                 # <li ...>
            depth += 1
    return html[start:hard_stop]
_COMMENT_AUTHOR_RE = re.compile(r'userid=([0-9a-fA-F-]{36})')
_COMMENT_DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2}T[0-9:.]+)')


def parse_comment_segments(html: str, *, thread_url: str, base_url: str) -> list[SourceSegment]:
    """Comment segments from thread markup, each attributed to its own author.

    A comment whose author cannot be identified is DROPPED rather than attributed to nobody: an
    unattributed segment could otherwise let a stranger's build reach a reporter's record, which is
    the one thing segment scoping exists to prevent.
    """
    segments: list[SourceSegment] = []
    page = html or ""
    markers = list(_COMMENT_MARKER_RE.finditer(page))
    for index, marker in enumerate(markers):
        cid = marker.group(1)
        hard_stop = markers[index + 1].start() if index + 1 < len(markers) else len(page)
        block = _comment_block(page, marker.end(), hard_stop)
        author = _COMMENT_AUTHOR_RE.search(block)
        if not author:
            continue
        text = strip_html(block)
        if not text:
            continue
        date = _COMMENT_DATE_RE.search(block)
        segments.append(SourceSegment(
            thread_url=thread_url, segment_type=SEGMENT_COMMENT, segment_id=cid,
            segment_url=f"{base_url}#comment-{cid}",
            segment_text=text,
            author_name="", author_id=author.group(1),
            author_role="", segment_date=date.group(1) if date else "",
            machine_generated=False,
        ))
    return segments
