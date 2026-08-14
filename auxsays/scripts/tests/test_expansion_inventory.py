#!/usr/bin/env python3
"""Tests for validate_expansion_inventory.py.

A validator that cannot fail is ceremony, so every rule is exercised by MUTATING a synthetic
inventory. Just as important: several mutations must still PASS, because a proof model that
rejects every honest combination is as useless as one that accepts everything. The committed
inventories are validated as-is so the planning data cannot drift out of agreement with
patch_products.yml unnoticed.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_expansion_inventory.py
"""
from __future__ import annotations

import copy
import datetime as dt
import io
import re
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

TODAY = dt.date.today()
FRESH = TODAY - dt.timedelta(days=2)
ANCIENT = TODAY - dt.timedelta(days=400)


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


# ---------------------------------------------------------------------------------------
# Synthetic fixtures: the smallest inventories that satisfy every rule, including ONE
# candidate that legitimately reaches ready_to_build so the gate is provably not vacuous.
# ---------------------------------------------------------------------------------------
PRODUCTS = [
    {"product_id": "prod-enabled", "product_name": "Enabled"},
    {"product_id": "prod-disabled", "product_name": "Disabled"},
]
INGESTION = [
    {"product_id": "prod-enabled", "enabled": True, "ingestion": {"adapter": "x"}},
    {"product_id": "prod-disabled", "enabled": False, "ingestion": {"adapter": "y"}},
]
DIMS_PROOF = ("local_reachable", "actions_reachable", "structure_proven",
              "patch_specificity_proven", "supply_proven", "production_proven")


def proof(**over):
    base = {d: "unknown" for d in DIMS_PROOF}
    base.update(over)
    return base


def opportunity(oid, lane="consensus", framework="fw-consensus", **over):
    o = {
        "opportunity_id": oid, "product_ids": ["prod-enabled"], "source_name": "S",
        "source_type": "t", "lane": lane, "official_or_community":
            "community" if lane == "consensus" else "official",
        "domain": "example.test", "entry_point": "https://example.test/",
        "discovery_method": "m", "auth_requirement": "none",
        "proof": proof(local_reachable="proven", structure_proven="proven"),
        "last_checked": FRESH, "recheck_after_days": 30,
        "measurement": "200 OK", "reuse_scope": ["prod-enabled"],
        "shared_framework": framework, "status": "transport_proven",
        "next_experiment": "probe",
    }
    o.update(over)
    return o


SOURCES = {
    "schema_version": 1,
    "lifecycle_states": {"needs_probe": "n", "transport_proven": "t", "viable": "v",
                         "blocked": "b", "needs_policy_decision": "p"},
    "proof_dimensions": {d: "d" for d in DIMS_PROOF},
    "proof_values": {"proven": "p", "failed": "f", "unknown": "u", "not_applicable": "n"},
    "shared_frameworks": {
        # The Zendesk lesson in miniature: same vendor family, different lane, different contract.
        "fw-consensus": {"lane": "consensus", "contract": "community posts", "reuse_note": "-"},
        "fw-official": {"lane": "official", "contract": "help-center articles", "reuse_note": "-"},
        "fw-any": {"lane": "any", "contract": "unknown", "reuse_note": "-"},
    },
    "strategic_priority_products": ["prod-enabled"],
    "product_source_audit": {
        "prod-enabled": {"state": "opportunities_identified",
                         "opportunity_ids": ["opp-ready", "opp-local"], "notes": "-"},
    },
    "opportunities": [
        # Fully proven: the only shape that may support ready_to_build.
        opportunity("opp-ready", proof=proof(
            local_reachable="proven", actions_reachable="proven", structure_proven="proven",
            patch_specificity_proven="proven", supply_proven="proven", production_proven="proven"),
            status="viable", recheck_after_days=14),
        # Honest partial: local + structure proven, Actions never measured.
        opportunity("opp-local"),
        opportunity("opp-official", lane="official", framework="fw-official"),
    ],
}

DIMS = {
    "user_impact": 3, "patch_risk": 4, "update_frequency": 2, "commercial_value": 3,
    "official_source_quality": 3, "consensus_source_quality": 4, "automation_feasibility": 5,
    "source_diversity": 2, "version_identifiability": 4, "maintenance_cost": 2,
    "cross_product_reuse": 2,
}
HARD = vei.HARD_GATE_DIMENSIONS


def basis(conf="high"):
    return {d: {"confidence": conf, "basis": f"measured for this product ({d})"} for d in HARD}


def candidate(cid, scores_value, *, repo_state, refs, readiness, tier,
              scope="installable_desktop_client", lifecycle="current", conf="high", **over):
    scores = {k: scores_value for k in DIMS}
    c = {
        "candidate_id": cid, "product_name": cid, "vendor": "V", "category": "c",
        "repo_state": repo_state, "product_scope": scope, "support_lifecycle": lifecycle,
        "scores": scores, "score_basis": basis(conf),
        "priority_score": sum(scores[k] * DIMS[k] for k in DIMS), "priority_tier": tier,
        "readiness": readiness, "readiness_blockers": [], "opportunity_refs": refs,
        "known_sources": ["opp"], "recommended_next_step": "go",
    }
    c.update(over)
    return c


CANDIDATES = {
    "schema_version": 1,
    "readiness_model": {
        "values": {k: "-" for k in vei.READINESS_VALUES},
        "ready_to_build_requires": ["documented gates"],
        "never_sufficient": ["a high priority score"],
    },
    "confidence_values": {k: "-" for k in vei.CONFIDENCE_VALUES},
    "product_scopes": {k: "-" for k in vei.PRODUCT_SCOPES},
    "support_lifecycles": {k: "-" for k in vei.SUPPORT_LIFECYCLES},
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
        candidate("prod-enabled", 5, repo_state="tracked_official_only", refs=["opp-ready"],
                  readiness="ready_to_build", tier="A"),
        candidate("prod-disabled", 5, repo_state="configured_disabled", refs=["opp-local"],
                  readiness="prove_source", tier="A"),
        candidate("brand-new", 1, repo_state="untracked", refs=[], readiness="defer", tier="C"),
    ],
}


def run_validator(sources: dict, candidates: dict, products=None, ingestion=None):
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


def _apply(fn, target):
    s, c = copy.deepcopy(SOURCES), copy.deepcopy(CANDIDATES)
    fn(c if target == "candidates" else s)
    return s, c


def must_fail(label, fn, target="candidates", needle=""):
    s, c = _apply(fn, target)
    rc, out = run_validator(s, c)
    ok = rc == 1 and (needle in out if needle else True)
    check(label, ok, f"rc={rc}\n{out.strip()[-500:]}")


def must_pass(label, fn, target="candidates", needle=""):
    s, c = _apply(fn, target)
    rc, out = run_validator(s, c)
    ok = rc == 0 and (needle in out if needle else True)
    check(label, ok, f"rc={rc}\n{out.strip()[-500:]}")


def opp(s, oid):
    return next(o for o in s["opportunities"] if o["opportunity_id"] == oid)


def run() -> int:  # noqa: PLR0915
    print("=" * 66)
    print("EXPANSION INVENTORY VALIDATOR")
    print("=" * 66)

    rc, out = run_validator(SOURCES, CANDIDATES)
    check("synthetic baseline validates clean", rc == 0, out)
    check("(1) six independent proof dimensions parse", "proof dimensions: 6 (independent)" in out, out)
    check("baseline recomputes 1 ready_to_build / 1 prove_source / 1 defer -- the gate is NOT vacuous",
          "ready_to_build=1  prove_source=1  defer=1" in out, out)

    # --- committed inventories -----------------------------------------------------------
    buf = io.StringIO()
    with redirect_stdout(buf):
        real_rc = vei.validate()
    real = buf.getvalue()
    check("committed inventories validate clean", real_rc == 0, real[-700:])
    m = re.search(r"source opportunities: (\d+)\s+product candidates: (\d+)", real)
    check("committed inventories are non-trivial (>=20 opportunities, >=40 candidates)",
          bool(m) and int(m.group(1)) >= 20 and int(m.group(2)) >= 40, real[:200])

    # =====================================================================================
    # PROOF MODEL -- independent dimensions, no ascending ladder
    # =====================================================================================
    # (2) and (3): the combinations HelpX and Blackmagic actually produced must be legal.
    must_pass("(2) local+structure proven with Actions UNKNOWN is valid",
              lambda s: opp(s, "opp-local")["proof"].update(actions_reachable="unknown"),
              target="sources")
    must_pass("(3) local+structure proven with Actions FAILED is valid",
              lambda s: opp(s, "opp-local")["proof"].update(actions_reachable="failed"),
              target="sources")
    must_pass("local proven while structure FAILED is valid (202 challenge-body shape)",
              lambda s: opp(s, "opp-local")["proof"].update(structure_proven="failed"),
              target="sources")
    must_pass("not_applicable is a legal proof value",
              lambda s: opp(s, "opp-local")["proof"].update(patch_specificity_proven="not_applicable"),
              target="sources")

    must_fail("(4) production_proven with Actions unknown is rejected",
              lambda s: opp(s, "opp-ready")["proof"].update(actions_reachable="unknown"),
              target="sources", needle="requires actions_reachable=proven")
    must_fail("(5) production_proven without patch-specificity proof is rejected",
              lambda s: opp(s, "opp-ready")["proof"].update(patch_specificity_proven="unknown"),
              target="sources", needle="requires patch_specificity_proven=proven")
    must_fail("production_proven without supply proof is rejected",
              lambda s: opp(s, "opp-ready")["proof"].update(supply_proven="unknown"),
              target="sources", needle="requires supply_proven=proven")
    must_fail("(6) an undeclared proof value is rejected",
              lambda s: opp(s, "opp-local")["proof"].update(structure_proven="probably"),
              target="sources", needle="not a declared proof value")
    must_fail("(7) a missing proof dimension is rejected",
              lambda s: opp(s, "opp-local")["proof"].pop("supply_proven"),
              target="sources", needle="missing required dimension")
    must_fail("an undeclared proof dimension is rejected",
              lambda s: opp(s, "opp-local")["proof"].update(vibes_proven="proven"),
              target="sources", needle="undeclared dimension")
    must_fail("the retired singular proof_level field is rejected on an opportunity",
              lambda s: opp(s, "opp-local").update(proof_level="structure_proven"),
              target="sources", needle="no longer a valid field")
    must_fail("a resurrected proof_levels ladder is rejected",
              lambda s: s.update(proof_levels={"none": "-"}),
              target="sources", needle="must not return")

    # Borrowed credibility: precedent can never substitute for product proof.
    def precedent_only(s):
        o = opp(s, "opp-local")
        o["transport_precedent"] = "github_issues is production-proven for another product"
        o["proof"].update(actions_reachable="proven")
    must_pass("transport_precedent is legal but only warns, never proves",
              precedent_only, target="sources", needle="precedent must not be read as product proof")

    def precedent_cannot_build(s_or_c):
        pass
    s, c = copy.deepcopy(SOURCES), copy.deepcopy(CANDIDATES)
    o = opp(s, "opp-ready")
    o["transport_precedent"] = "works for a different product"
    o["proof"].update(patch_specificity_proven="unknown", production_proven="unknown")
    rc2, out2 = run_validator(s, c)
    check("transport precedent cannot make a lane ready_to_build",
          rc2 == 1 and "stored readiness 'ready_to_build' != derived 'prove_source'" in out2,
          out2[-400:])

    # =====================================================================================
    # FRESHNESS
    # =====================================================================================
    must_fail("(8) a malformed last_checked is rejected",
              lambda s: opp(s, "opp-local").update(last_checked="last Tuesday"),
              target="sources", needle="malformed freshness metadata")
    must_fail("a zero/negative recheck window is rejected",
              lambda s: opp(s, "opp-local").update(recheck_after_days=0),
              target="sources", needle="malformed freshness metadata")
    must_fail("a non-integer recheck window is rejected",
              lambda s: opp(s, "opp-local").update(recheck_after_days="thirty"),
              target="sources", needle="malformed freshness metadata")
    must_fail("measured proof with NO last_checked is rejected",
              lambda s: opp(s, "opp-local").pop("last_checked"),
              target="sources", needle="last_checked is absent")
    must_pass("an all-unknown opportunity with no last_checked reads as never_measured",
              lambda s: opp(s, "opp-local").update(proof=proof(), last_checked=None),
              target="sources", needle="never measured")

    s, c = copy.deepcopy(SOURCES), copy.deepcopy(CANDIDATES)
    opp(s, "opp-local")["last_checked"] = ANCIENT
    rc3, out3 = run_validator(s, c)
    check("(9) a stale measurement is surfaced deterministically",
          "STALE measurement" in out3 and "1 stale" in out3, out3[-400:])

    s, c = copy.deepcopy(SOURCES), copy.deepcopy(CANDIDATES)
    opp(s, "opp-ready")["last_checked"] = ANCIENT
    rc4, out4 = run_validator(s, c)
    check("stale proof cannot keep a product ready_to_build",
          rc4 == 1 and "supporting proof is stale" in out4, out4[-400:])

    # =====================================================================================
    # SOURCE AUDIT
    # =====================================================================================
    must_fail("(10) a missing enabled-product audit entry is rejected",
              lambda s: s["product_source_audit"].pop("prod-enabled"),
              target="sources", needle="missing entry for enabled-ingestion product")
    must_fail("a missing STRATEGIC product audit entry is rejected",
              lambda s: (s["product_source_audit"].pop("prod-enabled"),
                         s.__setitem__("strategic_priority_products", ["prod-enabled"])),
              target="sources", needle="missing entry for")
    must_fail("(11) an invalid audit state is rejected",
              lambda s: s["product_source_audit"]["prod-enabled"].update(state="looking_into_it"),
              target="sources", needle="state 'looking_into_it' invalid")
    must_fail("(12) a dangling opportunity id in an audit entry is rejected",
              lambda s: s["product_source_audit"]["prod-enabled"].update(
                  opportunity_ids=["opp-does-not-exist"]),
              target="sources", needle="references unknown opportunity")
    must_fail("(13) opportunities_identified with zero opportunities is rejected",
              lambda s: s["product_source_audit"]["prod-enabled"].update(opportunity_ids=[]),
              target="sources", needle="requires at least one referenced opportunity")
    must_pass("needs_source_research with zero opportunities is valid (no invented coverage)",
              lambda s: s["product_source_audit"]["prod-enabled"].update(
                  state="needs_source_research", opportunity_ids=[]),
              target="sources")
    must_pass("no_viable_source_found with references is valid",
              lambda s: s["product_source_audit"]["prod-enabled"].update(
                  state="no_viable_source_found"),
              target="sources")
    must_fail("an audit entry for an unknown product is rejected",
              lambda s: s["product_source_audit"].update({"ghost": {"state": "needs_source_research",
                                                                    "opportunity_ids": []}}),
              target="sources", needle="unknown product_id")

    # =====================================================================================
    # PRIORITY vs READINESS
    # =====================================================================================
    must_fail("(14) ready_to_build cannot bypass unproven patch specificity",
              lambda s: opp(s, "opp-ready")["proof"].update(
                  patch_specificity_proven="unknown", production_proven="unknown"),
              target="sources", needle="patch specificity unproven")
    must_fail("ready_to_build cannot bypass an unproven Actions transport",
              lambda s: opp(s, "opp-ready")["proof"].update(
                  actions_reachable="unknown", production_proven="unknown"),
              target="sources", needle="not Actions-proven")
    must_fail("ready_to_build requires a referenced CONSENSUS opportunity",
              lambda c: c["candidates"][0].update(opportunity_refs=["opp-official"]),
              needle="no referenced consensus discovery opportunity")
    must_fail("ready_to_build requires a deterministic official path",
              lambda c: c["candidates"][0]["scores"].update(official_source_quality=1),
              needle="stored priority_score")
    must_fail("a declared readiness blocker prevents ready_to_build",
              lambda c: c["candidates"][0].update(
                  readiness_blockers=["patch identity unmeasured"]),
              needle="declared readiness blocker")
    must_fail("an invalid readiness value is rejected",
              lambda c: c["candidates"][0].update(readiness="probably_fine"),
              needle="is not allowed")
    must_pass("a Tier A product with unproven sources is prove_source, not defer",
              lambda c: c["candidates"][0].update(readiness="prove_source",
                                                  readiness_blockers=["unmeasured"]))
    must_fail("the legacy total_score field name is rejected",
              lambda c: c["candidates"][0].update(total_score=170),
              needle="renamed to distinguish")
    must_fail("the legacy tier field name is rejected",
              lambda c: c["candidates"][0].update(tier="A"),
              needle="renamed to distinguish")

    # =====================================================================================
    # SCORE GROUNDING
    # =====================================================================================
    must_fail("(15) a hard-gate dimension without an evidence basis is rejected",
              lambda c: c["candidates"][0]["score_basis"].pop("automation_feasibility"),
              needle="missing an entry for hard-gate dimension")
    must_fail("(16) an invalid basis confidence is rejected",
              lambda c: c["candidates"][0]["score_basis"]["automation_feasibility"].update(
                  confidence="vibes"),
              needle="is not allowed")
    must_fail("an empty basis string is rejected",
              lambda c: c["candidates"][0]["score_basis"]["automation_feasibility"].update(basis="  "),
              needle="basis must be non-empty")
    must_fail("(17) unproven feasibility evidence cannot manufacture ready_to_build",
              lambda c: c["candidates"][0]["score_basis"]["automation_feasibility"].update(
                  confidence="unproven"),
              needle="too weak to build on")
    must_fail("low version-identifiability evidence cannot manufacture ready_to_build",
              lambda c: c["candidates"][0]["score_basis"]["version_identifiability"].update(
                  confidence="low"),
              needle="too weak to build on")
    must_pass("a MAX score with medium evidence is still allowed to be ready_to_build",
              lambda c: [e.update(confidence="medium")
                         for e in c["candidates"][0]["score_basis"].values()])
    must_fail("a basis entry for a non-hard-gate dimension is rejected",
              lambda c: c["candidates"][0]["score_basis"].update({"user_impact": {
                  "confidence": "high", "basis": "x"}}),
              needle="non-hard-gate dimension")

    # =====================================================================================
    # ZENDESK LANE SEPARATION / PAID API
    # =====================================================================================
    must_fail("(18) an official-lane framework cannot back a consensus opportunity",
              lambda s: opp(s, "opp-local").update(shared_framework="fw-official"),
              target="sources", needle="contradicts shared_framework")
    must_fail("a consensus-lane framework cannot back an official opportunity",
              lambda s: opp(s, "opp-official").update(shared_framework="fw-consensus"),
              target="sources", needle="contradicts shared_framework")
    must_fail("an undeclared shared_framework is rejected",
              lambda s: opp(s, "opp-local").update(shared_framework="fw-imaginary"),
              target="sources", needle="not a declared framework")
    real_src = yaml.safe_load(vei.SOURCES_FILE.read_text(encoding="utf-8"))
    fw = real_src.get("shared_frameworks", {})
    check("(18) committed inventory keeps Zendesk articles and community posts distinct",
          "zendesk_help_center_articles" in fw and "zendesk_community_posts" in fw
          and fw["zendesk_help_center_articles"]["lane"] == "official"
          and fw["zendesk_community_posts"]["lane"] == "consensus",
          str(sorted(fw)))
    elg = next((o for o in real_src["opportunities"]
                if o["opportunity_id"] == "elgato-zendesk-community-posts"), None)
    check("the Elgato consensus opportunity uses the community-posts framework, not articles",
          bool(elg) and elg["shared_framework"] == "zendesk_community_posts"
          and "does NOT supply this transport" in str(elg.get("notes", "")),
          str(elg.get("shared_framework") if elg else None))

    must_pass("(19) a paid/keyed deterministic API is NOT categorically rejected",
              lambda s: opp(s, "opp-local").update(
                  auth_requirement="paid_api_key", status="viable"),
              target="sources")
    brave = next((o for o in real_src["opportunities"]
                  if o["opportunity_id"] == "brave-search-api"), None)
    check("(19) the invented 'paid API is forbidden' doctrine is gone from the committed file",
          bool(brave) and "forbids" not in str(brave) and "paid_api_evaluation" in brave
          and brave["status"] == "needs_policy_decision",
          str(brave.get("status") if brave else None))
    check("the paid-API evaluation records the required decision inputs",
          bool(brave) and all(k in brave["paid_api_evaluation"] for k in
                              ("cost", "key_management", "rate_limits", "reliability", "tos",
                               "vendor_lock_in", "single_source_risk", "deterministic_alternative")),
          str(sorted((brave or {}).get("paid_api_evaluation", {}))))

    # =====================================================================================
    # SCOPE / LIFECYCLE
    # =====================================================================================
    must_fail("(20) scope_split_required without a scope_split_note is rejected",
              lambda c: c["candidates"][0].update(product_scope="scope_split_required"),
              needle="must record scope_split_note")
    must_fail("(20) scope_split_required blocks ready_to_build",
              lambda c: c["candidates"][0].update(product_scope="scope_split_required",
                                                  scope_split_note="evaluate the desktop client"),
              needle="scope unresolved")
    must_fail("an undeclared product_scope is rejected",
              lambda c: c["candidates"][0].update(product_scope="website_probably"),
              needle="is not allowed")
    must_pass("a generic cloud service is a legal scope (not an automatic write-off)",
              lambda c: c["candidates"][2].update(product_scope="generic_cloud_service"))

    must_fail("(21) a missing support_lifecycle is rejected",
              lambda c: c["candidates"][0].pop("support_lifecycle"),
              needle="missing required field 'support_lifecycle'")
    must_fail("(21) an undeclared support_lifecycle is rejected",
              lambda c: c["candidates"][0].update(support_lifecycle="probably_fine"),
              needle="is not allowed")
    must_fail("(22) unknown lifecycle cannot silently behave like current",
              lambda c: c["candidates"][0].update(support_lifecycle="unknown"),
              needle="cannot support a build")
    must_fail("end_of_support cannot be ready_to_build",
              lambda c: c["candidates"][0].update(support_lifecycle="end_of_support"),
              needle="cannot support a build")
    must_fail("extended_security_only cannot be ready_to_build",
              lambda c: c["candidates"][0].update(support_lifecycle="extended_security_only"),
              needle="cannot support a build")
    must_pass("legacy_supported CAN be ready_to_build",
              lambda c: c["candidates"][0].update(support_lifecycle="legacy_supported"))

    # =====================================================================================
    # ARITHMETIC AND IDENTITY (retained from the first pass)
    # =====================================================================================
    must_fail("(23) a drifted priority_score is rejected",
              lambda c: c["candidates"][0].update(priority_score=999),
              needle="!= recomputed")
    must_fail("(23) a drifted priority_tier is rejected",
              lambda c: c["candidates"][0].update(priority_tier="C"),
              needle="!= recomputed")
    must_fail("(24) a non-integer priority_score fails closed (no traceback)",
              lambda c: c["candidates"][0].update(priority_score=None),
              needle="must be an integer")
    must_fail("(24) a non-integer score fails closed (no traceback)",
              lambda c: c["candidates"][0]["scores"].update(patch_risk="high"),
              needle="must be an integer")
    must_fail("a score above the declared max is rejected",
              lambda c: c["candidates"][0]["scores"].update(patch_risk=9),
              needle="outside declared bounds")
    must_fail("a negative score is rejected",
              lambda c: c["candidates"][0]["scores"].update(patch_risk=-1),
              needle="outside declared bounds")
    must_fail("a missing scoring dimension is rejected",
              lambda c: c["candidates"][0]["scores"].pop("patch_risk"),
              needle="missing dimensions")
    must_fail("an undeclared scoring dimension is rejected",
              lambda c: c["candidates"][0]["scores"].update(vibes=5),
              needle="undeclared dimensions")
    must_fail("a wrong declared weight_total is rejected",
              lambda c: c["scoring"].update(weight_total=999), needle="weight_total")
    must_fail("a wrong declared max_total is rejected",
              lambda c: c["scoring"].update(max_total=999), needle="max_total")
    must_fail("a high-scoring product failing the automation gate cannot be stored Tier A",
              lambda c: (c["candidates"][0]["scores"].update(automation_feasibility=1),
                         c["candidates"][0].update(priority_score=sum(
                             (1 if k == "automation_feasibility" else 5) * DIMS[k] for k in DIMS))),
              needle="stored priority_tier")
    must_fail("(25) a duplicate candidate_id is rejected",
              lambda c: c["candidates"].append(copy.deepcopy(c["candidates"][0])),
              needle="duplicate candidate_id")
    must_fail("(25) a duplicate opportunity_id is rejected",
              lambda s: s["opportunities"].append(copy.deepcopy(s["opportunities"][1])),
              target="sources", needle="duplicate opportunity_id")
    must_fail("a missing required candidate field is rejected",
              lambda c: c["candidates"][0].pop("recommended_next_step"),
              needle="missing required field")
    must_fail("a missing required opportunity field is rejected",
              lambda s: opp(s, "opp-local").pop("measurement"),
              target="sources", needle="missing required field")
    must_fail("a dangling opportunity_refs entry is rejected",
              lambda c: c["candidates"][0].update(opportunity_refs=["nope"]),
              needle="opportunity_refs references unknown opportunity")
    must_fail("a product_ids reference to an unknown product is rejected",
              lambda s: opp(s, "opp-local").update(product_ids=["ghost"]),
              target="sources", needle="unknown product_id")
    must_fail("claiming 'untracked' for a configured product is rejected",
              lambda c: c["candidates"][0].update(repo_state="untracked"),
              needle="marked untracked but present")
    must_fail("claiming 'configured_disabled' for an ENABLED product is rejected",
              lambda c: c["candidates"][0].update(repo_state="configured_disabled"),
              needle="ingestion source is enabled")
    must_fail("claiming 'tracked_official_only' for an unconfigured product is rejected",
              lambda c: c["candidates"][2].update(repo_state="tracked_official_only"),
              needle="no enabled ingestion source")
    must_fail("an undeclared lifecycle state on an opportunity is rejected",
              lambda s: opp(s, "opp-local").update(status="looks_promising"),
              target="sources", needle="not a declared lifecycle state")
    must_fail("a lane outside {official, consensus} is rejected",
              lambda s: opp(s, "opp-local").update(lane="both"),
              target="sources", needle="lane")

    # --- declared vocabularies must match what the validator enforces ---------------------
    must_fail("a readiness vocabulary that drifts from the enforced one is rejected",
              lambda c: c["readiness_model"]["values"].update(ship_it="-"),
              needle="readiness_model declares")
    must_fail("a confidence vocabulary that drifts from the enforced one is rejected",
              lambda c: c["confidence_values"].pop("unproven"),
              needle="confidence_values declares")
    must_fail("a scope vocabulary that drifts from the enforced one is rejected",
              lambda c: c["product_scopes"].pop("scope_split_required"),
              needle="product_scopes declares")
    must_fail("a lifecycle vocabulary that drifts from the enforced one is rejected",
              lambda c: c["support_lifecycles"].pop("unknown"),
              needle="support_lifecycles declares")
    must_fail("an undocumented ready_to_build gate list is rejected",
              lambda c: c["readiness_model"].pop("ready_to_build_requires"),
              needle="must list the derivation gates")

    # --- calibration cases the corrections named explicitly -------------------------------
    real_cand = yaml.safe_load(vei.CANDIDATES_FILE.read_text(encoding="utf-8"))
    by_cid = {c["candidate_id"]: c for c in real_cand["candidates"]}
    cu = by_cid.get("comfyui", {})
    check("CALIBRATION comfyui: high strategic priority retained",
          cu.get("priority_tier") == "A" and cu.get("priority_score", 0) >= 140,
          f"{cu.get('priority_tier')} {cu.get('priority_score')}")
    check("CALIBRATION comfyui: NOT ready_to_build while patch identity is unmeasured",
          cu.get("readiness") == "prove_source" and bool(cu.get("readiness_blockers")),
          str(cu.get("readiness")))
    check("CALIBRATION comfyui: consensus/automation evidence is not claimed as measured",
          cu.get("score_basis", {}).get("consensus_source_quality", {}).get("confidence")
          in {"low", "unproven"},
          str(cu.get("score_basis", {}).get("consensus_source_quality")))
    pp = by_cid.get("microsoft-powerpoint", {})
    check("CALIBRATION powerpoint: high strategic priority retained",
          pp.get("priority_tier") == "A", str(pp.get("priority_tier")))
    check("CALIBRATION powerpoint: represented as an observability proof gap, not a lane",
          pp.get("readiness") == "prove_source"
          and any("OBSERVABILITY" in str(b) for b in pp.get("readiness_blockers", [])),
          str(pp.get("readiness_blockers")))
    w10 = by_cid.get("windows-10", {})
    check("CALIBRATION windows-10: lifecycle is not hard-coded (unknown + verification note)",
          w10.get("support_lifecycle") == "unknown" and bool(w10.get("support_lifecycle_note")),
          str(w10.get("support_lifecycle")))
    for cid in ("github", "openai-chatgpt", "figma"):
        c0 = by_cid.get(cid, {})
        check(f"SCOPE {cid}: scope split recorded rather than the vendor written off",
              c0.get("product_scope") == "scope_split_required" and bool(c0.get("scope_split_note")),
              str(c0.get("product_scope")))

    print()
    print("=" * 66)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    print("=" * 66)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
