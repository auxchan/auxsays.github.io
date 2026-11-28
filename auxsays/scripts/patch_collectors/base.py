"""Shared evidence collection helpers for AUXSAYS patch intelligence.

The product collectors are intentionally small. This module owns the durable
evidence schema, generated-record discovery, duplicate detection, and the
deterministic gates that must pass before a row can count.
"""
from __future__ import annotations

import os
import re
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lib import evidence_facts
from lib.patch_identity import key_from as patch_key_from, require_build
from lib.reddit_access_policy import is_policy_disabled_row
from lib.source_segments import report_url_key
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / "_data" / "consensus_evidence.yml"
METHOD_HEALTH_PATH = ROOT / "_data" / "evidence_method_health.yml"
GENERATED_DIR = ROOT / "updates" / "generated"

EVIDENCE_FIELDS = (
    "id",
    "product_id",
    "update_version",
    "source_type",
    "source_name",
    "source_url",
    "archive_url",
    "parent_title",
    "report_title",
    "report_text_excerpt",
    "captured_at",
    "source_date",
    "source_date_resolved",
    "target_release_date",
    "next_release_date",
    "source_date_pass",
    "patch_version_matched",
    "matched_version",
    "match_basis",
    "version_match_confidence",
    "matched_product_alias",
    "applicability",
    "matched_kb",
    "matched_os_build",
    "matched_feature_version",
    "evidence_valid_for_current_patch",
    "stale_due_to_patch_rollover",
    "counted",
    "exclusion_reason",
    "issue_theme",
    "workflow_area",
    "platform",
    "severity",
    "sentiment",
    "source_weight",
    "capture_method",
    "source_date_text",
    "listing_card_title",
    "listing_card_category",
    "listing_card_date_text",
    # Exact vendor build. Part of the DURABLE schema, not a transient annotation: for a
    # build-aware product the canonical patch identity is (product_id, update_version,
    # target_build), so a row that loses its build here can no longer be attributed to the
    # patch it was accepted for. Optional (and empty) for every product without a build
    # contract -- see lib.patch_identity.BUILD_AWARE_PRODUCTS.
    "target_build",
    # WHICH DISCOVERY METHOD FOUND THIS ROW (lib.acquisition_methods method_id). Provenance only:
    # nothing counts, gates or deduplicates on it, and a row without it is not a lesser row. Stamped
    # forward-only at the append boundary (`append_evidence_rows(method_health=...)`), and only when
    # exactly one method of the row's own patch and source type accepted anything in the run -- a row
    # two methods could both have found is left unstamped rather than credited to a guess.
    "discovery_method_id",
    # The occurrence that satisfied the version match, which field it came from, and a bounded window
    # around it. Retained because `report_text_excerpt` is truncated and could not substantiate its
    # own row's match after the fact. Optional and appended LAST: rows written before this existed
    # carry none of the three, and normalize_evidence_row drops empty optional fields, so no stored
    # row gains, loses or reorders a key.
    "matched_text",
    "matched_field",
    "matched_context",
    # Structured evidence facts (G68, lib.evidence_facts): public, derived, computed by
    # `append_evidence_rows` from the row's own text when the row is written, and appended LAST.
    # Optional, so a row written before they existed gains no key on a load; the zero-network
    # migration (migrate_evidence_facts.py) backfilled every stored row.
    *evidence_facts.STORED_FIELDS,
)

OPTIONAL_EVIDENCE_FIELDS = {
    *evidence_facts.STORED_FIELDS,
    "archive_url",
    "target_build",
    "discovery_method_id",
    "matched_text",
    "matched_field",
    "matched_context",
    "source_date",
    "source_date_resolved",
    "target_release_date",
    "next_release_date",
    "source_date_pass",
    "version_match_confidence",
    "matched_product_alias",
    "applicability",
    "matched_kb",
    "matched_os_build",
    "matched_feature_version",
    "evidence_valid_for_current_patch",
    "stale_due_to_patch_rollover",
    "capture_method",
    "source_date_text",
    "listing_card_title",
    "listing_card_category",
    "listing_card_date_text",
}

METHOD_HEALTH_FIELDS = (
    "product_id",
    "update_version",
    # Method health is patch identity too: 2603/build-A learn_qna=success and
    # 2603/build-B learn_qna=blocked are two different facts about two different patches.
    # Empty for every product without a build contract, so their health identity is unchanged.
    "target_build",
    "method_id",
    "source_type",
    "status",
    "candidates_found",
    "accepted_candidates",
    "duplicate_existing_evidence",
    "evidence_rows_added",
    "public_counted_reports",
    "accepted_reports",
    "rejected_reports",
    "blocked_reason",
    "last_run",
    "notes",
    # --- measured history (all OPTIONAL; see METHOD_HEALTH_HISTORY_FIELDS) ---
    "attempts",
    "last_good_at",
    "last_accepted_at",
    "consecutive_failures",
    "consecutive_zero_accept_runs",
    "duration_ms",
    "requests",
    "rejection_reasons",
)

# MEASURED HISTORY, carried on the row the method already owns (no second store). Every field is
# OPTIONAL and is written only when it has a value, for two reasons. A row written before these
# existed must load and re-serialize to the same bytes, so a run that does not touch a row does not
# rewrite it. And an absent field means NOT MEASURED: a `duration_ms: 0` or `requests: 0` default
# would read as a free, instant method, which is the flattering default this file must not grow.
#
#   attempts                     runs in which this method was actually attempted for this patch
#   last_good_at                 last run whose status was a responding one (the source answered)
#   last_accepted_at             last run in which it accepted at least one candidate
#   consecutive_failures         attempted runs in a row ending blocked / stale / broken
#   consecutive_zero_accept_runs attempted runs in a row that accepted nothing
#   duration_ms, requests        cost of the LAST attempt, when the collector measured it
#   rejection_reasons            {exclusion code: count} for the LAST attempt's rejected candidates
#
# The first five are maintained by `upsert_method_health` from the row it replaces; a collector never
# supplies them. The last three are supplied by the collector that measured them.
METHOD_HEALTH_CARRIED_FIELDS = (
    "attempts", "last_good_at", "last_accepted_at",
    "consecutive_failures", "consecutive_zero_accept_runs",
)
METHOD_HEALTH_MEASURED_FIELDS = ("duration_ms", "requests", "rejection_reasons")
METHOD_HEALTH_HISTORY_FIELDS = METHOD_HEALTH_CARRIED_FIELDS + METHOD_HEALTH_MEASURED_FIELDS
_HISTORY_INT_FIELDS = ("attempts", "consecutive_failures", "consecutive_zero_accept_runs",
                       "duration_ms", "requests")
_HISTORY_TIME_FIELDS = ("last_good_at", "last_accepted_at")
# A status that means the SOURCE ANSWERED (whatever it answered) versus one that means it did not.
# `disabled` and `manual_review_needed` are neither: nothing was attempted.
RESPONDING_HEALTH_STATUSES = frozenset({"success", "partial", "no_results", "low_confidence"})
FAILING_HEALTH_STATUSES = frozenset({"blocked", "stale", "broken"})

VALID_METHOD_HEALTH_STATUSES = {
    "success",
    "partial",
    "no_results",
    "blocked",
    "stale",
    "broken",
    "low_confidence",
    "disabled",
    "manual_review_needed",
}

ISSUE_TERMS = (
    "crash",
    "crashes",
    "crashed",
    "freeze",
    "freezes",
    "frozen",
    "hang",
    "hangs",
    "failed",
    "failure",
    "bug",
    "broken",
    "corrupt",
    "corrupted",
    "corruption",
    "regression",
    "slow",
    "lag",
    "performance",
    "install",
    "won't open",
    "does not open",
    "can't open",
    "cannot open",
    "decode",
    "render",
    "export",
    "compatibility",
    "plugin",
    "workflow",
)

NON_REPORT_TERMS = (
    "release notes",
    "changelog",
    "what's new",
    "whats new",
    "announcement",
    "download",
    "version history",
    "new features",
)


@dataclass(frozen=True)
class PatchRecord:
    product_id: str
    update_version: str
    path: Path
    update_published_at: str
    update_status: str
    update_product: str
    # Exact vendor build from the record's front matter. Empty for every product without a build
    # contract; for a build-aware product it is the second half of this record's patch identity,
    # and collectors must attribute evidence and method health to it rather than to the YYMM.
    target_build: str = ""


@dataclass(frozen=True)
class CollectorContext:
    write: bool
    since: str | None
    max_pages: int
    target_versions: set[str] | None = None
    # Optional RuntimeBudget (patch_collectors.runtime_budget.RuntimeBudget). When present, budget-aware
    # collectors bound every network request/method/collector by a hard wall-clock deadline. Left None by
    # callers/tests that do not need bounding (behavior unchanged).
    budget: Any = None


class ProductCollector:
    product_id: str

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        raise NotImplementedError


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:96].strip("-")


def excerpt(text: str, width: int = 280) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return textwrap.shorten(text, width=width, placeholder="...") if text else ""


def parse_iso_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip().strip("'\"")
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def date_part(value: Any) -> str:
    parsed = parse_iso_date(value)
    return parsed.date().isoformat() if parsed else ""


def atomic_write_text(path: Path, text: str) -> None:
    """Write text via a same-directory temp file + ``os.replace`` (atomic on one filesystem), so a
    crash or exception mid-write can never leave a half-written tracked file. This is the
    file-level half of the transactional writeback guarantee: a reader either sees the previous
    complete file or the new complete file, never a truncated one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())  # durable before the atomic swap (Part H)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def split_front_matter(text: str) -> tuple[str | None, str]:
    """Split a Jekyll document into (front_matter_yaml_or_None, body). A delimiter is a line whose
    ENTIRE content is exactly ``---`` (a trailing CR is ignored). Robust against ``-----`` rules,
    admonitions, and any ``---`` sequence embedded inside a serialized scalar -- unlike
    ``text.split('---\\n')``, which matches ``---\\n`` as a substring and truncates any value whose
    line ends in three or more hyphens (the OBS ``release_summary`` / "Hotfix Changes -----" crash).
    Returns (None, text) when there is no valid front-matter fence."""
    if not text.startswith("---"):
        return None, text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None, text
    for idx in range(1, len(lines)):
        if lines[idx].rstrip("\r\n") == "---":
            return "".join(lines[1:idx]), "".join(lines[idx + 1:])
    return None, text  # opened but never closed -> treat as no front matter


def load_front_matter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    front, body = split_front_matter(text)
    if front is None:
        return {}, text
    data = yaml.safe_load(front) or {}
    return (data if isinstance(data, dict) else {}, body)


def write_front_matter_and_body(path: Path, data: dict[str, Any], body: str) -> None:
    front = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000).strip()
    atomic_write_text(path, f"---\n{front}\n---\n{body}")


def generated_records(product_id: str, target_versions: set[str] | None = None, *, include_archived: bool = False) -> list[PatchRecord]:
    records: list[PatchRecord] = []
    for path in sorted(GENERATED_DIR.glob("*.md")):
        data, _body = load_front_matter_and_body(path)
        if data.get("update_entry") is not True:
            continue
        if str(data.get("product_id") or "").strip() != product_id:
            continue
        status = str(data.get("update_status") or "").strip()
        if status == "archived" and not include_archived:
            continue
        version = str(data.get("update_version") or "").strip()
        if not version:
            continue
        if target_versions and version not in target_versions:
            continue
        records.append(PatchRecord(
            product_id=product_id,
            update_version=version,
            path=path,
            update_published_at=str(data.get("update_published_at") or "").strip(),
            update_status=status,
            update_product=str(data.get("update_product") or product_id).strip(),
            target_build=str(data.get("target_build") or "").strip(),
        ))
    return records


def newest_first(records: list[PatchRecord]) -> list[PatchRecord]:
    """Most recently released patch first.

    `generated_records` above returns the corpus in FILENAME order, and every generated filename is
    date-prefixed, so its natural order is oldest-first: 2014 before 2026. Every collector is bounded
    by a per-collector wall-clock budget (`AUXSAYS_COLLECTOR_DEADLINE_SECONDS`, 1200 s) and simply
    `break`s when it expires, so an oldest-first walk spends its entire budget re-scraping the
    historical head of the corpus and never reaches the patches a reader is actually looking at.

    This is not hypothetical and it is not a tail problem. Measured on DaVinci before this helper was
    used there: scheduled run 34377762747 processed versions 10.1.5 through 15.0.1 -- records
    published 2014-05-09 to 2018-09-03 -- rejected 77 of 77 candidates as
    `missing_exact_patch_version_match`, and stopped. 87 of 120 records were never reached; the
    newest release, 21.1, had never been searched once by any method; and the walk's high-water mark
    was RECEDING, because each newly ingested record lengthens the corpus ahead of the recent tail.

    Reversing the order does not create budget, it spends it where the value is. Old records keep
    whatever remains, and they are the ones that already carry evidence. Deterministic: ties break on
    version, so two runs walk the same order.

    NOTE ON DUPLICATION. `adobe_acrobat_community.py:130` and `microsoft_windows.py:1038` each carry
    their own private copy of this function, which is where the idea was proven (PRs #102-#105).
    They are deliberately NOT refactored to call this one: both products are frozen, and "the
    implementation could be cleaner" is not a licence to touch frozen code. This shared copy exists
    so the next collector inherits the fix instead of rediscovering it.
    """
    return sorted(records,
                  key=lambda r: (str(getattr(r, "update_published_at", "") or ""),
                                 str(getattr(r, "update_version", "") or "")),
                  reverse=True)


def load_evidence(path: Path = EVIDENCE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [normalize_evidence_row(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        evidence = payload.get("evidence") or []
        if not isinstance(evidence, list):
            raise ValueError(f"{path} field 'evidence' must be a list")
        return [normalize_evidence_row(item) for item in evidence if isinstance(item, dict)]
    raise ValueError(f"{path} must contain a YAML list or a mapping with an evidence list")


def write_evidence_file(rows: list[dict[str, Any]], path: Path = EVIDENCE_PATH) -> None:
    payload = {"schema_version": 1, "evidence": [normalize_evidence_row(row) for row in rows]}
    atomic_write_text(path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=1000))


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def normalize_rejection_reasons(value: Any) -> dict[str, int]:
    """{exclusion code: positive count}, keys sorted. Anything else is dropped, never guessed."""
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, int] = {}
    for code, count in value.items():
        number = _nonnegative_int(count)
        code_text = str(code or "").strip()
        if code_text and number:
            cleaned[code_text] = number
    return dict(sorted(cleaned.items()))


def rejection_reason_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count a method's rejected candidates by their own `exclusion_reason`. The codes are the ones
    the acceptance gates already wrote; this only counts them."""
    counts: dict[str, int] = {}
    for row in rows or ():
        code = str((row or {}).get("exclusion_reason") or "").strip() or "unspecified"
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def normalize_method_health_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_method_health_core(row)
    # Optional history: present only when it carries a value (see METHOD_HEALTH_HISTORY_FIELDS).
    for field in _HISTORY_INT_FIELDS:
        number = _nonnegative_int(row.get(field))
        if number is not None and (number or field in ("duration_ms", "requests")):
            normalized[field] = number
    for field in _HISTORY_TIME_FIELDS:
        text = str(row.get(field) or "").strip()
        if text:
            normalized[field] = text
    reasons = normalize_rejection_reasons(row.get("rejection_reasons"))
    if reasons:
        normalized["rejection_reasons"] = reasons
    return normalized


def _normalize_method_health_core(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: row.get(field) for field in METHOD_HEALTH_FIELDS
                  if field not in METHOD_HEALTH_HISTORY_FIELDS}
    for field in (
        "candidates_found",
        "accepted_candidates",
        "duplicate_existing_evidence",
        "evidence_rows_added",
        "public_counted_reports",
        "accepted_reports",
        "rejected_reports",
    ):
        normalized[field] = int(normalized.get(field) or 0)
    for field in list(normalized):
        if field in {
            "candidates_found",
            "accepted_candidates",
            "duplicate_existing_evidence",
            "evidence_rows_added",
            "public_counted_reports",
            "accepted_reports",
            "rejected_reports",
        }:
            continue
        if normalized[field] is None:
            normalized[field] = ""
        else:
            normalized[field] = str(normalized[field])
    if normalized["status"] not in VALID_METHOD_HEALTH_STATUSES:
        normalized["status"] = "broken"
    return normalized


def load_method_health(path: Path = METHOD_HEALTH_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return [normalize_method_health_row(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        methods = payload.get("methods") or []
        if not isinstance(methods, list):
            raise ValueError(f"{path} field 'methods' must be a list")
        return [normalize_method_health_row(item) for item in methods if isinstance(item, dict)]
    raise ValueError(f"{path} must contain a YAML list or a mapping with a methods list")


_KEEP: Any = object()


def write_method_health_file(rows: list[dict[str, Any]], path: Path = METHOD_HEALTH_PATH,
                             *, probes: list[dict[str, Any]] | None = None,
                             probe_step: Any = _KEEP) -> None:
    """Write the health file. ``probes`` is the re-probe section (see METHOD_PROBE_FIELDS); when it
    is not given, the section already in the file is PRESERVED -- a collector run that upserts
    method rows must not erase what the re-probe step recorded. The key is written only when the
    section is non-empty, so a file that never held a probe keeps the bytes it always had.
    ``probe_step`` (see `record_probe_step`) is preserved the same way; pass None to clear it."""
    if probes is None:
        probes = load_method_probes(path)
    if probe_step is _KEEP:
        probe_step = load_probe_step(path)
    payload: dict[str, Any] = {"schema_version": 1,
                               "methods": [normalize_method_health_row(row) for row in rows]}
    cleaned = [normalize_method_probe_row(row) for row in probes]
    if cleaned:
        payload["probes"] = cleaned
    step = normalize_probe_step(probe_step)
    if step:
        payload["probe_step"] = step
    atomic_write_text(path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=1000))


# --- re-probe records ----------------------------------------------------------------------------
# One record per (product_id, method_id) for a method that is switched OFF and is re-tested on a
# bounded cadence (scripts/reprobe_methods.py; policy in lib.acquisition_methods, cadence in
# lib.method_routing). Kept in the SAME file, written by the SAME writer: a probe is health
# telemetry about a method, and a second store is exactly what makes two views of one method drift.
# A probe record is never evidence and never a method row: the public pages read `methods` only.
METHOD_PROBE_FIELDS = (
    "product_id", "method_id",
    "result",                 # recovered | still_refused | inconclusive | relapsed
    "probed_at",              # when the last probe ran
    "next_probe_after",       # earliest time another probe may run (cooldown)
    "consecutive_refusals",   # probes in a row that were not `recovered`
    "requests",               # requests the LAST probe made
    "total_requests",         # requests all probes of this method have made
    "http_status",            # status of the decisive response, when there was one
    "reason",                 # bounded machine reason, e.g. access_challenge, http_403, marker_missing
    # --- service state of a method a probe returned (written by the re-probe step ONLY) ---
    "relapses",               # recoveries the real run then refused; an answered probe does NOT reset it
    "service_runs",           # answered real runs since the last recovery (the ramp position)
    "unsettled_runs",         # granted runs in a row that left no row behind (lost cycles)
    "granted_at",             # when the re-probe step granted the CURRENT run its service
    "grant_requests",         # the request budget granted for that run
    "state_at",               # when this record last changed; the newer copy wins a carry merge
)
VALID_PROBE_RESULTS = frozenset({"recovered", "still_refused", "inconclusive", "relapsed"})
_PROBE_COUNTERS = ("consecutive_refusals", "requests", "total_requests")
# Written only when they hold something, so a record that never served stays as small as it was.
_PROBE_OPTIONAL_COUNTERS = ("relapses", "service_runs", "unsettled_runs", "grant_requests")
_PROBE_OPTIONAL_TEXT = ("granted_at", "state_at")


def method_probe_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("product_id") or "").strip(), str(row.get("method_id") or "").strip())


def normalize_method_probe_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field in METHOD_PROBE_FIELDS:
        if field in _PROBE_COUNTERS:
            normalized[field] = _nonnegative_int(row.get(field)) or 0
        elif field == "http_status" or field in _PROBE_OPTIONAL_COUNTERS:
            number = _nonnegative_int(row.get(field))
            if number:
                normalized[field] = number
        elif field in _PROBE_OPTIONAL_TEXT:
            text = str(row.get(field) or "").strip()
            if text:
                normalized[field] = text
        else:
            normalized[field] = str(row.get(field) or "").strip()
    if normalized["result"] not in VALID_PROBE_RESULTS:
        normalized["result"] = "inconclusive"
    return normalized


# --- the re-probe STEP's own health --------------------------------------------------------------
# A probe step that crashes used to leave nothing behind: one log line, exit 0, a green run. Its
# failure is now a fact in the health file: `probe_step: {status: error, at, error, consecutive_errors}`,
# written by the step's own exception handler and removed by its next clean run. Absent = healthy.
PROBE_STEP_FIELDS = ("status", "at", "error", "consecutive_errors")


def normalize_probe_step(step: Any) -> dict[str, Any]:
    if not isinstance(step, dict) or str(step.get("status") or "").strip() != "error":
        return {}
    return {"status": "error", "at": str(step.get("at") or "").strip(),
            "error": str(step.get("error") or "").strip()[:120],
            "consecutive_errors": _nonnegative_int(step.get("consecutive_errors")) or 1}


def load_probe_step(path: Path = METHOD_HEALTH_PATH) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 -- an unreadable file has no step record to preserve
        return {}
    return normalize_probe_step(payload.get("probe_step")) if isinstance(payload, dict) else {}


def record_probe_step(path: Path = METHOD_HEALTH_PATH, *, error: str = "", at: str = "") -> bool:
    """Record that the re-probe step failed (`error` given) or ran clean (`error` empty, which
    removes the record). Returns True when the file changed. Method rows and probe records are
    rewritten as they are."""
    prior = load_probe_step(path)
    if not error:
        if not prior:
            return False
        write_method_health_file(load_method_health(path), path, probe_step=None)
        return True
    step = {"status": "error", "at": at, "error": error,
            "consecutive_errors": int(prior.get("consecutive_errors") or 0) + 1}
    write_method_health_file(load_method_health(path), path, probe_step=step)
    return True


def load_method_probes(path: Path = METHOD_HEALTH_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return []
    probes = payload.get("probes") or []
    if not isinstance(probes, list):
        raise ValueError(f"{path} field 'probes' must be a list")
    return [normalize_method_probe_row(item) for item in probes if isinstance(item, dict)]


def upsert_method_probes(rows: list[dict[str, Any]], path: Path = METHOD_HEALTH_PATH) -> tuple[int, list[dict[str, Any]]]:
    """Insert or replace probe records by (product_id, method_id). Method rows are untouched."""
    existing = load_method_probes(path)
    index = {method_probe_key(row): idx for idx, row in enumerate(existing)}
    changed = 0
    for row in rows:
        normalized = normalize_method_probe_row(row)
        key = method_probe_key(normalized)
        if not all(key):
            continue
        current = index.get(key)
        if current is None:
            index[key] = len(existing)
            existing.append(normalized)
            changed += 1
        elif existing[current] != normalized:
            existing[current] = normalized
            changed += 1
    if changed:
        write_method_health_file(load_method_health(path), path, probes=existing)
    return changed, existing


def _family_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    product_id, version, build = patch_key_from(row)
    return (product_id, version, build, str(row.get("source_type") or "").strip())


def _distribute_capped(rows: list[dict[str, Any]], total: int) -> list[int]:
    """Share `total` across `rows`, giving no row more than it accepted.

    An evidence row records the COMMUNITY it came from, not the route that found it, so a family
    delta cannot be split by method with certainty when several methods read one community
    (PowerPoint has three on `microsoft_learn_qna`; Adobe has five on `adobe_community_bug_report`).
    What IS certain is that a method cannot have stored more than it accepted, so the share is
    walked in order and capped at each row's own accepted count.

    The first version of this handed the whole family delta to the FIRST row with that key. On the
    real Premiere method order -- `adobe_community_search` first and usually empty, `brave_search_api`
    later and productive -- that published `accepted=0, stored=3` for a method that found nothing and
    `stored=0, already held=3` for the method that had just stored them. Worse, `stored > accepted`
    is refused by `validate_evidence_method_health`, which runs `--validate-before-commit` in both
    write lanes, so the whole run's writeback would have been rejected -- every product, every file,
    on every retry.
    """
    shares = [0] * len(rows)
    remaining = total
    for index, row in enumerate(rows):
        if remaining <= 0:
            break
        room = int(row.get("accepted_candidates") or 0)
        take = min(remaining, max(0, room))
        shares[index] = take
        remaining -= take
    return shares


def finalize_method_health_delta(health_rows: Iterable[dict[str, Any]],
                                 added_rows: Iterable[dict[str, Any]],
                                 already_held_rows: Iterable[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """Stamp the MEASURED append outcome onto health rows, after the append has happened.

    Both numbers come from the append itself -- `added_rows` from ``out_added`` and
    `already_held_rows` from ``out_already_held`` -- because neither can be inferred. Deriving
    duplicates as "accepted minus stored" was wrong three ways: a batch the build gate abandoned
    reported every accepted row as "already held" when the store was empty; a URL two methods of one
    collector both accepted in the SAME run was reported as archive depth; and the row credited with
    the family's stored rows reported them as duplicates.

    Attribution is by (canonical patch identity, source_type) because that is what both a health row
    and an evidence row carry, then shared within the family capped by each row's accepted count --
    see `_distribute_capped`. Within one community read by several methods the split between those
    methods is therefore approximate; the family total, and the invariant that no row claims more
    than it accepted, are exact.

    Mutates and returns the rows, so a caller can finalize the list it is about to hand back.
    """
    finalized = list(health_rows or ())
    added_by_family: dict[tuple[str, str, str, str], int] = {}
    for row in added_rows or ():
        key = _family_key(row)
        added_by_family[key] = added_by_family.get(key, 0) + 1
    held_by_family: dict[tuple[str, str, str, str], int] = {}
    for row in already_held_rows or ():
        key = _family_key(row)
        held_by_family[key] = held_by_family.get(key, 0) + 1

    families: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in finalized:
        families.setdefault(_family_key(row), []).append(row)
    for key, rows in families.items():
        for row, stored in zip(rows, _distribute_capped(rows, added_by_family.get(key, 0))):
            row["evidence_rows_added"] = stored
        for row, held in zip(rows, _distribute_capped(rows, held_by_family.get(key, 0))):
            # A row cannot have both stored and already-held more than it accepted in total.
            room = max(0, int(row.get("accepted_candidates") or 0) - int(row.get("evidence_rows_added") or 0))
            row["duplicate_existing_evidence"] = min(held, room)
    return finalized


def method_health_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    """Method-health identity = canonical patch identity + method.

    The build slot is '' for every product without a build contract, so their rows keep the exact
    identity they had. For a build-aware product two builds under one YYMM are two health rows and
    neither can overwrite the other."""
    product_id, version, build = patch_key_from(row)
    return (product_id, version, build, str(row.get("method_id") or "").strip())


def upsert_method_health(rows: list[dict[str, Any]], path: Path = METHOD_HEALTH_PATH) -> tuple[int, int, list[dict[str, Any]]]:
    existing = load_method_health(path)
    index = {method_health_key(row): idx for idx, row in enumerate(existing)}
    changed = 0
    for row in rows:
        normalized = normalize_method_health_row(row)
        key = method_health_key(normalized)
        # The REQUIRED identity components are product, version and method. The build slot is
        # legitimately empty for every product without a build contract, so `all(key)` would drop
        # each of their rows -- guard the required components explicitly instead.
        product_id, version, _build, method_id = key
        if not (product_id and version and method_id):
            continue
        current_idx = index.get(key)
        if current_idx is not None and is_policy_disabled_row(normalized) and not normalized["last_run"]:
            # AUX D2: a method switched off by ACCESS POLICY made no attempt this run, so it has
            # no timestamp of its own to write. Keep the prior row's real last attempt rather
            # than restamping history with a time nothing was attempted. Only policy rows
            # (status disabled + reason reddit_access_policy_unauthorised) take this path.
            normalized["last_run"] = existing[current_idx].get("last_run", "") or ""
        carry_method_history(existing[current_idx] if current_idx is not None else None, normalized)
        if current_idx is None:
            index[key] = len(existing)
            existing.append(normalized)
            changed += 1
        elif existing[current_idx] != normalized:
            existing[current_idx] = normalized
            changed += 1
    if changed:
        write_method_health_file(existing, path)
    return changed, len(existing), existing


def carry_method_history(prior: dict[str, Any] | None, row: dict[str, Any]) -> dict[str, Any]:
    """Maintain the carried history fields of `row` from the row it replaces. Mutates and returns it.

    Deterministic, and a function of the two rows only. An ATTEMPT is a row whose status is not
    `disabled` and whose `last_run` is new: a switched-off method made no attempt, and the same run
    upserted twice (a resumed cycle) is one attempt, not two. A non-attempt carries the prior
    history through unchanged, so a method that is switched off keeps the record of when it last
    answered instead of losing it.

    A prior row written before these fields existed is read for what it actually says -- its own
    status, accepted count and `last_run` are one known attempt -- and never back-filled further.
    """
    prior = prior or {}
    prior_status = str(prior.get("status") or "")
    prior_run = str(prior.get("last_run") or "")
    prior_attempted = bool(prior_run) and prior_status not in ("", "disabled")

    def _prior_int(field: str, seed: int) -> int:
        number = _nonnegative_int(prior.get(field))
        return seed if number is None else number

    attempts = _prior_int("attempts", 1 if prior_attempted else 0)
    last_good = str(prior.get("last_good_at") or "") or (
        prior_run if prior_attempted and prior_status in RESPONDING_HEALTH_STATUSES else "")
    last_accepted = str(prior.get("last_accepted_at") or "") or (
        prior_run if prior_attempted and int(prior.get("accepted_candidates") or 0) > 0 else "")
    failures = _prior_int("consecutive_failures",
                          1 if prior_attempted and prior_status in FAILING_HEALTH_STATUSES else 0)
    zero_runs = _prior_int("consecutive_zero_accept_runs",
                           1 if prior_attempted and int(prior.get("accepted_candidates") or 0) == 0 else 0)

    status = str(row.get("status") or "")
    last_run = str(row.get("last_run") or "")
    attempted = bool(last_run) and status != "disabled" and last_run != prior_run
    if attempted:
        attempts += 1
        if status in RESPONDING_HEALTH_STATUSES:
            last_good = last_run
        failures = failures + 1 if status in FAILING_HEALTH_STATUSES else 0
        if int(row.get("accepted_candidates") or 0) > 0:
            last_accepted = last_run
            zero_runs = 0
        else:
            zero_runs += 1
    elif status != "disabled" and last_run == prior_run and prior:
        # The same attempt written again: its measured cost belongs to it, keep what was stored.
        for field in METHOD_HEALTH_MEASURED_FIELDS:
            if field not in row and field in prior:
                row[field] = prior[field]
    for field, value in (("attempts", attempts), ("last_good_at", last_good),
                         ("last_accepted_at", last_accepted), ("consecutive_failures", failures),
                         ("consecutive_zero_accept_runs", zero_runs)):
        if value:
            row[field] = value
        else:
            row.pop(field, None)
    return row


def method_health_row(
    *,
    product_id: str,
    update_version: str,
    method_id: str,
    target_build: str = "",
    source_type: str,
    status: str,
    candidates_found: int,
    accepted_reports: int,
    rejected_reports: int,
    blocked_reason: str | None,
    last_run: str,
    notes: str,
    accepted_candidates: int | None = None,
    duplicate_existing_evidence: int = 0,
    evidence_rows_added: int | None = None,
    public_counted_reports: int | None = None,
    duration_ms: int | None = None,
    requests: int | None = None,
    rejection_reasons: dict[str, int] | None = None,
) -> dict[str, Any]:
    # `duration_ms` / `requests` / `rejection_reasons` are the MEASURED cost and outcome of this
    # attempt. None means the collector did not measure it, and the row then carries no such field.
    return normalize_method_health_row({
        "duration_ms": duration_ms,
        "requests": requests,
        "rejection_reasons": rejection_reasons,
        "product_id": product_id,
        "update_version": update_version,
        "target_build": target_build,
        "method_id": method_id,
        "source_type": source_type,
        "status": status,
        "candidates_found": candidates_found,
        "accepted_candidates": accepted_reports if accepted_candidates is None else accepted_candidates,
        "duplicate_existing_evidence": duplicate_existing_evidence,
        # ROWS PERSISTED, NOT CANDIDATES ACCEPTED. This defaulted to `accepted_reports`, which made
        # the field a second name for `accepted_candidates` -- and it was exactly that in all 1484
        # committed rows, with `duplicate_existing_evidence` zero in every one of them. A collector
        # re-finds the same threads every run and re-accepts them; `append_evidence_rows` then
        # refuses each one as a duplicate, so a run could accept 80 rows, store 0, and publish
        # "80 added" on the public methodology table. Measured over the git history of that table:
        # 336 rows claimed against 48 actually stored.
        #
        # A health row is now built claiming NOTHING was stored, and the collector overwrites it via
        # `finalize_method_health_delta` once `append_evidence_rows` has reported the real delta. A
        # dry run stores nothing and 0 is therefore correct there; a write run that forgets to
        # finalize understates instead of overstating, which is the safe direction for a number
        # whose whole job is to say what actually reached the store.
        "evidence_rows_added": 0 if evidence_rows_added is None else evidence_rows_added,
        "public_counted_reports": accepted_reports if public_counted_reports is None else public_counted_reports,
        "accepted_reports": accepted_reports,
        "rejected_reports": rejected_reports,
        "blocked_reason": blocked_reason or "",
        "last_run": last_run,
        "notes": notes,
    })


def normalize_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        field: row.get(field)
        for field in EVIDENCE_FIELDS
        if field not in OPTIONAL_EVIDENCE_FIELDS or row.get(field) not in (None, "")
    }
    normalized["source_weight"] = int(normalized.get("source_weight") or 1)
    normalized["counted"] = bool(normalized.get("counted"))
    normalized["patch_version_matched"] = bool(normalized.get("patch_version_matched"))
    for tri_field in ("source_date_pass", "evidence_valid_for_current_patch", "stale_due_to_patch_rollover"):
        if tri_field in normalized and normalized.get(tri_field) not in (True, False, None):
            normalized[tri_field] = bool(normalized.get(tri_field))
    for field in EVIDENCE_FIELDS:
        if field not in normalized:
            continue
        if field in {"source_weight", "counted", "patch_version_matched", "source_date_pass",
                     "evidence_valid_for_current_patch", "stale_due_to_patch_rollover"}:
            continue
        if normalized[field] is not None:
            normalized[field] = str(normalized[field])
    return normalized


def evidence_key(row: dict[str, Any], key_field: str) -> tuple[str, str, str, str]:
    """Append/dedup identity for a structured evidence row.

    The first three components are the canonical patch identity (``lib.patch_identity.key_from``),
    whose build slot is '' for every product without a build contract -- so this stays semantically
    identical for OBS/DaVinci/Premiere/Acrobat/Windows. For a build-aware product the exact build
    participates, so two reports sharing a source URL and YYMM but naming DIFFERENT builds are two
    rows, while two discoveries of the same report for the SAME build still deduplicate.

    The URL slot is the canonical REPORT identity (``lib.source_segments.report_url_key``), not the
    raw URL. For every host but Microsoft Learn Q&A that is ``normalize_url`` byte for byte. For a
    Learn Q&A URL it is the question id plus the anchored segment, because the URL's title slug
    follows the title: four Windows reports were stored and counted twice on one patch under two
    slugs of one question (AUX-078). The id slot stays ``normalize_url`` of the stored id; ids are
    labels and are never rewritten. This one function is the identity of the durable append guard
    AND of the write-authority validator (``collector_ownership``), so the two cannot drift."""
    product_id, version, build = patch_key_from(row)
    value = str(row.get(key_field) or "")
    slot = report_url_key(value) if key_field == "source_url" else normalize_url(value)
    return (product_id, version, build, slot)


def discovery_method_for(row: dict[str, Any], method_health: Iterable[dict[str, Any]] | None) -> str:
    """The ONE method that can have found `row` in this run, or '' when that is not established.

    A health row and an evidence row share exactly two things: the canonical patch identity and the
    source type. So the method is established only when exactly one method of that patch and source
    type accepted at least one candidate in this run. Two such methods (PowerPoint reads Microsoft
    Q&A three ways) leave the row unstamped -- unless the collector, which does know, set
    `discovery_method_id` itself; that value is kept when it is one of the run's own methods for the
    row's patch, and dropped otherwise. Fail closed: no guess is ever written."""
    health = [h for h in (method_health or ()) if isinstance(h, dict)]
    same_patch = [h for h in health if patch_key_from(h) == patch_key_from(row)]
    declared = str(row.get("discovery_method_id") or "").strip()
    if declared:
        return declared if any(str(h.get("method_id") or "") == declared for h in same_patch) else ""
    source_type = str(row.get("source_type") or "").strip()
    finders = sorted({str(h.get("method_id") or "") for h in same_patch
                      if str(h.get("source_type") or "").strip() == source_type
                      and int(h.get("accepted_candidates") or 0) > 0
                      and str(h.get("status") or "") != "disabled"} - {""})
    return finders[0] if len(finders) == 1 else ""


def append_evidence_rows(rows: list[dict[str, Any]], path: Path = EVIDENCE_PATH,
                         *, out_added: list[dict[str, Any]] | None = None,
                         out_already_held: list[dict[str, Any]] | None = None,
                         method_health: Iterable[dict[str, Any]] | None = None) -> tuple[int, int, list[dict[str, Any]]]:
    """Append rows the store does not already hold. Returns (added, total, all rows).

    ``out_added`` is an OPTIONAL sink for the rows actually persisted. It exists because the count
    alone cannot be attributed: method-health telemetry has to say how many rows THIS METHOD stored
    for THIS patch, and only the rows themselves carry the source_type and the patch identity. It is
    a keyword-only out-parameter rather than a fourth return value because seven production call
    sites unpack this function's three-tuple, and silently changing that arity is how a refactor
    becomes an outage.

    ``out_already_held`` is the other half, and it has to be MEASURED here rather than derived by
    the caller: a refusal because the STORE already held the row is not the same event as a refusal
    because an earlier row in this same batch had the identical URL, and neither is the same as a
    batch abandoned mid-flight by the build gate. Only this loop can tell them apart, because only
    it knows which keys were present before the batch started.

    ``method_health`` is the run's own health rows. When given, each NEW row is stamped with the
    discovery method that found it (``discovery_method_for``); a row whose finder is not established
    is stored without the field. Without it, nothing is stamped and any `discovery_method_id` a row
    arrives with is dropped, so the field can only ever name a method of the run that wrote the row.
    It is provenance: no gate, count or dedupe key reads it, and stored rows are never restamped.

    Both guard sets are ``evidence_key``, so a Microsoft Learn Q&A report re-found under a new title
    slug is "already held" (and counted in ``out_already_held``), never a second row. The row the
    store holds wins: its id and source_url are never rewritten, and the new spelling is not stored.
    """
    existing = load_evidence(path)
    # The keys the store held BEFORE this batch. `seen_ids` / `seen_urls` grow as the loop accepts,
    # so they cannot answer "was this already held?" once the batch is underway.
    seen_ids = {evidence_key(row, "id") for row in existing if row.get("id")}
    seen_urls = {
        evidence_key(row, "source_url")
        for row in existing
        if row.get("source_url") and row.get("match_basis") != "embedded_listing_report_card"
    }
    preexisting_ids = set(seen_ids)
    preexisting_urls = set(seen_urls)
    added = 0
    for row in rows:
        # The structured facts are computed HERE, from the text this row holds, so every collector that
        # persists through this boundary writes them (G68). Existing rows are never touched.
        normalized = evidence_facts.with_facts(normalize_evidence_row(row))
        finder = discovery_method_for(normalized, method_health)
        if finder:
            normalized["discovery_method_id"] = finder
            normalized = normalize_evidence_row(normalized)  # canonical key order
        else:
            normalized.pop("discovery_method_id", None)
        # Fail closed at the durable boundary: a COUNTED row for a build-aware product must carry
        # the exact build it was accepted for. Persisting a counted row without one would create
        # evidence that names a version but no patch -- unattributable to any build-specific
        # record, and silently uncounted by every build-aware consumer downstream. Uncounted rows
        # (rejected candidates, audit trail) are allowed to have no build.
        if normalized.get("counted") is not False:
            require_build(normalized.get("product_id"), normalized.get("update_version"),
                          normalized.get("target_build"),
                          f"counted evidence row {normalized.get('id') or normalized.get('source_url')!r}")
        id_key = evidence_key(normalized, "id")
        url_key = evidence_key(normalized, "source_url")
        url_duplicate = (
            normalized.get("match_basis") != "embedded_listing_report_card"
            and url_key in seen_urls
        )
        if id_key in seen_ids or url_duplicate:
            # Refused. Report it as "the store already held this" ONLY when the key was present
            # before this batch began; a collision with an earlier row of this same batch is a
            # different event and must not be published as archive depth.
            if out_already_held is not None and (
                    id_key in preexisting_ids
                    or (normalized.get("match_basis") != "embedded_listing_report_card"
                        and url_key in preexisting_urls)):
                out_already_held.append(normalized)
            continue
        existing.append(normalized)
        seen_ids.add(id_key)
        if normalized.get("match_basis") != "embedded_listing_report_card":
            seen_urls.add(url_key)
        added += 1
    if added:
        # Atomic append: preserve the existing file bytes EXACTLY and append only the serialized new
        # rows, then write the whole result via a temp sibling + os.replace. This removes the raw
        # `open("a")` torn-write hazard (an interruption can no longer leave a partial YAML document)
        # while keeping the historical bytes untouched (no full reformat). No additions -> no write.
        appended_rows = existing[-added:]
        if out_added is not None:
            out_added.extend(appended_rows)
        serialized = yaml.safe_dump(appended_rows, sort_keys=False, allow_unicode=True, width=1000)
        # The byte-append is only valid when the file already ENDS INSIDE the evidence list. A store
        # written as `{schema_version: 1, evidence: []}` ends inside a mapping, so concatenating a
        # bare top-level sequence onto it produces a document PyYAML then refuses to load
        # ("expected <block end>, but found '-'") -- the store is destroyed by its first append.
        # Not reachable from the live file, which has never been empty, but reachable from any fresh
        # store, which is how the mandated telemetry fixtures found it.
        if path.exists() and len(existing) > added:
            existing_text = path.read_text(encoding="utf-8")
            # A newline only to END an unterminated last line. The store normally ends in one already,
            # and a second would be a blank line before the batch: the stored format has none, and
            # the text between two rows is read as the earlier row's facts (E8). Until R4-FIX2 this
            # always added one, and the blank survived whenever no full rewrite followed in the run.
            separator = "\n" if existing_text and not existing_text.endswith("\n") else ""
            atomic_write_text(path, existing_text + separator + serialized)
        else:
            write_evidence_file(existing, path)
    return added, len(existing), existing


def row_is_counted(row: dict[str, Any]) -> bool:
    """The ROW half of the authoritative counted-evidence predicate: `counted is not False` AND
    `patch_version_matched is True`.

    `lib.report_counts.counted_evidence_rows` adds the record-relative half (the Windows current-patch
    identity gate) and groups by canonical identity. Defined here, at the lowest layer, so every
    counter -- the consensus writer, the audit, revalidation and collector diagnostics -- reads this
    one definition instead of re-deriving acceptance. Seven private copies of it disagreed in code
    and agreed only because the stored rows happened to be clean."""
    return row.get("counted") is not False and row.get("patch_version_matched") is True


def counted_rows(rows: Iterable[dict[str, Any]], product_id: str, update_version: str) -> list[dict[str, Any]]:
    """Version-level counted rows, for collector run diagnostics. Not identity-exact (no build, no
    Windows gate) -- the published count is `lib.report_counts.counted_evidence_counts`."""
    return [
        row for row in rows
        if str(row.get("product_id") or "").strip() == product_id
        and str(row.get("update_version") or "").strip() == update_version
        and row_is_counted(row)
    ]


def normalize_url(url: str) -> str:
    """Spelling normalisation (strip, trailing slash, lowercase). NOT a report identity on its own:
    dedup compares ``report_url_key``, which is this for every host except Learn Q&A (AUX-078)."""
    return url.strip().rstrip("/").lower()


# A version prefix a reporter writes immediately before the number. Only these: an arbitrary
# preceding letter must still block the match, or "dev25.001.21111" and "rev25.001.21111" would
# read as 25.001.21111.
_VERSION_PREFIX_RE = re.compile(r"(?:^|[^A-Za-z0-9.])(?:v|ver|version|build)\.?$", re.I)


def exact_version_match(text: str, version: str, aliases: Iterable[str] = ()) -> tuple[bool, str, str]:
    """(matched, matched_version, match_basis) -- `exact_version_match_span` without the offsets."""
    matched, candidate, basis, _start, _end = exact_version_match_span(text, version, aliases)
    return matched, candidate, basis


def exact_version_match_span(
        text: str, version: str, aliases: Iterable[str] = (),
) -> tuple[bool, str, str, int, int]:
    """Does ``text`` name exactly this version (or one of its product-local spellings)?

    Returns ``(matched, matched_version, match_basis, start, end)``, where ``start:end`` is the
    occurrence the matcher ACCEPTED. The offsets exist so a collector can retain the evidence for
    its own match. Stored excerpts are truncated (Reddit DaVinci rows are cut at 280 characters, 261
    of 319 at the cap), so an `exact_version_text` claim could not be audited after the fact: two rows
    from one post shared a truncated prefix, and nothing on disk showed which occurrence had matched.
    This is the one predicate; `exact_version_match` is a view of it, so the two cannot disagree.

    BOUNDARIES. The trailing guard has to reject a longer version -- "26.001.21745.1" is a
    different build, and "26.001.217450" is a different number -- while accepting the sentence that
    simply ENDS: "we are on version 26.001.21745." A period is only a version component when a
    digit follows it, so that is the rule, rather than banning the character outright. Measured on
    the live Acrobat corpus, the old guard refused six real reports on prose punctuation alone.

    The leading guard stays strict about letters, with one exception: a recognised version prefix
    written against the number ("v25.001.21111"). `dev`/`rev`/any other word still blocks.
    """
    body = text or ""
    for candidate in [version, *aliases]:
        candidate = str(candidate or "").strip()
        if not candidate:
            continue
        # No leading lookbehind in the pattern: a version prefix is alphabetic, so a lookbehind
        # would reject "v25.001.21111" before the loop could tell "v" from "dev". The leading
        # boundary is decided below instead, on the text actually preceding the hit.
        pattern = re.compile(rf"{re.escape(candidate)}(?![A-Za-z0-9])(?!\.\d)", flags=re.I)
        for hit in pattern.finditer(body):
            before = body[:hit.start()]
            if not before:
                pass                                    # start of text
            elif _VERSION_PREFIX_RE.search(before):
                pass                                    # v / ver / version / build, written against
            elif before[-1].isdigit() or before[-1] == "." or before[-1].isalpha():
                continue                                # inside a longer number, or another word
            return (True, candidate,
                    "exact_version_text" if candidate == version else "exact_version_alias",
                    hit.start(), hit.end())
    return False, "", "", -1, -1


#: Characters of surrounding text kept either side of an accepted version match. An audit aid, not a
#: copy of the post: enough to show the sentence the version appeared in, short enough that the
#: evidence store does not grow into an archive of forum threads.
MATCH_CONTEXT_CHARS = 80


def match_provenance(parts: list[tuple[str, str]], start: int, end: int) -> dict[str, str]:
    """Where an accepted match came from, for a text built as ``" ".join(value for _name, value)``.

    ``parts`` is the ordered (field_name, value) list the caller joined; ``start:end`` is the span
    `exact_version_match_span` accepted in that joined text. Nothing is searched again here -- a
    second search could land on a DIFFERENT occurrence than the one that established the match.
    """
    if start < 0 or end <= start:
        return {}
    joined = " ".join(value for _name, value in parts)
    field = ""
    offset = 0
    for name, value in parts:
        if offset <= start < offset + len(value):
            field = name
            break
        offset += len(value) + 1
    lo = max(0, start - MATCH_CONTEXT_CHARS)
    hi = min(len(joined), end + MATCH_CONTEXT_CHARS)
    context = " ".join(joined[lo:hi].split())
    return {
        "matched_text": joined[start:end],
        "matched_context": ("..." if lo > 0 else "") + context + ("..." if hi < len(joined) else ""),
        "matched_field": field,
    }


# --- version-centred excerpts (AUX-109) ---------------------------------------------------------
#
# `excerpt` keeps the first 280 characters of a report. When the reporter named the version further
# in, the stored row cannot show the occurrence its own match rests on: 132 Acrobat rows are like
# that. For a NEW row whose text is one opening post, the SAME field and the SAME cap are positioned
# around the accepted occurrence instead -- nothing grows, no field is added, and a row whose head
# already shows the version is stored exactly as before. No stored row changes (the append path
# never rewrites one, and collector ownership refuses a modified row). Acceptance never reads the
# excerpt: every gate reads the full in-memory text, so this changes what is stored, not what counts.

#: Characters a version-centred excerpt keeps before the accepted occurrence (the OBS collector's lead).
EXCERPT_LEAD_CHARS = 90
#: The last characters of a post, where a sign-off or a signature sits. A window never reaches into
#: them unless the version itself is there, and then it stops at the end of the version's sentence.
EXCERPT_TAIL_CHARS = 60
#: Set to True by a discovery method whose candidate `report_text` is the OPENING POST ONLY (no reply,
#: no comment, no page chrome). Only such a candidate is re-centred: in a whole-thread page a centred
#: window could land inside another author's reply. Absent means False, so an unknown candidate
#: shape keeps the head.
FIRST_POST_ONLY = "report_text_is_first_post_only"
_PLACEHOLDER = "..."

# What a window must not carry that the head would not have shown: an e-mail address, an @handle
# (with up to two capitalised words after it, a display name), a greeting with the name it addresses,
# a sign-off or a signature. These only ever SHRINK a window -- never move it onto other text -- so
# a false hit costs context, not privacy. The head is untouched by design (byte-identical to today).
_EXCERPT_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_EXCERPT_HANDLE_RE = re.compile(r"(?<![\w.@])@\w[\w.-]*(?:\s+[A-Z][\w'-]*){0,2}")
_EXCERPT_GREETING_RE = re.compile(
    r"\b(?:hi|hello|hey|dear|greetings|good\s+(?:morning|afternoon|evening))\b"
    r"(?:\s+[@\w][\w.'@-]*){0,3}?\s*[,!:]", re.I)
_EXCERPT_SIGN_OFF_RE = re.compile(
    r"(?<![\w'])(?:many\s+thanks|thanks|thank\s+you|thx|tia|cheers|(?:best|kind|warm|warmest)\s+regards|"
    r"regards|best\s+wishes|sincerely|respectfully|sent\s+from\s+my)\b", re.I)
# A dash signature closing the post: "-- Bob", " - Jane Smith", "— IT team".
_EXCERPT_DASH_SIGNATURE_RE = re.compile(r"\s(?:--+|[-–—])\s*[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,2}\s*$")
_EXCERPT_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def excerpt_visible_head(text: str, width: int = 280) -> str:
    """The part of `excerpt(text)` that is the reporter's own text: the excerpt without the
    placeholder `textwrap.shorten` appends when it cuts. Always a prefix of the collapsed text."""
    head = excerpt(text, width)
    if len(_collapse_ws(text)) <= width:
        return head
    return head[:-len(_PLACEHOLDER)] if head.endswith(_PLACEHOLDER) else head


def excerpt_at(text: str, start: int, end: int, width: int = 280) -> str:
    """The stored excerpt of `text`, positioned so the accepted occurrence ``text[start:end]`` is in it.

    Byte-identical to ``excerpt(text, width)`` -- today's head -- unless ALL of these hold: the span is
    valid, the collapsed text is longer than `width`, and the occurrence does not end inside the
    head's visible text. Then a window of at most `width` characters, cut from the same collapsed
    text: up to EXCERPT_LEAD_CHARS before the occurrence and the rest after it, word-aligned, with
    the placeholder at each end that does not reach the post's own start or end. The window never
    reaches into a sign-off, signature, greeting, e-mail address or @handle around the occurrence,
    nor (unless the occurrence is there) into the post's last EXCERPT_TAIL_CHARS characters. Any
    inconsistency returns the head, so this can only ever fall back to today's behaviour.
    """
    head = excerpt(text, width)
    if start is None or end is None or start < 0 or end <= start or end > len(text or ""):
        return head
    collapsed = _collapse_ws(text)
    if len(collapsed) <= width:
        return head
    token = _collapse_ws(text[start:end])
    if not token:
        return head
    cstart = len(re.sub(r"\s+", " ", text[:start]).lstrip())
    cend = cstart + len(token)
    visible = excerpt_visible_head(text, width)
    if collapsed[cstart:cend] != token or not collapsed.startswith(visible):
        return head
    if cend <= len(visible):
        return head
    budget = width - 2 * len(_PLACEHOLDER)
    if cend - cstart > budget:
        return head
    # Hard limits first: nothing the window must not carry may sit inside it.
    left_cap, right_cap = 0, len(collapsed)
    for rx in (_EXCERPT_EMAIL_RE, _EXCERPT_HANDLE_RE, _EXCERPT_GREETING_RE):
        for m in rx.finditer(collapsed):
            if m.end() <= cstart:
                left_cap = max(left_cap, m.end())
            elif m.start() >= cend:
                right_cap = min(right_cap, m.start())
            elif rx is not _EXCERPT_GREETING_RE:
                return head                                  # it overlaps the occurrence itself
    for m in _EXCERPT_SIGN_OFF_RE.finditer(collapsed):
        if m.start() >= cend:
            right_cap = min(right_cap, m.start())
            break
        if cstart - budget - 40 < m.end() <= cstart:
            # A sign-off BEFORE the occurrence, within a window's reach ("Thanks, Bob. Edit: the
            # version is ..."): the window starts after the sentence it closes, or at the occurrence
            # itself when no sentence end follows it.
            close = _EXCERPT_SENTENCE_END_RE.search(collapsed, m.end(), cstart)
            left_cap = max(left_cap, close.end() if close else cstart)
    dash = _EXCERPT_DASH_SIGNATURE_RE.search(collapsed, cend)
    if dash:
        right_cap = min(right_cap, dash.start())
    # The post's last characters are where an unrecognised sign-off sits ("Bob from IT"). The window
    # stops at the tail's start, or -- when the occurrence's own sentence runs on into the tail, or the
    # occurrence is inside it -- at the end of that sentence, and at the occurrence itself when that
    # sentence never ends.
    tail = len(collapsed) - EXCERPT_TAIL_CHARS
    sentence = _EXCERPT_SENTENCE_END_RE.search(collapsed, cend)
    own_end = sentence.start() if sentence else None
    if cend <= tail:
        right_cap = min(right_cap, tail if own_end is None else max(tail, own_end))
    else:
        right_cap = min(right_cap, cend if own_end is None else own_end)
    # Then the budget, between the caps: the lead before the occurrence, the rest after it, and any
    # room the right-hand cap leaves goes back to the left.
    lo = max(left_cap, cstart - EXCERPT_LEAD_CHARS)
    hi = min(right_cap, lo + budget)
    lo = max(left_cap, hi - budget)
    # Word-aligned: an edge that falls inside a word moves to the nearest space on the window's side
    # (a cut before trailing punctuation, or after an opening bracket or quote, is already a boundary).
    if lo > 0 and collapsed[lo - 1] not in " ([{\"'":
        nxt = collapsed.find(" ", lo)
        if 0 <= nxt < cstart:
            lo = nxt + 1
    if hi < len(collapsed) and collapsed[hi] not in " .,;:!?)]}\"'":
        prv = collapsed.rfind(" ", lo, hi)
        if prv >= cend:
            hi = prv
    if not collapsed[hi:].strip(" .!?") and len(collapsed) - lo <= budget:
        hi = len(collapsed)                                  # only the post's closing punctuation is left
    window = collapsed[lo:hi].strip()
    result = (_PLACEHOLDER if lo > 0 else "") + window + (_PLACEHOLDER if hi < len(collapsed) else "")
    if not (lo <= cstart and cend <= hi) or token not in window or len(result) > width:
        return head
    return result


def part_span(parts: list[tuple[str, str]], start: int, end: int) -> tuple[str, int, int] | None:
    """The part of a ``" ".join(value for _name, value in parts)`` text that holds ALL of ``start:end``,
    as ``(field_name, local_start, local_end)``; None for an invalid span or one that crosses a join.
    The field walk `match_provenance` makes, returning offsets instead of a window."""
    if start < 0 or end <= start:
        return None
    offset = 0
    for name, value in parts:
        if offset <= start and end <= offset + len(value):
            return name, start - offset, end - offset
        offset += len(value) + 1
    return None


def first_post_excerpt_span(
        candidate: dict[str, Any], parts: list[tuple[str, str]], text: str, version: str,
        aliases: Iterable[str] = (), *, accepted: tuple[bool, str, str], field: str = "report_text",
        width: int = 280,
) -> tuple[int, int] | None:
    """Where a new row's excerpt is centred: offsets of the ACCEPTED occurrence inside
    ``candidate[field]`` -- the text `make_evidence_row` cuts the excerpt from -- or None to keep
    today's head excerpt.

    `text` is the joined text acceptance matched (``" ".join`` of `parts`' values) and `accepted` the
    (matched, matched_version, match_basis) it decided; the span comes from `exact_version_match_span`
    over the same text and spellings, and is used only when it agrees with that decision. None when:
    the candidate is not one opening post (FIRST_POST_ONLY), there is no exact-text match (Premiere's
    "build 65" basis has no span), the occurrence lies in another part (a title is stored whole) or
    across a join, or the head already shows an accepted spelling of the version.
    """
    if candidate.get(FIRST_POST_ONLY) is not True or not accepted or not accepted[0]:
        return None
    if " ".join(value for _name, value in parts) != text:
        return None
    aliases = tuple(aliases)
    matched, matched_version, basis, start, end = exact_version_match_span(text, version, aliases)
    if (matched, matched_version, basis) != tuple(accepted):
        return None
    located = part_span(parts, start, end)
    if located is None or located[0] != field:
        return None
    raw = str(candidate.get(field) or "")
    value = next(v for name, v in parts if name == field)
    lead = raw.find(value) if value else -1
    if lead < 0:
        return None
    local_start, local_end = located[1] + lead, located[2] + lead
    if raw[local_start:local_end] != text[start:end]:
        return None
    if exact_version_match(excerpt_visible_head(raw, width), version, aliases)[0]:
        return None
    return local_start, local_end


def source_url_is_specific(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parse_qs(parsed.query)
    if "reddit.com" in host:
        return "/comments/" in path and len(path.strip("/").split("/")) >= 4
    if "github.com" in host:
        return bool(re.search(r"/issues/\d+/?$", path))
    if "forum.blackmagicdesign.com" in host:
        return path.endswith("viewtopic.php") and bool(query.get("t"))
    if "creativecow.net" in host:
        return bool(re.fullmatch(r"/forums/thread/[^/]+/?", path))
    if "learn.microsoft.com" in host:
        # Microsoft Q&A: a specific question thread, e.g. /en-us/answers/questions/2412345/<slug>.
        return bool(re.search(r"/answers/questions/\d+", path))
    if "techcommunity.microsoft.com" in host:
        # Khoros/Aurora thread permalinks: /t5/.../m-p/<id>, /td-p/<id>, or a
        # /<board>/<slug>/<numeric-message-id> path. Board/search roots are rejected.
        if re.search(r"/(?:m-p|td-p)/\d+", path):
            return True
        segments = [seg for seg in path.strip("/").split("/") if seg]
        return len(segments) >= 3 and bool(re.search(r"\d{4,}", segments[-1]))
    return not path.rstrip("/").endswith(("/search", "/forums", "/forum")) and path.strip("/") not in {"", "forums", "forum"}


def source_date_passes(source_date: str, target_release_date: str) -> bool | None:
    if not target_release_date:
        return None
    if not source_date:
        return False
    source = parse_iso_date(source_date)
    target = parse_iso_date(target_release_date)
    if not source or not target:
        return False
    return source.date() >= target.date()


def text_describes_issue(text: str) -> bool:
    lowered = (text or "").lower()
    if not any(term in lowered for term in ISSUE_TERMS):
        return False
    if any(term in lowered for term in NON_REPORT_TERMS) and not any(term in lowered for term in ("crash", "bug", "broken", "failed", "regression")):
        return False
    return True


def make_evidence_row(
    *,
    product_id: str,
    update_version: str,
    source_type: str,
    source_name: str,
    source_url: str,
    parent_title: str,
    report_title: str,
    report_text: str,
    captured_at: str,
    source_date: str,
    target_release_date: str,
    patch_version_matched: bool,
    matched_version: str,
    match_basis: str,
    counted: bool,
    exclusion_reason: str | None,
    matched_kb: str = "",
    matched_os_build: str = "",
    matched_feature_version: str = "",
    matched_product_alias: str = "",
    applicability: str = "",
    issue_theme: str,
    workflow_area: str,
    platform: str,
    severity: str,
    sentiment: str,
    row_id: str | None = None,
    matched_text: str = "",
    matched_field: str = "",
    matched_context: str = "",
    excerpt_span: tuple[int, int] | None = None,
) -> dict[str, Any]:
    # `excerpt_span` (AUX-109): offsets of the accepted occurrence in `report_text`, from
    # `first_post_excerpt_span`. None -- every caller but the two Adobe opening-post paths -- keeps
    # `excerpt(report_text)` exactly, and so does a span whose occurrence the head already shows.
    stored_excerpt = excerpt_at(report_text, *excerpt_span) if excerpt_span else excerpt(report_text)
    return normalize_evidence_row({
        "id": row_id or f"{product_id}-{slug(update_version)}-{slug(source_type)}-{slug(source_url)}",
        "product_id": product_id,
        "update_version": update_version,
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "parent_title": parent_title,
        "report_title": report_title,
        "report_text_excerpt": stored_excerpt,
        "captured_at": captured_at,
        "source_date": source_date,
        "target_release_date": target_release_date,
        "source_date_pass": source_date_passes(source_date, target_release_date),
        "patch_version_matched": patch_version_matched,
        "matched_version": matched_version,
        "match_basis": match_basis,
        "matched_product_alias": matched_product_alias,
        "applicability": applicability,
        "matched_kb": matched_kb,
        "matched_os_build": matched_os_build,
        "matched_feature_version": matched_feature_version,
        "counted": counted,
        "exclusion_reason": exclusion_reason,
        "issue_theme": issue_theme,
        "workflow_area": workflow_area,
        "platform": platform,
        "severity": severity,
        "sentiment": sentiment,
        "source_weight": 1,
        "matched_text": matched_text,
        "matched_field": matched_field,
        "matched_context": matched_context,
    })


def apply_acceptance_gates(row: dict[str, Any], *, report_text: str) -> dict[str, Any]:
    gated = dict(row)
    reason: str | None = None
    if not gated.get("patch_version_matched"):
        reason = "missing_exact_patch_version_match"
    elif not source_url_is_specific(str(gated.get("source_url") or "")):
        reason = "source_url_not_specific_report"
    elif gated.get("source_date_pass") is False:
        reason = "source_date_before_or_unverified_against_release"
    elif not text_describes_issue(report_text):
        reason = "not_a_real_issue_report"

    if reason:
        gated["counted"] = False
        gated["exclusion_reason"] = reason
    else:
        gated["counted"] = True
        gated["exclusion_reason"] = None
    gated["source_weight"] = 1
    return normalize_evidence_row(gated)


# --- Windows patch-identity gate ---------------------------------------------
# Windows 11 records are keyed by feature train (24H2/25H2/...), but a patch
# decision is per cumulative update (KB / OS build). This fail-closed gate lets a
# Windows report count ONLY for the record's CURRENT patch identity, so evidence for
# an older KB/build stops counting the moment the record rolls over to a newer one.
WINDOWS_PRODUCT_ID = "microsoft-windows-11"


def windows_identity_gate(row: dict[str, Any], target: dict[str, Any] | None) -> tuple[bool, str | None]:
    """Return (counts_ok, exclusion_reason) for a Windows evidence row.

    `target` is the generated record's current-patch identity, i.e. its
    ``target_os_build`` / ``target_kb`` / ``target_feature_version`` /
    ``target_release_date`` front-matter fields (``update_version`` is accepted as a
    fallback feature-train value). Matching rules (fail closed):

    - **Primary** — exact OS build (``matched_os_build == target_os_build``). The build
      is train-specific, so this is unambiguous.
    - **Secondary** — exact KB *and* matching feature train
      (``matched_kb == target_kb`` and ``matched_feature_version == target_feature``).
      A KB can be shared across trains (e.g. 24H2 and 25H2 both ship KB5095093), so KB
      alone is never sufficient.
    - Source date must be on/after the current patch's release date when known.

    Any missing identity (on the record or the row), a KB that matches the wrong train,
    or an identity that no longer matches the record's current target (stale after a
    KB/build rollover) is excluded — never counted.
    """
    target = target or {}
    target_build = str(target.get("target_os_build") or "").strip()
    target_kb = str(target.get("target_kb") or "").strip()
    target_feature = str(target.get("target_feature_version") or target.get("update_version") or "").strip()
    target_release_date = str(target.get("target_release_date") or "").strip()

    matched_build = str(row.get("matched_os_build") or "").strip()
    matched_kb = str(row.get("matched_kb") or "").strip()
    matched_feature = str(row.get("matched_feature_version") or "").strip()

    # Fail closed: the record must expose a current-patch identity to gate against.
    if not target_build and not target_kb:
        return False, "windows_record_missing_target_identity"
    # Fail closed: the row must carry a proven KB/build identity ("latest update",
    # date-only, and generic reports never populate these).
    if not matched_build and not matched_kb:
        return False, "missing_kb_or_build"

    build_ok = bool(target_build and matched_build == target_build)
    kb_ok = bool(
        target_kb and matched_kb == target_kb
        and target_feature and matched_feature == target_feature
    )
    if not (build_ok or kb_ok):
        if matched_kb and matched_kb == target_kb and matched_feature and matched_feature != target_feature:
            return False, "wrong_feature_train_for_kb"
        return False, "stale_due_to_patch_rollover"

    if target_release_date and source_date_passes(str(row.get("source_date") or ""), target_release_date) is False:
        return False, "source_date_before_target_release_date"

    return True, None
