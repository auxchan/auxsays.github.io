#!/usr/bin/env python3
"""Consensus-to-generated-record dry-run updater.

Reads structured evidence rows from either:
  - auxsays/_data/consensus_evidence.yml  (production evidence)
  - A candidate staging file              (--candidate-file)

Aggregates by (product_id, update_version), finds matching generated Markdown
records, validates all safety gates, and outputs a dry-run plan.

THIS SCRIPT DEFAULTS TO DRY-RUN MODE.
It does NOT modify generated records in Phase 1E. The --write flag is present
as a future extension point but is disabled and will exit non-zero if passed.

Usage:
  python auxsays/scripts/apply_consensus_to_records.py --dry-run
  python auxsays/scripts/apply_consensus_to_records.py --dry-run --product-id blackmagic-davinci
  python auxsays/scripts/apply_consensus_to_records.py --dry-run \\
      --candidate-file .project-control/evidence-staging/davinci-real-evidence-candidates.yml
  python auxsays/scripts/apply_consensus_to_records.py --dry-run \\
      --product-id blackmagic-davinci \\
      --candidate-file .project-control/evidence-staging/davinci-real-evidence-candidates.yml \\
      --output .project-control/probe-output/phase1e/davinci-real-candidate-consensus-dry-run.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"
DEFAULT_EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"

VALID_SENTIMENTS = {"positive", "moderate", "negative"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}

# Fields the write-back MUST NEVER overwrite (editorial/identity fields).
PROTECTED_FIELDS = frozenset({
    "layout", "title", "description", "permalink",
    "update_entry", "company_id", "product_id",
    "update_product", "update_version",
    "update_published_at", "update_source_url", "update_download_url",
    "official_patch_notes_body", "official_checksums_body",
    "official_summary", "release_summary",
    "quick_verdict", "update_decision_label", "update_decision_body",
    "practical_recommendations", "complaint_themes",
    "record_note", "legacy_manual_report_count",
    "legacy_report_count", "evidence_backfill_status",
})


# ─────────────────────────────────────────────────────────────────────────── #
# Loading helpers                                                              #
# ─────────────────────────────────────────────────────────────────────────── #

def _load_yaml_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        # consensus_evidence.yml uses {"schema_version": 1, "evidence": [...]}
        for key in ("evidence", "candidates"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _load_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1]) or {}
    return data if isinstance(data, dict) else {}


def _record_count(data: dict[str, Any]) -> int:
    for key in ("confirmed_patch_specific_report_count", "update_report_count"):
        val = data.get(key)
        if val not in (None, ""):
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0
    return 0


def _latest_captured_at(rows: list[dict[str, Any]]) -> str:
    parsed: list[datetime] = []
    for row in rows:
        value = str(row.get("captured_at") or "").strip()
        if not value:
            continue
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed.append(dt.astimezone(timezone.utc))
        except ValueError:
            continue
    if not parsed:
        return ""
    return max(parsed).isoformat().replace("+00:00", "Z")


# ─────────────────────────────────────────────────────────────────────────── #
# Generated record index                                                       #
# ─────────────────────────────────────────────────────────────────────────── #

def _index_generated_records() -> dict[tuple[str, str], dict[str, Any]]:
    """Return a mapping of (product_id, update_version) → record metadata."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(GENERATED_DIR.glob("*.md")):
        data = _load_front_matter(path)
        if not data.get("update_entry"):
            continue
        product_id = str(data.get("product_id") or "").strip()
        version = str(data.get("update_version") or "").strip()
        if product_id and version:
            index[(product_id, version)] = {
                "path": str(path.relative_to(ROOT)),
                "abs_path": path,
                "product_id": product_id,
                "update_version": version,
                "current_report_count": _record_count(data),
                "evidence_state": str(data.get("evidence_state") or "").strip(),
                "intelligence_stage": str(data.get("intelligence_stage") or "").strip(),
                "consensus_collection_status": str(data.get("consensus_collection_status") or "").strip(),
                "legacy_manual_report_count": data.get("legacy_manual_report_count"),
            }
    return index


# ─────────────────────────────────────────────────────────────────────────── #
# Consensus aggregation (shared with build_consensus_from_evidence.py logic)  #
# ─────────────────────────────────────────────────────────────────────────── #

def _consensus_label(counts: Counter) -> str:
    total = sum(counts.values())
    if total <= 0:
        return "Insufficient data"
    if counts["negative"] / total >= 0.55:
        return "Negative"
    if counts["positive"] / total >= 0.55 and counts["negative"] == 0:
        return "Positive"
    return "Moderate"


def _confidence(total: int) -> str:
    if total >= 25:
        return "Medium"
    if total >= 8:
        return "Low-Medium"
    if total > 0:
        return "Low"
    return "Insufficient"


def _evidence_state(count: int) -> str:
    if count == 0:
        return "official_only"
    return "pilot_sample"


def _collection_status(count: int) -> str:
    if count == 0:
        return "deferred_official_only"
    return "pilot_initial_sample"


# ─────────────────────────────────────────────────────────────────────────── #
# Safety gate evaluation                                                       #
# ─────────────────────────────────────────────────────────────────────────── #

def _evaluate_gates(
    *,
    product_id: str,
    version: str,
    included_rows: list[dict[str, Any]],
    excluded_rows: list[dict[str, Any]],
    record: dict[str, Any] | None,
    is_candidate_mode: bool,
) -> dict[str, Any]:
    """Evaluate all 14 safety gates. Returns gate_results dict and would_write bool."""
    gates: dict[str, dict[str, Any]] = {}
    block_reasons: list[str] = []
    proposed_count = len(included_rows)

    def _gate(name: str, passed: bool, note: str, blocking: bool = True) -> None:
        gates[name] = {"passed": passed, "note": note, "blocking": blocking}
        if not passed and blocking:
            block_reasons.append(name)

    # Gate 1 — nonzero count requires matching rows
    _gate(
        "gate_01_nonzero_count_requires_rows",
        not (proposed_count > 0 and len(included_rows) == 0),
        f"Proposed count {proposed_count} equals included row count {len(included_rows)}.",
    )

    # Gate 2 — count must equal qualifying included row count
    _gate(
        "gate_02_count_equals_included_rows",
        proposed_count == len(included_rows),
        f"proposed_count={proposed_count}, included_rows={len(included_rows)}.",
    )

    # Gate 3 — product_id must match generated record
    if record:
        _gate(
            "gate_03_product_id_matches_record",
            record["product_id"] == product_id,
            f"Evidence product_id={product_id!r}, record product_id={record['product_id']!r}.",
        )
    else:
        _gate(
            "gate_03_product_id_matches_record",
            False,
            "No generated record found for this (product_id, version) key.",
        )

    # Gate 4 — version must match after normalization (direct string match here;
    # normalization is expected to have been applied before rows reach this function)
    if record:
        _gate(
            "gate_04_version_matches_record",
            record["update_version"] == version,
            f"Evidence version={version!r}, record version={record['update_version']!r}.",
        )
    else:
        _gate(
            "gate_04_version_matches_record",
            False,
            "No generated record found — cannot verify version match.",
        )

    # Gate 5 — beta and stable must not cross-match
    # Check that all included rows have the same version string as the record.
    version_mismatches = [
        r for r in included_rows
        if str(r.get("proposed_update_version") or r.get("update_version") or "").strip() != version
    ]
    _gate(
        "gate_05_no_beta_stable_cross_match",
        len(version_mismatches) == 0,
        f"{len(version_mismatches)} included row(s) have a version mismatch vs record version {version!r}.",
    )

    # Gate 6 — legacy_manual_report_count must not drive verified count
    if record:
        legacy = record.get("legacy_manual_report_count")
        legacy_in_count = legacy is not None and legacy != "" and proposed_count == legacy
        _gate(
            "gate_06_legacy_count_not_verified",
            not legacy_in_count or len(included_rows) > 0,
            f"legacy_manual_report_count={legacy!r}; proposed_count={proposed_count}; backed_by_rows={len(included_rows) > 0}.",
            blocking=False,  # Warning only — would be an error if nonzero without rows
        )

    # Gate 7 — official_only records with zero evidence rows stay zero
    if record:
        is_official_only = record.get("evidence_state") == "official_only"
        _gate(
            "gate_07_official_only_zero_rows_stays_zero",
            not (is_official_only and proposed_count > 0 and len(included_rows) == 0),
            f"evidence_state={record.get('evidence_state')!r}, proposed_count={proposed_count}, included_rows={len(included_rows)}.",
        )

    # Gate 8 — ambiguous version normalization blocks write
    # Check for rows that could not be normalized (they should have been excluded already).
    ambiguous_rows = [r for r in included_rows if not str(r.get("proposed_update_version") or r.get("update_version") or "").strip()]
    _gate(
        "gate_08_no_ambiguous_versions",
        len(ambiguous_rows) == 0,
        f"{len(ambiguous_rows)} included row(s) have an empty proposed_update_version.",
    )

    # Gate 9 — no generated record update if no matching record exists
    _gate(
        "gate_09_record_must_exist_for_write",
        record is not None,
        "A matching generated record must exist before a write can proceed.",
    )

    # Gate 10 — dry-run must show proposed changes (always passes in dry-run mode)
    _gate(
        "gate_10_dry_run_mode_active",
        True,
        "Dry-run mode is active. Proposed changes are shown but not written.",
        blocking=False,
    )

    # Gate 11 — candidate rows must have source_url (checked during pre-filtering)
    missing_url = [r for r in included_rows if not str(r.get("source_url") or "").strip()]
    _gate(
        "gate_11_source_url_required",
        len(missing_url) == 0,
        f"{len(missing_url)} included row(s) are missing source_url.",
    )

    # Gate 12 — candidate rows must have exact_version_match: true (pre-filtered)
    no_exact_match = [r for r in included_rows if r.get("exact_version_match") is not True]
    _gate(
        "gate_12_exact_version_match_required",
        len(no_exact_match) == 0,
        f"{len(no_exact_match)} included row(s) do not have exact_version_match: true.",
    )

    # Gate 13 — include_in_dry_run: false rows must not contribute (pre-filtered)
    dry_run_false = [r for r in included_rows if r.get("include_in_dry_run") is False]
    _gate(
        "gate_13_include_in_dry_run_required",
        len(dry_run_false) == 0,
        f"{len(dry_run_false)} included row(s) have include_in_dry_run: false.",
    )

    # Gate 14 — access-limited rows must be flagged
    access_limited = [
        r for r in included_rows
        if "blocked" in str(r.get("access_status") or "").lower()
        or "limited" in str(r.get("access_status") or "").lower()
    ]
    _gate(
        "gate_14_access_limited_rows_flagged",
        True,  # Non-blocking — informational flag
        f"{len(access_limited)} included row(s) have limited access (blocked/snippet_only). Human review recommended.",
        blocking=False,
    )

    would_write = len(block_reasons) == 0
    return {
        "gate_results": gates,
        "blocking_failures": block_reasons,
        "would_write": would_write,
        "write_blocked_reason": "; ".join(block_reasons) if block_reasons else None,
    }


# ─────────────────────────────────────────────────────────────────────────── #
# Row pre-filtering                                                            #
# ─────────────────────────────────────────────────────────────────────────── #

def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    product_id: str,
    version: str,
    is_candidate_mode: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split rows into included and excluded for a given (product_id, version)."""
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for row in rows:
        row_product = str(row.get("product_id") or "").strip()
        # For production evidence: use update_version; for candidates: use proposed_update_version
        if is_candidate_mode:
            row_version = str(row.get("proposed_update_version") or row.get("update_version") or "").strip()
        else:
            row_version = str(row.get("update_version") or "").strip()

        exc_reason: str | None = None

        if row_product != product_id:
            exc_reason = f"wrong_product_id (got {row_product!r})"
        elif row_version != version:
            exc_reason = f"version_mismatch (got {row_version!r}, expected {version!r})"
        elif not str(row.get("source_url") or "").strip():
            exc_reason = "gate_11_missing_source_url"
        elif row.get("exact_version_match") is not True:
            exc_reason = "gate_12_exact_version_match_false"
        elif is_candidate_mode and row.get("include_in_dry_run") is False:
            exc_reason = row.get("rejection_reason") or "gate_13_include_in_dry_run_false"
        elif not is_candidate_mode and row.get("counted") is False:
            exc_reason = "gate_counted_false"
        elif not is_candidate_mode and row.get("patch_version_matched") is not True:
            exc_reason = "gate_patch_version_matched_false"
        elif str(row.get("sentiment") or "").strip().lower() not in VALID_SENTIMENTS:
            exc_reason = f"invalid_sentiment ({row.get('sentiment')!r})"
        else:
            severity = str(row.get("severity") or "").strip().lower()
            if severity and severity not in VALID_SEVERITIES:
                exc_reason = f"invalid_severity ({severity!r})"

        if exc_reason:
            excluded.append({**row, "_exclusion_reason": exc_reason})
        else:
            included.append(row)

    return included, excluded


# ─────────────────────────────────────────────────────────────────────────── #
# Main dry-run logic                                                           #
# ─────────────────────────────────────────────────────────────────────────── #

def run_dry_run(
    *,
    evidence_path: Path,
    product_id_filter: str | None,
    is_candidate_mode: bool,
    records_index: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run the dry-run for all (product_id, version) groups in the evidence file."""
    all_rows = _load_yaml_list(evidence_path)
    results: list[dict[str, Any]] = []

    # Group all rows by (product_id, proposed_update_version or update_version)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        pid = str(row.get("product_id") or "").strip()
        if is_candidate_mode:
            ver = str(row.get("proposed_update_version") or row.get("update_version") or "").strip()
        else:
            ver = str(row.get("update_version") or "").strip()
        if pid and ver:
            groups[(pid, ver)].append(row)
        # Also collect rows with null/missing proposed_update_version into a rejected bucket
        elif pid:
            groups[(pid, "")].append(row)

    # If filter active, only process matching product
    if product_id_filter:
        groups = {k: v for k, v in groups.items() if k[0] == product_id_filter}

    for (pid, ver), rows in sorted(groups.items()):
        if not ver:
            # All rows in this group have no resolvable version — fully excluded
            results.append({
                "product_id": pid,
                "update_version": ver or "(empty)",
                "matched_generated_record_path": None,
                "evidence_row_count": len(rows),
                "included_candidate_count": 0,
                "excluded_candidate_count": len(rows),
                "confirmed_patch_specific_report_count": 0,
                "proposed_update_report_count": 0,
                "proposed_evidence_state": "official_only",
                "proposed_consensus_collection_status": "deferred_official_only",
                "proposed_consensus_label": "Insufficient data",
                "proposed_confidence": "Insufficient",
                "source_urls": [],
                "rejected_candidate_reasons": [
                    str(r.get("rejection_reason") or "missing_proposed_update_version")
                    for r in rows
                ],
                "safety_gate_results": {},
                "would_write": False,
                "write_blocked_reason": "all_rows_excluded_no_version",
            })
            continue

        included, excluded = _filter_rows(rows, product_id=pid, version=ver, is_candidate_mode=is_candidate_mode)
        record = records_index.get((pid, ver))

        sentiments = Counter(str(r.get("sentiment") or "").lower() for r in included)
        themes = Counter(str(r.get("issue_theme") or "unspecified") for r in included)
        proposed_count = len(included)

        gate_eval = _evaluate_gates(
            product_id=pid,
            version=ver,
            included_rows=included,
            excluded_rows=excluded,
            record=record,
            is_candidate_mode=is_candidate_mode,
        )

        # Proposed fields (only meaningful if gates pass)
        proposed_fields: dict[str, Any] = {}
        if gate_eval["would_write"]:
            proposed_fields = {
                "update_report_count": proposed_count,
                "confirmed_patch_specific_report_count": proposed_count,
                "evidence_state": _evidence_state(proposed_count),
                "evidence_state_label": "Official source only" if proposed_count == 0 else "Verified reports",
                "consensus_collection_status": _collection_status(proposed_count),
                "update_consensus_label": _consensus_label(sentiments),
                "update_consensus_confidence": _confidence(proposed_count),
                "evidence_last_checked": _latest_captured_at(included),
                "record_last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }

        results.append({
            "product_id": pid,
            "update_version": ver,
            "matched_generated_record_path": record["path"] if record else None,
            "evidence_row_count": len(rows),
            "included_candidate_count": proposed_count,
            "excluded_candidate_count": len(excluded),
            "confirmed_patch_specific_report_count": proposed_count,
            "proposed_update_report_count": proposed_count,
            "proposed_evidence_state": _evidence_state(proposed_count),
            "proposed_consensus_collection_status": _collection_status(proposed_count),
            "proposed_consensus_label": _consensus_label(sentiments),
            "proposed_confidence": _confidence(proposed_count),
            "proposed_issue_themes": dict(themes.most_common()),
            "source_urls": [str(r.get("source_url") or "") for r in included],
            "included_rows": [
                {
                    "id": r.get("id"),
                    "source_url": r.get("source_url"),
                    "source_title": r.get("source_title"),
                    "proposed_update_version": r.get("proposed_update_version") if is_candidate_mode else r.get("update_version"),
                    "exact_version_match": r.get("exact_version_match"),
                    "patch_version_matched": r.get("patch_version_matched"),
                    "access_status": r.get("access_status"),
                    "confidence": r.get("confidence"),
                    "sentiment": r.get("sentiment"),
                    "severity": r.get("severity"),
                    "issue_theme": r.get("issue_theme"),
                }
                for r in included
            ],
            "rejected_candidate_reasons": [
                {"id": r.get("id"), "reason": r.get("_exclusion_reason")}
                for r in excluded
            ],
            "safety_gate_results": gate_eval["gate_results"],
            "blocking_gate_failures": gate_eval["blocking_failures"],
            "would_write": gate_eval["would_write"],
            "write_blocked_reason": gate_eval["write_blocked_reason"],
            "proposed_fields_if_written": proposed_fields,
            "protected_fields_not_touched": sorted(PROTECTED_FIELDS),
        })

    return results


# ─────────────────────────────────────────────────────────────────────────── #
# CLI                                                                          #
# ─────────────────────────────────────────────────────────────────────────── #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Consensus-to-generated-record dry-run updater. Defaults to dry-run mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run mode (default). Show proposed changes without writing.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        default=False,
        help="(Future) Live write mode. DISABLED in Phase 1E — exits non-zero.",
    )
    parser.add_argument(
        "--product-id",
        default=None,
        help="Filter to a single product_id (e.g. blackmagic-davinci).",
    )
    parser.add_argument(
        "--candidate-file",
        default=None,
        help="Path to a candidate staging YAML file instead of production consensus_evidence.yml.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write JSON output. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--version-filter",
        default=None,
        help="Further filter to a specific update_version string.",
    )

    args = parser.parse_args(argv)

    if args.write:
        print("ERROR: --write mode is disabled in Phase 1E. Use --dry-run.", file=sys.stderr)
        return 2

    # Resolve evidence source
    if args.candidate_file:
        evidence_path = Path(args.candidate_file)
        if not evidence_path.is_absolute():
            evidence_path = Path.cwd() / evidence_path
        is_candidate_mode = True
    else:
        evidence_path = DEFAULT_EVIDENCE_PATH
        is_candidate_mode = False

    if not evidence_path.exists():
        print(f"ERROR: Evidence file not found: {evidence_path}", file=sys.stderr)
        return 1

    records_index = _index_generated_records()
    results = run_dry_run(
        evidence_path=evidence_path,
        product_id_filter=args.product_id,
        is_candidate_mode=is_candidate_mode,
        records_index=records_index,
    )

    # Apply version filter if requested
    if args.version_filter:
        results = [r for r in results if r["update_version"] == args.version_filter]

    output_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "dry_run_candidate_staging" if is_candidate_mode else "dry_run_production_evidence",
        "write_mode_active": False,
        "evidence_source": str(evidence_path.relative_to(ROOT) if evidence_path.is_relative_to(ROOT) else evidence_path),
        "product_id_filter": args.product_id,
        "version_filter": args.version_filter,
        "generated_records_indexed": len(records_index),
        "aggregate_groups_evaluated": len(results),
        "groups_would_write": sum(1 for r in results if r["would_write"]),
        "groups_write_blocked": sum(1 for r in results if not r["would_write"]),
        "total_included_candidates": sum(r["included_candidate_count"] for r in results),
        "total_excluded_candidates": sum(r["excluded_candidate_count"] for r in results),
        "results": results,
        "safety_note": (
            "Dry-run only. No generated records were modified. "
            "Public site counts remain unchanged. "
            "Candidate rows have not been written to consensus_evidence.yml."
        ),
    }

    json_text = json.dumps(output_payload, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_text, encoding="utf-8")
        print(f"Dry-run output written to: {out_path}")
    else:
        print(json_text)

    # Print summary to stderr so it's always visible
    print(
        f"[apply_consensus_to_records] dry-run: {len(results)} group(s) evaluated; "
        f"{output_payload['groups_would_write']} would write; "
        f"{output_payload['groups_write_blocked']} blocked; "
        f"{output_payload['total_included_candidates']} included candidates; "
        f"{output_payload['total_excluded_candidates']} excluded candidates.",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
