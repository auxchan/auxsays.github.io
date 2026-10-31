"""The one authority for a patch record's evidence MATURITY.

Maturity is stored on four axes that every surface reads and, until this module, every writer
derived for itself:

    evidence_state              official_only           | pilot_sample          | consensus_live
    consensus_collection_status deferred_official_only  | pilot_initial_sample  | consensus_live
    evidence_state_label        Official source only    | Verified reports      | Live consensus
    intelligence_stage          official_live           | pilot                 | consensus_live

Four writers each carried a private copy of that table (`report_counts.reconcile_record_counts`,
`apply_consensus_to_records._proposed_record_fields`, `write_update_record.build_front_matter` and
`build_consensus_from_evidence.evidence_state`) and they disagreed. Reconcile never wrote
`intelligence_stage`, so a record demoted to zero kept stage `pilot` (13 records did); the consensus
writer wrote `manual_watch` at zero while record creation wrote `official_live`; and every writer
hardcoded the two-valued mapping, so nothing could ever keep a live state alive through one cycle.

Now every writer asks `record_maturity`, which consults `certify_live` and returns the whole
canonical tuple. A writer cannot write three axes and forget the fourth, and cannot overrule a live
certification with a literal of its own.

The live DECISION itself is `live_eligibility.evaluate`, the same function the deploy-time
projection runs. A writer reaches it through the run context it was handed
(`live_eligibility.RunContext`); a writer handed none can never promote, so a lane that forgets to
build one fails closed to the count's non-live maturity rather than open.

Pure: no I/O and no imports from the writers or from `live_eligibility` (the context is duck-typed),
so `report_counts`, `apply_consensus_to_records`, `write_update_record` and `qa_patch_records` can
all depend on it without a cycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

#: The accepted-report volume a live consensus claim must have behind it. NOT a new threshold: it is
#: the top rung ("High") of the community evidence strength ladder the patch table already publishes
#: and `test_evidence_strength_thresholds` already locks --
#: 0 Insufficient | 1-7 Low | 8-24 Low-Medium | 25-32 Medium | 33+ High.
HIGH_STRENGTH_MIN_REPORTS = 33
LIVE_MIN_ACCEPTED_REPORTS = HIGH_STRENGTH_MIN_REPORTS

#: The four stored maturity axes, in the order they are compared and reported.
AXES = ("evidence_state", "consensus_collection_status", "evidence_state_label", "intelligence_stage")


@dataclass(frozen=True)
class Maturity:
    """One canonical maturity, as all four stored axes at once."""
    level: str
    evidence_state: str
    consensus_collection_status: str
    evidence_state_label: str
    intelligence_stage: str

    def axes(self) -> dict[str, str]:
        return {axis: getattr(self, axis) for axis in AXES}


OFFICIAL_ONLY = Maturity("official", "official_only", "deferred_official_only",
                         "Official source only", "official_live")
PILOT_SAMPLE = Maturity("pilot", "pilot_sample", "pilot_initial_sample",
                        "Verified reports", "pilot")
CONSENSUS_LIVE = Maturity("live", "consensus_live", "consensus_live",
                          "Live consensus", "consensus_live")
CANONICAL = (OFFICIAL_ONLY, PILOT_SAMPLE, CONSENSUS_LIVE)

# READ-side vocabulary. Words a stored record may still carry that no writer emits any more. They
# stay recognised so a consumer meeting one reads it honestly rather than as "unknown"; QA reports a
# record carrying one as non-canonical.
LEGACY_EVIDENCE_STATES = frozenset({"pilot_initial_sample", "insufficient_data"})
#: `live_consensus` is the legacy word order, accepted on READ only because aux-update.html tests both.
LEGACY_LIVE_COLLECTION_STATUSES = frozenset({"live_consensus"})
#: `manual_watch` was the consensus writer's zero-count stage; `staged` and `archived` predate it.
#: None of them is written now. A product-level manual watch is SOURCE configuration
#: (`patch_ingestion_sources.yml` `type: manual_watch`), a different field that this does not touch.
LEGACY_INTELLIGENCE_STAGES = frozenset({"manual_watch", "staged", "archived"})

VALID_EVIDENCE_STATES = frozenset(m.evidence_state for m in CANONICAL) | LEGACY_EVIDENCE_STATES
VALID_COLLECTION_STATUSES = (frozenset(m.consensus_collection_status for m in CANONICAL)
                             | LEGACY_LIVE_COLLECTION_STATUSES)
VALID_EVIDENCE_STATE_LABELS = frozenset(m.evidence_state_label for m in CANONICAL)
VALID_INTELLIGENCE_STAGES = frozenset(m.intelligence_stage for m in CANONICAL) | LEGACY_INTELLIGENCE_STAGES

LIVE_COLLECTION_STATUSES = (CONSENSUS_LIVE.consensus_collection_status,
                            *sorted(LEGACY_LIVE_COLLECTION_STATUSES))
_LIVE_WORDS = {
    "evidence_state": {CONSENSUS_LIVE.evidence_state, *LEGACY_LIVE_COLLECTION_STATUSES},
    "consensus_collection_status": set(LIVE_COLLECTION_STATUSES),
    "evidence_state_label": {CONSENSUS_LIVE.evidence_state_label},
    "intelligence_stage": {CONSENSUS_LIVE.intelligence_stage},
}


def maturity_for(accepted_count: int, *, live: bool = False) -> Maturity:
    """The canonical maturity for an authoritative accepted-report count.

    `live` is a DECISION handed in by `certify_live`, never inferred from the count: volume alone
    does not make consensus live. A live decision below the High rung is a caller bug, so it
    raises rather than publishing a mature claim on thin evidence."""
    count = int(accepted_count)
    if count < 0:
        raise ValueError(f"accepted_count cannot be negative: {accepted_count!r}")
    if live:
        if count < LIVE_MIN_ACCEPTED_REPORTS:
            raise ValueError(f"live consensus needs at least {LIVE_MIN_ACCEPTED_REPORTS} accepted "
                             f"reports; got {count}")
        return CONSENSUS_LIVE
    return OFFICIAL_ONLY if count == 0 else PILOT_SAMPLE


@dataclass(frozen=True)
class LiveDecision:
    """Whether a patch identity is certified live, and why. The reasons are diagnostics for the run
    log; nothing publishes them."""
    live: bool
    reasons: tuple[str, ...] = ()


#: What a writer with no run context decides. Live eligibility needs the whole counted population,
#: the method-health telemetry and one instant, and a writer that was not handed them cannot know
#: whether the collection behind a claim is still running -- so it never promotes, and a live claim
#: it meets is written back as the count's non-live maturity.
NOT_ENABLED = LiveDecision(False, ("no_run_context",))


def certify_live(record: Mapping[str, Any] | None,
                 counted_rows: Iterable[Mapping[str, Any]], context: Any = None) -> LiveDecision:
    """The live-consensus decision for one identity, as every writer reaches it.

    `context` is the run's `live_eligibility.RunContext`, whose `decide` is
    `live_eligibility.evaluate` -- the one place eligibility is computed, shared with the deploy-time
    projection. Every writer asks through here, so promotion and revocation are one function in every
    lane rather than a step one lane adds and the next lane's writer undoes, and both happen on the
    run that observes the change: there is no cooldown to keep a revoked claim alive."""
    if context is None:
        return NOT_ENABLED
    return context.decide(record, counted_rows)


def record_decision(record: Mapping[str, Any] | None, counted_rows: Iterable[Mapping[str, Any]],
                    context: Any = None) -> tuple[Maturity, LiveDecision]:
    """`record_maturity` plus the decision behind it, for a writer that logs transitions."""
    rows = list(counted_rows)
    decision = certify_live(record, rows, context)
    return maturity_for(len(rows), live=decision.live), decision


def record_maturity(record: Mapping[str, Any] | None,
                    counted_rows: Iterable[Mapping[str, Any]], context: Any = None) -> Maturity:
    """The maturity a writer must store for one patch identity, from its AUTHORITATIVE counted rows
    (`report_counts.counted_evidence_rows`, or the consensus writer's identical population).
    `record` must be the record's full front matter: eligibility reads its release date and exact
    build, which the consensus writer's index summary does not carry."""
    return record_decision(record, counted_rows, context)[0]


def stored_axes(data: Mapping[str, Any]) -> dict[str, str]:
    """A record's four stored maturity axes, normalised to strings ('' when absent)."""
    return {axis: str(data.get(axis) or "").strip() for axis in AXES}


def stored_level(data: Mapping[str, Any]) -> str:
    """The canonical level a record's four stored axes spell, or 'noncanonical'. Diagnostics only."""
    axes = stored_axes(data)
    return next((m.level for m in CANONICAL if m.axes() == axes), "noncanonical")


def claims_live(data: Mapping[str, Any]) -> bool:
    """True when ANY axis claims live consensus, in the current or a legacy spelling. One live axis
    is enough: each surface reads a different axis, so a claim on any of them reaches some reader."""
    axes = stored_axes(data)
    return any(axes[axis] in words for axis, words in _LIVE_WORDS.items())


def contradictions(data: Mapping[str, Any], accepted_count: int) -> list[str]:
    """The axes whose stored value differs from the canonical tuple this record must carry.

    A record claiming live on any axis must carry the whole canonical live tuple; otherwise it must
    carry the non-live tuple its count implies. Whether a live claim is EARNED is not decided here
    (that needs the evidence population); this only says whether the four axes agree."""
    expected = CONSENSUS_LIVE if claims_live(data) else maturity_for(max(int(accepted_count), 0))
    want = expected.axes()
    have = stored_axes(data)
    return [axis for axis in AXES if have[axis] != want[axis]]
