#!/usr/bin/env python3
"""Public-safe structured ownership reason codes.

Production run 30945433808 failed four collectors with only `ownership_violation:OwnershipViolation` --
safe publicly but insufficient operationally (the exact rule could not be recovered). This adds a
structured, public-safe reason code to every OwnershipViolation and surfaces it via
normalize_failure_reason, WITHOUT changing any ownership predicate. These tests prove each rule maps to
its code, the surfaced reason is public-safe (no path/url/token/exception), and normalize emits it.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_ownership_reason_codes.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import collector_ownership as o  # noqa: E402
from patch_collectors.base import write_front_matter_and_body  # noqa: E402
import run_patch_evidence_collection as runner  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def expect_code(label: str, fn, code: str) -> None:
    try:
        fn()
        check(label, False, "no OwnershipViolation raised")
    except o.OwnershipViolation as e:
        pr = e.public_reason()
        leak = any(b in pr for b in ("http://", "https://", ".md", "Traceback", "\\", "/updates/"))
        norm = runner.normalize_failure_reason(e)
        check(f"{label}: code={code}", e.code == code, f"got {e.code!r}")
        check(f"{label}: public_reason safe", (not leak) and pr.startswith(f"code={code}"), pr)
        check(f"{label}: normalize -> ownership_violation:{code}", norm == f"ownership_violation:{code}", norm)


def ev(before_rows, after_rows) -> tuple[str, str]:
    import yaml
    b = yaml.safe_dump({"schema_version": 1, "evidence": before_rows}, sort_keys=False)
    a = yaml.safe_dump({"schema_version": 1, "evidence": after_rows}, sort_keys=False)
    return b, a


def erow(rid, pid="obs-studio", ver="1", url="http://x/1", st="github_issue", matched=True, counted=True):
    r = {"id": rid, "product_id": pid, "update_version": ver, "source_url": url, "source_type": st,
         "patch_version_matched": matched, "counted": counted, "sentiment": "negative"}
    return r


def run() -> int:
    o._existing_versions = lambda pid: {"1"}  # deterministic version resolution
    print("=" * 66)
    print("Ownership structured reason codes")
    print("=" * 66)

    # --- validate_method_health ---
    expect_code("mh product mismatch", lambda: o.validate_method_health("obs-studio", [{"product_id": "x", "method_id": "github_issues", "update_version": "1", "status": "success"}]), "method_health_product_mismatch")
    expect_code("mh method not allowed", lambda: o.validate_method_health("obs-studio", [{"product_id": "obs-studio", "method_id": "reddit_search", "update_version": "1", "status": "success"}]), "method_not_allowed")
    expect_code("mh version unresolved", lambda: o.validate_method_health("obs-studio", [{"product_id": "obs-studio", "method_id": "github_issues", "update_version": "9.9", "status": "success"}]), "method_health_version_unresolved")
    expect_code("mh noncanonical status", lambda: o.validate_method_health("obs-studio", [{"product_id": "obs-studio", "method_id": "github_issues", "update_version": "1", "status": "totally_made_up"}]), "method_health_noncanonical_status")

    # --- validate_evidence ---
    expect_code("ev existing modified", lambda: o.validate_evidence("obs-studio", *ev([erow("k", counted=True)], [dict(erow("k"), sentiment="TAMPER")])), "evidence_existing_row_modified")
    expect_code("ev existing deleted", lambda: o.validate_evidence("obs-studio", *ev([erow("k")], [])), "evidence_existing_row_deleted")
    expect_code("ev product mismatch", lambda: o.validate_evidence("obs-studio", *ev([], [erow("n", pid="adobe-premiere-pro")])), "evidence_product_mismatch")
    expect_code("ev version unresolved", lambda: o.validate_evidence("obs-studio", *ev([], [erow("n", ver="9.9")])), "evidence_version_unresolved")
    expect_code("ev unauthorized source", lambda: o.validate_evidence("obs-studio", *ev([], [erow("n", st="reddit_community_report")])), "evidence_unauthorized_source")
    expect_code("ev duplicate url", lambda: o.validate_evidence("obs-studio", *ev([erow("a", url="http://dup")], [erow("a", url="http://dup"), erow("b", url="http://dup")])), "evidence_duplicate_url")

    # --- validate_records ---
    gen = Path(tempfile.mkdtemp(prefix="rc-")) / "gen"
    gen.mkdir()
    cross = gen / "cross.md"
    write_front_matter_and_body(cross, {"update_entry": True, "product_id": "adobe-premiere-pro", "update_version": "1", "permalink": "/updates/adobe/adobe-premiere-pro/1/"}, "b\n")
    expect_code("rec product mismatch", lambda: o.validate_records("obs-studio", gen, {cross}, lambda p: None), "record_product_mismatch")
    badperm = gen / "badperm.md"
    write_front_matter_and_body(badperm, {"update_entry": True, "product_id": "obs-studio", "update_version": "1", "permalink": "/updates/x/y/1/"}, "b\n")
    expect_code("rec permalink mismatch", lambda: o.validate_records("obs-studio", gen, {badperm}, lambda p: None), "record_permalink_mismatch")
    unresolved = gen / "unres.md"
    write_front_matter_and_body(unresolved, {"update_entry": True, "product_id": "obs-studio", "update_version": "9.9", "permalink": "/updates/x/obs-studio/9-9/"}, "b\n")
    expect_code("rec version unresolved", lambda: o.validate_records("obs-studio", gen, {unresolved}, lambda p: None), "record_version_unresolved")
    deleted = gen / "gone.md"  # never created -> deletion
    expect_code("rec undeclared deletion", lambda: o.validate_records("obs-studio", gen, {deleted}, lambda p: None), "undeclared_deletion")

    # --- non-ownership normalize unchanged; legit input still accepted ---
    check("non-ownership normalize unchanged", runner.normalize_failure_reason(ValueError("x")) == "collector_error:ValueError")
    try:
        o.validate_method_health("obs-studio", [{"product_id": "obs-studio", "method_id": "github_issues", "update_version": "1", "status": "success"}])
        check("legit method-health still accepted", True)
    except o.OwnershipViolation as e:
        check("legit method-health still accepted", False, e.public_reason())

    print()
    print("=" * 66)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 66)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
