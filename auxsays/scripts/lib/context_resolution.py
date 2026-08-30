#!/usr/bin/env python3
"""Deterministic, SEGMENT-SCOPED exact-build context resolution for build-aware products (R2).

THE PROBLEM. A Learn Q&A search-RSS item carries only a title and a short description. A user who
wrote "PowerPoint Version 2607 crashes on save" in the title but stated the Click-to-Run build
further down their own post is rejected ``missing_exact_build`` -- correctly, because the SEARCH
RESULT did not demonstrate a build. The information may nonetheless exist in the source; we simply
never looked at it.

THE ATTRIBUTION RULE. Looking is not enough: it matters WHO said it. A thread is an authored
question plus authored replies by different people on different machines. If the OP writes "2607
crashes when I save" and a stranger replies "I'm on Build 20228.20110", the OP's report is NOT a
20228.20110 report -- the OP never said that, and nothing here may transfer identity between
participants. So build extraction happens strictly WITHIN the segment that produced the candidate:

  * exactly one explicit build in the candidate's OWN segment -> re-present to the UNCHANGED
    acceptance authority, which re-decides and still applies the exact-build match
  * zero  -> no_explicit_build
  * two or more -> conflicting_build (choosing between them would be inference)
  * a build present only in some OTHER segment -> cross_segment_build_ignored, and NOTHING is
    borrowed. It is reported so the effect of scoping is measurable rather than invisible.

INDEPENDENT REPORTS. A reply that stands on its own -- concrete issue, same patch context, exactly
one explicit build it states itself, and a specific platform-supported anchor URL -- is offered back
to the caller as its OWN candidate, evaluated on its own merits by the same authority. It is never
pasted onto somebody else's report. A machine-generated ("AI answer") segment is never offered: AI
text must not enter the evidence corpus.

WHAT THIS IS NOT. It never infers. Explicitly forbidden and structurally impossible here:

  * the only build AUXSAYS happens to track for that YYMM
  * release-date proximity or Current Channel chronology
  * "latest update"
  * likely Microsoft rollout timing
  * any AI/LLM reasoning (this module imports only the standard library and repo code)

Unrelated pages that merely mention the same YYMM are never consulted -- the fetch target is derived
from the candidate's own URL, not from a search.

PROVENANCE. Every attempt returns a structured record (``ResolutionOutcome``) naming the source URL,
the segment and its author, whether an explicit build was found, and the excerpt it came from.
``provenance_excerpt`` is a whitespace-NORMALIZED excerpt of the segment text -- the source markup
is HTML, so a byte-exact slice would not be readable; it is named and documented as normalized
rather than claimed to be verbatim, and ``resolution_source_url`` addresses the exact segment so any
excerpt can be checked against the source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .build_claims import (
    BUILD_TOKEN_RE, ROLE_AMBIGUOUS, ROLE_CURRENT_FAILING, ROLE_ROLLBACK_PREVIOUS, BuildClaim,
    build_tokens, extract_build_claims, role_counts, select_current_failing_build,
    single_named_build,
)
from .source_segments import (
    PARSE_OK, SEGMENT_ANSWER, SEGMENT_QUESTION, SourceSegment, ThreadSegments,
    learn_qna_question_id, parse_learn_qna_thread,
)

# The build token and the role classifier both live in lib.build_claims, which the collector's
# acceptance gate reads too -- one primitive, so the resolver can never see a build the authority
# cannot, and a role can never be judged two different ways.
BUILD_RE = BUILD_TOKEN_RE

# The rejection reason this stage is allowed to act on. Anything else is not_applicable: a report
# rejected for being about another product, another version, an announcement, a bad URL or a
# non-concrete issue is not made countable by finding a build somewhere on its page.
RESOLVABLE_REASON = "missing_exact_build"
# `missing_powerpoint_version` is resolvable for the SAME structural reason. A search-RSS item shows
# only the opener; when a responder asks "what build?" the reporter answers in a comment that names
# BOTH the version and the build ("The build is current channel 2607 20228.20124"). The opener is
# then rejected on the version gate before the build gate is ever reached, so restricting resolution
# to missing_exact_build made that whole class unreachable.
#
# This widens only WHAT MAY BE RECONSIDERED, never what is accepted: the resolver re-presents the
# candidate to the UNCHANGED authority, which re-decides product, version, channel, build, date and
# concrete issue for itself, and it reads only the reporter's OWN segments.
RESOLVABLE_REASONS = frozenset({RESOLVABLE_REASON, "missing_powerpoint_version"})

# resolution_result vocabulary. The first six are the required contract values.
RESOLVED_EXACT_BUILD = "resolved_exact_build"
NO_EXPLICIT_BUILD = "no_explicit_build"
CONFLICTING_BUILD = "conflicting_build"
FETCH_BLOCKED = "fetch_blocked"
FETCH_BROKEN = "fetch_broken"
NOT_APPLICABLE = "not_applicable"
# Added by the attribution correction so scoping is measurable, never silent:
CROSS_SEGMENT_BUILD_IGNORED = "cross_segment_build_ignored"
SEGMENT_NOT_IDENTIFIED = "segment_not_identified"

RESOLUTION_RESULTS = frozenset({
    RESOLVED_EXACT_BUILD, NO_EXPLICIT_BUILD, CONFLICTING_BUILD,
    FETCH_BLOCKED, FETCH_BROKEN, NOT_APPLICABLE,
    CROSS_SEGMENT_BUILD_IGNORED, SEGMENT_NOT_IDENTIFIED,
})

METHOD_ID = "learn_qna_segment_context"
SOURCE_SCOPE = "origin_segment"


@dataclass
class ResolutionOutcome:
    """Auditable record of one resolution attempt, scoped to one authored segment."""

    original_candidate_url: str = ""
    original_rejection_reason: str = ""
    resolution_attempted: bool = False
    resolution_method: str = ""
    resolution_source_url: str = ""
    resolution_source_scope: str = ""
    explicit_build_found: bool = False
    resolved_build: str = ""
    resolution_match_basis: str = ""
    resolution_result: str = NOT_APPLICABLE
    # Segment attribution.
    segment_key: str = ""
    segment_type: str = ""
    segment_id: str = ""
    segment_author_id: str = ""
    segment_author_name: str = ""
    segments_discovered: int = 0
    cross_segment_builds: list[str] = field(default_factory=list)
    # Every build the origin segment named, with the role its own author gave it, and the counts
    # per role -- so a role-attributed acceptance is diagnosable without re-reading the source.
    build_claims: list[dict[str, Any]] = field(default_factory=list)
    role_counts: dict[str, int] = field(default_factory=dict)
    # Whitespace-normalized excerpt of the segment text -- NOT a byte-exact source slice.
    provenance_excerpt: str = ""
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class IndependentReport:
    """A reply that qualifies as a report in its OWN right, offered back as its own candidate."""

    candidate: dict[str, Any]
    segment_key: str
    segment_url: str
    author_id: str
    author_name: str
    explicit_build: str
    provenance_excerpt: str

    def as_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["candidate"] = dict(self.candidate)
        return data


@dataclass
class ResolutionBudget:
    """Bounded work: a resolver must never turn one collection run into a crawl.

    Two distinct caches, because with segment scoping a URL is no longer sufficient identity:

    * ``threads``  -- one NETWORK fetch per thread URL, shared by every segment on it
    * ``receipts`` -- one OUTCOME per segment key, so a restart neither refetches nor confuses two
      segments of the same thread
    """

    max_fetches: int = 8
    fetched: int = 0
    threads: dict[str, tuple[ThreadSegments | None, str]] = field(default_factory=dict)
    receipts: dict[str, ResolutionOutcome] = field(default_factory=dict)

    def exhausted(self) -> bool:
        return self.fetched >= self.max_fetches


def _excerpt(text: str, build: str, width: int = 160) -> str:
    """Normalized excerpt of the segment text around the build -- the provenance evidence."""
    idx = (text or "").find(build)
    if idx < 0:
        return ""
    start = max(0, idx - width // 2)
    return " ".join(text[start:idx + len(build) + width // 2].split())


def find_explicit_builds(text: str) -> list[str]:
    """Distinct full builds explicitly present in the text, in first-appearance order."""
    return build_tokens(text)


def origin_segment(thread: ThreadSegments, candidate: dict[str, Any]) -> SourceSegment | None:
    """The segment that produced this candidate.

    Learn Q&A discovery is search-RSS over QUESTION threads, so a discovered candidate is the
    question segment of its own thread. An already-segment-anchored candidate (``#answer-<id>``)
    resolves to that answer segment instead. Identity is matched on ids, never on text similarity.
    """
    url = str(candidate.get("source_url") or "")
    anchored = re.search(r"#answer-(\d+)\s*$", url)
    if anchored:
        for seg in thread.answers():
            if seg.segment_id == anchored.group(1):
                return seg
        return None
    question = thread.question()
    if question is None:
        return None
    qid = learn_qna_question_id(url)
    if qid and question.segment_id and qid != question.segment_id:
        return None          # the page is not the thread this candidate came from
    return question


def _fetch_thread(url: str, *, fetch_thread: Callable[[str], tuple[str, str]],
                  budget: ResolutionBudget) -> tuple[ThreadSegments | None, str]:
    """One network fetch per thread URL, cached across segments and across a resumed run."""
    if url in budget.threads:
        return budget.threads[url]
    if budget.exhausted():
        budget.threads[url] = (None, "budget_exhausted")
        return budget.threads[url]

    budget.fetched += 1
    try:
        page, status = fetch_thread(url)
    except Exception as exc:  # noqa: BLE001 -- transport failure is telemetry, not a crash
        budget.threads[url] = (None, f"broken:{type(exc).__name__}")
        return budget.threads[url]

    if status == "blocked":
        budget.threads[url] = (None, "blocked")
    elif status != "ok":
        budget.threads[url] = (None, f"broken:status={status}")
    else:
        parsed = parse_learn_qna_thread(url, page)
        budget.threads[url] = ((parsed, "ok") if parsed.parse_status == PARSE_OK
                               else (None, f"broken:{parsed.parse_status}"))
    return budget.threads[url]


def resolve_candidate(candidate: dict[str, Any], rejection_reason: str, *,
                      fetch_thread: Callable[[str], tuple[str, str]],
                      budget: ResolutionBudget) -> ResolutionOutcome:
    """Attempt deterministic, segment-scoped exact-build resolution for ONE rejected candidate.

    ``fetch_thread(url) -> (page_html, status)`` is injected: production binds the shared HTTP
    transport, fixtures bind a deterministic stand-in. ``status`` is "ok" | "blocked" | "broken".
    The page must be RAW HTML -- the segment model reads the page's schema.org structured data.

    Returns an outcome; the caller decides whether to re-run the acceptance authority. This
    function never decides acceptance itself."""
    url = str(candidate.get("source_url") or "").strip()
    outcome = ResolutionOutcome(original_candidate_url=url,
                                original_rejection_reason=str(rejection_reason or ""))

    if rejection_reason not in RESOLVABLE_REASONS:
        outcome.detail = "only missing_exact_build is resolvable"
        return outcome
    if not url:
        outcome.detail = "candidate has no source url"
        return outcome

    thread_url = url.split("#", 1)[0]
    # Provisional receipt lookup: the segment key needs the parse, but an already-decided candidate
    # URL short-circuits before any network work.
    cached = budget.receipts.get(url)
    if cached is not None:
        return cached

    outcome.resolution_attempted = True
    outcome.resolution_method = METHOD_ID
    outcome.resolution_source_scope = SOURCE_SCOPE
    outcome.resolution_source_url = url

    thread, status = _fetch_thread(thread_url, fetch_thread=fetch_thread, budget=budget)
    if thread is None:
        if status == "blocked":
            outcome.resolution_result = FETCH_BLOCKED
            outcome.detail = "source refused the request"
        elif status == "budget_exhausted":
            outcome.resolution_attempted = False
            outcome.resolution_result = NOT_APPLICABLE
            outcome.detail = "resolution budget exhausted"
            return outcome                       # not receipted: a later run may still try
        else:
            outcome.resolution_result = FETCH_BROKEN
            outcome.detail = status
        budget.receipts[url] = outcome
        return outcome

    outcome.segments_discovered = len(thread.segments)
    segment = origin_segment(thread, candidate)
    if segment is None:
        outcome.resolution_result = SEGMENT_NOT_IDENTIFIED
        outcome.detail = "could not attribute the candidate to a segment of this thread"
        budget.receipts[url] = outcome
        return outcome

    outcome.segment_key = segment.segment_key
    outcome.segment_type = segment.segment_type
    outcome.segment_id = segment.segment_id
    outcome.segment_author_id = segment.author_id
    outcome.segment_author_name = segment.author_name
    outcome.resolution_source_url = segment.segment_url or url

    # A segment-keyed receipt: two segments of one thread must never share an outcome.
    prior = budget.receipts.get(segment.segment_key)
    if prior is not None:
        budget.receipts[url] = prior
        return prior

    # AUTHOR-scoped, not segment-scoped. The rule this module states is about WHO spoke -- "a build
    # exists on this thread, but a DIFFERENT participant stated it" -- but the comparison was
    # `segment_key`, so a reporter's OWN later post counted as a stranger's. That is the normal
    # shape of a support thread: the opener describes the symptom, a responder asks for the build,
    # and the SAME person supplies it in a comment. On the calibration thread the question author
    # and the comment naming Build 20228.20124 carry the identical author GUID
    # (4bf12226-06e6-4d29-81dd-92bb3ba0d634), while three other comments carry two different ones.
    #
    # A reporter may therefore complete their own single report. Nothing is relaxed across authors:
    # a segment with a different author_id -- or with no identifiable author at all -- is still
    # "elsewhere" and is still never borrowed.
    own_author = str(segment.author_id or "").strip()

    def _is_own(seg: Any) -> bool:
        other = str(getattr(seg, "author_id", "") or "").strip()
        return bool(own_author) and other == own_author

    # Segments are joined on a CLAUSE BOUNDARY, never a bare space. Real comment text routinely ends
    # without terminal punctuation, and _CLAUSE_SPLIT_RE breaks on newline but not on " ", so a space
    # join merged two segments into ONE clause: cue words from the question ("crashes ... started
    # after") then classified a build named in a later comment, turning a build the author had
    # ROLLED BACK TO into current_failing. The newline keeps each segment its own clause.
    same_author_text = "\n".join(seg.segment_text for seg in thread.segments
                                if _is_own(seg) and seg.segment_key != segment.segment_key)
    elsewhere = [b for seg in thread.segments
                 if seg.segment_key != segment.segment_key and not _is_own(seg)
                 for b in build_tokens(seg.segment_text)]
    # Everything this reporter wrote on this thread, in order: their origin segment first, then any
    # other segment carrying their author id. The provenance excerpt is cut from THIS, so a build
    # they supplied in a later comment is quoted with the sentence that surrounds it -- which is
    # what carries the version alongside it ("The build is current channel 2607 20228.20124").
    own_text = (segment.segment_text + "\n" + same_author_text).strip()
    # The reporter's OWN text is their origin segment plus anything else they wrote on this
    # thread. Build claims are extracted from that combined text so a build they supplied
    # when asked still carries its author's own role language with it.
    claims = extract_build_claims(segment.segment_text + "\n" + same_author_text)
    builds = [c.build for c in claims]
    outcome.cross_segment_builds = sorted(set(elsewhere))
    outcome.build_claims = [c.as_dict() for c in claims]
    outcome.role_counts = role_counts(claims)

    if not builds:
        if outcome.cross_segment_builds:
            # A build exists on this thread, but a DIFFERENT participant stated it. Nothing is
            # borrowed. Reported so the attribution rule's effect is measurable.
            outcome.resolution_result = CROSS_SEGMENT_BUILD_IGNORED
            outcome.detail = ("build(s) stated only by other segments, not by this reporter: "
                              + ", ".join(outcome.cross_segment_builds))
        else:
            outcome.resolution_result = NO_EXPLICIT_BUILD
            outcome.detail = "this reporter's own segment states no full build"
    elif single_named_build(claims):
        # One build named and nothing said to rule it out: behaves exactly as it always has.
        named = single_named_build(claims)
        outcome.explicit_build_found = True
        outcome.resolved_build = named
        outcome.resolution_result = RESOLVED_EXACT_BUILD
        outcome.resolution_match_basis = f"explicit_build_in_own_{segment.segment_type}_segment"
        outcome.provenance_excerpt = _excerpt(own_text, named)
    elif len(set(builds)) == 1:
        # The ONLY build named, and its own author positively placed it somewhere other than the
        # current/failing role -- rolled back to, on another machine, or contradicted. Being the
        # only candidate does not make it the one the report is about, and inventing an unstated
        # current build is exactly what this stage may not do. Nothing resolves.
        outcome.resolution_result = NO_EXPLICIT_BUILD
        outcome.resolved_build = ""
        outcome.detail = ("the only build named is explicitly not the current/failing one: "
                          + "; ".join(f"{c.build}={c.role}({c.match_basis})" for c in claims))
    else:
        # Several builds in the reporter's OWN segment. Their author may have said which is which:
        # "on 2607 (Build A) it crashes, I rolled back to Build B and it works" names A as current
        # and B as previous. Only the author's own explicit role language decides, and only when
        # exactly one build is shown current and none is left unclassified.
        selected, basis, refusal = select_current_failing_build(claims)
        if selected:
            outcome.explicit_build_found = True
            outcome.resolved_build = selected
            outcome.resolution_result = RESOLVED_EXACT_BUILD
            outcome.resolution_match_basis = (
                f"explicit_role_{basis}_in_own_{segment.segment_type}_segment")
            outcome.provenance_excerpt = _excerpt(own_text, selected)
            outcome.detail = ("role-attributed: "
                              + "; ".join(f"{c.build}={c.role}" for c in claims))
        else:
            outcome.resolution_result = CONFLICTING_BUILD
            outcome.resolved_build = ""
            outcome.detail = (f"{refusal}: "
                              + "; ".join(f"{c.build}={c.role}" for c in claims))

    budget.receipts[segment.segment_key] = outcome
    budget.receipts[url] = outcome
    return outcome


def independent_reports(candidate: dict[str, Any], *, budget: ResolutionBudget,
                        exclude_segment_key: str = "",
                        issue_predicate: Callable[[str], bool] | None = None,
                        ) -> list[IndependentReport]:
    """Reply segments of an ALREADY-FETCHED thread that qualify as reports in their own right.

    Requires, per segment: not machine-generated, exactly one explicit build stated by that segment
    itself, and a specific anchor URL. The returned candidates are evaluated by the same unchanged
    acceptance authority on their own merits -- concrete issue, date and version gates all still
    apply, and a segment that fails them simply produces nothing. No network work: this reads the
    thread already fetched for the original candidate, so it can never introduce a second fetch."""
    thread_url = str(candidate.get("source_url") or "").split("#", 1)[0]
    thread, status = budget.threads.get(thread_url, (None, "not_fetched"))
    if thread is None or not thread.ok:
        return []

    found: list[IndependentReport] = []
    for segment in thread.answers():
        if segment.segment_key == exclude_segment_key or segment.machine_generated:
            continue
        # The reply must describe the problem ITSELF. Otherwise a bare "I'm on Build X" would become
        # evidence by borrowing the concrete issue from the question title -- the reply's build is
        # its own, but the issue would be somebody else's. ``issue_predicate`` is injected so this
        # module stays independent of the product collectors; production binds the real gate.
        if issue_predicate is not None and not issue_predicate(segment.segment_text):
            continue
        claims = extract_build_claims(segment.segment_text)
        # Same rule as the origin segment: one build named, or several with exactly one shown
        # current by this reply's OWN author. Never a build this reply merely quotes from elsewhere.
        build = single_named_build(claims) or select_current_failing_build(claims)[0]
        if not build or not segment.segment_url:
            continue
        reply = dict(candidate)
        reply.update({
            "source_url": segment.segment_url,
            "report_title": "",
            "parent_title": str(candidate.get("parent_title") or ""),
            "report_text": segment.segment_text,
            "source_date": segment.segment_date or str(candidate.get("source_date") or ""),
            "segment_key": segment.segment_key,
            "segment_author_id": segment.author_id,
        })
        found.append(IndependentReport(
            candidate=reply, segment_key=segment.segment_key, segment_url=segment.segment_url,
            author_id=segment.author_id, author_name=segment.author_name,
            explicit_build=build,
            provenance_excerpt=_excerpt(segment.segment_text, build),
        ))
    return found


def augmented_candidate(candidate: dict[str, Any], outcome: ResolutionOutcome) -> dict[str, Any]:
    """The candidate re-presented to the acceptance authority with its OWN segment's build text.

    The build is appended as the normalized provenance excerpt from that reporter's own segment --
    not as a decision. The unchanged authority then applies every gate, including matching the build
    against the record's target_build, so a resolved-but-wrong build still fails ``build_mismatch``.
    """
    if outcome.resolution_result != RESOLVED_EXACT_BUILD or not outcome.resolved_build:
        return dict(candidate)
    enriched = dict(candidate)
    body = str(enriched.get("report_text") or "")
    enriched["report_text"] = (
        f"{body} [segment context from {outcome.resolution_source_url}: "
        f"{outcome.provenance_excerpt or outcome.resolved_build}]"
    ).strip()
    enriched["context_resolved_build"] = outcome.resolved_build
    enriched["context_resolution_source_url"] = outcome.resolution_source_url
    enriched["context_resolution_segment_key"] = outcome.segment_key
    return enriched
