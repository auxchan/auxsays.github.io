#!/usr/bin/env python3
"""Deterministic exact-build context resolution for build-aware products (R2).

THE PROBLEM. A Learn Q&A search-RSS item carries only a title and a short description. A user who
wrote "PowerPoint Version 2607 crashes on save" in the title but stated the Click-to-Run build
further down the thread is rejected ``missing_exact_build`` -- correctly, because the SEARCH RESULT
did not demonstrate a build. The live production write proof measured exactly three such
candidates. The information may nonetheless exist in the source; we simply never looked at it.

WHAT THIS DOES. For a candidate rejected specifically as ``missing_exact_build``, fetch MORE OF THE
SAME REPORT -- the thread page the candidate's own canonical URL points at -- and look for an
explicitly stated build. If exactly one distinct build is stated, the candidate text is augmented
with that verbatim source sentence and handed BACK to the unchanged acceptance authority, which
re-decides. The authority still has to accept it, and it still applies the exact-build match
against the record's ``target_build``.

WHAT THIS IS NOT. It never infers. Explicitly forbidden and structurally impossible here:

  * the only build AUXSAYS happens to track for that YYMM
  * release-date proximity or Current Channel chronology
  * "latest update"
  * likely Microsoft rollout timing
  * any AI/LLM reasoning (this module imports only the standard library and repo code)

Only a build string the SOURCE itself states, on the SAME thread the report came from, can resolve
a candidate. Two conflicting builds resolve nothing (``conflicting_build``). Unrelated pages that
merely mention the same YYMM are never consulted -- the fetch target is derived from the
candidate's own URL, not from a search.

PROVENANCE. Every attempt returns a structured record (``ResolutionOutcome``) naming the source URL,
the scope fetched, whether an explicit build was found, and the verbatim snippet it came from, so a
resolved acceptance can always be audited back to the sentence that justified it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

# Full Click-to-Run build, e.g. 20228.20110 (matches the collector's own BUILD_RE shape).
BUILD_RE = re.compile(r"(?<![0-9.])(\d{4,6}\.\d{4,6})(?![0-9.])")

# The rejection reason this stage is allowed to act on. Anything else is not_applicable: a report
# rejected for being about another product, another version, an announcement, a bad URL or a
# non-concrete issue is not made countable by finding a build somewhere on its page.
RESOLVABLE_REASON = "missing_exact_build"

# resolution_result vocabulary.
RESOLVED_EXACT_BUILD = "resolved_exact_build"
NO_EXPLICIT_BUILD = "no_explicit_build"
CONFLICTING_BUILD = "conflicting_build"
FETCH_BLOCKED = "fetch_blocked"
FETCH_BROKEN = "fetch_broken"
NOT_APPLICABLE = "not_applicable"

RESOLUTION_RESULTS = frozenset({
    RESOLVED_EXACT_BUILD, NO_EXPLICIT_BUILD, CONFLICTING_BUILD,
    FETCH_BLOCKED, FETCH_BROKEN, NOT_APPLICABLE,
})

METHOD_ID = "learn_qna_thread_context"
SOURCE_SCOPE = "same_thread_page"


@dataclass
class ResolutionOutcome:
    """Auditable record of one resolution attempt."""

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
    provenance_snippet: str = ""
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class ResolutionBudget:
    """Bounded work: a resolver must never turn one collection run into a crawl."""

    max_fetches: int = 8
    fetched: int = 0
    # Receipts across a resumed run: canonical URL -> outcome already produced. A URL is never
    # fetched twice, so a restart after a checkpointed resolution does no duplicate network work.
    receipts: dict[str, ResolutionOutcome] = field(default_factory=dict)

    def exhausted(self) -> bool:
        return self.fetched >= self.max_fetches


def _snippet(text: str, build: str, width: int = 160) -> str:
    """The verbatim source fragment the build was read from -- the provenance evidence."""
    idx = text.find(build)
    if idx < 0:
        return ""
    start = max(0, idx - width // 2)
    return " ".join(text[start:idx + len(build) + width // 2].split())


def find_explicit_builds(text: str) -> list[str]:
    """Distinct full builds explicitly present in the text, in first-appearance order."""
    seen: list[str] = []
    for match in BUILD_RE.findall(text or ""):
        if match not in seen:
            seen.append(match)
    return seen


def resolve_candidate(candidate: dict[str, Any], rejection_reason: str, *,
                      fetch_thread: Callable[[str], tuple[str, str]],
                      budget: ResolutionBudget) -> ResolutionOutcome:
    """Attempt deterministic exact-build resolution for ONE rejected candidate.

    ``fetch_thread(url) -> (text, status)`` is injected: production binds the shared HTTP transport,
    fixtures bind a deterministic stand-in. ``status`` is "ok" | "blocked" | "broken".

    Returns an outcome; the caller decides whether to re-run the acceptance authority. This
    function never decides acceptance itself."""
    url = str(candidate.get("source_url") or "").strip()
    outcome = ResolutionOutcome(original_candidate_url=url,
                                original_rejection_reason=str(rejection_reason or ""))

    if rejection_reason != RESOLVABLE_REASON:
        outcome.resolution_result = NOT_APPLICABLE
        outcome.detail = "only missing_exact_build is resolvable"
        return outcome
    if not url:
        outcome.resolution_result = NOT_APPLICABLE
        outcome.detail = "candidate has no source url"
        return outcome
    if url in budget.receipts:
        return budget.receipts[url]          # receipt: never fetch the same thread twice
    if budget.exhausted():
        outcome.resolution_result = NOT_APPLICABLE
        outcome.detail = "resolution budget exhausted"
        return outcome

    outcome.resolution_attempted = True
    outcome.resolution_method = METHOD_ID
    # The fetch target is the candidate's OWN canonical URL: more of the same report, never a
    # search for other pages that happen to mention the same YYMM.
    outcome.resolution_source_url = url
    outcome.resolution_source_scope = SOURCE_SCOPE

    budget.fetched += 1
    try:
        text, status = fetch_thread(url)
    except Exception as exc:  # noqa: BLE001 -- transport failure is telemetry, not a crash
        outcome.resolution_result = FETCH_BROKEN
        outcome.detail = f"{type(exc).__name__}"
        budget.receipts[url] = outcome
        return outcome

    if status == "blocked":
        outcome.resolution_result = FETCH_BLOCKED
        outcome.detail = "source refused the request"
        budget.receipts[url] = outcome
        return outcome
    if status != "ok":
        outcome.resolution_result = FETCH_BROKEN
        outcome.detail = f"status={status}"
        budget.receipts[url] = outcome
        return outcome

    builds = find_explicit_builds(text)
    if not builds:
        outcome.resolution_result = NO_EXPLICIT_BUILD
        outcome.detail = "thread states no full build"
    elif len(builds) > 1:
        # Two or more distinct builds on the same thread: which one the reporter is on is not
        # demonstrated. Picking either would be inference, so nothing resolves.
        outcome.resolution_result = CONFLICTING_BUILD
        outcome.resolved_build = ""
        outcome.detail = f"conflicting builds stated: {', '.join(builds)}"
    else:
        outcome.explicit_build_found = True
        outcome.resolved_build = builds[0]
        outcome.resolution_result = RESOLVED_EXACT_BUILD
        outcome.resolution_match_basis = "explicit_build_in_same_thread"
        outcome.provenance_snippet = _snippet(text, builds[0])

    budget.receipts[url] = outcome
    return outcome


def augmented_candidate(candidate: dict[str, Any], outcome: ResolutionOutcome) -> dict[str, Any]:
    """The candidate re-presented to the acceptance authority with the SOURCE's own build text.

    The build is appended as the verbatim provenance snippet from the thread -- not as a decision.
    The unchanged authority then applies every gate, including matching that build against the
    record's target_build, so a resolved-but-wrong build still fails ``build_mismatch``."""
    if outcome.resolution_result != RESOLVED_EXACT_BUILD or not outcome.resolved_build:
        return dict(candidate)
    enriched = dict(candidate)
    body = str(enriched.get("report_text") or "")
    enriched["report_text"] = (
        f"{body} [thread context from {outcome.resolution_source_url}: "
        f"{outcome.provenance_snippet or outcome.resolved_build}]"
    ).strip()
    enriched["context_resolved_build"] = outcome.resolved_build
    enriched["context_resolution_source_url"] = outcome.resolution_source_url
    return enriched
