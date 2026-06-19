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

DEFAULT_PATH = Path("auxsays/_data/evidence_method_health.yml")

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


def validate(path: Path = DEFAULT_PATH) -> int:
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
    seen_keys: dict[tuple[str, str, str], int] = {}

    for row_index, row in enumerate(methods, start=1):
        if not isinstance(row, dict):
            _add_error(errors, row_index, "row", "must be a mapping")
            continue

        for field in REQUIRED_FIELDS:
            value = row.get(field)
            if value in (None, ""):
                _add_error(errors, row_index, field, "is required")

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

        key = (
            str(row.get("product_id") or "").strip(),
            str(row.get("update_version") or "").strip(),
            str(row.get("method_id") or "").strip(),
        )
        if all(key):
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

    if errors:
        print(f"Evidence method-health validation failed: {len(errors)} error(s).")
        for error in errors:
            print(error)
        return 1

    counts = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
    print(f"Evidence method-health validation passed: {len(methods)} method rows checked.")
    print(f"Status counts: {counts if counts else 'none'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AUXSAYS evidence method-health telemetry.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    return validate(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
