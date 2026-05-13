#!/usr/bin/env python3
"""Consensus-to-generated-record updater with dry-run-first safety gates.

Reads structured evidence rows from either production consensus_evidence.yml or
an internal candidate staging file, aggregates by (product_id, update_version),
finds matching generated Markdown records, validates safety gates, and outputs
an auditable plan.

Write mode is intentionally guarded. It requires all of:
  --write --confirm-write --product-id <id> --update-version <version>

Evidence automation uses this to update exactly one generated record after
matching source-backed evidence rows are present in consensus_evidence.yml.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"
DEFAULT_EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"

VALID_SENTIMENTS = {"positive", "moderate", "negative"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}

PROTECTED_FIELDS = frozenset({
    "layout", "title", "description", "permalink",
    "update_entry", "company_id", "product_id",
    "update_product", "update_version",
    "update_published_at", "update_source_url", "update_download_url",
    "official_patch_notes_body", "official_checksums_body",
    "official_summary", "release_summary",
    "quick_verdict", "update_decision_label", "update_decision_body",
    "practical_recommendations", "complaint_themes",
    "record_note", "legacy_manual_report_count", "legacy_manual_report_count_note",
    "legacy_report_count", "evidence_backfill_status",
})

WRITEABLE_FIELDS = {
    "update_report_count",
    "confirmed_patch_specific_report_count",
    "evidence_state",
    "evidence_state_label",
    "consensus_collection_status",
    "update_consensus_label",
    "update_consensus_confidence",
    "consensus_report_count_label",
    "update_consensus_summary",
    "consensus_report",
    "evidence_last_checked",
    "record_last_updated",
    "intelligence_stage",
    "evidence_samples",
    "status_events",
}


def _load_yaml_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("evidence", "candidates"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _load_front_matter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    data = yaml.safe_load(parts[1]) or {}
    return (data if isinstance(data, dict) else {}, parts[2])


def _load_front_matter(path: Path) -> dict[str, Any]:
    data, _body = _load_front_matter_and_body(path)
    return data


def _write_front_matter_and_body(path: Path, data: dict[str, Any], body: str) -> None:
    yaml_text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)
    path.write_text("---\n" + yaml_text + "---\n" + body, encoding="utf-8")


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


def _index_generated_records() -> dict[tuple[str, str], dict[str, Any]]:
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
                "update_product": str(data.get("update_product") or product_id).strip(),
                "current_report_count": _record_count(data),
                "evidence_state": str(data.get("evidence_state") or "").strip(),
                "intelligence_stage": str(data.get("intelligence_stage") or "").strip(),
                "consensus_collection_status": str(data.get("consensus_collection_status") or "").strip(),
                "legacy_manual_report_count": data.get("legacy_manual_report_count"),
            }
    return index


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
    return "official_only" if count == 0 else "pilot_sample"


def _collection_status(count: int) -> str:
    return "deferred_official_only" if count == 0 else "pilot_initial_sample"


def _row_version(row: dict[str, Any], *, is_candidate_mode: bool) -> str:
    if is_candidate_mode:
        return str(row.get("proposed_update_version") or row.get("update_version") or "").strip()
    return str(row.get("update_version") or "").strip()


def _evaluate_gates(
    *,
    product_id: str,
    version: str,
    included_rows: list[dict[str, Any]],
    excluded_rows: list[dict[str, Any]],
    record: dict[str, Any] | None,
    is_candidate_mode: bool,
    write_requested: bool = False,
) -> dict[str, Any]:
    gates: dict[str, dict[str, Any]] = {}
    block_reasons: list[str] = []
    proposed_count = len(included_rows)

    def _gate(name: str, passed: bool, note: str, blocking: bool = True) -> None:
        gates[name] = {"passed": passed, "note": note, "blocking": blocking}
        if not passed and blocking:
            block_reasons.append(name)

    _gate("gate_01_nonzero_count_requires_rows", not (proposed_count > 0 and len(included_rows) == 0), f"Proposed count {proposed_count}; included rows {len(included_rows)}.")
    _gate("gate_02_count_equals_included_rows", proposed_count == len(included_rows), f"proposed_count={proposed_count}, included_rows={len(included_rows)}.")

    if record:
        _gate("gate_03_product_id_matches_record", record["product_id"] == product_id, f"Evidence product_id={product_id!r}, record product_id={record['product_id']!r}.")
        _gate("gate_04_version_matches_record", record["update_version"] == version, f"Evidence version={version!r}, record version={record['update_version']!r}.")
    else:
        _gate("gate_03_product_id_matches_record", False, "No generated record found for this (product_id, version) key.")
        _gate("gate_04_version_matches_record", False, "No generated record found — cannot verify version match.")

    version_mismatches = [r for r in included_rows if _row_version(r, is_candidate_mode=is_candidate_mode) != version]
    _gate("gate_05_no_beta_stable_cross_match", len(version_mismatches) == 0, f"{len(version_mismatches)} included row(s) have a version mismatch vs {version!r}.")

    if record:
        legacy = record.get("legacy_manual_report_count")
        legacy_in_count = legacy not in (None, "") and proposed_count == legacy
        _gate("gate_06_legacy_count_not_verified", not legacy_in_count or len(included_rows) > 0, f"legacy_manual_report_count={legacy!r}; proposed_count={proposed_count}; backed_by_rows={len(included_rows) > 0}.", blocking=False)

        is_official_only = record.get("evidence_state") == "official_only"
        _gate("gate_07_official_only_zero_rows_stays_zero", not (is_official_only and proposed_count > 0 and len(included_rows) == 0), f"evidence_state={record.get('evidence_state')!r}, proposed_count={proposed_count}, included_rows={len(included_rows)}.")

    ambiguous_rows = [r for r in included_rows if not _row_version(r, is_candidate_mode=is_candidate_mode)]
    _gate("gate_08_no_ambiguous_versions", len(ambiguous_rows) == 0, f"{len(ambiguous_rows)} included row(s) have an empty version.")
    _gate("gate_09_record_must_exist_for_write", record is not None, "A matching generated record must exist before a write can proceed.")
    _gate("gate_10_dry_run_precedes_write", True, "Dry-run/write planning completed before any write.", blocking=False)

    missing_url = [r for r in included_rows if not str(r.get("source_url") or "").strip()]
    _gate("gate_11_source_url_required", len(missing_url) == 0, f"{len(missing_url)} included row(s) are missing source_url.")

    if is_candidate_mode:
        bad_version_match = [r for r in included_rows if r.get("exact_version_match") is not True]
        _gate("gate_12_exact_version_match_required", len(bad_version_match) == 0, f"{len(bad_version_match)} candidate row(s) do not have exact_version_match: true.")
        dry_run_false = [r for r in included_rows if r.get("include_in_dry_run") is False]
        _gate("gate_13_include_in_dry_run_required", len(dry_run_false) == 0, f"{len(dry_run_false)} included row(s) have include_in_dry_run: false.")
    else:
        bad_patch_match = [r for r in included_rows if r.get("patch_version_matched") is not True]
        _gate("gate_12_patch_version_matched_required", len(bad_patch_match) == 0, f"{len(bad_patch_match)} evidence row(s) do not have patch_version_matched: true.")
        counted_false = [r for r in included_rows if r.get("counted") is False]
        _gate("gate_13_counted_required", len(counted_false) == 0, f"{len(counted_false)} evidence row(s) have counted: false.")
        source_date_failed = [r for r in included_rows if r.get("source_date_pass") is False]
        _gate("gate_16_source_date_gate_required", len(source_date_failed) == 0, f"{len(source_date_failed)} evidence row(s) failed the source-date gate.")

    access_limited = [
        r for r in included_rows
        if "blocked" in str(r.get("access_status") or "").lower()
        or "limited" in str(r.get("access_status") or "").lower()
    ]
    _gate("gate_14_access_limited_rows_flagged", True, f"{len(access_limited)} included row(s) have limited access metadata; user verification required for promotion.", blocking=False)

    if write_requested:
        _gate("gate_15_write_requested_explicitly", True, "Write mode requested with explicit product/version/confirm flags.")

    would_write = len(block_reasons) == 0
    return {
        "gate_results": gates,
        "blocking_failures": block_reasons,
        "would_write": would_write,
        "write_blocked_reason": "; ".join(block_reasons) if block_reasons else None,
    }


def _filter_rows(rows: list[dict[str, Any]], *, product_id: str, version: str, is_candidate_mode: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for row in rows:
        row_product = str(row.get("product_id") or "").strip()
        row_version = _row_version(row, is_candidate_mode=is_candidate_mode)
        exc_reason: str | None = None

        if row_product != product_id:
            exc_reason = f"wrong_product_id (got {row_product!r})"
        elif row_version != version:
            exc_reason = f"version_mismatch (got {row_version!r}, expected {version!r})"
        elif not str(row.get("source_url") or "").strip():
            exc_reason = "gate_11_missing_source_url"
        elif is_candidate_mode and row.get("exact_version_match") is not True:
            exc_reason = "gate_12_exact_version_match_false"
        elif not is_candidate_mode and row.get("patch_version_matched") is not True:
            exc_reason = "gate_12_patch_version_matched_false"
        elif is_candidate_mode and row.get("include_in_dry_run") is False:
            exc_reason = row.get("rejection_reason") or "gate_13_include_in_dry_run_false"
        elif not is_candidate_mode and row.get("counted") is False:
            exc_reason = "gate_13_counted_false"
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


def _group_rows(rows: list[dict[str, Any]], *, is_candidate_mode: bool) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pid = str(row.get("product_id") or "").strip()
        ver = _row_version(row, is_candidate_mode=is_candidate_mode)
        if pid:
            groups[(pid, ver)].append(row)
    return groups


def _result_for_group(pid: str, ver: str, rows: list[dict[str, Any]], *, is_candidate_mode: bool, records_index: dict[tuple[str, str], dict[str, Any]], write_requested: bool = False) -> dict[str, Any]:
    if not ver:
        return {
            "product_id": pid,
            "update_version": "(empty)",
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
            "rejected_candidate_reasons": [{"id": r.get("id"), "reason": r.get("rejection_reason") or "missing_version"} for r in rows],
            "safety_gate_results": {},
            "blocking_gate_failures": ["all_rows_excluded_no_version"],
            "would_write": False,
            "write_blocked_reason": "all_rows_excluded_no_version",
            "proposed_fields_if_written": {},
            "included_rows": [],
        }

    included, excluded = _filter_rows(rows, product_id=pid, version=ver, is_candidate_mode=is_candidate_mode)
    record = records_index.get((pid, ver))
    sentiments = Counter(str(r.get("sentiment") or "").lower() for r in included)
    themes = Counter(str(r.get("issue_theme") or "unspecified") for r in included)
    count = len(included)
    gate_eval = _evaluate_gates(product_id=pid, version=ver, included_rows=included, excluded_rows=excluded, record=record, is_candidate_mode=is_candidate_mode, write_requested=write_requested)

    evidence_last_checked = _latest_captured_at(included)
    proposed_fields: dict[str, Any] = {}
    if gate_eval["would_write"]:
        proposed_fields = _proposed_record_fields(pid, ver, included, record, evidence_last_checked)

    return {
        "product_id": pid,
        "update_version": ver,
        "matched_generated_record_path": record["path"] if record else None,
        "evidence_row_count": len(rows),
        "included_candidate_count": count,
        "excluded_candidate_count": len(excluded),
        "confirmed_patch_specific_report_count": count,
        "proposed_update_report_count": count,
        "proposed_evidence_state": _evidence_state(count),
        "proposed_consensus_collection_status": _collection_status(count),
        "proposed_consensus_label": _consensus_label(sentiments),
        "proposed_confidence": _confidence(count),
        "proposed_issue_themes": dict(themes.most_common()),
        "source_urls": [str(r.get("source_url") or "") for r in included],
        "included_rows": [_public_row_summary(r, is_candidate_mode=is_candidate_mode) for r in included],
        "rejected_candidate_reasons": [{"id": r.get("id"), "reason": r.get("_exclusion_reason")} for r in excluded],
        "safety_gate_results": gate_eval["gate_results"],
        "blocking_gate_failures": gate_eval["blocking_failures"],
        "would_write": gate_eval["would_write"],
        "write_blocked_reason": gate_eval["write_blocked_reason"],
        "proposed_fields_if_written": proposed_fields,
        "protected_fields_not_touched": sorted(PROTECTED_FIELDS),
    }


def _public_row_summary(row: dict[str, Any], *, is_candidate_mode: bool) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "source_url": row.get("source_url"),
        "source_title": row.get("source_title") or row.get("report_title") or row.get("parent_title"),
        "proposed_update_version": row.get("proposed_update_version") if is_candidate_mode else row.get("update_version"),
        "exact_version_match": row.get("exact_version_match"),
        "patch_version_matched": row.get("patch_version_matched"),
        "access_status": row.get("access_status"),
        "confidence": row.get("confidence"),
        "sentiment": row.get("sentiment"),
        "severity": row.get("severity"),
        "issue_theme": row.get("issue_theme"),
    }


def _proposed_record_fields(pid: str, ver: str, rows: list[dict[str, Any]], record: dict[str, Any] | None, evidence_last_checked: str) -> dict[str, Any]:
    count = len(rows)
    sentiments = Counter(str(r.get("sentiment") or "").lower() for r in rows)
    themes = Counter(str(r.get("issue_theme") or "unspecified") for r in rows)
    consensus_label = _consensus_label(sentiments)
    confidence = _confidence(count)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    version_label = ver
    source_list = "; ".join(str(r.get("source_url") or "") for r in rows if r.get("source_url"))
    product_label = str((record or {}).get("update_product") or pid).strip()
    top_themes = ", ".join(theme for theme, _count in themes.most_common(3)) or "general workflow issues"
    summary = (
        f"AUXSAYS has verified {count} source-backed, patch-specific report"
        f"{'s' if count != 1 else ''} for {product_label} {version_label}. "
        f"The current verified-report set is {consensus_label.lower()} with {confidence} confidence. "
        f"Most common theme{'s' if len(themes) != 1 else ''}: {top_themes}."
    )
    report = (
        f"AUXSAYS counted {count} source-backed, deterministically accepted report"
        f"{'s' if count != 1 else ''} for {product_label} {version_label}. "
        "The promoted evidence rows are stored in consensus_evidence.yml and matched by product_id/update_version; "
        "every accepted row has equal source_weight. "
        f"Sources: {source_list}."
    )
    samples = []
    for row in rows:
        samples.append({
            "source_name": row.get("source_name") or row.get("source_type") or "Source",
            "source_url": row.get("source_url"),
            "source_title": row.get("source_title") or row.get("report_title") or row.get("parent_title"),
            "counted": True,
            "version_matched": row.get("matched_version") or row.get("update_version") or ver,
            "patch_version_matched": True,
            "issue": row.get("issue_theme") or row.get("report_title") or row.get("observed_issue_summary") or "Confirmed patch-specific report",
            "outcome": row.get("severity") or "medium",
        })
    return {
        "update_report_count": count,
        "confirmed_patch_specific_report_count": count,
        "evidence_state": _evidence_state(count),
        "evidence_state_label": "Official source only" if count == 0 else "Verified reports",
        "consensus_collection_status": _collection_status(count),
        "update_consensus_label": consensus_label,
        "update_consensus_confidence": confidence,
        "consensus_report_count_label": "confirmed patch-specific reports",
        "update_consensus_summary": summary,
        "consensus_report": report,
        "evidence_last_checked": evidence_last_checked,
        "record_last_updated": now,
        "intelligence_stage": "manual_watch" if count == 0 else "pilot",
        "evidence_samples": samples,
        "status_events_append": {
            "at": now,
            "label": "Verified reports" if count > 0 else "Insufficient data",
            "note": (
                f"Automated evidence write-back: {count} source-backed, patch-specific "
                f"report{'s' if count != 1 else ''} promoted from consensus_evidence.yml."
            ),
        },
    }


def run_dry_run(*, evidence_path: Path, product_id_filter: str | None, is_candidate_mode: bool, records_index: dict[tuple[str, str], dict[str, Any]], write_requested: bool = False) -> list[dict[str, Any]]:
    all_rows = _load_yaml_list(evidence_path)
    groups = _group_rows(all_rows, is_candidate_mode=is_candidate_mode)
    if product_id_filter:
        groups = {k: v for k, v in groups.items() if k[0] == product_id_filter}
    return [_result_for_group(pid, ver, rows, is_candidate_mode=is_candidate_mode, records_index=records_index, write_requested=write_requested) for (pid, ver), rows in sorted(groups.items())]


def _payload(results: list[dict[str, Any]], *, evidence_path: Path, is_candidate_mode: bool, product_id_filter: str | None, version_filter: str | None, records_index: dict[tuple[str, str], dict[str, Any]], write_mode_active: bool) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "write_back" if write_mode_active else ("dry_run_candidate_staging" if is_candidate_mode else "dry_run_production_evidence"),
        "write_mode_active": write_mode_active,
        "evidence_source": str(evidence_path.relative_to(ROOT) if evidence_path.is_relative_to(ROOT) else evidence_path),
        "product_id_filter": product_id_filter,
        "version_filter": version_filter,
        "generated_records_indexed": len(records_index),
        "aggregate_groups_evaluated": len(results),
        "groups_would_write": sum(1 for r in results if r["would_write"]),
        "groups_write_blocked": sum(1 for r in results if not r["would_write"]),
        "total_included_candidates": sum(r["included_candidate_count"] for r in results),
        "total_excluded_candidates": sum(r["excluded_candidate_count"] for r in results),
        "results": results,
    }


def _write_json(payload: dict[str, Any], output: str | None) -> None:
    json_text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if output:
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_text, encoding="utf-8")
        print(f"Output written to: {out_path}")
    else:
        print(json_text)


def _apply_record_fields(record_path: Path, fields: dict[str, Any]) -> dict[str, Any]:
    data, body = _load_front_matter_and_body(record_path)
    before = deepcopy(data)
    illegal = sorted(k for k in fields if k in PROTECTED_FIELDS)
    if illegal:
        raise RuntimeError(f"Refusing to overwrite protected fields: {illegal}")
    for key, value in fields.items():
        if key == "status_events_append":
            events = data.get("status_events")
            if not isinstance(events, list):
                events = []
            events.append(value)
            data["status_events"] = events
        elif key in WRITEABLE_FIELDS:
            data[key] = value
        else:
            raise RuntimeError(f"Refusing to write unapproved field: {key}")
    _write_front_matter_and_body(record_path, data, body)
    return {"before": before, "after": data}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consensus-to-generated-record dry-run/write-back updater.")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Show proposed changes without writing.")
    parser.add_argument("--write", action="store_true", default=False, help="Write matching generated record after all safety gates pass.")
    parser.add_argument("--confirm-write", action="store_true", default=False, help="Required with --write.")
    parser.add_argument("--product-id", default=None, help="Filter to a single product_id.")
    parser.add_argument("--update-version", default=None, help="Required with --write. Exact generated record update_version.")
    parser.add_argument("--candidate-file", default=None, help="Candidate staging YAML file instead of production consensus_evidence.yml.")
    parser.add_argument("--output", default=None, help="Path to write JSON output.")
    parser.add_argument("--version-filter", default=None, help="Dry-run filter to a specific update_version string.")
    args = parser.parse_args(argv)

    if args.write:
        if not args.confirm_write:
            print("ERROR: --write requires --confirm-write.", file=sys.stderr)
            return 2
        if not args.product_id:
            print("ERROR: --write requires --product-id.", file=sys.stderr)
            return 2
        if not args.update_version:
            print("ERROR: --write requires --update-version.", file=sys.stderr)
            return 2
        if args.candidate_file:
            print("ERROR: --write cannot use --candidate-file. Promote rows to consensus_evidence.yml first.", file=sys.stderr)
            return 2

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
    results = run_dry_run(evidence_path=evidence_path, product_id_filter=args.product_id, is_candidate_mode=is_candidate_mode, records_index=records_index, write_requested=args.write)

    version_filter = args.update_version if args.write else args.version_filter
    if version_filter:
        results = [r for r in results if r["update_version"] == version_filter]

    payload = _payload(results, evidence_path=evidence_path, is_candidate_mode=is_candidate_mode, product_id_filter=args.product_id, version_filter=version_filter, records_index=records_index, write_mode_active=args.write)

    if args.write:
        if len(results) != 1:
            payload["write_result"] = {"success": False, "reason": f"Expected exactly one group to write; found {len(results)}."}
            _write_json(payload, args.output)
            return 2
        result = results[0]
        if not result["would_write"]:
            payload["write_result"] = {"success": False, "reason": result.get("write_blocked_reason")}
            _write_json(payload, args.output)
            return 2
        record_rel = result.get("matched_generated_record_path")
        if not record_rel:
            payload["write_result"] = {"success": False, "reason": "No matching generated record path."}
            _write_json(payload, args.output)
            return 2
        record_path = ROOT / record_rel
        snapshot = _apply_record_fields(record_path, result["proposed_fields_if_written"])
        payload["write_result"] = {
            "success": True,
            "record_path": str(record_path.relative_to(ROOT)),
            "fields_written": sorted(k for k in result["proposed_fields_if_written"].keys() if k != "status_events_append") + ["status_events"],
            "pre_write_report_count": snapshot["before"].get("update_report_count"),
            "post_write_report_count": snapshot["after"].get("update_report_count"),
            "pre_write_evidence_state": snapshot["before"].get("evidence_state"),
            "post_write_evidence_state": snapshot["after"].get("evidence_state"),
        }

    _write_json(payload, args.output)
    print(
        f"[apply_consensus_to_records] {payload['mode']}: {len(results)} group(s); "
        f"{payload['groups_would_write']} would write; {payload['groups_write_blocked']} blocked; "
        f"{payload['total_included_candidates']} included; {payload['total_excluded_candidates']} excluded.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
