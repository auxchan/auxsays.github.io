#!/usr/bin/env python3
"""Validate AUXSAYS evidence method-health telemetry.

This validator is read-only. Method-health rows describe collector execution
attempts; they are not accepted evidence, verdicts, or consensus state.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    print(
        "PyYAML is required. Install dependencies with:\n"
        ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.patch_identity import BUILD_AWARE_PRODUCTS  # noqa: E402
# Stdlib only, so it is as safe for this bare script as `lib.patch_identity` above.
from lib.reddit_access_policy import is_policy_disabled_row  # noqa: E402
# The method registry: stdlib-only literals, so it is as safe to import here as the two above.
from lib import acquisition_methods as registry  # noqa: E402

DEFAULT_PATH = Path("auxsays/_data/evidence_method_health.yml")
CANONICAL_PATH = Path(__file__).resolve().parents[1] / "_data" / "evidence_method_health.yml"

# Optional measured-history fields (patch_collectors.base.METHOD_HEALTH_HISTORY_FIELDS). Absent means
# not measured; present must be well-formed.
HISTORY_COUNTER_FIELDS = ("attempts", "consecutive_failures", "consecutive_zero_accept_runs",
                          "duration_ms", "requests")
HISTORY_TIME_FIELDS = ("last_good_at", "last_accepted_at")
PROBE_RESULTS = ("recovered", "still_refused", "inconclusive")
PROBE_COUNTER_FIELDS = ("consecutive_refusals", "requests", "total_requests", "http_status")
PROBE_TIME_FIELDS = ("probed_at", "next_probe_after")
# An ACTIVE method that keeps finding candidates and accepting none is a recall/precision review
# item. It is a WARNING, never an error: low yield is a fact about a source, not a broken file.
ZERO_ACCEPT_WARNING_RUNS = 20
# Ids that may write a health row without being a scheduled reporter (an operator's manual tool).
MANUAL_HEALTH_WRITERS = frozenset({"local_playwright_capture_promotion"})

REQUIRED_FIELDS = (
    "product_id",
    "update_version",
    "method_id",
    "source_type",
    "status",
    "last_run",
)

COUNTER_FIELDS = (
    "candidates_found",
    "accepted_candidates",
    "duplicate_existing_evidence",
    "evidence_rows_added",
    "public_counted_reports",
    "accepted_reports",
    "rejected_reports",
)

ALLOWED_STATUSES = {
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

TIMESTAMP_LIKE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:[T\s]\d{2}:\d{2}(?::\d{2})?"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)


def _label(row_index: int | None, field: str) -> str:
    if row_index is None:
        return f"field {field}"
    return f"row {row_index} field {field}"


def _add_error(errors: list[str], row_index: int | None, field: str, message: str) -> None:
    errors.append(f"FAIL {_label(row_index, field)}: {message}")


def _load_payload(path: Path, errors: list[str]) -> Any:
    if not path.exists():
        _add_error(errors, None, str(path), "file does not exist")
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        _add_error(errors, None, str(path), f"invalid YAML: {exc}")
        return None


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_timestamp_like(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(TIMESTAMP_LIKE.match(text))


def _validate_counter(
    errors: list[str],
    *,
    row_index: int,
    row: dict[str, Any],
    field: str,
) -> None:
    if field not in row or row.get(field) in (None, ""):
        return
    if not _is_nonnegative_int(row.get(field)):
        _add_error(errors, row_index, field, "must be a nonnegative integer")


def _present_counter(row: dict[str, Any], field: str) -> int | None:
    value = row.get(field)
    if _is_nonnegative_int(value):
        return value
    return None


def _validate_counter_relationships(errors: list[str], *, row_index: int, row: dict[str, Any]) -> None:
    candidates = _present_counter(row, "candidates_found")
    accepted = _present_counter(row, "accepted_candidates")
    evidence_added = _present_counter(row, "evidence_rows_added")
    public_counted = _present_counter(row, "public_counted_reports")
    accepted_reports = _present_counter(row, "accepted_reports")

    if candidates is not None and accepted is not None and accepted > candidates:
        _add_error(
            errors,
            row_index,
            "accepted_candidates",
            "cannot exceed candidates_found",
        )
    if accepted is not None and evidence_added is not None and evidence_added > accepted:
        _add_error(
            errors,
            row_index,
            "evidence_rows_added",
            "cannot exceed accepted_candidates",
        )
    if accepted_reports is not None and public_counted is not None and public_counted > accepted_reports:
        _add_error(
            errors,
            row_index,
            "public_counted_reports",
            "cannot exceed accepted_reports",
        )


def _validate_history(errors: list[str], *, row_index: int, row: dict[str, Any]) -> None:
    for field in HISTORY_COUNTER_FIELDS:
        _validate_counter(errors, row_index=row_index, row=row, field=field)
    for field in HISTORY_TIME_FIELDS:
        value = row.get(field)
        if value not in (None, "") and not _is_timestamp_like(value):
            _add_error(errors, row_index, field, f"must look like a timestamp, got {value!r}")
    reasons = row.get("rejection_reasons")
    if reasons in (None, ""):
        return
    if not isinstance(reasons, dict):
        _add_error(errors, row_index, "rejection_reasons", "must be a mapping of exclusion code to count")
        return
    for code, count in reasons.items():
        if not isinstance(code, str) or not code.strip() or len(code) > 120:
            _add_error(errors, row_index, "rejection_reasons", f"invalid exclusion code {code!r}")
        if not _is_nonnegative_int(count) or count == 0:
            _add_error(errors, row_index, "rejection_reasons", f"count for {code!r} must be a positive integer")
    rejected = _present_counter(row, "rejected_reports")
    total = sum(c for c in reasons.values() if _is_nonnegative_int(c))
    if rejected is not None and total > rejected:
        _add_error(errors, row_index, "rejection_reasons",
                   f"counts sum to {total}, more than rejected_reports {rejected}")


def _validate_probes(errors: list[str], probes: Any, *, check_registry: bool) -> int:
    """The re-probe section: one record per (product, method). Never evidence, never a method row."""
    if probes in (None, ""):
        return 0
    if not isinstance(probes, list):
        _add_error(errors, None, "probes", "must be a list")
        return 0
    seen: set[tuple[str, str]] = set()
    for index, probe in enumerate(probes, start=1):
        label = f"probes[{index}]"
        if not isinstance(probe, dict):
            _add_error(errors, None, label, "must be a mapping")
            continue
        key = (str(probe.get("product_id") or "").strip(), str(probe.get("method_id") or "").strip())
        if not all(key):
            _add_error(errors, None, label, "product_id and method_id are required")
        elif key in seen:
            _add_error(errors, None, label, f"duplicate probe record {key!r}")
        seen.add(key)
        if probe.get("result") not in PROBE_RESULTS:
            _add_error(errors, None, label, f"unknown result {probe.get('result')!r}")
        for field in PROBE_TIME_FIELDS:
            if not _is_timestamp_like(probe.get(field)):
                _add_error(errors, None, label, f"{field} must look like a timestamp")
        for field in PROBE_COUNTER_FIELDS:
            if probe.get(field) not in (None, "") and not _is_nonnegative_int(probe.get(field)):
                _add_error(errors, None, label, f"{field} must be a nonnegative integer")
        requests = probe.get("requests")
        if _is_nonnegative_int(requests) and requests > registry.REPROBE_MAX_REQUESTS_PER_METHOD:
            _add_error(errors, None, label,
                       f"a probe made {requests} requests; the cap is {registry.REPROBE_MAX_REQUESTS_PER_METHOD}")
        if check_registry and key[1]:
            refusal = registry.reprobe_refusal(key[1])
            if refusal:
                # A probe record for a source the owner or its terms closed must not exist.
                _add_error(errors, None, label, f"method {key[1]!r} may not be re-probed ({refusal})")
    return len(probes)


def validate(path: Path = DEFAULT_PATH, *, check_registry: bool | None = None) -> int:
    # REGISTRY JOIN. For the canonical file every row's method_id must be a registry entry that
    # reports to method health. It is on for the canonical file and off for any other path, so a
    # fixture may use made-up ids; pass check_registry explicitly to override either way.
    if check_registry is None:
        try:
            check_registry = Path(path).resolve() == CANONICAL_PATH
        except OSError:
            check_registry = False
    known_methods = registry.HEALTH_REPORTING_METHODS | MANUAL_HEALTH_WRITERS
    active_methods = {m["method_id"] for m in registry.METHODS if m["status"] == "active"}
    warnings: list[str] = []
    errors: list[str] = []
    payload = _load_payload(path, errors)
    if errors:
        for error in errors:
            print(error)
        return 1

    if not isinstance(payload, dict):
        _add_error(errors, None, "root", "must be a mapping")
    elif "schema_version" not in payload:
        _add_error(errors, None, "schema_version", "is required")

    methods = payload.get("methods") if isinstance(payload, dict) else None
    if not isinstance(methods, list):
        _add_error(errors, None, "methods", "must be a list")
        methods = []

    status_counts: Counter[str] = Counter()
    seen_keys: dict[tuple[str, str, str, str], int] = {}

    for row_index, row in enumerate(methods, start=1):
        if not isinstance(row, dict):
            _add_error(errors, row_index, "row", "must be a mapping")
            continue

        for field in REQUIRED_FIELDS:
            value = row.get(field)
            if value in (None, ""):
                if field == "last_run" and is_policy_disabled_row(row):
                    # A row switched off by ACCESS POLICY (status `disabled` + reason
                    # `reddit_access_policy_unauthorised`) made no attempt, so it has no run time
                    # to record. For a key that already exists the writer keeps the prior row's
                    # real last attempt; a NEW patch has no prior row, so its policy row is stored
                    # with an empty last_run. Stamping a time there would claim an attempt that
                    # never happened. Every other row still needs last_run, and a non-empty value
                    # on a policy row is still checked below.
                    continue
                _add_error(errors, row_index, field, "is required")

        # A BUILD-AWARE PRODUCT'S TELEMETRY MUST NAME ITS BUILD, for the same reason its counted
        # evidence must (`patch_collectors.base.append_evidence_rows` -> `require_build`): a row
        # keyed (product, "25H2", "") belongs to no patch, because every record of a build-aware
        # product carries a build. Four such rows survived the Windows build-aware migration --
        # frozen at 2026-09-04T17:30Z, one of them reading `success` with 4 accepted reports for
        # an identity that owns zero counted rows -- and the public methodology audit table
        # renders every method row, so that number was live. Nothing can write the shape again;
        # this rung is what keeps it that way.
        if str(row.get("product_id") or "").strip() in BUILD_AWARE_PRODUCTS \
                and not str(row.get("target_build") or "").strip():
            _add_error(errors, row_index, "target_build",
                       f"is required for build-aware product "
                       f"{str(row.get('product_id') or '')!r}")

        status = str(row.get("status") or "").strip()
        if status:
            if status not in ALLOWED_STATUSES:
                _add_error(errors, row_index, "status", f"unknown status {status!r}")
            else:
                status_counts[status] += 1

        last_run = row.get("last_run")
        if last_run not in (None, "") and not _is_timestamp_like(last_run):
            _add_error(errors, row_index, "last_run", f"must look like a timestamp, got {last_run!r}")

        for field in COUNTER_FIELDS:
            _validate_counter(errors, row_index=row_index, row=row, field=field)
        _validate_counter_relationships(errors, row_index=row_index, row=row)
        _validate_history(errors, row_index=row_index, row=row)

        method_id = str(row.get("method_id") or "").strip()
        if check_registry and method_id and method_id not in known_methods:
            _add_error(errors, row_index, "method_id",
                       f"{method_id!r} is not a health-reporting method in lib/acquisition_methods.py; "
                       f"catalogue it before it writes telemetry")
        zero_runs = row.get("consecutive_zero_accept_runs")
        if (method_id in active_methods and _is_nonnegative_int(zero_runs)
                and zero_runs >= ZERO_ACCEPT_WARNING_RUNS and (_present_counter(row, "candidates_found") or 0) > 0):
            warnings.append(f"WARN row {row_index}: active method {method_id!r} accepted nothing in "
                            f"{zero_runs} consecutive runs while still finding candidates "
                            f"({row.get('product_id')} {row.get('update_version')})")

        # Duplicate detection must use the CANONICAL health identity, which includes the exact
        # build for a build-aware product. Keyed on (product, version, method) alone, two
        # legitimate PowerPoint rows -- 2603/build-A and 2603/build-B -- would be rejected as a
        # duplicate. The build slot is empty for every other product, so their duplicate
        # detection is unchanged.
        key = (
            str(row.get("product_id") or "").strip(),
            str(row.get("update_version") or "").strip(),
            str(row.get("target_build") or "").strip(),
            str(row.get("method_id") or "").strip(),
        )
        # product / version / method are required; the build slot is legitimately empty.
        if key[0] and key[1] and key[3]:
            first_row = seen_keys.get(key)
            if first_row is not None:
                _add_error(
                    errors,
                    row_index,
                    "method_id",
                    f"duplicate key {key!r}; first seen on row {first_row}",
                )
            else:
                seen_keys[key] = row_index

    probe_count = _validate_probes(errors, payload.get("probes") if isinstance(payload, dict) else None,
                                   check_registry=bool(check_registry))

    if errors:
        print(f"Evidence method-health validation failed: {len(errors)} error(s).")
        for error in errors:
            print(error)
        return 1

    counts = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
    print(f"Evidence method-health validation passed: {len(methods)} method rows checked.")
    print(f"Status counts: {counts if counts else 'none'}")
    if probe_count:
        print(f"Re-probe records checked: {probe_count}")
    if check_registry:
        print("Registry join: every method_id is a catalogued health-reporting method.")
    if warnings:
        print(f"Low-yield review items: {len(warnings)} (warnings, not errors)")
        for warning in warnings[:20]:
            print(warning)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AUXSAYS evidence method-health telemetry.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    return validate(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
