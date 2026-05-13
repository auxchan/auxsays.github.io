#!/usr/bin/env python3
"""Promote repo-owned DaVinci verification fixtures into consensus evidence.

This is a bridge, not the final discovery system. It only promotes structured
verification rows that already live in the repo and pass the same deterministic
DaVinci evidence gates. Chat-only claims and incomplete calibration examples
are reported as missing-field blockers and are not written.
"""
from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
FIXTURE_PATH = SCRIPT_DIR / "tests" / "fixtures" / "davinci_verified_reports.yml"

REQUIRED_STRUCTURED_FIELDS = (
    "product_id",
    "update_version",
    "source_type",
    "source_name",
    "source_url",
    "thread_title",
    "report_title",
    "report_text_excerpt",
    "source_date",
    "target_release_date",
    "match_basis_expected",
    "concrete_issue_basis",
    "date_gate_basis",
    "counted",
    "source_weight",
    "verification_source",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or promote DaVinci verified report fixtures.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate fixtures without writing evidence.")
    mode.add_argument("--write", action="store_true", help="Append promotable rows and run DaVinci consensus writeback.")
    parser.add_argument("--fixture", default=str(FIXTURE_PATH), help="Fixture path to validate/promote.")
    return parser.parse_args(argv)


def ensure_imports(write: bool) -> None:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import yaml  # noqa: F401
    except Exception as exc:
        if write:
            raise SystemExit(f"PyYAML is required for --write promotion: {type(exc).__name__}: {exc}") from exc
        sys.modules.setdefault(
            "yaml",
            types.SimpleNamespace(safe_load=lambda *_args, **_kwargs: {}, safe_dump=lambda *_args, **_kwargs: ""),
        )


def load_fixture_reports(path: Path) -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.startswith("  - "):
            if current:
                reports.append(current)
            current = {}
            key, value = line[4:].split(":", 1)
            current[key.strip()] = clean_value(value)
        elif current is not None and line.startswith("    ") and ":" in line:
            key, value = line.strip().split(":", 1)
            current[key.strip()] = clean_value(value)
    if current:
        reports.append(current)
    return reports


def clean_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if value.lower() == "true":
        return "true"
    if value.lower() == "false":
        return "false"
    return value


def candidate_from_fixture(report: dict[str, str]) -> dict[str, str]:
    return {
        "source_type": report.get("source_type", ""),
        "source_name": report.get("source_name", ""),
        "source_url": report.get("source_url", ""),
        "parent_title": report.get("thread_title", ""),
        "report_title": report.get("report_title", ""),
        "report_text": report.get("report_text_excerpt", ""),
        "source_date": report.get("source_date", ""),
    }


def record_from_fixture(report: dict[str, str]) -> Any:
    from patch_collectors.base import PatchRecord

    return PatchRecord(
        product_id=report.get("product_id", ""),
        update_version=report.get("update_version", ""),
        path=ROOT / "updates" / "generated" / "2026-04-14-davinci-resolve-21-public-beta-1.md",
        update_published_at=report.get("target_release_date", ""),
        update_status="current",
        update_product="DaVinci Resolve",
    )


def missing_fields(report: dict[str, str]) -> list[str]:
    missing = [field for field in REQUIRED_STRUCTURED_FIELDS if not str(report.get(field, "")).strip()]
    if report.get("product_id") != "blackmagic-davinci":
        missing.append("exact_product_id_blackmagic-davinci")
    if report.get("update_version") != "21 Public Beta 1":
        missing.append("exact_update_version_21_public_beta_1")
    if report.get("promotion_ready") != "true":
        missing.append("promotion_ready_true")
    if report.get("verification_source") != "taylor_phase_1g_1h_manual_verification":
        missing.append("verification_source_taylor_phase_1g_1h_manual_verification")
    if report.get("counted") != "true":
        missing.append("counted_true")
    if report.get("source_weight") != "1":
        missing.append("source_weight_1")
    return missing


def evidence_id(report: dict[str, str]) -> str:
    source_url = report.get("source_url", "")
    thread_id = source_url.rsplit("t=", 1)[-1].split("&", 1)[0]
    return f"blackmagic-davinci-21-public-beta-1-bmd-forum-t{thread_id}-verified-calibration"


def validation_report(report: dict[str, str], row: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    promotable = not missing and row.get("counted") is True and row.get("source_weight") == 1
    return {
        "id": report.get("id", ""),
        "source_url": report.get("source_url", ""),
        "product_id": report.get("product_id", ""),
        "update_version": report.get("update_version", ""),
        "has_structured_title_text_date_version": all(
            report.get(field) for field in ("thread_title", "report_title", "report_text_excerpt", "source_date", "update_version")
        ),
        "gate_counted": row.get("counted") is True,
        "gate_exclusion_reason": row.get("exclusion_reason"),
        "match_basis": row.get("match_basis"),
        "source_date_pass": row.get("source_date_pass"),
        "source_weight": row.get("source_weight"),
        "verification_source": report.get("verification_source", ""),
        "promotion_ready": report.get("promotion_ready") == "true",
        "promotion_blocker": report.get("promotion_blocker", ""),
        "missing_fields": missing,
        "promotable": promotable,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_imports(write=bool(args.write))

    from patch_collectors.base import append_evidence_rows, utc_now
    from patch_collectors.davinci import apply_consensus_writeback, row_from_candidate

    fixture_path = Path(args.fixture)
    captured_at = utc_now()
    reports = load_fixture_reports(fixture_path)
    rows: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []

    for report in reports:
        row = row_from_candidate(record_from_fixture(report), candidate_from_fixture(report), captured_at)
        row["id"] = evidence_id(report)
        missing = missing_fields(report)
        validation = validation_report(report, row, missing)
        validations.append(validation)
        if validation["promotable"]:
            rows.append(row)

    added = 0
    total = 0
    record_updated = False
    if args.write and rows:
        added, total, _existing = append_evidence_rows(rows)
        if added:
            record_updated = apply_consensus_writeback("21 Public Beta 1")

    payload = {
        "mode": "write" if args.write else "dry-run",
        "fixture": str(fixture_path),
        "reports_reviewed": len(reports),
        "promotable_count": len(rows),
        "evidence_rows_added": added,
        "evidence_rows_total": total,
        "davinci_record_updated": record_updated,
        "reports": validations,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if rows or not args.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
