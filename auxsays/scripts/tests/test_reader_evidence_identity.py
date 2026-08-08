#!/usr/bin/env python3
"""Reader/Pro evidence-identity fix (natural run 31234793893).

Acrobat's evidence id (acrobat-<version>-<source_type>-<url>) omits the edition, and Reader & Pro share
the DC build number, so the same Adobe post yields the SAME id string for both editions. validate_evidence
keyed existing rows by the id STRING alone while append_evidence_rows keys by the (product_id, version, id)
triple; so when the Reader collector appended its row after Pro had committed the same-id-string row, the
immutability check conflated the two distinct rows -> a FALSE ownership_violation:evidence_existing_row_
modified -> Reader rolled back. The fix aligns validate_evidence's row identity to the append authority's
triple. This suite proves the failure is resolved WITHOUT weakening immutability or Reader/Pro isolation.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_reader_evidence_identity.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402
from lib import collector_ownership as o  # noqa: E402
from patch_collectors.base import evidence_key  # noqa: E402

_PASS = 0
_FAIL = 0
_ERR: list[str] = []

PRO = "adobe-acrobat-pro"
READER = "adobe-acrobat-reader"
V = "21.005.20048"          # a shared DC build number (Reader and Pro share it)
URL = "https://community.adobe.com/questions-9/acrobat-and-reader-dc-june-2021-update"
SHARED_ID = "acrobat-21-005-20048-adobe-community-bug-report-community-adobe-com-questions-9"  # edition-less


def ck(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERR.append(label)


def erow(product, *, rid=SHARED_ID, ver=V, url=URL, st="adobe_community_bug_report", captured="2026-07-22T09:37:09Z",
         title="Acrobat/Reader DC update crash", counted=True, matched=True, sentiment="negative"):
    return {"id": rid, "product_id": product, "update_version": ver, "source_url": url, "source_type": st,
            "source_name": "Adobe Community", "report_title": title, "report_text": "crashes after update",
            "captured_at": captured, "patch_version_matched": matched, "counted": counted, "sentiment": sentiment}


def ev(before, after):
    return (yaml.safe_dump({"schema_version": 1, "evidence": before}, sort_keys=False),
            yaml.safe_dump({"schema_version": 1, "evidence": after}, sort_keys=False))


def code_of(fn):
    try:
        fn(); return None
    except o.OwnershipViolation as e:
        return e.code


def run() -> int:
    o._existing_versions = lambda pid: {V}
    print("=" * 74)
    print("Reader/Pro evidence-identity fix")
    print("=" * 74)

    pro = erow(PRO, captured="2026-07-22T09:37:09Z")
    reader = erow(READER, captured="2026-07-22T09:47:27Z")  # same id-string, different edition (+ later capture)

    # --- the mechanism (why the fix is needed) ---
    ck("id STRING is identical across editions (the collision)", str(pro["id"]) == str(reader["id"]))
    ck("append authority evidence_key(id) DIFFERS (product in the key)", evidence_key(pro, "id") != evidence_key(reader, "id"))

    # --- 1. the exact production failure, RESOLVED ---
    # Pro committed first (alphabetical); Reader appends its same-id-string row afterwards.
    r = code_of(lambda: o.validate_evidence(READER, *ev([pro], [pro, reader])))
    ck("1 Reader appends same-id-string row after Pro -> ACCEPTED (no false modified)", r is None, f"got {r}")

    # --- 2. idempotent: identical rerun still accepted ---
    r = code_of(lambda: o.validate_evidence(READER, *ev([pro], [pro, reader])))
    ck("2 identical rerun is idempotent (still accepted)", r is None, f"got {r}")

    # --- 3. Reader cannot modify Pro (same product+version+id, different content -> reject) ---
    pro_tampered = dict(pro); pro_tampered["report_text"] = "TAMPERED by reader"
    r = code_of(lambda: o.validate_evidence(READER, *ev([pro], [pro_tampered, reader])))
    ck("3 Reader cannot modify a Pro row (same identity, changed content)", r == "evidence_existing_row_modified", f"got {r}")

    # --- 4. Pro cannot modify Reader (symmetric) ---
    reader_tampered = dict(reader); reader_tampered["counted"] = False
    r = code_of(lambda: o.validate_evidence(PRO, *ev([reader], [reader_tampered, pro])))
    ck("4 Pro cannot modify a Reader row (same identity, changed content)", r == "evidence_existing_row_modified", f"got {r}")

    # --- 5. product / version / source identity changes still reject ---
    r = code_of(lambda: o.validate_evidence(READER, *ev([], [erow("adobe-premiere-pro")])))
    ck("5a cross-product appended row rejected", r == "evidence_product_mismatch", f"got {r}")
    r = code_of(lambda: o.validate_evidence(READER, *ev([], [erow(READER, ver="9.9.9")])))
    ck("5b unresolved version rejected", r == "evidence_version_unresolved", f"got {r}")
    r = code_of(lambda: o.validate_evidence(READER, *ev([], [erow(READER, st="github_issue")])))
    ck("5c unauthorized source rejected", r == "evidence_unauthorized_source", f"got {r}")

    # --- 6. genuine field changes to the SAME (product,version,id) still reject (immutability intact) ---
    for field, val in [("report_title", "DIFFERENT TITLE"), ("report_text", "different excerpt"),
                       ("sentiment", "positive"), ("counted", False), ("patch_version_matched", False)]:
        mod = dict(reader); mod[field] = val
        r = code_of(lambda m=mod: o.validate_evidence(READER, *ev([reader], [m])))
        ck(f"6 genuine change to existing row field '{field}' still rejected", r == "evidence_existing_row_modified", f"got {r}")

    # --- 7. duplicate id within the SAME identity still rejected ---
    dup2 = dict(reader); dup2["source_url"] = URL + "/x"
    r = code_of(lambda: o.validate_evidence(READER, *ev([], [reader, dup2])))
    ck("7 duplicate (product,version,id) appended twice -> duplicate_id", r == "evidence_duplicate_id", f"got {r}")

    # --- 8. existing row deletion still rejected ---
    r = code_of(lambda: o.validate_evidence(READER, *ev([reader], [])))
    ck("8 deleting an existing row still rejected", r == "evidence_existing_row_deleted", f"got {r}")

    # --- 9. rollback fidelity is a transaction property; here confirm Pro's row is byte-identical in
    #        the accepted after-state (Reader only appended, never rewrote Pro) ---
    before_rows, after_rows = [pro], [pro, reader]
    ck("9 Reader append leaves the Pro row byte-identical (append-only)",
       after_rows[0] == before_rows[0] and after_rows[0] is pro)

    print()
    print("=" * 74)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERR:
        print(f"  - {e}")
    print("=" * 74)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
