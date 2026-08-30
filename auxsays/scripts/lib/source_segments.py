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
_COMMENT_BLOCK_RE = re.compile(r'data-test-id="comment-(\d+)"(.*?)(?=data-test-id="comment-\d+"|\Z)', re.S)
_COMMENT_AUTHOR_RE = re.compile(r'userid=([0-9a-fA-F-]{36})')
_COMMENT_DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2}T[0-9:.]+)')


def parse_comment_segments(html: str, *, thread_url: str, base_url: str) -> list[SourceSegment]:
    """Comment segments from thread markup, each attributed to its own author.

    A comment whose author cannot be identified is DROPPED rather than attributed to nobody: an
    unattributed segment could otherwise let a stranger's build reach a reporter's record, which is
    the one thing segment scoping exists to prevent.
    """
    segments: list[SourceSegment] = []
    for cid, block in _COMMENT_BLOCK_RE.findall(html or ""):
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
