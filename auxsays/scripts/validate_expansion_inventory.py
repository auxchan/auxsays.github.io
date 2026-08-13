#!/usr/bin/env python3
"""Validate the expansion planning inventories.

`_data/expansion_source_opportunities.yml` and `_data/expansion_product_candidates.yml` are
planning data, not production config -- but planning data that quietly drifts out of agreement
with the repo is worse than none, because it produces confident roadmaps about products and
sources that no longer exist as described. This validator pins the parts a human cannot check
by eye:

  * required fields present, ids unique;
  * lifecycle state / proof level / repo_state drawn from the vocabularies the files declare
    (no prose-only states);
  * every referenced product_id actually exists in `_data/patch_products.yml`;
  * scores inside the declared bounds, with every declared dimension present;
  * `total_score` and `tier` RECOMPUTED from `scores` and required to match what is stored, so
    the stored values are a checked cache rather than a second source of truth;
  * `repo_state` cross-checked against the real repo (untracked products must be absent from
    patch_products.yml; configured_disabled must be present and disabled; tracked_official_only
    must be present and enabled).

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/validate_expansion_inventory.py
Exit 0 clean, 1 on any error.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

_REPO = Path(__file__).resolve().parents[2]
_DATA = _REPO / "auxsays" / "_data"

SOURCES_FILE = _DATA / "expansion_source_opportunities.yml"
CANDIDATES_FILE = _DATA / "expansion_product_candidates.yml"
PRODUCTS_FILE = _DATA / "patch_products.yml"
INGESTION_FILE = _DATA / "patch_ingestion_sources.yml"

OPPORTUNITY_REQUIRED = (
    "opportunity_id", "product_ids", "source_name", "source_type", "lane",
    "official_or_community", "domain", "entry_point", "discovery_method", "auth_requirement",
    "proof_level", "measured_at", "measurement", "reuse_scope", "shared_framework", "status",
    "next_experiment",
)
CANDIDATE_REQUIRED = (
    "candidate_id", "product_name", "vendor", "category", "repo_state", "scores",
    "total_score", "tier", "known_sources", "recommended_next_step",
)
LANES = {"official", "consensus"}
ORIGINS = {"official", "community"}


def _load(path: Path) -> Any:
    if not path.exists():
        raise SystemExit(f"missing required file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    products = _load(PRODUCTS_FILE)
    plist = products if isinstance(products, list) else products.get("products", [])
    known_products = {str(p.get("product_id")) for p in plist if p.get("product_id")}

    ingestion = _load(INGESTION_FILE)
    slist = ingestion if isinstance(ingestion, list) else ingestion.get("sources", [])
    enabled_products = {
        str(s.get("product_id")) for s in slist if s.get("enabled") and s.get("product_id")
    }

    # ---------------- source opportunities ----------------------------------------------
    src = _load(SOURCES_FILE)
    states = src.get("lifecycle_states") or {}
    levels = src.get("proof_levels") or {}
    if not isinstance(states, dict) or not states:
        errors.append("expansion_source_opportunities.yml: lifecycle_states must be a non-empty map")
    if not isinstance(levels, dict) or not levels:
        errors.append("expansion_source_opportunities.yml: proof_levels must be a non-empty map")

    opportunities = src.get("opportunities") or []
    seen_opp: set[str] = set()
    for i, o in enumerate(opportunities):
        if not isinstance(o, dict):
            errors.append(f"opportunity[{i}] is not a mapping")
            continue
        oid = str(o.get("opportunity_id") or f"<index {i}>")
        for field in OPPORTUNITY_REQUIRED:
            if field not in o:
                errors.append(f"{oid}: missing required field '{field}'")
        if oid in seen_opp:
            errors.append(f"{oid}: duplicate opportunity_id")
        seen_opp.add(oid)
        if o.get("status") not in states:
            errors.append(f"{oid}: status {o.get('status')!r} is not a declared lifecycle state")
        if o.get("proof_level") not in levels:
            errors.append(f"{oid}: proof_level {o.get('proof_level')!r} is not a declared proof level")
        if o.get("lane") not in LANES:
            errors.append(f"{oid}: lane {o.get('lane')!r} must be one of {sorted(LANES)}")
        if o.get("official_or_community") not in ORIGINS:
            errors.append(f"{oid}: official_or_community {o.get('official_or_community')!r} invalid")
        for key in ("product_ids", "reuse_scope"):
            value = o.get(key)
            if value is None:
                continue
            if not isinstance(value, list):
                errors.append(f"{oid}: {key} must be a list")
                continue
            for pid in value:
                if str(pid) not in known_products:
                    errors.append(f"{oid}: {key} references unknown product_id {pid!r}")
        # A claim of production_proven or actions_reachable must not be attached to an
        # opportunity that is still only `discovered`/`needs_probe` -- that combination is how
        # unmeasured sources acquire borrowed credibility.
        if o.get("proof_level") in {"actions_reachable", "patch_specificity_proven",
                                    "supply_proven", "production_proven"} \
                and o.get("status") in {"discovered", "needs_probe"}:
            errors.append(f"{oid}: proof_level {o.get('proof_level')!r} contradicts status {o.get('status')!r}")

    # ---------------- product candidates ------------------------------------------------
    cand = _load(CANDIDATES_FILE)
    scoring = cand.get("scoring") or {}
    dims = scoring.get("dimensions") or {}
    scale = scoring.get("scale") or {}
    tiers = scoring.get("tiers") or {}
    repo_states = cand.get("repo_states") or {}

    lo, hi = int(scale.get("min", 0)), int(scale.get("max", 5))
    weights = {k: int(v["weight"]) for k, v in dims.items()}
    if sum(weights.values()) != int(scoring.get("weight_total", -1)):
        errors.append(
            f"scoring.weight_total {scoring.get('weight_total')!r} != sum of weights {sum(weights.values())}")
    if int(scoring.get("max_total", -1)) != hi * sum(weights.values()):
        errors.append(
            f"scoring.max_total {scoring.get('max_total')!r} != max score * total weight "
            f"({hi * sum(weights.values())})")
    for name in ("A", "B", "C"):
        if name not in tiers:
            errors.append(f"scoring.tiers missing tier {name}")

    def compute_total(scores: dict[str, Any]) -> int:
        return sum(int(scores[d]) * weights[d] for d in weights)

    def compute_tier(total: int, scores: dict[str, Any]) -> str:
        gates = tiers.get("A", {}).get("hard_gates") or {}
        if total >= int(tiers["A"]["min_total"]) and all(
                int(scores.get(k, -1)) >= int(v) for k, v in gates.items()):
            return "A"
        return "B" if total >= int(tiers["B"]["min_total"]) else "C"

    candidates = cand.get("candidates") or []
    seen_cand: set[str] = set()
    tier_counts = {"A": 0, "B": 0, "C": 0}
    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            errors.append(f"candidate[{i}] is not a mapping")
            continue
        cid = str(c.get("candidate_id") or f"<index {i}>")
        for field in CANDIDATE_REQUIRED:
            if field not in c:
                errors.append(f"{cid}: missing required field '{field}'")
        if cid in seen_cand:
            errors.append(f"{cid}: duplicate candidate_id")
        seen_cand.add(cid)

        state = c.get("repo_state")
        if state not in repo_states:
            errors.append(f"{cid}: repo_state {state!r} is not a declared repo_state")
        elif state == "untracked" and cid in known_products:
            errors.append(f"{cid}: marked untracked but present in patch_products.yml")
        elif state == "configured_disabled":
            if cid not in known_products:
                errors.append(f"{cid}: marked configured_disabled but absent from patch_products.yml")
            elif cid in enabled_products:
                errors.append(f"{cid}: marked configured_disabled but its ingestion source is enabled")
        elif state == "tracked_official_only":
            if cid not in enabled_products:
                errors.append(f"{cid}: marked tracked_official_only but has no enabled ingestion source")

        scores = c.get("scores")
        if not isinstance(scores, dict):
            errors.append(f"{cid}: scores must be a mapping")
            continue
        missing = sorted(set(weights) - set(scores))
        extra = sorted(set(scores) - set(weights))
        if missing:
            errors.append(f"{cid}: scores missing dimensions {missing}")
        if extra:
            errors.append(f"{cid}: scores has undeclared dimensions {extra}")
        well_typed = True
        for dim, value in scores.items():
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"{cid}: score {dim}={value!r} must be an integer")
                well_typed = False
            elif not lo <= value <= hi:
                errors.append(f"{cid}: score {dim}={value} outside declared bounds {lo}..{hi}")
        if missing or extra or not well_typed:
            # The shape is already wrong; recomputing a total from it would raise rather than
            # report, and the specific errors above are the useful output.
            continue

        total = compute_total(scores)
        # A malformed stored value must be an ERROR, not a crash: this validator runs in gates,
        # and a traceback there reads as "the tool is broken" rather than "the data is wrong".
        stored_total = c.get("total_score")
        if not isinstance(stored_total, int) or isinstance(stored_total, bool):
            errors.append(f"{cid}: total_score {stored_total!r} must be an integer")
        elif stored_total != total:
            errors.append(f"{cid}: stored total_score {stored_total!r} != recomputed {total}")
        tier = compute_tier(total, scores)
        if str(c.get("tier")) != tier:
            errors.append(f"{cid}: stored tier {c.get('tier')!r} != recomputed {tier}")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        if not c.get("known_sources"):
            warnings.append(f"{cid}: no known_sources recorded")

    # Every candidate that names an opportunity family should have at least one opportunity row,
    # and every opportunity product should be reachable -- a warning, not an error, because the
    # two inventories legitimately grow at different rates.
    opp_products = {str(p) for o in opportunities if isinstance(o, dict)
                    for p in (o.get("product_ids") or [])}
    for c in candidates:
        if isinstance(c, dict) and c.get("repo_state") in {"configured_disabled", "tracked_official_only"} \
                and str(c.get("candidate_id")) not in opp_products:
            warnings.append(
                f"{c.get('candidate_id')}: tracked/configured candidate has no source opportunity row")

    print(f"Expansion inventory validation: {len(opportunities)} source opportunities, "
          f"{len(candidates)} product candidates")
    print(f"  lifecycle states declared: {len(states)}   proof levels declared: {len(levels)}")
    print(f"  scoring dimensions: {len(weights)}   weight total: {sum(weights.values())}   "
          f"max total: {scoring.get('max_total')}")
    print(f"  tiers (recomputed): A={tier_counts.get('A', 0)} B={tier_counts.get('B', 0)} "
          f"C={tier_counts.get('C', 0)}")
    print(f"  product references checked against {len(known_products)} configured products "
          f"({len(enabled_products)} with enabled ingestion)")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    print(f"  {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(validate())
