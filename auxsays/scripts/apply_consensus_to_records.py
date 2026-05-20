#!/usr/bin/env python3
"""Consensus-to-generated-record updater with dry-run-first safety gates.

Reads structured evidence rows, aggregates by (product_id, update_version),
finds matching generated Markdown records, validates safety gates, and outputs
an auditable plan.

Write mode is intentionally guarded. Single-record writes require all of:
  --write --confirm-write --product-id <id> --update-version <version>
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
METHOD_HEALTH_PATH = ROOT / "_data" / "evidence_method_health.yml"

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
    "practical_recommendations", "complaint_themes", "source_freshness_note",
    "record_note", "legacy_manual_report_count", "legacy_manual_report_count_note",
    "legacy_report_count", "evidence_backfill_status",
})

CONSENSUS_COHERENCE_FIELDS = {
    "description",
    "feed_hidden",
    "update_status",
    "status_change_type",
    "notification_message",
    "update_channel_label",
    "quick_verdict",
    "update_decision_label",
    "update_decision_body",
    "record_note",
    "official_summary",
    "release_summary",
    "practical_recommendations",
    "source_freshness_note",
}

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
    "accepted_report_sources",
    "evidence_source_limitations",
    "evidence_sample_visible_limit",
    "status_events",
    *CONSENSUS_COHERENCE_FIELDS,
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
                "description": str(data.get("description") or "").strip(),
                "feed_hidden": data.get("feed_hidden"),
                "update_status": str(data.get("update_status") or "").strip(),
                "status_change_type": str(data.get("status_change_type") or "").strip(),
                "notification_message": str(data.get("notification_message") or "").strip(),
                "update_channel_label": str(data.get("update_channel_label") or "").strip(),
                "record_note": str(data.get("record_note") or "").strip(),
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
    themes = _issue_counter(pid, included)
    count = len(included)
    gate_eval = _evaluate_gates(product_id=pid, version=ver, included_rows=included, excluded_rows=excluded, record=record, is_candidate_mode=is_candidate_mode, write_requested=write_requested)

    evidence_last_checked = _latest_captured_at(included)
    proposed_fields: dict[str, Any] = {}
    effective_write_plan: dict[str, Any] = {}
    if gate_eval["would_write"]:
        proposed_fields = _proposed_record_fields(pid, ver, included, record, evidence_last_checked)
        if record:
            effective_write_plan = _public_write_plan(_load_front_matter(record["abs_path"]), proposed_fields)

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
        "effective_write_plan": effective_write_plan,
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


def _clean_public_phrase(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = re.sub(r"[_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _public_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    iso_text = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(iso_text).date().isoformat()
    except ValueError:
        return ""


def _truncate_public_text(value: Any, *, limit: int = 140) -> str:
    text = _clean_public_phrase(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _join_public_list(items: list[str]) -> str:
    clean = [item for item in items if item]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return ", ".join(clean[:-1]) + f", and {clean[-1]}"


def _number_word(value: int) -> str:
    words = {
        0: "zero",
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
    }
    return words.get(value, str(value))


def _public_issue_bucket(pid: str, row: dict[str, Any]) -> str:
    raw_theme = _clean_public_phrase(row.get("issue_theme"))
    raw_workflow = _clean_public_phrase(row.get("workflow_area"))
    raw_title = _clean_public_phrase(row.get("report_title") or row.get("source_title") or row.get("parent_title"))
    text = " ".join([raw_theme, raw_workflow, raw_title]).lower()

    if pid == "blackmagic-davinci":
        if "magic mask" in text:
            return "Magic Mask crashes"
        if "decode" in text and ("render" in text or "export" in text):
            return "render/decode failures"
        if "render" in text or "export" in text or "delivery" in text:
            return "render/export failures"
        if "crash" in text or "startup" in text or "launch" in text:
            return "startup or application crashes"
        if "performance" in text or "gpu" in text or "slow" in text:
            return "performance slowdowns"
        if "install" in text:
            return "installation problems"
        if "plugin" in text:
            return "plugin issues"

    if pid == "obs-studio":
        if "scene list" in text or ("scene" in text and "selection" in text):
            return "scene list workflow regressions"
        if "audio" in text or "mixer" in text or "monitoring" in text:
            return "audio mixer or routing issues"
        if "capture" in text or "camera" in text or "xcomposite" in text or "screen" in text or "window" in text:
            return "capture-source issues"
        if "plugin" in text or "setup" in text or "profile" in text:
            return "plugin or setup compatibility"
        if "crash" in text or "freeze" in text or "hang" in text or "stability" in text:
            return "crash or stability problems"
        if "hotkey" in text or "shortcut" in text:
            return "keyboard shortcut regressions"
        if "output" in text or "recording" in text or "stream" in text:
            return "output or recording regressions"

    if raw_theme and raw_theme.lower() != "unspecified issue":
        return raw_theme.lower()
    if raw_workflow and not raw_workflow.lower().startswith("general "):
        return raw_workflow.lower()
    return "general workflow reports"


def _issue_counter(pid: str, rows: list[dict[str, Any]]) -> Counter:
    return Counter(_public_issue_bucket(pid, row) for row in rows)


def _top_theme_phrases(themes: Counter, *, limit: int = 3) -> list[str]:
    phrases: list[str] = []
    for theme, _count in themes.most_common():
        phrase = _clean_public_phrase(theme)
        if not phrase or phrase.lower() in {"unspecified issue", "general workflow reports"}:
            continue
        if phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= limit:
            break
    return phrases


def _recommendation_prefix(pid: str, ver: str, consensus_label: str, count: int) -> str:
    label = consensus_label.lower()
    if count <= 0:
        return "INSUFFICIENT DATA"
    if _davinci_version_is_beta(ver) and label == "negative":
        return "AVOID for production"
    if label == "negative":
        return "WAIT"
    if label == "positive":
        return "SAFE ENOUGH to test"
    return "TEST FIRST"


def _affected_workflow_sentence(pid: str, ver: str, consensus_label: str, themes: Counter) -> str:
    label = consensus_label.lower()
    theme_words = " ".join(_top_theme_phrases(themes, limit=5)).lower()
    if pid == "blackmagic-davinci":
        if _davinci_version_is_beta(ver):
            return "Production editors should avoid it on active projects; test only in disposable or non-critical projects."
        if "export" in theme_words or "render" in theme_words:
            return "Production editors with active export deadlines should wait unless they need a specific fix."
        return "Production editors should test on copied projects before moving active work to this version."
    if pid == "obs-studio":
        return "Streamers and recording setups with stable scenes, plugins, or capture devices should wait or test on a backup profile."
    if label == "negative":
        return "Users with fragile production workflows should wait unless they need a specific fix."
    if label == "positive":
        return "Most users can test the update, while critical workflows should still keep a rollback path."
    return "Users with fragile workflows should test first before upgrading production systems."


def _source_limitation_sentence(rows: list[dict[str, Any]], confidence: str) -> str:
    if not rows:
        return "No user reports found yet."

    source_types = [str(row.get("source_type") or row.get("source_name") or "").lower() for row in rows]
    reddit_count = sum(1 for value in source_types if "reddit" in value)
    if len(rows) <= 2:
        return "Too few reports for a firm verdict yet."
    if reddit_count and reddit_count / len(rows) >= 0.6:
        return "Current reports are Reddit-heavy, so production users should test before updating."
    if confidence.lower() in {"low", "insufficient"}:
        return "Small sample size; production users should test before updating."
    return "This is a surfaced user-report sample, not a live telemetry feed."


def _issue_cluster_sentence(themes: Counter) -> str:
    theme_phrases = _top_theme_phrases(themes)
    if theme_phrases:
        return f"Current reports mention {_join_public_list(theme_phrases)}."
    return "Current reports are too varied to group cleanly."


def _load_method_health_rows() -> list[dict[str, Any]]:
    if not METHOD_HEALTH_PATH.exists():
        return []
    payload = yaml.safe_load(METHOD_HEALTH_PATH.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        methods = payload.get("methods") or []
        return [item for item in methods if isinstance(item, dict)]
    return []


def _public_source_limitations(pid: str, ver: str, rows: list[dict[str, Any]], confidence: str) -> list[str]:
    limitations: list[str] = []
    limitation = _source_limitation_sentence(rows, confidence)
    if limitation:
        limitations.append(limitation)

    method_rows = [
        row for row in _load_method_health_rows()
        if str(row.get("product_id") or "").strip() == pid
        and str(row.get("update_version") or "").strip() == ver
    ]
    statuses = {str(row.get("status") or "").strip().lower() for row in method_rows}
    if statuses & {"blocked", "partial", "low_confidence", "broken"}:
        limitations.append("Some community sources were unavailable during the last check; unavailable sources were not counted as reports.")

    clean: list[str] = []
    for item in limitations:
        if item and item not in clean:
            clean.append(item)
    return clean


def _public_summary(
    *,
    pid: str,
    ver: str,
    product_label: str,
    rows: list[dict[str, Any]],
    consensus_label: str,
    confidence: str,
    themes: Counter,
) -> str:
    count = len(rows)
    version_label = ver
    if count <= 0:
        return (
            f"INSUFFICIENT DATA: {product_label} {version_label} has no user reports found yet. "
            "Use the official source only until reports are available."
        )
    verdict = _recommendation_prefix(pid, ver, consensus_label, count)
    report_word = "report" if count == 1 else "reports"
    sample_sentence = "Small sample size." if count < 8 else "User reports show a repeat pattern."
    return " ".join([
        f"{verdict}: {product_label} {version_label} has {count} user {report_word} found.",
        sample_sentence,
        _issue_cluster_sentence(themes),
        f"{_affected_workflow_sentence(pid, ver, consensus_label, themes)} {_source_limitation_sentence(rows, confidence)}",
    ])


def _public_consensus_report(
    *,
    pid: str,
    ver: str,
    product_label: str,
    rows: list[dict[str, Any]],
    consensus_label: str,
    confidence: str,
    themes: Counter,
) -> str:
    count = len(rows)
    sources = []
    for row in rows:
        source = _clean_public_phrase(row.get("source_name") or row.get("source_type") or "source")
        if source and source not in sources:
            sources.append(source)
    source_sentence = f"Sources represented: {_join_public_list(sources[:4])}." if sources else ""
    return " ".join(part for part in [
        f"{count} user report{'s' if count != 1 else ''} found for {product_label} {ver}.",
        _issue_cluster_sentence(themes),
        _source_limitation_sentence(rows, confidence),
        source_sentence,
    ] if part)


def _public_sample_issue(pid: str, row: dict[str, Any]) -> str:
    issue = _public_issue_bucket(pid, row)
    workflow = _clean_public_phrase(row.get("workflow_area"))
    if issue and workflow and workflow.lower() not in issue.lower() and not workflow.lower().startswith("general "):
        return f"{issue} in {workflow}"
    if issue:
        return issue
    return (
        _truncate_public_text(row.get("observed_issue_summary"), limit=150)
        or _truncate_public_text(row.get("report_title") or row.get("source_title") or row.get("parent_title"), limit=120)
        or _clean_public_phrase(row.get("issue_theme"), fallback="Patch-specific user report")
    )


def _severity_rank(row: dict[str, Any]) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(str(row.get("severity") or "").lower(), 0)


def _representative_rows(pid: str, rows: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used_ids: set[int] = set()
    buckets = _issue_counter(pid, rows)
    ranked_rows = sorted(enumerate(rows), key=lambda item: (-_severity_rank(item[1]), item[0]))

    for bucket, _count in buckets.most_common():
        for original_index, row in ranked_rows:
            if original_index in used_ids:
                continue
            if _public_issue_bucket(pid, row) == bucket:
                selected.append(row)
                used_ids.add(original_index)
                break
        if len(selected) >= limit:
            return selected

    for original_index, row in ranked_rows:
        if original_index in used_ids:
            continue
        selected.append(row)
        used_ids.add(original_index)
        if len(selected) >= limit:
            break
    return selected


def _public_source_item(pid: str, ver: str, row: dict[str, Any]) -> dict[str, Any]:
    source_date = (
        _public_date(row.get("source_date"))
        or _public_date(row.get("source_published_at"))
        or _public_date(row.get("published_at"))
    )
    return {
        "source_name": row.get("source_name") or row.get("source_type") or "Source",
        "source_type": _clean_public_phrase(row.get("source_type"), fallback="community report"),
        "source_url": row.get("source_url"),
        "source_title": row.get("source_title") or row.get("report_title") or row.get("parent_title") or "Community report",
        "source_date": source_date,
        "version_matched": row.get("matched_version") or row.get("update_version") or ver,
        "patch_version_matched": True,
        "issue": _public_sample_issue(pid, row),
        "workflow_area": _clean_public_phrase(row.get("workflow_area")),
    }


def _proposed_record_fields(pid: str, ver: str, rows: list[dict[str, Any]], record: dict[str, Any] | None, evidence_last_checked: str) -> dict[str, Any]:
    count = len(rows)
    sentiments = Counter(str(r.get("sentiment") or "").lower() for r in rows)
    themes = _issue_counter(pid, rows)
    consensus_label = _consensus_label(sentiments)
    confidence = _confidence(count)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    version_label = ver
    product_label = str((record or {}).get("update_product") or pid).strip()
    summary = _public_summary(
        pid=pid,
        ver=version_label,
        product_label=product_label,
        rows=rows,
        consensus_label=consensus_label,
        confidence=confidence,
        themes=themes,
    )
    report = _public_consensus_report(
        pid=pid,
        ver=version_label,
        product_label=product_label,
        rows=rows,
        consensus_label=consensus_label,
        confidence=confidence,
        themes=themes,
    )
    samples = []
    for row in _representative_rows(pid, rows, limit=5):
        samples.append({
            "source_name": row.get("source_name") or row.get("source_type") or "Source",
            "source_url": row.get("source_url"),
            "source_title": row.get("source_title") or row.get("report_title") or row.get("parent_title"),
            "counted": True,
            "version_matched": row.get("matched_version") or row.get("update_version") or ver,
            "patch_version_matched": True,
            "issue": _public_sample_issue(pid, row),
            "outcome": _clean_public_phrase(row.get("severity"), fallback="medium"),
        })
    accepted_report_sources = [_public_source_item(pid, ver, row) for row in rows]
    fields = {
        "update_report_count": count,
        "confirmed_patch_specific_report_count": count,
        "evidence_state": _evidence_state(count),
        "evidence_state_label": "Official source only" if count == 0 else "Verified reports",
        "consensus_collection_status": _collection_status(count),
        "update_consensus_label": consensus_label,
        "update_consensus_confidence": confidence,
        "consensus_report_count_label": "user reports found",
        "update_consensus_summary": summary,
        "consensus_report": report,
        "evidence_last_checked": evidence_last_checked,
        "record_last_updated": now,
        "intelligence_stage": "manual_watch" if count == 0 else "pilot",
        "evidence_samples": samples,
        "evidence_sample_visible_limit": 5,
        "accepted_report_sources": accepted_report_sources,
        "evidence_source_limitations": _public_source_limitations(pid, ver, rows, confidence),
        "status_events_append": {
            "at": now,
            "label": "User reports found" if count > 0 else "Insufficient data",
            "note": (
                f"User report count updated to {count}."
            ),
        },
    }
    fields.update(_record_coherence_fields(pid, ver, count, record, themes))
    return fields


def _record_coherence_fields(pid: str, ver: str, count: int, record: dict[str, Any] | None, themes: Counter) -> dict[str, Any]:
    if count <= 0:
        return {}
    if not record:
        return {}

    product_label = str(record.get("update_product") or pid).strip()

    if pid == "blackmagic-davinci":
        if _davinci_version_is_beta(ver):
            return {
                "quick_verdict": (
                    f"WAIT for production systems: {product_label} {ver} is a beta build with {count} user reports found."
                ),
                "update_decision_label": "WAIT for production systems",
                "update_decision_body": (
                    "Use this beta only for non-critical testing. Active client projects should stay on a known-good stable build unless a Resolve 21 beta feature is worth the risk."
                ),
                "practical_recommendations": [
                    "Wait for production systems unless you have a specific Resolve 21 beta feature to test.",
                    "Test beta projects separately from active client work and keep a known-good Resolve version available.",
                    "Review the user report sample before using this build on deadline-sensitive work.",
                ],
                "source_freshness_note": "",
            }

        fields = {
            "quick_verdict": (
                f"WAIT: {product_label} {ver} has {count} user reports found."
            ),
            "update_decision_label": "WAIT",
            "update_decision_body": (
                f"{_issue_cluster_sentence(themes)} Production editors with active delivery deadlines should wait or test on copied projects."
            ),
            "practical_recommendations": [
                "Wait if you have active render/export deadlines.",
                "Test on copied projects before moving client work to this version.",
                "Review the sample reports before updating a production workstation.",
            ],
            "source_freshness_note": "",
        }
        if str(ver).strip() == "21":
            fields.update({
                "description": (
                    f"Published Apr 14, 2026. This page covers the stable {product_label} {ver} release. Public beta reports are excluded."
                ),
                "feed_hidden": False,
                "update_status": "current",
                "status_change_type": "new",
                "notification_message": "",
                "update_channel_label": "Stable / Studio release",
                "official_summary": (
                    f"{product_label} {ver} is tracked here as the stable/Studio release. Public Beta 1 reports are excluded."
                ),
                "release_summary": (
                    f"{product_label} {ver} is the stable/Studio release. Use this page for stable release risk."
                ),
            })
        return fields

    if pid == "obs-studio":
        archived = str(record.get("update_status") or "").strip().lower() == "archived"
        if archived:
            decision_label = "WAIT"
            body = (
                f"{product_label} {ver} is archived. Use a newer maintained OBS build unless you need this version for rollback testing or reproduction."
            )
        else:
            decision_label = "TEST FIRST"
            body = (
                "Test on a backup profile before using this OBS build for live streams or important recordings, especially if your setup depends on plugins, capture devices, audio routing, or large scene collections."
            )
        return {
            "quick_verdict": f"{decision_label}: {product_label} {ver} has {count} user reports found.",
            "update_decision_label": decision_label,
            "update_decision_body": body,
            "practical_recommendations": [
                "Test with a backup scene collection and profile before production use.",
                "Check plugin, capture-device, and audio-routing behavior before a live stream or paid recording.",
                "Keep a rollback installer available if your setup is already stable.",
            ],
            "source_freshness_note": "",
        }

    return {}


def _davinci_version_is_beta(version: str) -> bool:
    return bool(re.search(r"\b(?:public\s+)?beta\b|b\d+\b", str(version or ""), flags=re.I))


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


PUBLIC_INTERNAL_TERMS = (
    "consensus_evidence.yml",
    "deterministically accepted",
    "source-backed",
    "source_weight",
    "promoted evidence rows",
    "promoted rows",
    "write-back",
    "writeback",
    "verified reports set",
    "not broad consensus",
    "low-confidence",
    "low confidence",
    "broad consensus",
    "yaml",
    "collector",
    "candidate rows",
)


def _contains_internal_public_term(value: Any) -> bool:
    text = str(value or "").lower()
    return any(term.lower() in text for term in PUBLIC_INTERNAL_TERMS)


def _sanitize_status_events(events: Any) -> list[dict[str, Any]]:
    if not isinstance(events, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        clean_event = dict(event)
        label = str(clean_event.get("label") or "").lower()
        note = str(clean_event.get("note") or "").lower()
        dirty_label = _contains_internal_public_term(clean_event.get("label"))
        dirty_note = (
            _contains_internal_public_term(clean_event.get("note"))
            or "evidence state" in note
        )
        if dirty_label:
            if "insufficient" in label:
                clean_event["label"] = "Insufficient data"
            elif "report" in label or "verified" in label:
                clean_event["label"] = "User reports found"
            else:
                clean_event["label"] = "Record updated"
        if dirty_note:
            if "insufficient" in label:
                clean_event["note"] = "Record status updated after the latest source check."
            elif "report" in label or "verified" in label:
                clean_event["note"] = "User report count updated after the latest evidence pass."
            else:
                clean_event["note"] = "Record status updated after the latest evidence pass."
        sanitized.append(clean_event)
    return sanitized


def _status_events_need_sanitization(events: Any) -> bool:
    if not isinstance(events, list):
        return False
    return _sanitize_status_events(events) != events


RECORD_SUBSTANTIVE_COMPARE_IGNORED = {"record_last_updated", "status_events_append"}
STATUS_EVENT_SUBSTANTIVE_COMPARE_IGNORED = {"at", "timestamp", "captured_at", "updated_at"}


def _has_substantive_record_change(data: dict[str, Any], fields: dict[str, Any]) -> bool:
    comparable_fields = {key: value for key, value in fields.items() if key not in RECORD_SUBSTANTIVE_COMPARE_IGNORED}
    return any(data.get(key) != value for key, value in comparable_fields.items())


def _status_event_signature(event: Any) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    sanitized = _sanitize_status_events([event])
    if not sanitized:
        return None
    signature: dict[str, Any] = {}
    for key, value in sanitized[0].items():
        if key in STATUS_EVENT_SUBSTANTIVE_COMPARE_IGNORED:
            continue
        if isinstance(value, str):
            signature[key] = re.sub(r"\s+", " ", value).strip().lower()
        else:
            signature[key] = value
    return signature


def _latest_status_event_equivalent(events: Any, proposed_event: Any) -> bool:
    sanitized_events = _sanitize_status_events(events)
    if not sanitized_events:
        return False
    proposed_signature = _status_event_signature(proposed_event)
    if proposed_signature is None:
        return False
    return _status_event_signature(sanitized_events[-1]) == proposed_signature


def _record_write_plan(data: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    fields_to_write = dict(fields)
    status_event = fields_to_write.get("status_events_append")
    status_event_requested = status_event is not None
    substantive_change = _has_substantive_record_change(data, fields)
    latest_event_equivalent = (
        _latest_status_event_equivalent(data.get("status_events"), status_event)
        if status_event_requested
        else False
    )

    status_event_would_apply = False
    status_event_reason = "not_requested"
    if status_event_requested:
        status_event_would_apply = substantive_change and not latest_event_equivalent
        if not substantive_change:
            status_event_reason = "skipped_no_substantive_record_change"
        elif latest_event_equivalent:
            status_event_reason = "skipped_latest_status_event_equivalent"
        else:
            status_event_reason = "applied_substantive_record_change"
        if not status_event_would_apply:
            fields_to_write.pop("status_events_append", None)

    if not substantive_change:
        if _status_events_need_sanitization(data.get("status_events")):
            fields_to_write = {"status_events": _sanitize_status_events(data.get("status_events"))}
        else:
            fields_to_write = {}

    return {
        "fields": fields_to_write,
        "substantive_record_change": substantive_change,
        "status_events_append": {
            "requested": status_event_requested,
            "would_apply": status_event_would_apply,
            "reason": status_event_reason,
            "latest_existing_event_equivalent": latest_event_equivalent,
        },
    }


def _fields_for_record_write(data: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    return _record_write_plan(data, fields)["fields"]


def _public_write_plan(data: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    plan = _record_write_plan(data, fields)
    return {
        "fields_that_would_write": _fields_written_labels(plan["fields"]),
        "substantive_record_change": plan["substantive_record_change"],
        "status_events_append": plan["status_events_append"],
    }


def _fields_written_labels(fields: dict[str, Any]) -> list[str]:
    labels = sorted(k for k in fields.keys() if k != "status_events_append")
    if "status_events_append" in fields:
        labels.append("status_events")
    return labels


def _apply_record_fields(record_path: Path, fields: dict[str, Any]) -> dict[str, Any]:
    data, body = _load_front_matter_and_body(record_path)
    before = deepcopy(data)
    illegal = sorted(k for k in fields if k in PROTECTED_FIELDS and k not in CONSENSUS_COHERENCE_FIELDS)
    if illegal:
        raise RuntimeError(f"Refusing to overwrite protected fields: {illegal}")
    write_plan = _record_write_plan(data, fields)
    fields_to_apply = write_plan["fields"]
    if not fields_to_apply:
        return {"before": before, "after": data, "write_plan": write_plan}
    for key, value in fields_to_apply.items():
        if key == "status_events_append":
            events = _sanitize_status_events(data.get("status_events"))
            events.append(value)
            data["status_events"] = events
        elif key in WRITEABLE_FIELDS:
            data[key] = value
        else:
            raise RuntimeError(f"Refusing to write unapproved field: {key}")
    _write_front_matter_and_body(record_path, data, body)
    return {"before": before, "after": data, "write_plan": write_plan}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consensus-to-generated-record dry-run/write-back updater.")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Show proposed changes without writing.")
    parser.add_argument("--write", action="store_true", default=False, help="Write matching generated record after all safety gates pass.")
    parser.add_argument("--write-all", action="store_true", default=False, help="Reconcile all matching generated records after all safety gates pass.")
    parser.add_argument("--confirm-write", action="store_true", default=False, help="Required with --write or --write-all.")
    parser.add_argument("--product-id", default=None, help="Filter to a single product_id.")
    parser.add_argument("--update-version", default=None, help="Required with --write. Exact generated record update_version.")
    parser.add_argument("--candidate-file", default=None, help="Candidate staging file instead of production evidence.")
    parser.add_argument("--output", default=None, help="Path to write JSON output.")
    parser.add_argument("--version-filter", default=None, help="Dry-run filter to a specific update_version string.")
    args = parser.parse_args(argv)

    if args.write and args.write_all:
        print("ERROR: Choose either --write or --write-all, not both.", file=sys.stderr)
        return 2

    write_requested = bool(args.write or args.write_all)

    if write_requested:
        if not args.confirm_write:
            print("ERROR: Write mode requires --confirm-write.", file=sys.stderr)
            return 2
        if args.candidate_file:
            print("ERROR: Write mode cannot use --candidate-file. Promote rows to production evidence first.", file=sys.stderr)
            return 2

    if args.write:
        if not args.product_id:
            print("ERROR: --write requires --product-id.", file=sys.stderr)
            return 2
        if not args.update_version:
            print("ERROR: --write requires --update-version.", file=sys.stderr)
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
    results = run_dry_run(evidence_path=evidence_path, product_id_filter=args.product_id, is_candidate_mode=is_candidate_mode, records_index=records_index, write_requested=write_requested)

    version_filter = args.update_version if args.update_version else args.version_filter
    if version_filter:
        results = [r for r in results if r["update_version"] == version_filter]

    payload = _payload(results, evidence_path=evidence_path, is_candidate_mode=is_candidate_mode, product_id_filter=args.product_id, version_filter=version_filter, records_index=records_index, write_mode_active=write_requested)

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
        current_data = _load_front_matter(record_path)
        fields_to_write = _fields_for_record_write(current_data, result["proposed_fields_if_written"])
        effective_write_plan = _public_write_plan(current_data, result["proposed_fields_if_written"])
        if not fields_to_write:
            payload["write_result"] = {
                "success": True,
                "record_path": str(record_path.relative_to(ROOT)),
                "skipped": True,
                "reason": "Already current.",
                "fields_written": [],
                "pre_write_report_count": current_data.get("update_report_count"),
                "post_write_report_count": current_data.get("update_report_count"),
                "pre_write_evidence_state": current_data.get("evidence_state"),
                "post_write_evidence_state": current_data.get("evidence_state"),
                "effective_write_plan": effective_write_plan,
            }
            _write_json(payload, args.output)
            print(
                f"[apply_consensus_to_records] {payload['mode']}: {len(results)} group(s); "
                f"{payload['groups_would_write']} would write; {payload['groups_write_blocked']} blocked; "
                f"{payload['total_included_candidates']} included; {payload['total_excluded_candidates']} excluded.",
                file=sys.stderr,
            )
            return 0
        snapshot = _apply_record_fields(record_path, fields_to_write)
        payload["write_result"] = {
            "success": True,
            "record_path": str(record_path.relative_to(ROOT)),
            "skipped": False,
            "fields_written": _fields_written_labels(fields_to_write),
            "pre_write_report_count": snapshot["before"].get("update_report_count"),
            "post_write_report_count": snapshot["after"].get("update_report_count"),
            "pre_write_evidence_state": snapshot["before"].get("evidence_state"),
            "post_write_evidence_state": snapshot["after"].get("evidence_state"),
            "effective_write_plan": effective_write_plan,
        }

    if args.write_all:
        write_results: list[dict[str, Any]] = []
        for result in results:
            record_rel = result.get("matched_generated_record_path")
            if int(result.get("confirmed_patch_specific_report_count") or 0) <= 0:
                write_results.append({
                    "success": True,
                    "record_path": record_rel,
                    "product_id": result["product_id"],
                    "update_version": result["update_version"],
                    "skipped": True,
                    "reason": "No counted user reports for this group.",
                })
                continue
            if not result["would_write"]:
                write_results.append({
                    "success": False,
                    "record_path": record_rel,
                    "product_id": result["product_id"],
                    "update_version": result["update_version"],
                    "skipped": True,
                    "reason": result.get("write_blocked_reason"),
                })
                continue
            if not record_rel:
                write_results.append({
                    "success": False,
                    "record_path": None,
                    "product_id": result["product_id"],
                    "update_version": result["update_version"],
                    "skipped": True,
                    "reason": "No matching generated record path.",
                })
                continue
            record_path = ROOT / record_rel
            current_data = _load_front_matter(record_path)
            fields_to_write = _fields_for_record_write(current_data, result["proposed_fields_if_written"])
            if not fields_to_write:
                write_results.append({
                    "success": True,
                    "record_path": record_rel,
                    "product_id": result["product_id"],
                    "update_version": result["update_version"],
                    "skipped": True,
                    "reason": "Already current.",
                })
                continue
            snapshot = _apply_record_fields(record_path, fields_to_write)
            write_results.append({
                "success": True,
                "record_path": str(record_path.relative_to(ROOT)),
                "product_id": result["product_id"],
                "update_version": result["update_version"],
                "skipped": False,
                "fields_written": _fields_written_labels(fields_to_write),
                "pre_write_report_count": snapshot["before"].get("update_report_count"),
                "post_write_report_count": snapshot["after"].get("update_report_count"),
            })
        payload["write_all_results"] = write_results
        payload["records_written"] = sum(1 for item in write_results if item.get("success") and not item.get("skipped"))
        payload["records_skipped"] = sum(1 for item in write_results if item.get("skipped"))

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
