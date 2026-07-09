#!/usr/bin/env python3
"""Locks the community-evidence-strength tiering thresholds.

"Community evidence strength" measures how strong the confirmed patch-specific
report *sample* is for supporting the displayed consensus label. It is NOT a claim
that the patch is safe -- a High-strength sample can carry a Negative verdict.

The deterministic scale (report count -> tier) lives in two mirrored functions:
  - apply_consensus_to_records._confidence  (writeback path)
  - build_consensus_from_evidence.confidence (dry-run status path)

Required scale:
  0        -> Insufficient
  1  - 7   -> Low
  8  - 24  -> Low-Medium
  25 - 32  -> Medium
  33+      -> High

Offline only: no network, no writes. A YAML shim is installed because both modules
import PyYAML at module load and CI/local envs may lack it; these tier functions do
no YAML I/O.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_evidence_strength_thresholds.py
"""
from __future__ import annotations

import sys
import traceback
import types
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

# Both modules do `import yaml` at load; the tier functions themselves need no YAML.
sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda *_a, **_k: {}, safe_dump=lambda *_a, **_k: ""))

from apply_consensus_to_records import _confidence as writeback_strength
from build_consensus_from_evidence import confidence as status_strength

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


# (count, expected_tier) pairs covering every band and both sides of every boundary.
EXPECTED = [
    (0, "Insufficient"),
    (1, "Low"),
    (7, "Low"),
    (8, "Low-Medium"),
    (24, "Low-Medium"),
    (25, "Medium"),
    (32, "Medium"),
    (33, "High"),
    (34, "High"),
    (79, "High"),
    (1000, "High"),
]

# Exact boundary transitions -- one below flips to the next tier.
BOUNDARIES = [
    (7, "Low", 8, "Low-Medium"),
    (24, "Low-Medium", 25, "Medium"),
    (32, "Medium", 33, "High"),
]

ALLOWED_TIERS = {"Insufficient", "Low", "Low-Medium", "Medium", "High"}


def run() -> int:
    print("=" * 60)
    print("Community evidence strength threshold tests")
    print("=" * 60)

    for count, tier in EXPECTED:
        got = writeback_strength(count)
        check(f"writeback strength: {count} -> {tier}", got == tier, f"got {got!r}")
        got2 = status_strength(count)
        check(f"status strength:    {count} -> {tier}", got2 == tier, f"got {got2!r}")

    # 33+ is the new High band; 25-32 must remain Medium (not silently promoted).
    check("33 is the exact High threshold (32 stays Medium)", writeback_strength(32) == "Medium" and writeback_strength(33) == "High")
    check("High requires 33+, so 25-32 never reads High", all(writeback_strength(n) == "Medium" for n in range(25, 33)))

    for low_n, low_tier, high_n, high_tier in BOUNDARIES:
        check(
            f"boundary {low_n}->{low_tier} / {high_n}->{high_tier} (writeback)",
            writeback_strength(low_n) == low_tier and writeback_strength(high_n) == high_tier,
        )

    # The two deterministic implementations must stay in lockstep across the range.
    parity = all(writeback_strength(n) == status_strength(n) for n in range(0, 120))
    check("writeback and status strength agree for 0..119", parity)

    # No tier outside the sanctioned vocabulary may ever be produced.
    vocab_ok = {writeback_strength(n) for n in range(0, 200)} <= ALLOWED_TIERS
    check("only sanctioned tier labels are produced", vocab_ok, str({writeback_strength(n) for n in range(0, 200)}))

    # --- product-history layout mirrors the same thresholds -----------------
    # No Liquid engine is available offline, so statically assert that the
    # product-history template DERIVES the displayed strength from the row's
    # report count with this exact table -- rather than rendering the stored
    # (and possibly stale) update_consensus_confidence field. This guards against
    # a regression where a 33+ report record still shows Medium.
    layout = (_REPO / "auxsays" / "_layouts" / "aux-patch-product.html").read_text(encoding="utf-8")
    check("layout column header reads 'Community evidence strength'",
          "<span>Community evidence strength</span>" in layout)
    check("layout derives strength from the report-count source (item.update_report_count)",
          "{% assign evidence_strength_count = item.update_report_count %}" in layout)
    check("layout renders the derived strength, not the stale stored field",
          "<span>{{ evidence_strength }}</span>" in layout
          and '{{ item.update_consensus_confidence | default: "Low" }}' not in layout)
    check("layout falls back to the stored field only when the count is missing",
          'evidence_strength = item.update_consensus_confidence | default: "Insufficient"' in layout)
    for clause, tier in [
        ('>= 33 %}{% assign evidence_strength = "High" %}', "High"),
        ('>= 25 %}{% assign evidence_strength = "Medium" %}', "Medium"),
        ('>= 8 %}{% assign evidence_strength = "Low-Medium" %}', "Low-Medium"),
        ('> 0 %}{% assign evidence_strength = "Low" %}', "Low"),
        ('{% else %}{% assign evidence_strength = "Insufficient" %}{% endif %}', "Insufficient"),
    ]:
        check(f"layout threshold clause present: count {tier}", clause in layout, clause)

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
