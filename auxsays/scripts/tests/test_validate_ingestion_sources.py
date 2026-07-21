#!/usr/bin/env python3
"""Tests for ingestion-source config validation of the record/scan window contract.

`validate_ingestion_sources._validate_entry` guards `ingestion.scan_limit` (and the
`ingestion.record_limit` it is checked against) so that a misconfigured candidate
scan window fails CI fail-closed rather than silently broadening network activity:
  - scan_limit must be a positive integer,
  - at least record_limit (the per-run write budget it must cover),
  - at most SEEN_RETENTION (so the seen ledger always covers the active window).
No network or filesystem writes: the validator is pure over an in-memory dict, and
the real config is read-only.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import validate_ingestion_sources as vis

_CONFIG = _REPO / "auxsays" / "_data" / "patch_ingestion_sources.yml"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def base(**ingestion_extra: object) -> dict[str, object]:
    ingestion: dict[str, object] = {
        "adapter": "elgato_help_center",
        "type": "help_center_release_notes",
        "official_url": "https://help.elgato.com/hc/en-us/sections/1-Example-Release-Notes",
    }
    ingestion.update(ingestion_extra)
    return {"company_id": "elgato", "product_id": "elgato-example", "enabled": True, "ingestion": ingestion}


def entry_errors(source: dict[str, object]) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    vis._validate_entry(errors, warnings, source)
    return errors


def scan_errors(source: dict[str, object]) -> list[str]:
    return [e for e in entry_errors(source) if "scan_limit" in e]


def record_errors(source: dict[str, object]) -> list[str]:
    return [e for e in entry_errors(source) if "record_limit" in e]


def run() -> int:
    print("=" * 60)
    print("validate_ingestion_sources scan_limit contract tests")
    print("=" * 60)

    retention = vis.SEEN_RETENTION

    # --- baseline: a clean source produces no errors at all ------------------
    check("baseline source (no scan_limit) has no validation errors", entry_errors(base()) == [], str(entry_errors(base())))

    # --- valid scan_limit values ---------------------------------------------
    check("scan_limit absent is valid (default backfill window applies)", scan_errors(base()) == [])
    check("scan_limit=8 is valid", scan_errors(base(scan_limit=8)) == [], str(scan_errors(base(scan_limit=8))))
    check("scan_limit == record_limit is valid", scan_errors(base(scan_limit=2, record_limit=2)) == [], str(scan_errors(base(scan_limit=2, record_limit=2))))
    check("scan_limit == SEEN_RETENTION upper bound is valid", scan_errors(base(scan_limit=retention)) == [], str(scan_errors(base(scan_limit=retention))))

    # --- invalid scan_limit values must be REJECTED (fail-closed) ------------
    check("scan_limit above SEEN_RETENTION is rejected", scan_errors(base(scan_limit=retention + 1)) != [], "expected an error")
    check("scan_limit zero is rejected", scan_errors(base(scan_limit=0)) != [])
    check("scan_limit negative is rejected", scan_errors(base(scan_limit=-4)) != [])
    check("scan_limit non-integer string is rejected", scan_errors(base(scan_limit="lots")) != [])
    check("scan_limit float is rejected (must be an integer)", scan_errors(base(scan_limit=8.5)) != [])
    check("scan_limit boolean is rejected (bool is not an accepted integer)", scan_errors(base(scan_limit=True)) != [])
    check("scan_limit below record_limit is rejected", scan_errors(base(scan_limit=3, record_limit=6)) != [], "3 < 6 must error")

    # --- record_limit sanity (needed for the scan_limit >= record_limit check) ---
    check("record_limit zero is rejected", record_errors(base(record_limit=0)) != [])
    check("record_limit non-integer is rejected", record_errors(base(record_limit="six")) != [])
    check("record_limit boolean is rejected", record_errors(base(record_limit=True)) != [])
    check("valid record_limit alone produces no error", record_errors(base(record_limit=6)) == [], str(record_errors(base(record_limit=6))))

    # --- integration: the real, shipped config still validates cleanly -------
    check("real patch_ingestion_sources.yml passes full validation (exit 0)", vis.validate(_CONFIG) == 0)

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
