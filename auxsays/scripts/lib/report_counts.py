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

from pathlib import Path
from typing import Any, Iterable

from patch_collectors.base import load_front_matter_and_body, write_front_matter_and_body
from .patch_identity import patch_key, require_build


def counted_evidence_counts(evidence_rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str, str], int]:
    """Authoritative count of final counted, patch-matched evidence rows per CANONICAL patch identity.

    Predicate (identical to the QA gate): ``counted is not False`` AND ``patch_version_matched is True``.
    Keys are patch_key(product_id, update_version, target_build); Reader and Pro are distinct product_ids
    and are never merged."""
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
    counts = counted_evidence_counts(evidence_rows)
    scope = {str(p).strip() for p in product_ids} if product_ids is not None else None
    changed: list[dict[str, Any]] = []
    for path in sorted(Path(generated_dir).glob("*.md")):
        data, body = load_front_matter_and_body(path)
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
        if (_as_int(data.get("update_report_count")) == n
                and _as_int(data.get("confirmed_patch_specific_report_count")) == n
                and cur_state == new_state
                and str(data.get("consensus_collection_status") or "") == new_status
                and str(data.get("evidence_state_label") or "") == new_label):
            continue  # already authoritative -> no write (idempotent)
        before = _as_int(data.get("update_report_count"))
        data["update_report_count"] = n
        data["confirmed_patch_specific_report_count"] = n
        data["evidence_state"] = new_state
        data["consensus_collection_status"] = new_status
        data["evidence_state_label"] = new_label
        write_front_matter_and_body(path, data, body)
        changed.append({"product_id": product_id, "version": version,
                        "before": before, "after": n, "record": path.name})
    return len(changed), changed
