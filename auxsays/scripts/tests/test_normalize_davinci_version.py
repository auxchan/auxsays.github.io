#!/usr/bin/env python3
"""Tests for normalize_davinci_version.

Run with: python auxsays/scripts/tests/test_normalize_davinci_version.py

No external test framework required.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Allow running from repo root or from within scripts/tests/
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib.normalize_davinci_version import normalize_davinci_version, is_same_version

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


def result(raw: str) -> dict:
    return normalize_davinci_version(raw)


def canonical(raw: str) -> str | None:
    return result(raw)["canonical_update_version"]


def rejected(raw: str) -> bool:
    return result(raw)["rejected"]


def reason(raw: str) -> str | None:
    return result(raw)["rejection_reason"]


def run() -> int:
    print("=" * 60)
    print("DaVinci version normalization tests")
    print("=" * 60)

    # ------------------------------------------------------------------ #
    # 1. Stable major releases — prefix stripping                         #
    # ------------------------------------------------------------------ #
    print("\n--- 1. Stable major releases ---")

    check(
        '"DaVinci Resolve 21" → "21"',
        canonical("DaVinci Resolve 21") == "21",
        f'got: {canonical("DaVinci Resolve 21")}',
    )
    check(
        '"DaVinci Resolve Studio 21" → "21"',
        canonical("DaVinci Resolve Studio 21") == "21",
        f'got: {canonical("DaVinci Resolve Studio 21")}',
    )
    check(
        '"Resolve 21" → "21"',
        canonical("Resolve 21") == "21",
        f'got: {canonical("Resolve 21")}',
    )
    check(
        '"DaVinci 21" → "21"',
        canonical("DaVinci 21") == "21",
        f'got: {canonical("DaVinci 21")}',
    )
    check(
        '"21" → "21"',
        canonical("21") == "21",
        f'got: {canonical("21")}',
    )
    check(
        '"v21" → "21"',
        canonical("v21") == "21",
        f'got: {canonical("v21")}',
    )

    # ------------------------------------------------------------------ #
    # 2. Stable point releases                                            #
    # ------------------------------------------------------------------ #
    print("\n--- 2. Stable point releases ---")

    check(
        '"21.0" → "21.0"',
        canonical("21.0") == "21.0",
        f'got: {canonical("21.0")}',
    )
    check(
        '"DaVinci Resolve 21.0" → "21.0"',
        canonical("DaVinci Resolve 21.0") == "21.0",
        f'got: {canonical("DaVinci Resolve 21.0")}',
    )
    check(
        '"21.0.1" → "21.0.1"',
        canonical("21.0.1") == "21.0.1",
        f'got: {canonical("21.0.1")}',
    )
    check(
        '"DaVinci Resolve 21.0.1" → "21.0.1"',
        canonical("DaVinci Resolve 21.0.1") == "21.0.1",
        f'got: {canonical("DaVinci Resolve 21.0.1")}',
    )
    check(
        '"20.0.0" → "20.0.0"',
        canonical("20.0.0") == "20.0.0",
        f'got: {canonical("20.0.0")}',
    )
    check(
        '"DaVinci Resolve 19.1.1" → "19.1.1"',
        canonical("DaVinci Resolve 19.1.1") == "19.1.1",
        f'got: {canonical("DaVinci Resolve 19.1.1")}',
    )
    check(
        '"DaVinci Resolve 19.1" → "19.1"',
        canonical("DaVinci Resolve 19.1") == "19.1",
        f'got: {canonical("DaVinci Resolve 19.1")}',
    )

    # ------------------------------------------------------------------ #
    # 3. Beta releases — canonical mapping                                #
    # ------------------------------------------------------------------ #
    print("\n--- 3. Beta releases ---")

    check(
        '"DaVinci Resolve 21 Public Beta 1" → "21 Public Beta 1"',
        canonical("DaVinci Resolve 21 Public Beta 1") == "21 Public Beta 1",
        f'got: {canonical("DaVinci Resolve 21 Public Beta 1")}',
    )
    check(
        '"DaVinci Resolve Studio 21 Public Beta 1" → "21 Public Beta 1"',
        canonical("DaVinci Resolve Studio 21 Public Beta 1") == "21 Public Beta 1",
        f'got: {canonical("DaVinci Resolve Studio 21 Public Beta 1")}',
    )
    check(
        '"DaVinci Resolve 21 Beta 1" → "21 Public Beta 1"',
        canonical("DaVinci Resolve 21 Beta 1") == "21 Public Beta 1",
        f'got: {canonical("DaVinci Resolve 21 Beta 1")}',
    )
    check(
        '"Resolve 21 Beta 1" → "21 Public Beta 1"',
        canonical("Resolve 21 Beta 1") == "21 Public Beta 1",
        f'got: {canonical("Resolve 21 Beta 1")}',
    )
    check(
        '"Resolve 21b1" → "21 Public Beta 1"',
        canonical("Resolve 21b1") == "21 Public Beta 1",
        f'got: {canonical("Resolve 21b1")}',
    )
    check(
        '"21b1" → "21 Public Beta 1"',
        canonical("21b1") == "21 Public Beta 1",
        f'got: {canonical("21b1")}',
    )
    check(
        '"21 Public Beta 1" → "21 Public Beta 1"',
        canonical("21 Public Beta 1") == "21 Public Beta 1",
        f'got: {canonical("21 Public Beta 1")}',
    )
    check(
        '"21 Beta1" → "21 Public Beta 1"',
        canonical("21 Beta1") == "21 Public Beta 1",
        f'got: {canonical("21 Beta1")}',
    )
    check(
        '"21 Public Beta 2" → "21 Public Beta 2"',
        canonical("21 Public Beta 2") == "21 Public Beta 2",
        f'got: {canonical("21 Public Beta 2")}',
    )
    check(
        '"21b2" → "21 Public Beta 2"',
        canonical("21b2") == "21 Public Beta 2",
        f'got: {canonical("21b2")}',
    )

    # ------------------------------------------------------------------ #
    # 4. Stable vs beta must NOT collapse                                 #
    # ------------------------------------------------------------------ #
    print("\n--- 4. Stable vs beta separation ---")

    check(
        '"21" != "21 Public Beta 1"',
        canonical("21") != canonical("21 Public Beta 1"),
        f'stable={canonical("21")!r}  beta={canonical("21 Public Beta 1")!r}',
    )
    check(
        '"21.0" != "21 Public Beta 1"',
        canonical("21.0") != canonical("21 Public Beta 1"),
        f'got: {canonical("21.0")!r} vs {canonical("21 Public Beta 1")!r}',
    )
    check(
        '"21 Public Beta 1" != "21 Public Beta 2"',
        canonical("21 Public Beta 1") != canonical("21 Public Beta 2"),
        f'got: {canonical("21 Public Beta 1")!r} vs {canonical("21 Public Beta 2")!r}',
    )
    check(
        'is_same_version("21b1", "DaVinci Resolve 21 Public Beta 1") == True',
        is_same_version("21b1", "DaVinci Resolve 21 Public Beta 1"),
    )
    check(
        'is_same_version("21b1", "21") == False',
        not is_same_version("21b1", "21"),
    )

    # ------------------------------------------------------------------ #
    # 5. is_beta field                                                    #
    # ------------------------------------------------------------------ #
    print("\n--- 5. is_beta field ---")

    check(
        'result("21")["is_beta"] == False',
        result("21")["is_beta"] is False,
    )
    check(
        'result("21 Public Beta 1")["is_beta"] == True',
        result("21 Public Beta 1")["is_beta"] is True,
    )
    check(
        'result("21 Public Beta 1")["beta_number"] == 1',
        result("21 Public Beta 1")["beta_number"] == 1,
    )
    check(
        'result("21b2")["beta_number"] == 2',
        result("21b2")["beta_number"] == 2,
    )
    check(
        'result("21")["major_version"] == 21',
        result("21")["major_version"] == 21,
    )
    check(
        'result("21.0.1")["minor_version"] == "0.1"',
        result("21.0.1")["minor_version"] == "0.1",
        f'got: {result("21.0.1")["minor_version"]!r}',
    )

    # ------------------------------------------------------------------ #
    # 6. product_id field                                                 #
    # ------------------------------------------------------------------ #
    print("\n--- 6. product_id ---")

    check(
        'result("21")["product_id"] == "blackmagic-davinci"',
        result("21")["product_id"] == "blackmagic-davinci",
    )
    check(
        'result("DaVinci Resolve Studio 21 Public Beta 1")["product_id"] == "blackmagic-davinci"',
        result("DaVinci Resolve Studio 21 Public Beta 1")["product_id"] == "blackmagic-davinci",
    )

    # ------------------------------------------------------------------ #
    # 7. Rejection cases — must fail closed                               #
    # ------------------------------------------------------------------ #
    print("\n--- 7. Rejections ---")

    check(
        '"21 beta" → rejected (ambiguous_beta_no_number)',
        rejected("21 beta") and reason("21 beta") == "ambiguous_beta_no_number",
        f'rejected={rejected("21 beta")}, reason={reason("21 beta")!r}',
    )
    check(
        '"21b" → rejected (ambiguous_beta_no_number)',
        rejected("21b") and reason("21b") == "ambiguous_beta_no_number",
        f'rejected={rejected("21b")}, reason={reason("21b")!r}',
    )
    check(
        '"Resolve 21 Beta" → rejected (ambiguous_beta_no_number)',
        rejected("Resolve 21 Beta") and reason("Resolve 21 Beta") == "ambiguous_beta_no_number",
        f'rejected={rejected("Resolve 21 Beta")}, reason={reason("Resolve 21 Beta")!r}',
    )
    check(
        '"DaVinci Resolve 21 Beta" → rejected (ambiguous_beta_no_number)',
        rejected("DaVinci Resolve 21 Beta") and reason("DaVinci Resolve 21 Beta") == "ambiguous_beta_no_number",
        f'rejected={rejected("DaVinci Resolve 21 Beta")}, reason={reason("DaVinci Resolve 21 Beta")!r}',
    )
    check(
        '"DR21" → rejected (abbreviation_dr_ambiguous)',
        rejected("DR21") and reason("DR21") == "abbreviation_dr_ambiguous",
        f'rejected={rejected("DR21")}, reason={reason("DR21")!r}',
    )
    check(
        '"DR 21" → rejected (abbreviation_dr_ambiguous)',
        rejected("DR 21") and reason("DR 21") == "abbreviation_dr_ambiguous",
        f'rejected={rejected("DR 21")}, reason={reason("DR 21")!r}',
    )
    check(
        '"21.x" → rejected (wildcard_version)',
        rejected("21.x") and reason("21.x") == "wildcard_version",
        f'rejected={rejected("21.x")}, reason={reason("21.x")!r}',
    )
    check(
        '"" → rejected (empty_or_invalid_input)',
        rejected("") and reason("") == "empty_or_invalid_input",
        f'rejected={rejected("")}, reason={reason("")!r}',
    )
    check(
        '"DaVinci Resolve" (no version) → rejected',
        rejected("DaVinci Resolve"),
        f'rejected={rejected("DaVinci Resolve")}, canonical={canonical("DaVinci Resolve")!r}',
    )

    # ------------------------------------------------------------------ #
    # 8. False positives — non-DaVinci strings                           #
    # ------------------------------------------------------------------ #
    print("\n--- 8. False positive rejection ---")

    check(
        '"OBS Studio 31.0" → rejected (unrecognized_version_format)',
        rejected("OBS Studio 31.0"),
        f'rejected={rejected("OBS Studio 31.0")}, reason={reason("OBS Studio 31.0")!r}',
    )
    check(
        '"Premiere Pro 26.2" → rejected',
        rejected("Premiere Pro 26.2"),
        f'rejected={rejected("Premiere Pro 26.2")}, reason={reason("Premiere Pro 26.2")!r}',
    )
    check(
        '"Windows 11 24H2" → rejected',
        rejected("Windows 11 24H2"),
        f'rejected={rejected("Windows 11 24H2")}, reason={reason("Windows 11 24H2")!r}',
    )

    # ------------------------------------------------------------------ #
    # 9. normalized_aliases presence                                      #
    # ------------------------------------------------------------------ #
    print("\n--- 9. Alias lists ---")

    aliases_beta1 = result("21 Public Beta 1")["normalized_aliases"]
    check(
        '"21 Public Beta 1" aliases include "21b1"',
        "21b1" in aliases_beta1,
        f'aliases: {aliases_beta1}',
    )
    check(
        '"21 Public Beta 1" aliases include "DaVinci Resolve 21 Public Beta 1"',
        "DaVinci Resolve 21 Public Beta 1" in aliases_beta1,
        f'aliases: {aliases_beta1}',
    )

    aliases_stable = result("21")["normalized_aliases"]
    check(
        '"21" aliases include "DaVinci Resolve 21"',
        "DaVinci Resolve 21" in aliases_stable,
        f'aliases: {aliases_stable}',
    )

    # ------------------------------------------------------------------ #
    # Summary                                                             #
    # ------------------------------------------------------------------ #
    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 60)

    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
