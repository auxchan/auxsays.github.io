"""Single authoritative definition of a patch record's report count.

The publishing defect this fixes: a generated record's ``update_report_count`` was written by the
per-collector consensus writer (``apply_consensus_to_records._filter_rows`` -> ``len(included)``) and
by the OBS writer (``collect_obs_reports.counted_evidence_count``), using predicates that DIFFER from
the QA gate (``qa_patch_records.load_counted_evidence_counts``). The consensus writer is STRICTER than
QA (it also requires a non-empty source_url and valid sentiment/severity), so a counted, version-matched
evidence row with e.g. an unclassified sentiment is counted by QA but excluded from the record -> a
record can show 4 while structured evidence has 14 (run 30804068954, adobe-acrobat-pro). The OBS writer
is LOOSER than QA (it omits the patch_version_matched requirement), so it can drift the other way.

This module makes the count SINGLE-SOURCE: ``counted_evidence_counts`` is the authoritative predicate
used by BOTH the QA gate and the post-collection reconciliation, so ``update_report_count`` can never
diverge from what QA enforces. The predicate is deliberately the QA basis -- this does NOT weaken QA,
does not change acceptance (the ``counted`` / ``patch_version_matched`` flags), and does not discard
evidence; it only makes every record's rendered count equal the final counted evidence for that exact
normalized canonical patch identity (product_id, update_version, target_build).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from patch_collectors.base import (WINDOWS_PRODUCT_ID, load_front_matter_and_body,
                                   windows_identity_gate, write_front_matter_and_body)
from .patch_identity import patch_display_label, patch_key, require_build
from .write_update_record import (DEFAULT_CONSENSUS, DEFERRED_CONSENSUS_REPORT,
                                  deferred_quick_verdict)


def windows_targets_from_front_matter(
        records: Iterable[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Canonical patch key -> that Windows record's CURRENT-patch identity.

    Pure: the caller supplies front matter it has already read, so building this costs no extra I/O.
    Windows-only because ``windows_identity_gate`` is the only identity gate keyed on a record's
    rolling ``target_kb``/``target_os_build``; every other product's acceptance is decided by the row
    alone."""
    targets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for data in records or []:
        if not isinstance(data, dict) or data.get("update_entry") is not True:
            continue
        if str(data.get("product_id") or "").strip() != WINDOWS_PRODUCT_ID:
            continue
        version = str(data.get("update_version") or "").strip()
        if not version:
            continue
        targets[patch_key(WINDOWS_PRODUCT_ID, version, data.get("target_build"))] = data
    return targets


def counted_evidence_counts(
        evidence_rows: Iterable[dict[str, Any]],
        *,
        windows_targets: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[tuple[str, str, str], int]:
    """Authoritative count of final counted, patch-matched evidence rows per CANONICAL patch identity.

    Predicate: ``counted is not False`` AND ``patch_version_matched is True`` AND, for
    ``microsoft-windows-11``, the row passes ``windows_identity_gate`` against that record's current
    target identity.

    THE WINDOWS GATE IS PART OF THE PREDICATE, not an extra. A Windows record tracks ONE cumulative
    update (a KB / OS build) inside a feature train, and the train rolls over monthly. Without the
    gate this function counted every row ever accepted for "25H2" -- live, 32 rows spanning THREE
    different cumulative updates (KB5095093/26200.8737, KB5101684/26200.8973 and the record's actual
    KB5121003/26200.9168) -- while the consensus writer counted the 12 belonging to the current
    patch. The record then published `update_report_count: 32` beside prose saying "9 user reports".
    Reports about a superseded KB are reports about a different patch; counting them is exactly the
    version-mismatched evidence AUXSAYS doctrine forbids.

    ``windows_targets`` supplies those identities (see ``windows_targets_from_front_matter``). It is
    keyword-only and REQUIRED, deliberately: if it were optional, omitting it would silently return
    0 for every Windows patch, and ``reconcile_record_counts`` would then write that 0 onto a live
    record. Required makes a forgotten argument a TypeError at the call site instead. Passing a map
    that simply has no entry for some Windows patch stays FAIL-CLOSED -- those rows are not counted
    rather than counted against an unknown identity, the same direction ``windows_identity_gate``
    itself takes -- so a genuinely record-less patch reads 0 while a caller bug cannot.
    Keys are patch_key(product_id, update_version, target_build); Reader and Pro are distinct
    product_ids and are never merged."""
    counts: dict[tuple[str, str, str], int] = {}
    for row in evidence_rows or []:
        if not isinstance(row, dict):
            continue
        product_id = str(row.get("product_id") or "").strip()
        version = str(row.get("update_version") or "").strip()
        if not product_id or not version:
            continue
        if row.get("counted") is False:
            continue
        if row.get("patch_version_matched") is not True:
            continue
        if product_id == WINDOWS_PRODUCT_ID:
            target = windows_targets.get(
                patch_key(product_id, version, row.get("target_build")))
            counts_ok, _reason = windows_identity_gate(row, target)
            if not counts_ok:
                continue
        # Fail closed. This is the AUTHORITATIVE counted-evidence predicate -- QA alignment and
        # record reconciliation both read it. A counted, patch-matched row for a build-aware
        # product that carries no exact build cannot be attributed to any build-specific record;
        # bucketing it under (product, version, "") would create an orphan count that silently
        # never reconciles onto anything. Refuse instead of inventing that bucket.
        require_build(product_id, version, row.get("target_build"),
                      f"counted evidence row {row.get('id') or row.get('source_url')!r}")
        key = patch_key(product_id, version, row.get("target_build"))
        counts[key] = counts.get(key, 0) + 1
    return counts


# Count-derived presentation fields. These MIRROR apply_consensus_to_records exactly -- this module is
# not new scoring, it is the same mapping applied to the authoritative count so a reconciled record
# stays internally consistent (a record can never show "14 reports" while labelled "official only").
def evidence_state_for(count: int) -> str:
    return "official_only" if count == 0 else "pilot_sample"


def evidence_state_label_for(count: int) -> str:
    return "Official source only" if count == 0 else "Verified reports"


def collection_status_for(count: int) -> str:
    return "deferred_official_only" if count == 0 else "pilot_initial_sample"


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# Count PROJECTIONS: fields that publicly assert "this patch has N accepted reports". They are
# written by the consensus writer from the same population the count comes from -- but only while
# that population is NON-EMPTY. `apply_consensus_to_records --write-all` skips a group whose
# confirmed count is <= 0, and `_record_coherence_fields` returns {} at count <= 0, so once the
# population empties nothing downstream can retract what it previously published.
#
# Windows empties one every month. On a KB rollover the record's target moves to the new cumulative
# update, every previously accepted row becomes stale_due_to_patch_rollover, and the count correctly
# falls to 0 -- leaving `0` / "Official source only" published beside "WAIT: ... has 12 user reports
# found" and twelve source links about a superseded KB. That is the same count-vs-prose
# contradiction this module exists to prevent, merely inverted, and it recurs on every patch Tuesday.
#
# Retracting them here follows the one rule the count follows: zero accepted reports means zero
# reported reports. The target shape is a genuine zero record (2026-06-09-windows-11-23h2.md) --
# deferred sentence, no summary, no source list, no samples, "Insufficient data" as the label.
# Measured against the live corpus: all 781 records whose canonical count is 0 already match this
# shape, so on a coherent tree it rewrites nothing.
ZERO_COUNT_PROJECTION_FIELDS = ("update_consensus_summary", "accepted_report_sources",
                                "evidence_samples", "evidence_sample_visible_limit",
                                "evidence_source_limitations")

# RETRACTION IS ONLY SAFE WHERE RESTORATION IS AUTOMATIC.
#
# Retracting is the one thing in this module that DELETES published content, and deletion and
# regeneration are not symmetric: reconciliation runs for every product, but only a product with a
# scoped `apply_consensus_to_records --write-all` step in the lane gets its projections rebuilt when
# its population refills. Retracting for a product without one is a one-way door -- e.g. obs-studio
# 32.2.0 dipping 9 -> 0 -> 9 (which `revalidate_consensus_evidence` can legitimately do) would come
# back with the count restored and the summary and source list gone, which QA then reports as
# `report_count_without_consensus_summary`: a blocking error with no automated way out.
#
# So retraction is limited to the products the lane can regenerate. `test_windows_count_authority`
# asserts this set EQUALS the scoped promotion steps actually present in the workflow, so the two
# cannot drift apart silently. For every other product a stale projection beside a dropped count
# stays visible -- unchanged from before this module retracted anything -- and the QA warning
# `report_count_source_list_mismatch` is what surfaces it.
#
# obs-studio joined when its promotion step did. It is the product that PROVED why membership and a
# promotion step must move together: with no step in the lane, obs 32.2.2's count reached 7 while its
# source list stayed at the first 3 of those 7 issues and its `quick_verdict` still read "has 3 user
# reports found". Coherence had been restored only by the unscoped --write-all in
# davinci-updates.yml, which is manual-dispatch-only.
# adobe-acrobat-pro/-reader joined for the same reason obs-studio did, arriving from the opposite
# direction: they have had scoped promotion steps in the lane for some time, so they satisfied
# `retractable <= promoted` already -- membership was simply never granted. The gap became load
# bearing when vendor-authored posts stopped being counted: two Acrobat records drop to a real zero,
# and NO lane in this repo could produce the zero shape for them. `--write-all` skips zero-count
# groups, so promotion cannot reach them, and without membership `reconcile_record_counts` may not
# retract -- leaving records that publish "has 1 user report found" beside "0 confirmed community
# reports", still listing Adobe's own release announcement as the source, with QA exiting 0.
# Measured blast radius before granting it: of 807 zero-count records across every product, ZERO
# have `zero_count_projection_drift`, so this reaches exactly the records a change drives to zero.
CONSENSUS_PROMOTION_PRODUCTS = frozenset({"microsoft-powerpoint", "microsoft-windows-11",
                                          "obs-studio", "adobe-acrobat-pro",
                                          "adobe-acrobat-reader"})


def format_reconcile_detail(detail: dict[str, Any]) -> str:
    """One log line per reconciled record, naming anything DELETED.

    Separate from the print so it can be tested: a retraction on a record already at zero renders as
    "0 -> 0", which reads as a no-op while a summary, a source list and its samples were removed. The
    only content-destroying step in this lane must not be invisible in the run log."""
    retracted = detail.get("retracted") or []
    suffix = f" (retracted: {', '.join(retracted)})" if retracted else ""
    return (f"{detail['record']}: {detail['product_id']} {detail['version']} "
            f"{detail['before']} -> {detail['after']}{suffix}")


# A headline verdict that STATES a report count is a count projection, whatever field it lives in.
# obs-studio's coherence branch writes "TEST FIRST: OBS Studio 32.2.2 has 7 user reports found" into
# quick_verdict; Windows and PowerPoint have no such branch, so this matches nothing for them. It is
# matched on CONTENT rather than by product, so a hand-written verdict that names no number -- the
# shape premiere 26.2 carries -- is never touched by the retraction.
COUNT_IN_VERDICT_RE = re.compile(r"\d+\s+user report")


def verdict_states_a_count(data: dict[str, Any]) -> bool:
    return bool(COUNT_IN_VERDICT_RE.search(str(data.get("quick_verdict") or "")))


def zero_count_projection_drift(data: dict[str, Any]) -> bool:
    """Does this record still claim accepted reports it no longer has? (No mutation.)"""
    return (str(data.get("consensus_report") or "").strip() != DEFERRED_CONSENSUS_REPORT
            or str(data.get("update_consensus_label") or "").strip() != DEFAULT_CONSENSUS
            or verdict_states_a_count(data)
            or any(field in data for field in ZERO_COUNT_PROJECTION_FIELDS))


def retract_zero_count_projections(data: dict[str, Any]) -> list[str]:
    """Return a record with ZERO accepted reports to the zero shape. Returns the fields changed.

    Deliberately does NOT touch ``update_consensus_confidence`` -- a real zero record stores "Low",
    not ``_confidence(0)``, and 779 of 896 live records already disagree with that function, so
    writing it here would be a corpus-wide change disguised as a coherence fix. Nor does it touch
    ``quick_verdict``, the decision body, recommendations, or official/release prose: those are not
    count projections and are not this function's to rewrite."""
    changed: list[str] = []
    if str(data.get("consensus_report") or "").strip() != DEFERRED_CONSENSUS_REPORT:
        data["consensus_report"] = DEFERRED_CONSENSUS_REPORT
        changed.append("consensus_report")
    # Only when it actually states a number. Retracting the count while leaving the HEADLINE saying
    # "has 7 user reports found" republishes exactly the contradiction this module exists to end --
    # and worse, the QA warning that catches it is keyed on a non-empty source list, which the very
    # next line of this function deletes. So the alarm would go quiet at the same moment the page
    # started lying.
    if verdict_states_a_count(data):
        data["quick_verdict"] = deferred_quick_verdict(
            str(data.get("update_product") or data.get("product_id") or "").strip(),
            patch_display_label(data.get("update_version"), data.get("target_build"),
                                data.get("product_id")))
        changed.append("quick_verdict")
    if str(data.get("update_consensus_label") or "").strip() != DEFAULT_CONSENSUS:
        data["update_consensus_label"] = DEFAULT_CONSENSUS
        changed.append("update_consensus_label")
    for field in ZERO_COUNT_PROJECTION_FIELDS:
        if field in data:
            data.pop(field)
            changed.append(field)
    return changed


def reconcile_record_counts(evidence_rows: Iterable[dict[str, Any]], generated_dir: Path,
                            product_ids: set[str] | None = None) -> tuple[int, list[dict[str, Any]]]:
    """One authoritative reconciliation: after all collectors + consensus, set every update record's
    ``update_report_count`` (and the count-derived state fields) to the final counted evidence for its
    exact canonical patch identity. Idempotent -- an already-aligned tree produces zero writes. Returns
    (changed_count, [details]). Never merges across products; never touches records that already match.

    ``product_ids`` OPTIONALLY narrows the records this call may touch. ``None`` (the default, and
    what every existing production caller passes) means "every product", preserving the whole-tree
    behaviour exactly. A caller that only ran ONE product's collection -- e.g. an orchestration run
    scoped to microsoft-powerpoint -- passes its own product set so a pre-existing mismatch on an
    unrelated product's record cannot be silently rewritten by a run that never collected for it.
    The algorithm is unchanged; this only restricts which records are eligible.
    """
    # ONE pass of record I/O. The Windows identity gate needs each record's current target, so read
    # every record once, build the target map from what we already hold, then count -- rather than
    # scanning the tree twice or re-reading per row.
    loaded = [(path, *load_front_matter_and_body(path))
              for path in sorted(Path(generated_dir).glob("*.md"))]
    counts = counted_evidence_counts(
        evidence_rows,
        windows_targets=windows_targets_from_front_matter(data for _p, data, _b in loaded))
    scope = {str(p).strip() for p in product_ids} if product_ids is not None else None
    changed: list[dict[str, Any]] = []
    for path, data, body in loaded:
        if not isinstance(data, dict) or data.get("update_entry") is not True:
            continue
        product_id = str(data.get("product_id") or "").strip()
        version = str(data.get("update_version") or "").strip()
        if not product_id or not version:
            continue
        if scope is not None and product_id not in scope:
            continue
        n = counts.get(patch_key(product_id, version, data.get("target_build")), 0)
        new_state = evidence_state_for(n)
        new_status = collection_status_for(n)
        cur_state = str(data.get("evidence_state") or "")
        state_changed = cur_state != new_state
        # Only re-derive the label when the count crosses the 0<->N state boundary. Otherwise leave
        # the existing label untouched so this count fix never rewrites legitimate label variation
        # (e.g. "User reports found" vs "Verified reports") or otherwise mutates verdict presentation.
        new_label = evidence_state_label_for(n) if state_changed else str(data.get("evidence_state_label") or "")
        # At zero the record must also stop CLAIMING reports, not merely report the number 0.
        # Two guards, both load-bearing. `counts` being wholly empty means the evidence file was
        # missing, empty, or key-less -- `load_evidence()` returns [] for all three -- and NOT that
        # every patch on earth lost its reports; retracting then would strip 124 records (570 source
        # entries) in one pass, and only two products could ever rebuild them. Reconciling the
        # NUMBERS on an empty map stays as it was, because that is self-healing: the next healthy run
        # restores it. Deleting content is not.
        may_retract = (bool(counts)
                       and product_id in CONSENSUS_PROMOTION_PRODUCTS)
        needs_retraction = n == 0 and may_retract and zero_count_projection_drift(data)
        if (_as_int(data.get("update_report_count")) == n
                and _as_int(data.get("confirmed_patch_specific_report_count")) == n
                and cur_state == new_state
                and str(data.get("consensus_collection_status") or "") == new_status
                and str(data.get("evidence_state_label") or "") == new_label
                and not needs_retraction):
            continue  # already authoritative -> no write (idempotent)
        before = _as_int(data.get("update_report_count"))
        data["update_report_count"] = n
        data["confirmed_patch_specific_report_count"] = n
        data["evidence_state"] = new_state
        data["consensus_collection_status"] = new_status
        data["evidence_state_label"] = new_label
        retracted = (retract_zero_count_projections(data)
                     if n == 0 and may_retract else [])
        write_front_matter_and_body(path, data, body)
        changed.append({"product_id": product_id, "version": version,
                        "before": before, "after": n, "record": path.name,
                        "retracted": retracted})
    return len(changed), changed
