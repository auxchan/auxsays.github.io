#!/usr/bin/env python3
"""Validate the expansion planning inventories.

`_data/expansion_source_opportunities.yml` and `_data/expansion_product_candidates.yml` are
planning data, not production config -- but planning data that quietly drifts out of agreement
with the repo is worse than none, because it produces confident roadmaps about products and
sources that no longer exist as described.

WHAT THIS PINS (and why each rule exists):

* INDEPENDENT PROOF DIMENSIONS. There is no single ascending proof ladder. helpx.adobe.com is
  reachable locally and times out on every Actions User-Agent class, so `local_reachable` cannot
  imply `actions_reachable`; forum.blackmagicdesign.com answers with HTTP 202 and a zero-byte
  challenge body, so `local_reachable: proven` legitimately coexists with
  `structure_proven: failed`. Each dimension is measured or not, independently. Only
  `production_proven` is derived-constrained: it requires actions + structure + patch specificity
  + supply to be proven, because that is what "a scheduled run produced accepted evidence" means.

* NO BORROWED CREDIBILITY. `github_issues` is production-proven for obs-studio. That is transport
  PRECEDENT for a ComfyUI lane, not proof of ComfyUI patch identity. Precedent lives in
  `transport_precedent` (free text, never a proof value) and can never satisfy a proof gate.

* FRESHNESS. A measurement without an expiry silently becomes a claim. Every opportunity that has
  measured anything carries `last_checked` + `recheck_after_days`; stale proof is surfaced and
  cannot support `ready_to_build`. All-unknown proof with no `last_checked` is `never_measured`.

* PRIORITY IS NOT READINESS. `priority_score`/`priority_tier` answer "would this be valuable";
  `readiness` answers "do we have enough proof to build it now". Readiness is recomputed here and
  fails closed: a large priority score can never bypass missing proof.

* GROUNDED HARD-GATE SCORES. The four feasibility-critical dimensions each carry a
  `score_basis` with an explicit confidence. A high number with low/unproven evidence cannot
  manufacture `ready_to_build`.

* EXPLICIT SOURCE-AUDIT COVERAGE. Every enabled-ingestion product and every declared strategic
  product must have a `product_source_audit` entry, so "no source research done yet" is a stated
  state rather than an absence nobody notices.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/validate_expansion_inventory.py
Exit 0 clean, 1 on any error.
"""
from __future__ import annotations

import datetime as _dt
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
    "proof", "measurement", "reuse_scope", "shared_framework", "status", "next_experiment",
)
CANDIDATE_REQUIRED = (
    "candidate_id", "product_name", "vendor", "category", "repo_state", "product_scope",
    "support_lifecycle", "scores", "score_basis", "priority_score", "priority_tier",
    "readiness", "opportunity_refs", "known_sources", "recommended_next_step",
)
LANES = {"official", "consensus"}
ORIGINS = {"official", "community"}

# Dimensions that gate feasibility, so each needs a stated evidence basis.
HARD_GATE_DIMENSIONS = (
    "official_source_quality", "consensus_source_quality",
    "automation_feasibility", "version_identifiability",
)
CONFIDENCE_VALUES = ("high", "medium", "low", "unproven")
# Only these confidences may support ready_to_build.
READY_CONFIDENCES = {"high", "medium"}

READINESS_VALUES = ("ready_to_build", "prove_source", "defer")
AUDIT_STATES = (
    "opportunities_identified", "needs_source_research",
    "no_viable_source_found", "production_sources_sufficient",
)
PRODUCT_SCOPES = (
    "generic_cloud_service", "installable_desktop_client", "installable_mobile_client",
    "separately_versioned_application", "scope_split_required",
)
SUPPORT_LIFECYCLES = (
    "current", "legacy_supported", "extended_security_only", "end_of_support", "unknown",
)
# Lifecycle states that may support ready_to_build. `unknown` must never behave like `current`.
READY_LIFECYCLES = {"current", "legacy_supported"}

FRESHNESS_CURRENT = "current"
FRESHNESS_STALE = "stale"
FRESHNESS_NEVER = "never_measured"


def _load(path: Path) -> Any:
    if not path.exists():
        raise SystemExit(f"missing required file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _today() -> _dt.date:
    return _dt.date.today()


def freshness_of(opportunity: dict[str, Any], today: _dt.date | None = None) -> tuple[str, str]:
    """(state, detail) from last_checked + recheck_after_days. Never guesses a date."""
    today = today or _today()
    proof = opportunity.get("proof") or {}
    measured_anything = any(
        str(v) in {"proven", "failed"} for v in proof.values()) if isinstance(proof, dict) else False
    last = opportunity.get("last_checked")
    if last in (None, "", "never"):
        if measured_anything:
            return FRESHNESS_NEVER, "proof recorded without last_checked"
        return FRESHNESS_NEVER, "nothing measured"
    if isinstance(last, _dt.datetime):
        last = last.date()
    if not isinstance(last, _dt.date):
        return FRESHNESS_STALE, f"last_checked {last!r} is not a date"
    window = opportunity.get("recheck_after_days")
    if not isinstance(window, int) or isinstance(window, bool) or window <= 0:
        return FRESHNESS_STALE, f"recheck_after_days {window!r} is not a positive integer"
    age = (today - last).days
    if age > window:
        return FRESHNESS_STALE, f"measured {age}d ago, recheck window {window}d"
    return FRESHNESS_CURRENT, f"measured {age}d ago, recheck window {window}d"


def derive_readiness(
    candidate: dict[str, Any],
    opportunities: dict[str, dict[str, Any]],
    today: _dt.date | None = None,
) -> tuple[str, list[str]]:
    """Deterministically derive readiness. FAILS CLOSED: anything unproven means not ready.

    ready_to_build requires ALL of:
      1. a deterministic OFFICIAL path -- official_source_quality >= 3;
      2. exact version identity plausibly enforceable -- version_identifiability >= 4;
      3. a deterministic CONSENSUS discovery path -- a referenced consensus opportunity whose
         structure is proven;
      4. that consensus transport Actions-proven or production-proven (transport_precedent from
         another product never counts), AND its patch specificity proven;
      5. no declared readiness blocker, and no scope split still unresolved;
      6. every hard-gate score backed by high/medium confidence;
      7. supporting proof not stale;
      8. support lifecycle declared and not unknown/end-of-support.
    Returns (readiness, reasons_it_is_not_ready).
    """
    today = today or _today()
    scores = candidate.get("scores") or {}
    reasons: list[str] = []

    def score(name: str) -> int:
        value = scores.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else -1

    if score("official_source_quality") < 3:
        reasons.append("no deterministic official path (official_source_quality < 3)")
    if score("version_identifiability") < 4:
        reasons.append("exact version identity not plausibly enforceable (version_identifiability < 4)")

    refs = candidate.get("opportunity_refs") or []
    consensus = [opportunities[r] for r in refs
                 if r in opportunities and opportunities[r].get("lane") == "consensus"]
    if not consensus:
        reasons.append("no referenced consensus discovery opportunity")
    else:
        def proven(o: dict[str, Any], dim: str) -> bool:
            return str((o.get("proof") or {}).get(dim)) == "proven"

        structural = [o for o in consensus if proven(o, "structure_proven")]
        if not structural:
            reasons.append("no referenced consensus opportunity with structure_proven")
        runnable = [o for o in structural
                    if proven(o, "actions_reachable") or proven(o, "production_proven")]
        if structural and not runnable:
            reasons.append("consensus transport is not Actions-proven or production-proven "
                           "(transport precedent elsewhere does not count)")
        identified = [o for o in runnable if proven(o, "patch_specificity_proven")]
        if runnable and not identified:
            reasons.append("consensus patch specificity unproven for this product")
        fresh = [o for o in identified if freshness_of(o, today)[0] == FRESHNESS_CURRENT]
        if identified and not fresh:
            reasons.append("supporting proof is stale")

    if candidate.get("readiness_blockers"):
        reasons.append(f"{len(candidate['readiness_blockers'])} declared readiness blocker(s)")
    if candidate.get("product_scope") == "scope_split_required":
        reasons.append("product scope unresolved (scope_split_required)")
    if str(candidate.get("support_lifecycle")) not in READY_LIFECYCLES:
        reasons.append(f"support lifecycle {candidate.get('support_lifecycle')!r} cannot support a build")

    basis = candidate.get("score_basis") or {}
    for dim in HARD_GATE_DIMENSIONS:
        entry = basis.get(dim) if isinstance(basis, dict) else None
        conf = str((entry or {}).get("confidence")) if isinstance(entry, dict) else None
        if conf not in READY_CONFIDENCES:
            reasons.append(f"{dim} evidence confidence {conf!r} is too weak to build on")

    if reasons:
        # `defer` only when the product is also low priority; otherwise the work is to prove it.
        tier = str(candidate.get("priority_tier"))
        return ("defer" if tier == "C" else "prove_source"), reasons
    return "ready_to_build", []


def validate() -> int:  # noqa: PLR0912, PLR0915 - one linear pass keeps the rules readable
    errors: list[str] = []
    warnings: list[str] = []
    today = _today()

    products = _load(PRODUCTS_FILE)
    plist = products if isinstance(products, list) else products.get("products", [])
    configured_products = {str(p.get("product_id")) for p in plist if p.get("product_id")}

    ingestion = _load(INGESTION_FILE)
    slist = ingestion if isinstance(ingestion, list) else ingestion.get("sources", [])
    enabled_ingestion_products = {
        str(s.get("product_id")) for s in slist if s.get("enabled") and s.get("product_id")
    }

    # ---------------- source opportunities ----------------------------------------------
    src = _load(SOURCES_FILE)
    states = src.get("lifecycle_states") or {}
    proof_dims = src.get("proof_dimensions") or {}
    proof_values = src.get("proof_values") or {}
    frameworks = src.get("shared_frameworks") or {}
    strategic = src.get("strategic_priority_products") or []
    audit = src.get("product_source_audit") or {}

    if not isinstance(states, dict) or not states:
        errors.append("expansion_source_opportunities.yml: lifecycle_states must be a non-empty map")
    if not isinstance(proof_dims, dict) or not proof_dims:
        errors.append("expansion_source_opportunities.yml: proof_dimensions must be a non-empty map")
    if not isinstance(proof_values, dict) or not proof_values:
        errors.append("expansion_source_opportunities.yml: proof_values must be a non-empty map")
    if "proof_levels" in src:
        errors.append("expansion_source_opportunities.yml: the single ascending proof_levels ladder "
                      "was replaced by independent proof_dimensions and must not return")

    required_dims = tuple(proof_dims)
    allowed_values = set(proof_values)
    if not isinstance(frameworks, dict) or not frameworks:
        errors.append("expansion_source_opportunities.yml: shared_frameworks must be a non-empty map")

    opportunities = src.get("opportunities") or []
    by_id: dict[str, dict[str, Any]] = {}
    stale_ids: list[str] = []
    never_ids: list[str] = []

    for i, o in enumerate(opportunities):
        if not isinstance(o, dict):
            errors.append(f"opportunity[{i}] is not a mapping")
            continue
        oid = str(o.get("opportunity_id") or f"<index {i}>")
        for field in OPPORTUNITY_REQUIRED:
            if field not in o:
                errors.append(f"{oid}: missing required field '{field}'")
        if oid in by_id:
            errors.append(f"{oid}: duplicate opportunity_id")
        by_id[oid] = o

        if "proof_level" in o:
            errors.append(f"{oid}: singular 'proof_level' is no longer a valid field "
                          "(use independent proof dimensions)")
        if o.get("status") not in states:
            errors.append(f"{oid}: status {o.get('status')!r} is not a declared lifecycle state")
        if o.get("lane") not in LANES:
            errors.append(f"{oid}: lane {o.get('lane')!r} must be one of {sorted(LANES)}")
        if o.get("official_or_community") not in ORIGINS:
            errors.append(f"{oid}: official_or_community {o.get('official_or_community')!r} invalid")

        framework = o.get("shared_framework")
        if frameworks and framework not in frameworks:
            errors.append(f"{oid}: shared_framework {framework!r} is not a declared framework")
        elif framework in frameworks:
            declared_lane = (frameworks[framework] or {}).get("lane")
            # The Zendesk lesson: Help Center ARTICLES (official ingestion) and COMMUNITY POSTS
            # (consensus discovery) are different endpoint families with different contracts and
            # different acceptance semantics. A framework pinned to one lane cannot serve the other.
            if declared_lane in LANES and declared_lane != o.get("lane"):
                errors.append(f"{oid}: lane {o.get('lane')!r} contradicts shared_framework "
                              f"{framework!r} declared lane {declared_lane!r}")

        # --- independent proof dimensions ---
        proof = o.get("proof")
        if not isinstance(proof, dict):
            errors.append(f"{oid}: proof must be a mapping of independent dimensions")
        else:
            for dim in required_dims:
                if dim not in proof:
                    errors.append(f"{oid}: proof missing required dimension '{dim}'")
            for dim, value in proof.items():
                if dim not in required_dims:
                    errors.append(f"{oid}: proof has undeclared dimension '{dim}'")
                elif str(value) not in allowed_values:
                    errors.append(f"{oid}: proof.{dim} value {value!r} is not a declared proof value")
            if str(proof.get("production_proven")) == "proven":
                for dim in ("actions_reachable", "structure_proven",
                            "patch_specificity_proven", "supply_proven"):
                    if str(proof.get(dim)) != "proven":
                        errors.append(
                            f"{oid}: production_proven=proven requires {dim}=proven "
                            f"(got {proof.get(dim)!r})")
            if o.get("transport_precedent") and str(proof.get("actions_reachable")) == "proven" \
                    and str(proof.get("patch_specificity_proven")) != "proven":
                # Legal, but worth surfacing: precedent plus a runnable transport is the exact
                # shape that tempts a premature "ready" call.
                warnings.append(f"{oid}: transport_precedent recorded alongside unproven patch "
                                "specificity -- precedent must not be read as product proof")

        # --- freshness ---
        state, detail = freshness_of(o, today)
        if state == FRESHNESS_STALE:
            if not isinstance(o.get("last_checked"), (_dt.date, _dt.datetime)):
                errors.append(f"{oid}: malformed freshness metadata -- {detail}")
            elif not isinstance(o.get("recheck_after_days"), int) or isinstance(
                    o.get("recheck_after_days"), bool) or o.get("recheck_after_days", 0) <= 0:
                errors.append(f"{oid}: malformed freshness metadata -- {detail}")
            else:
                stale_ids.append(oid)
                warnings.append(f"{oid}: STALE measurement -- {detail}")
        elif state == FRESHNESS_NEVER:
            never_ids.append(oid)
            if detail == "proof recorded without last_checked":
                errors.append(f"{oid}: proof dimensions are measured but last_checked is absent")

        for key in ("product_ids", "reuse_scope"):
            value = o.get(key)
            if value is None:
                continue
            if not isinstance(value, list):
                errors.append(f"{oid}: {key} must be a list")
                continue
            for pid in value:
                if str(pid) not in configured_products:
                    errors.append(f"{oid}: {key} references unknown product_id {pid!r}")

    # --- product source audit -------------------------------------------------------------
    if not isinstance(audit, dict):
        errors.append("product_source_audit must be a mapping of product_id -> audit entry")
        audit = {}
    audit_state_counts: dict[str, int] = {}
    for pid, entry in audit.items():
        pid = str(pid)
        if pid not in configured_products:
            errors.append(f"product_source_audit[{pid}]: unknown product_id")
        if not isinstance(entry, dict):
            errors.append(f"product_source_audit[{pid}]: entry must be a mapping")
            continue
        state = str(entry.get("state"))
        if state not in AUDIT_STATES:
            errors.append(f"product_source_audit[{pid}]: state {entry.get('state')!r} invalid")
        audit_state_counts[state] = audit_state_counts.get(state, 0) + 1
        refs = entry.get("opportunity_ids")
        if refs is None or not isinstance(refs, list):
            errors.append(f"product_source_audit[{pid}]: opportunity_ids must be a list")
            continue
        for ref in refs:
            if str(ref) not in by_id:
                errors.append(f"product_source_audit[{pid}]: references unknown opportunity {ref!r}")
        if state == "opportunities_identified" and not refs:
            errors.append(f"product_source_audit[{pid}]: state 'opportunities_identified' requires "
                          "at least one referenced opportunity")

    for pid in sorted(enabled_ingestion_products):
        if pid not in audit:
            errors.append(f"product_source_audit: missing entry for enabled-ingestion product {pid}")
    for pid in [str(p) for p in strategic]:
        if pid not in configured_products:
            errors.append(f"strategic_priority_products: {pid} is not a configured product")
        elif pid not in audit:
            errors.append(f"product_source_audit: missing entry for strategic product {pid}")
    for pid in sorted(configured_products - set(audit)):
        warnings.append(f"product_source_audit: no entry for configured product {pid} "
                        "(disabled and not declared strategic)")

    # ---------------- product candidates ------------------------------------------------
    cand = _load(CANDIDATES_FILE)
    scoring = cand.get("scoring") or {}
    dims = scoring.get("dimensions") or {}
    scale = scoring.get("scale") or {}
    tiers = scoring.get("tiers") or {}
    repo_states = cand.get("repo_states") or {}

    # The file declares its own vocabularies so a reader never has to open this script. Pin them
    # against the constants used to enforce them, in BOTH directions, so the two cannot drift.
    for key, expected in (("readiness_model", READINESS_VALUES),
                          ("confidence_values", CONFIDENCE_VALUES),
                          ("product_scopes", PRODUCT_SCOPES),
                          ("support_lifecycles", SUPPORT_LIFECYCLES)):
        declared = cand.get(key)
        if key == "readiness_model":
            declared = (declared or {}).get("values")
        if not isinstance(declared, dict) or not declared:
            errors.append(f"expansion_product_candidates.yml: {key} must declare its vocabulary")
            continue
        if set(declared) != set(expected):
            errors.append(f"{key} declares {sorted(declared)} but the validator enforces "
                          f"{sorted(expected)}")
    gate_doc = (cand.get("readiness_model") or {}).get("ready_to_build_requires")
    if not isinstance(gate_doc, list) or not gate_doc:
        errors.append("readiness_model.ready_to_build_requires must list the derivation gates")

    lo, hi = int(scale.get("min", 0)), int(scale.get("max", 5))
    weights = {k: int(v["weight"]) for k, v in dims.items()}
    if sum(weights.values()) != int(scoring.get("weight_total", -1)):
        errors.append(f"scoring.weight_total {scoring.get('weight_total')!r} != sum of weights "
                      f"{sum(weights.values())}")
    if int(scoring.get("max_total", -1)) != hi * sum(weights.values()):
        errors.append(f"scoring.max_total {scoring.get('max_total')!r} != "
                      f"{hi * sum(weights.values())}")
    for name in ("A", "B", "C"):
        if name not in tiers:
            errors.append(f"scoring.tiers missing tier {name}")
    for dim in HARD_GATE_DIMENSIONS:
        if dim not in weights:
            errors.append(f"hard-gate dimension {dim} is not a declared scoring dimension")

    def compute_priority(scores: dict[str, Any]) -> int:
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
    readiness_counts = {k: 0 for k in READINESS_VALUES}
    scope_counts: dict[str, int] = {}
    lifecycle_counts: dict[str, int] = {}

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
        for legacy in ("total_score", "tier"):
            if legacy in c:
                errors.append(f"{cid}: '{legacy}' was renamed to distinguish strategic priority "
                              "from implementation readiness")

        state = c.get("repo_state")
        if state not in repo_states:
            errors.append(f"{cid}: repo_state {state!r} is not a declared repo_state")
        elif state == "untracked" and cid in configured_products:
            errors.append(f"{cid}: marked untracked but present in patch_products.yml")
        elif state == "configured_disabled":
            if cid not in configured_products:
                errors.append(f"{cid}: marked configured_disabled but absent from patch_products.yml")
            elif cid in enabled_ingestion_products:
                errors.append(f"{cid}: marked configured_disabled but its ingestion source is enabled")
        elif state == "tracked_official_only" and cid not in enabled_ingestion_products:
            errors.append(f"{cid}: marked tracked_official_only but has no enabled ingestion source")

        scope = str(c.get("product_scope"))
        if scope not in PRODUCT_SCOPES:
            errors.append(f"{cid}: product_scope {c.get('product_scope')!r} is not allowed")
        scope_counts[scope] = scope_counts.get(scope, 0) + 1
        if scope == "scope_split_required" and not c.get("scope_split_note"):
            errors.append(f"{cid}: scope_split_required must record scope_split_note "
                          "naming the separately versioned variant to evaluate")

        lifecycle = str(c.get("support_lifecycle"))
        if lifecycle not in SUPPORT_LIFECYCLES:
            errors.append(f"{cid}: support_lifecycle {c.get('support_lifecycle')!r} is not allowed")
        lifecycle_counts[lifecycle] = lifecycle_counts.get(lifecycle, 0) + 1

        refs = c.get("opportunity_refs")
        if refs is None or not isinstance(refs, list):
            errors.append(f"{cid}: opportunity_refs must be a list (may be empty)")
            refs = []
        for ref in refs:
            if str(ref) not in by_id:
                errors.append(f"{cid}: opportunity_refs references unknown opportunity {ref!r}")

        # --- grounded hard-gate scores ---
        basis = c.get("score_basis")
        if not isinstance(basis, dict):
            errors.append(f"{cid}: score_basis must be a mapping")
            basis = {}
        for dim in HARD_GATE_DIMENSIONS:
            entry = basis.get(dim)
            if not isinstance(entry, dict):
                errors.append(f"{cid}: score_basis missing an entry for hard-gate dimension '{dim}'")
                continue
            if str(entry.get("confidence")) not in CONFIDENCE_VALUES:
                errors.append(f"{cid}: score_basis.{dim}.confidence "
                              f"{entry.get('confidence')!r} is not allowed")
            if not str(entry.get("basis") or "").strip():
                errors.append(f"{cid}: score_basis.{dim}.basis must be non-empty")
        for dim in basis:
            if dim not in HARD_GATE_DIMENSIONS:
                errors.append(f"{cid}: score_basis has an entry for non-hard-gate dimension '{dim}'")

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
            continue

        total = compute_priority(scores)
        stored_total = c.get("priority_score")
        if not isinstance(stored_total, int) or isinstance(stored_total, bool):
            errors.append(f"{cid}: priority_score {stored_total!r} must be an integer")
        elif stored_total != total:
            errors.append(f"{cid}: stored priority_score {stored_total!r} != recomputed {total}")
        tier = compute_tier(total, scores)
        if str(c.get("priority_tier")) != tier:
            errors.append(f"{cid}: stored priority_tier {c.get('priority_tier')!r} != recomputed {tier}")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        stored_readiness = str(c.get("readiness"))
        if stored_readiness not in READINESS_VALUES:
            errors.append(f"{cid}: readiness {c.get('readiness')!r} is not allowed")
        derived, reasons = derive_readiness(c, by_id, today)
        if stored_readiness != derived:
            errors.append(f"{cid}: stored readiness {stored_readiness!r} != derived {derived!r}"
                          + (f" -- unmet: {reasons[0]}" if reasons else ""))
        readiness_counts[derived] = readiness_counts.get(derived, 0) + 1
        if derived == "ready_to_build" and reasons:
            errors.append(f"{cid}: internal inconsistency -- ready_to_build with unmet reasons")

        if not c.get("known_sources"):
            warnings.append(f"{cid}: no known_sources recorded")

    print("Expansion inventory validation")
    print(f"  source opportunities: {len(opportunities)}   product candidates: {len(candidates)}")
    print(f"  proof dimensions: {len(required_dims)} (independent)   "
          f"proof values: {sorted(allowed_values)}")
    print(f"  freshness: {len(opportunities) - len(stale_ids) - len(never_ids)} current, "
          f"{len(stale_ids)} stale, {len(never_ids)} never measured")
    print(f"  shared frameworks declared: {len(frameworks)}")
    print(f"  scoring dimensions: {len(weights)}   weight total: {sum(weights.values())}   "
          f"max total: {scoring.get('max_total')}")
    print(f"  strategic priority tier (recomputed): A={tier_counts.get('A', 0)} "
          f"B={tier_counts.get('B', 0)} C={tier_counts.get('C', 0)}")
    print(f"  implementation readiness (recomputed): "
          + "  ".join(f"{k}={readiness_counts.get(k, 0)}" for k in READINESS_VALUES))
    print(f"  product scope: {scope_counts}")
    print(f"  support lifecycle: {lifecycle_counts}")
    print(f"  source-audit entries: {len(audit)}  states: {audit_state_counts}")
    print(f"  configured products: {len(configured_products)}   "
          f"enabled-ingestion products: {len(enabled_ingestion_products)}   "
          f"declared strategic: {len(strategic)}")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    print(f"  {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(validate())
