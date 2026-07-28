#!/usr/bin/env python3
"""Lock test: evidence method-health rejects duplicate (product_id, update_version, method_id).

The monitoring-status model trusts EMH as clean source data -- duplicate health rows for the same
exact patch+method are invalid and must be rejected upstream, so counting logic can never double-count
or read an ambiguous status. validate_evidence_method_health.py already enforces this with
string-normalized keys; this pins that behaviour, including the numeric-vs-quoted version case that the
Liquid join also normalizes.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_evidence_method_health_dupes.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
VALIDATOR = _AUX / "scripts" / "validate_evidence_method_health.py"

_ROW = (
    "- product_id: test-product\n"
    "  update_version: {ver}\n"
    "  method_id: {mid}\n"
    "  source_type: reddit\n"
    "  status: {status}\n"
    "  last_run: '{run}'\n"
)


def _payload(rows: str) -> str:
    return "schema_version: 1\nmethods:\n" + rows


DUP = _payload(
    _ROW.format(ver="'1.0'", mid="reddit_search", status="success", run="2026-07-01T00:00:00Z")
    + _ROW.format(ver="'1.0'", mid="reddit_search", status="blocked", run="2026-07-02T00:00:00Z")
)
# Same product+method, version once numeric (2607) and once quoted ('2607'): the validator
# string-normalizes keys, so this MUST also be caught as a duplicate.
DUP_NUMERIC = _payload(
    _ROW.format(ver="2607", mid="web_search", status="success", run="2026-07-01T00:00:00Z")
    + _ROW.format(ver="'2607'", mid="web_search", status="no_results", run="2026-07-02T00:00:00Z")
)
OK = _payload(
    _ROW.format(ver="'1.0'", mid="reddit_search", status="success", run="2026-07-01T00:00:00Z")
    + _ROW.format(ver="'1.0'", mid="web_search", status="no_results", run="2026-07-02T00:00:00Z")
)

_PASS = 0
_FAIL = 0
_SKIP = False


def _run_validator(payload: str):
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8") as fh:
        fh.write(payload)
        tmp = fh.name
    try:
        proc = subprocess.run([sys.executable, str(VALIDATOR), tmp],
                              capture_output=True, text=True)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


def run() -> int:
    global _SKIP
    print("=" * 60)
    print("Evidence method-health duplicate-rejection tests")
    print("=" * 60)

    rc, out = _run_validator(DUP)
    if "PyYAML is required" in out:
        print("  SKIP  PyYAML unavailable in this interpreter; validator not exercised.")
        _SKIP = True
        return 0

    check("duplicate (product_id, version, method_id) is rejected (exit != 0)", rc != 0, out.strip())
    check("rejection names the duplicate key", "duplicate key" in out, out.strip())

    rc_num, out_num = _run_validator(DUP_NUMERIC)
    check("numeric 2607 and quoted '2607' collide as the same key (string-normalized)",
          rc_num != 0 and "duplicate key" in out_num, out_num.strip())

    rc_ok, out_ok = _run_validator(OK)
    check("distinct method_ids for the same patch validate cleanly (exit 0)", rc_ok == 0, out_ok.strip())

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
