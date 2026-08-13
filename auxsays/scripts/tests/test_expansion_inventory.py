#!/usr/bin/env python3
"""Tests for validate_expansion_inventory.py.

A validator that cannot fail is ceremony, so every rule is exercised by MUTATING a synthetic
inventory and asserting the validator rejects it. The committed inventories are also validated
as-is, so the planning data cannot drift out of agreement with patch_products.yml unnoticed.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_expansion_inventory.py
"""
from __future__ import annotations

import copy
import io
import sys
import tempfile
import traceback
from contextlib import redirect_stdout
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import validate_expansion_inventory as vei  # noqa: E402

_PASS = 0
_FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


# ---------------------------------------------------------------------------------------
# Synthetic fixtures: the smallest inventories that satisfy every rule.
# ---------------------------------------------------------------------------------------
PRODUCTS = [
    {"product_id": "prod-enabled", "product_name": "Enabled"},
    {"product_id": "prod-disabled", "product_name": "Disabled"},
]
INGESTION = [
    {"product_id": "prod-enabled", "enabled": True, "ingestion": {"adapter": "x"}},
    {"product_id": "prod-disabled", "enabled": False, "ingestion": {"adapter": "y"}},
]
SOURCES = {
    "schema_version": 1,
    "lifecycle_states": {"discovered": "d", "needs_probe": "n", "viable": "v",
                         "transport_proven": "t", "production_proven": "p"},
    "proof_levels": {"none": "-", "local_reachable": "-", "structure_proven": "-",
                     "actions_reachable": "-", "production_proven": "-"},
    "opportunities": [
        {
            "opportunity_id": "opp-one", "product_ids": ["prod-enabled"],
            "source_name": "S", "source_type": "t", "lane": "consensus",
            "official_or_community": "community", "domain": "example.test",
            "entry_point": "https://example.test/", "discovery_method": "m",
            "auth_requirement": "none", "proof_level": "structure_proven",
            "measured_at": "2026-08-13", "measurement": "200 OK",
            "reuse_scope": ["prod-enabled"], "shared_framework": "f",
            "status": "transport_proven", "next_experiment": "probe",
        },
    ],
}
DIMS = {
    "user_impact": 3, "patch_risk": 4, "update_frequency": 2, "commercial_value": 3,
    "official_source_quality": 3, "consensus_source_quality": 4, "automation_feasibility": 5,
    "source_diversity": 2, "version_identifiability": 4, "maintenance_cost": 2,
    "cross_product_reuse": 2,
}
CANDIDATES = {
    "schema_version": 1,
    "scoring": {
        "scale": {"min": 0, "max": 5},
        "dimensions": {k: {"weight": w, "direction": "higher_is_better", "meaning": "m"}
                       for k, w in DIMS.items()},
        "weight_total": sum(DIMS.values()),
        "max_total": 5 * sum(DIMS.values()),
        "tiers": {
            "A": {"label": "A", "min_total": 120,
                  "hard_gates": {"automation_feasibility": 4, "version_identifiability": 4,
                                 "official_source_quality": 3}},
            "B": {"label": "B", "min_total": 90},
            "C": {"label": "C"},
        },
    },
    "repo_states": {"untracked": "u", "configured_disabled": "c", "tracked_official_only": "t"},
    "candidates": [
        {
            "candidate_id": "prod-enabled", "product_name": "Enabled", "vendor": "V",
            "category": "c", "repo_state": "tracked_official_only",
            "scores": {k: 5 for k in DIMS}, "total_score": 5 * sum(DIMS.values()), "tier": "A",
            "known_sources": ["opp-one"], "recommended_next_step": "go",
        },
        {
            "candidate_id": "prod-disabled", "product_name": "Disabled", "vendor": "V",
            "category": "c", "repo_state": "configured_disabled",
            "scores": {k: 1 for k in DIMS}, "total_score": sum(DIMS.values()), "tier": "C",
            "known_sources": ["none"], "recommended_next_step": "wait",
        },
        {
            "candidate_id": "brand-new", "product_name": "New", "vendor": "V",
            "category": "c", "repo_state": "untracked",
            "scores": {k: 3 for k in DIMS}, "total_score": 3 * sum(DIMS.values()), "tier": "B",
            "known_sources": ["none"], "recommended_next_step": "probe",
        },
    ],
}


def run_validator(sources: dict, candidates: dict, products=None, ingestion=None) -> tuple[int, str]:
    """Point the validator at temp copies and return (exit_code, stdout)."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        files = {
            "SOURCES_FILE": ("src.yml", sources),
            "CANDIDATES_FILE": ("cand.yml", candidates),
            "PRODUCTS_FILE": ("prod.yml", products if products is not None else PRODUCTS),
            "INGESTION_FILE": ("ing.yml", ingestion if ingestion is not None else INGESTION),
        }
        saved = {}
        for attr, (name, payload) in files.items():
            p = d / name
            p.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
            saved[attr] = getattr(vei, attr)
            setattr(vei, attr, p)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = vei.validate()
            return rc, buf.getvalue()
        finally:
            for attr, prior in saved.items():
                setattr(vei, attr, prior)


def mutate(label: str, fn, target: str = "candidates", needle: str = "") -> None:
    """Apply fn to a deep copy of the named fixture and require the validator to reject it."""
    s, c = copy.deepcopy(SOURCES), copy.deepcopy(CANDIDATES)
    fn(c if target == "candidates" else s)
    rc, out = run_validator(s, c)
    ok = rc == 1 and (needle in out if needle else True)
    check(label, ok, f"rc={rc}\n{out.strip()[-400:]}")


def run() -> int:  # noqa: PLR0915
    print("=" * 60)
    print("EXPANSION INVENTORY VALIDATOR")
    print("=" * 60)

    # --- the synthetic baseline must be clean, else every mutation test is meaningless ---
    rc, out = run_validator(SOURCES, CANDIDATES)
    check("synthetic baseline inventory validates clean", rc == 0, out)
    check("baseline recomputes the expected tier split", "A=1 B=1 C=1" in out, out)

    # --- the COMMITTED inventories must validate ------------------------------------------
    buf = io.StringIO()
    with redirect_stdout(buf):
        real_rc = vei.validate()
    real_out = buf.getvalue()
    check("committed expansion inventories validate clean", real_rc == 0, real_out[-600:])
    check("committed inventories are non-trivial (>=20 opportunities, >=40 candidates)",
          (lambda m: m and int(m[0]) >= 20 and int(m[1]) >= 40)(
              __import__("re").findall(r"(\d+) source opportunities, (\d+) product candidates", real_out)[0]
              if "source opportunities" in real_out else None),
          real_out[:200])

    # --- score arithmetic is the thing most likely to drift silently ----------------------
    def drift_total(c):
        c["candidates"][0]["total_score"] += 1
    mutate("a drifted total_score is rejected", drift_total, needle="!= recomputed")

    def drift_tier(c):
        c["candidates"][0]["tier"] = "C"
    mutate("a drifted tier is rejected", drift_tier, needle="!= recomputed")

    def out_of_range(c):
        c["candidates"][0]["scores"]["patch_risk"] = 9
        c["candidates"][0]["total_score"] = None
    mutate("a score above the declared max is rejected", out_of_range, needle="outside declared bounds")

    def negative(c):
        c["candidates"][0]["scores"]["patch_risk"] = -1
    mutate("a negative score is rejected", negative, needle="outside declared bounds")

    def non_integer(c):
        c["candidates"][0]["scores"]["patch_risk"] = "high"
    mutate("a non-integer score is rejected", non_integer, needle="must be an integer")

    def missing_dim(c):
        del c["candidates"][0]["scores"]["patch_risk"]
    mutate("a missing scoring dimension is rejected", missing_dim, needle="missing dimensions")

    def extra_dim(c):
        c["candidates"][0]["scores"]["vibes"] = 5
    mutate("an undeclared scoring dimension is rejected", extra_dim, needle="undeclared dimensions")

    def bad_weight_total(c):
        c["scoring"]["weight_total"] = 999
    mutate("a wrong declared weight_total is rejected", bad_weight_total, needle="weight_total")

    def bad_max_total(c):
        c["scoring"]["max_total"] = 999
    mutate("a wrong declared max_total is rejected", bad_max_total, needle="max_total")

    # --- the Tier A hard gates must actually gate -----------------------------------------
    def popular_but_unautomatable(c):
        """High impact/value, unattendable lane: must NOT be recomputed as Tier A."""
        s = {k: 5 for k in DIMS}
        s["automation_feasibility"] = 1
        c["candidates"][0]["scores"] = s
        c["candidates"][0]["total_score"] = sum(s[k] * DIMS[k] for k in DIMS)
        c["candidates"][0]["tier"] = "A"
    mutate("a high-scoring product that fails the automation gate cannot be stored as Tier A",
           popular_but_unautomatable, needle="stored tier")

    def fails_version_gate(c):
        s = {k: 5 for k in DIMS}
        s["version_identifiability"] = 2
        c["candidates"][0]["scores"] = s
        c["candidates"][0]["total_score"] = sum(s[k] * DIMS[k] for k in DIMS)
        c["candidates"][0]["tier"] = "A"
    mutate("a product that fails the version-identifiability gate cannot be Tier A",
           fails_version_gate, needle="stored tier")

    # --- identity and referential integrity ----------------------------------------------
    def dup_candidate(c):
        c["candidates"].append(copy.deepcopy(c["candidates"][0]))
    mutate("a duplicate candidate_id is rejected", dup_candidate, needle="duplicate candidate_id")

    def missing_field(c):
        del c["candidates"][0]["recommended_next_step"]
    mutate("a missing required candidate field is rejected", missing_field, needle="missing required field")

    def bad_repo_state(c):
        c["candidates"][0]["repo_state"] = "probably_fine"
    mutate("an undeclared repo_state is rejected", bad_repo_state, needle="not a declared repo_state")

    def lying_untracked(c):
        c["candidates"][0]["repo_state"] = "untracked"
    mutate("claiming 'untracked' for a product that IS configured is rejected",
           lying_untracked, needle="marked untracked but present")

    def lying_disabled(c):
        c["candidates"][0]["repo_state"] = "configured_disabled"
    mutate("claiming 'configured_disabled' for an ENABLED product is rejected",
           lying_disabled, needle="ingestion source is enabled")

    def lying_tracked(c):
        c["candidates"][2]["repo_state"] = "tracked_official_only"
    mutate("claiming 'tracked_official_only' for an unconfigured product is rejected",
           lying_tracked, needle="no enabled ingestion source")

    # --- source opportunities -------------------------------------------------------------
    def bad_status(s):
        s["opportunities"][0]["status"] = "looks_promising"
    mutate("an undeclared lifecycle state is rejected", bad_status, target="sources",
           needle="not a declared lifecycle state")

    def bad_proof(s):
        s["opportunities"][0]["proof_level"] = "definitely_works"
    mutate("an undeclared proof_level is rejected", bad_proof, target="sources",
           needle="not a declared proof level")

    def bad_lane(s):
        s["opportunities"][0]["lane"] = "both"
    mutate("a lane outside {official, consensus} is rejected", bad_lane, target="sources",
           needle="lane")

    def dangling_product(s):
        s["opportunities"][0]["product_ids"] = ["prod-does-not-exist"]
    mutate("a product_ids reference to an unknown product is rejected", dangling_product,
           target="sources", needle="unknown product_id")

    def dangling_reuse(s):
        s["opportunities"][0]["reuse_scope"] = ["nope"]
    mutate("a reuse_scope reference to an unknown product is rejected", dangling_reuse,
           target="sources", needle="unknown product_id")

    def dup_opportunity(s):
        s["opportunities"].append(copy.deepcopy(s["opportunities"][0]))
    mutate("a duplicate opportunity_id is rejected", dup_opportunity, target="sources",
           needle="duplicate opportunity_id")

    def missing_opp_field(s):
        del s["opportunities"][0]["measurement"]
    mutate("a missing required opportunity field is rejected", missing_opp_field,
           target="sources", needle="missing required field")

    def borrowed_credibility(s):
        """An unprobed source must not claim a high proof level."""
        s["opportunities"][0]["status"] = "needs_probe"
        s["opportunities"][0]["proof_level"] = "production_proven"
    mutate("a high proof_level on an unprobed status is rejected", borrowed_credibility,
           target="sources", needle="contradicts status")

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
