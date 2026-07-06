#!/usr/bin/env python3
"""Tests for per-source record-limit resolution in patch_ingest.

`patch_ingest.resolve_record_limit` lets a single source cap its own adapter
output via `ingestion.record_limit`, while every other source keeps the global
`--limit` default. These tests prove:
  - a per-source `record_limit` overrides the global limit,
  - its absence falls back to the global limit,
  - invalid / non-positive values fall back to the global limit,
  - against the real config: only microsoft-windows-11 overrides (to 6), while
    microsoft-365-apps and microsoft-teams fall back to the global default.
No network or filesystem writes: the helper is pure, and the config is read-only.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import yaml

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import patch_ingest

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


def args(limit: int = 2) -> SimpleNamespace:
    # Minimal stand-in for the argparse.Namespace used by patch_ingest.
    return SimpleNamespace(limit=limit)


def src(record_limit: object = "__absent__") -> dict[str, object]:
    ingestion: dict[str, object] = {"adapter": "x"}
    if record_limit != "__absent__":
        ingestion["record_limit"] = record_limit
    return {"product_id": "p", "ingestion": ingestion}


def load_config_source(product_id: str) -> dict[str, object]:
    rows = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    return next(r for r in rows if r.get("product_id") == product_id)


def run() -> int:
    print("=" * 60)
    print("patch_ingest per-source record_limit tests")
    print("=" * 60)

    resolve = patch_ingest.resolve_record_limit

    # --- helper semantics ----------------------------------------------------
    check("per-source record_limit overrides the global limit (6 > 2)", resolve(src(6), args(2)) == 6, str(resolve(src(6), args(2))))
    check("global default applies when record_limit is absent", resolve(src(), args(2)) == 2, str(resolve(src(), args(2))))
    check("global default applies when record_limit is null/None", resolve(src(None), args(2)) == 2, str(resolve(src(None), args(2))))
    check("record_limit can also lower below the global (1 < 2)", resolve(src(1), args(2)) == 1, str(resolve(src(1), args(2))))
    check("string-numeric record_limit is coerced to int", resolve(src("6"), args(2)) == 6, str(resolve(src("6"), args(2))))
    check("non-numeric record_limit falls back to the global limit", resolve(src("lots"), args(2)) == 2, str(resolve(src("lots"), args(2))))
    check("zero record_limit falls back to the global limit", resolve(src(0), args(2)) == 2, str(resolve(src(0), args(2))))
    check("negative record_limit falls back to the global limit", resolve(src(-3), args(2)) == 2, str(resolve(src(-3), args(2))))
    check("missing ingestion block falls back to the global limit", resolve({"product_id": "p"}, args(2)) == 2, "no ingestion key")
    check("override is honored regardless of the global default value", resolve(src(6), args(5)) == 6 and resolve(src(), args(5)) == 5, "global=5")

    # --- against the real config --------------------------------------------
    win = load_config_source("microsoft-windows-11")
    check("config: microsoft-windows-11 declares record_limit: 6", (win.get("ingestion") or {}).get("record_limit") == 6, str((win.get("ingestion") or {}).get("record_limit")))
    check("config: windows-11 resolves to 6 even with global --limit 2", resolve(win, args(2)) == 6, str(resolve(win, args(2))))

    m365 = load_config_source("microsoft-365-apps")
    check("config: microsoft-365-apps has NO record_limit (regression guard)", "record_limit" not in (m365.get("ingestion") or {}), str((m365.get("ingestion") or {}).get("record_limit")))
    check("config: microsoft-365-apps falls back to global limit (2)", resolve(m365, args(2)) == 2, str(resolve(m365, args(2))))

    teams = load_config_source("microsoft-teams")
    check("config: microsoft-teams has NO record_limit (regression guard)", "record_limit" not in (teams.get("ingestion") or {}), str((teams.get("ingestion") or {}).get("record_limit")))
    check("config: microsoft-teams falls back to global limit (2)", resolve(teams, args(2)) == 2, str(resolve(teams, args(2))))

    # --- no other source unexpectedly grew a record_limit -------------------
    rows = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    with_override = [r.get("product_id") for r in rows if isinstance(r.get("ingestion"), dict) and "record_limit" in r["ingestion"]]
    check("only microsoft-windows-11 sets a record_limit in the whole config", with_override == ["microsoft-windows-11"], str(with_override))

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
