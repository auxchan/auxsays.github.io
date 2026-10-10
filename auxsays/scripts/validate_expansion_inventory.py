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

* EXPLICIT, LANE-SPECIFIC SOURCE-AUDIT COVERAGE. Every CONFIGURED product carries an audit entry
  -- not just the enabled or strategic ones -- because a validator that permanently reports the
  same warnings teaches everyone to ignore warnings, and the products it would skip are exactly
  the ones most likely to be forgotten. OFFICIAL and CONSENSUS are audited separately: they fail
  independently, and one shared status produced contradictory records (Premiere read
  `no_viable_source_found` while its own notes described PR #51's Algolia lane as working).
  `no_viable_source_found` means NO viable source exists for that lane; "we have one and cannot
  find another" is diversification debt and lives in `diversification_state`.

* CONFIGURATION IS NOT EXECUTION. A method can be fully wired -- enabled adapter, or registered in
  collector_ownership.ALLOWED_METHODS -- and still never have run. `configured_unobserved` says
  exactly that and asserts neither success nor failure; `unobserved_methods` exposes the individual
  wired methods with no health observation even when the lane as a whole is working (both Acrobats).
  Both are DERIVED from repo telemetry here, never taken on the YAML's word, and an unobserved lane
  can never be ready_to_build.

* THE OFFICIAL PATH MUST BE PROVEN, NOT SCORED, AND HISTORY IS NOT HEALTH.
  `official_source_quality >= 3` is an estimate. ready_to_build additionally needs
  product-specific official proof: either enabled ingestion WITH committed records AND a current
  healthy `source_health.yml` signal, or a referenced official-lane opportunity proven end to end.
  Records alone are history: adobe-premiere-pro has 2 committed records and books `Failing`, and
  blackmagic-davinci has 106 with official ingestion on `Manual watch`. A product with no health
  row at all also fails -- absence of a signal is not a pass. Same-vendor precedent never counts.

* AUDIT METHODS ARE ANCHORED TO REPO CONFIG. `current_methods` are checked against ground truth:
  official against the enabled ingestion adapter, consensus against
  collector_ownership.ALLOWED_METHODS. `pending_methods` must NOT already be registered/enabled --
  something the repo already runs is current, not pending. Otherwise `current_methods` is prose
  and every state derived from it inherits the fiction.

* PROBE BEFORE PRODUCTION. An unproven source's next action must be a measurement. A plan whose
  leading action is registration contradicts the status that says the source is unproven.

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
SOURCE_HEALTH_FILE = _DATA / "source_health.yml"
METHOD_HEALTH_FILE = _DATA / "evidence_method_health.yml"

# Official-lane health, as the repo books it. Only an explicit healthy signal proves a working
# official lane: committed records are HISTORY, and a lane that produced records last month can be
# Failing today (adobe-premiere-pro) or not running unattended at all (blackmagic-davinci, Manual
# watch). A MISSING health row is not a pass either -- absence of a signal cannot prove health.
HEALTHY_OFFICIAL_STATUSES = {"healthy"}
UNHEALTHY_OFFICIAL_STATUSES = {"degraded", "failing", "manual watch", "staged"}

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

# OFFICIAL and CONSENSUS are audited separately: they fail independently, and one shared status
# produced flatly contradictory records (adobe-premiere-pro read `no_viable_source_found` while its
# own notes described PR #51's Algolia lane as a working path).
AUDIT_LANES = ("official", "consensus")
AUDIT_LANE_STATES = (
    "production_source_present", "production_source_degraded", "configured_unobserved",
    "pending_production_source", "opportunities_identified", "needs_source_research",
    "no_viable_source_found",
)
# States that assert a source exists now or is proven-and-waiting.
AUDIT_STATES_WITH_SOURCE = {
    "production_source_present", "production_source_degraded", "configured_unobserved",
    "pending_production_source",
}
# Wiring exists: the repo is configured to run something for this lane.
AUDIT_STATES_WIRED = {
    "production_source_present", "production_source_degraded", "configured_unobserved",
}
# Execution has actually been OBSERVED. Only these may carry a real diversification judgement --
# an unobserved method is never an independent proven source.
AUDIT_STATES_OBSERVED = {"production_source_present", "production_source_degraded"}
# Consensus health statuses that make a method usable. Anything else that HAS a row is observed
# but unusable (degraded); NO row at all is unobserved, which is a different fact entirely.
USABLE_CONSENSUS_STATUSES = {"success", "partial"}
AUDIT_DIVERSIFICATION_STATES = (
    "sufficient", "opportunities_identified", "needs_source_research",
    "no_viable_additional_source_found", "not_applicable",
)
AUDIT_LANE_REQUIRED = ("state", "current_methods", "pending_methods", "unobserved_methods",
                       "opportunity_ids", "diversification_state")
# An unproven thing's next action must be a MEASUREMENT. If the plan reads as production wiring,
# it contradicts the very status that says the source is unproven.
PRODUCTION_ACTIVATION_PHRASES = (
    "register the", "register `", "allowed_methods", "collector_ownership",
    "collector ownership", "activate the method", "enable the method", "wire it into production",
)
# Deliberately ORDER-AWARE rather than a bare substring test. A correct plan may legitimately name
# registration as the step that happens AFTER the probe ("probe first ... registration is a
# separate task"), and flagging that would push authors into wording games instead of better plans.
# What must not happen is activation being the LEADING action.
MEASUREMENT_PHRASES = (
    "probe", "measure", "dry-run", "dry run", "sample", "count", "diagnose", "enumerate",
    "trace", "verify", "decide", "policy", "confirm",
)


def leading_action_is_activation(text: str) -> str | None:
    """The activation phrase that precedes any measurement verb, or None."""
    low = str(text or "").lower()
    activation = [(low.index(p), p) for p in PRODUCTION_ACTIVATION_PHRASES if p in low]
    if not activation:
        return None
    first_activation, phrase = min(activation)
    measurement = [low.index(p) for p in MEASUREMENT_PHRASES if p in low]
    if measurement and min(measurement) < first_activation:
        return None
    return phrase


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


def _opportunity_proof_complete(o: dict[str, Any], today: _dt.date) -> bool:
    """True only when THIS opportunity is proven end to end for its own product.

    Same bar for both lanes. Deliberately excludes `transport_precedent`: proof that a transport
    works for a different product can never satisfy this.
    """
    proof = o.get("proof") or {}
    if str(proof.get("structure_proven")) != "proven":
        return False
    if str(proof.get("actions_reachable")) != "proven" \
            and str(proof.get("production_proven")) != "proven":
        return False
    if str(proof.get("patch_specificity_proven")) != "proven":
        return False
    return freshness_of(o, today)[0] == FRESHNESS_CURRENT


def official_path_proof(
    candidate: dict[str, Any],
    opportunities: dict[str, dict[str, Any]],
    enabled_products: set[str],
    record_counts: dict[str, int],
    today: _dt.date,
    official_health: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Is there PRODUCT-SPECIFIC proof of a working official path? (satisfied, reason_if_not)

    Two ways in, mirroring how the repo actually establishes an official lane:

      A. EXISTING PRODUCTION PROOF -- ingestion ENABLED for this product, committed records, AND a
         CURRENT healthy official signal in `_data/source_health.yml`.
      B. A REFERENCED OFFICIAL OPPORTUNITY proven end to end for this product.

    A score of `official_source_quality >= 3` with an acceptable confidence is necessary but was
    never sufficient: it is an estimate, and estimating that a vendor "probably has release notes"
    says nothing about whether a parser works from an Actions runner.

    HISTORY IS NOT HEALTH. Records alone used to satisfy path A, which let a lane the repo itself
    books as broken read as proven: adobe-premiere-pro is enabled with 2 committed records and
    source_health `Failing`, and blackmagic-davinci has 106 records with official ingestion on
    `Manual watch` -- neither is a working unattended official path. A product with no health row
    at all also fails: no signal is not a pass.
    """
    cid = str(candidate.get("candidate_id"))
    health = (official_health or {})
    if cid in enabled_products and record_counts.get(cid, 0) > 0:
        status = health.get(cid, "")
        if status in HEALTHY_OFFICIAL_STATUSES:
            return True, ""
        if not status:
            return False, (f"official path unproven: {record_counts.get(cid, 0)} committed records "
                           "are history, and there is no current official health signal for this "
                           "product (absent from source_health.yml)")
        return False, (f"official path unproven: ingestion is enabled with committed records, but "
                       f"current official health is {status!r} -- history is not health")
    refs = candidate.get("opportunity_refs") or []
    official = [opportunities[r] for r in refs
                if r in opportunities and opportunities[r].get("lane") == "official"]
    if not official:
        return False, ("no product-specific official proof: not an enabled-ingestion product with "
                       "records, and no official-lane opportunity referenced")
    if any(_opportunity_proof_complete(o, today) for o in official):
        return True, ""
    return False, ("official path is inferred, not proven: no referenced official opportunity has "
                   "structure + Actions/production + patch specificity proven and current")


def derive_readiness(
    candidate: dict[str, Any],
    opportunities: dict[str, dict[str, Any]],
    today: _dt.date | None = None,
    enabled_products: set[str] | None = None,
    record_counts: dict[str, int] | None = None,
    official_health: dict[str, str] | None = None,
    unobserved_lanes: bool = False,
) -> tuple[str, list[str]]:
    """Deterministically derive readiness. FAILS CLOSED: anything unproven means not ready.

    ready_to_build requires ALL of:
      1. a deterministic OFFICIAL path -- official_source_quality >= 3 AND product-specific
         official proof (see official_path_proof), because a score is an estimate and committed
         records are history rather than current health;
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
    ok_official, why = official_path_proof(
        candidate, opportunities, enabled_products or set(), record_counts or {}, today,
        official_health or {})
    if not ok_official:
        reasons.append(why)
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

        # Same end-to-end bar as the official lane (official_path_proof), reported dimension by
        # dimension so the unmet gate is named rather than just denied.
        if not any(_opportunity_proof_complete(o, today) for o in consensus):
            structural = [o for o in consensus if proven(o, "structure_proven")]
            if not structural:
                reasons.append("no referenced consensus opportunity with structure_proven")
            else:
                runnable = [o for o in structural
                            if proven(o, "actions_reachable") or proven(o, "production_proven")]
                if not runnable:
                    reasons.append("consensus transport is not Actions-proven or production-proven "
                                   "(transport precedent elsewhere does not count)")
                else:
                    identified = [o for o in runnable if proven(o, "patch_specificity_proven")]
                    if not identified:
                        reasons.append("consensus patch specificity unproven for this product")
                    else:
                        reasons.append("supporting proof is stale")

    if unobserved_lanes:
        reasons.append("a lane is configured_unobserved: wired but never observed to execute")
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


GENERATED_DIR = _REPO / "auxsays" / "updates" / "generated"
_PRODUCT_ID_RE = __import__("re").compile(r"^product_id:\s*['\"]?([\w\-\.]+)", 8)  # re.M


def official_health_by_product() -> dict[str, str]:
    """Lowercased official-lane health status per product, from `_data/source_health.yml`.

    Products absent from that file (both Acrobats, the four Elgato products, 365-apps, PowerPoint,
    Teams, Windows 11 at the time of writing) map to '' -- no signal, which is NOT health.
    """
    if not SOURCE_HEALTH_FILE.exists():
        return {}
    rows = yaml.safe_load(SOURCE_HEALTH_FILE.read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else (rows or {}).get("sources", [])
    return {str(r.get("product_id")): str(r.get("status") or "").strip().lower()
            for r in rows if isinstance(r, dict) and r.get("product_id")}


def official_config_by_product() -> dict[str, dict[str, Any]]:
    """Enabled flag + configured adapter per product, from `_data/patch_ingestion_sources.yml`.

    The audit's official `current_methods` are anchored to THIS, so the inventory cannot claim an
    official method the repo does not actually run.
    """
    rows = yaml.safe_load(INGESTION_FILE.read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else (rows or {}).get("sources", [])
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not isinstance(r, dict) or not r.get("product_id"):
            continue
        ingestion = r.get("ingestion") or {}
        out[str(r["product_id"])] = {
            "enabled": bool(r.get("enabled")),
            "adapter": str(ingestion.get("adapter") or ""),
        }
    return out


def registered_consensus_methods() -> dict[str, set[str]]:
    """Per-product registered consensus method ids, from collector_ownership.ALLOWED_METHODS.

    The audit's consensus `current_methods` are anchored to THIS: a method that is not registered
    cannot be operational, whatever the planning data says.
    """
    scripts = str(_REPO / "auxsays" / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from lib.collector_ownership import ALLOWED_METHODS  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - a missing manifest must not silently disable the anchor
        return {}
    return {str(k): {str(m) for m in v} for k, v in ALLOWED_METHODS.items()}


def observed_consensus_methods() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(methods with ANY health row, methods with a USABLE row) per product.

    Derived from `_data/evidence_method_health.yml`. The distinction is the whole point of
    `configured_unobserved`: a method with no row has never been seen to run, which is not the same
    as a method whose rows say blocked/broken. Generated records are deliberately NOT consulted --
    they are historical output and prove nothing about present execution.
    """
    rows: dict[str, set[str]] = {}
    usable: dict[str, set[str]] = {}
    if not METHOD_HEALTH_FILE.exists():
        return rows, usable
    doc = yaml.safe_load(METHOD_HEALTH_FILE.read_text(encoding="utf-8")) or {}
    entries = doc.get("methods", doc) if isinstance(doc, dict) else doc
    for row in entries or []:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("product_id"))
        mid = str(row.get("method_id"))
        rows.setdefault(pid, set()).add(mid)
        if str(row.get("status")) in USABLE_CONSENSUS_STATUSES:
            usable.setdefault(pid, set()).add(mid)
    return rows, usable


def derive_lane_wiring(
    pid: str,
    lane: str,
    official_config: dict[str, dict[str, Any]],
    official_health: dict[str, str],
    registered: dict[str, set[str]],
    health_rows: dict[str, set[str]],
    health_usable: dict[str, set[str]],
) -> dict[str, Any]:
    """What the REPO says about this lane: wired methods, unobserved subset, derived state.

    Nothing here reads the planning YAML, so authored data cannot manufacture an unobserved claim
    or hide a real one.
    """
    if lane == "official":
        cfg = official_config.get(pid, {})
        wired = [cfg["adapter"]] if cfg.get("enabled") and cfg.get("adapter") else []
        status = official_health.get(pid, "")
        # No source-health row => execution never observed. A row saying Failing/Degraded/Manual
        # watch IS an observation, and means degraded rather than unobserved.
        unobserved = list(wired) if (wired and not status) else []
        usable = bool(wired) and status in HEALTHY_OFFICIAL_STATUSES
        observed_bad = bool(wired) and status in UNHEALTHY_OFFICIAL_STATUSES
    else:
        wired = sorted(registered.get(pid, set()))
        unobserved = sorted(set(wired) - health_rows.get(pid, set()))
        usable = bool(health_usable.get(pid, set()) & set(wired))
        observed_bad = bool(wired) and not usable and bool(set(wired) & health_rows.get(pid, set()))

    if wired and unobserved and len(unobserved) == len(wired):
        state = "configured_unobserved"
    elif wired and usable:
        state = "production_source_present"
    elif wired and observed_bad:
        state = "production_source_degraded"
    else:
        state = ""  # not wired: the state is an authored judgement, not derivable
    return {"wired": wired, "unobserved": unobserved, "derived_state": state}


def generated_record_counts() -> dict[str, int]:
    """Records actually committed per product_id -- ground truth for existing official proof.

    Measured from the repo rather than read from this inventory, so `ready_to_build` cannot be
    obtained by asserting a healthy official lane in planning data.
    """
    counts: dict[str, int] = {}
    if not GENERATED_DIR.exists():
        return counts
    for path in GENERATED_DIR.rglob("*.md"):
        match = _PRODUCT_ID_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def validate() -> int:  # noqa: PLR0912, PLR0915 - one linear pass keeps the rules readable
    errors: list[str] = []
    warnings: list[str] = []
    today = _today()
    record_counts = generated_record_counts()
    official_health = official_health_by_product()
    official_config = official_config_by_product()
    registered_methods = registered_consensus_methods()
    health_rows, health_usable = observed_consensus_methods()

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

        # An unproven opportunity's next experiment must be a MEASUREMENT. Same rule as candidate
        # recommendations: planning that starts by wiring an unproven source into production
        # contradicts the very status that says it is unproven.
        if isinstance(proof, dict) and str(proof.get("patch_specificity_proven")) != "proven":
            hit = leading_action_is_activation(o.get("next_experiment"))
            if hit:
                errors.append(f"{oid}: patch specificity is unproven but next_experiment reads as "
                              f"production activation ({hit!r}) -- it must be a probe")

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

    # --- product source audit: LANE-SPECIFIC, and every configured product covered ---------
    declared_lane_states = src.get("audit_lane_states") or {}
    declared_div_states = src.get("audit_diversification_states") or {}
    for key, declared, expected in (("audit_lane_states", declared_lane_states, AUDIT_LANE_STATES),
                                    ("audit_diversification_states", declared_div_states,
                                     AUDIT_DIVERSIFICATION_STATES)):
        if not isinstance(declared, dict) or set(declared) != set(expected):
            errors.append(f"{key} must declare exactly {sorted(expected)} "
                          f"(declared {sorted(declared) if isinstance(declared, dict) else declared})")

    if not isinstance(audit, dict):
        errors.append("product_source_audit must be a mapping of product_id -> per-lane audit")
        audit = {}
    audit_state_counts: dict[str, dict[str, int]] = {lane: {} for lane in AUDIT_LANES}
    unobserved_lane_count = 0
    div_counts: dict[str, int] = {}
    for pid, entry in audit.items():
        pid = str(pid)
        if pid not in configured_products:
            errors.append(f"product_source_audit[{pid}]: unknown product_id")
        if not isinstance(entry, dict):
            errors.append(f"product_source_audit[{pid}]: entry must be a mapping")
            continue
        if "state" in entry:
            errors.append(f"product_source_audit[{pid}]: a single product-level 'state' is no longer "
                          "valid -- official and consensus are audited separately")
        for lane in AUDIT_LANES:
            block = entry.get(lane)
            if not isinstance(block, dict):
                errors.append(f"product_source_audit[{pid}]: missing '{lane}' lane block")
                continue
            for field in AUDIT_LANE_REQUIRED:
                if field not in block:
                    errors.append(f"product_source_audit[{pid}].{lane}: missing '{field}'")
            state = str(block.get("state"))
            if state not in AUDIT_LANE_STATES:
                errors.append(f"product_source_audit[{pid}].{lane}: state "
                              f"{block.get('state')!r} invalid")
            audit_state_counts[lane][state] = audit_state_counts[lane].get(state, 0) + 1

            lists = {}
            bad_list = False
            for field in ("current_methods", "pending_methods", "unobserved_methods", "opportunity_ids"):
                value = block.get(field)
                if not isinstance(value, list):
                    errors.append(f"product_source_audit[{pid}].{lane}: {field} must be a list")
                    bad_list = True
                    lists[field] = []
                else:
                    lists[field] = value
            if bad_list:
                continue

            # Referenced opportunities must exist AND belong to THIS lane. An official-lane row can
            # never close a consensus gap -- the microsoft-windows-11 defect.
            same_lane_refs = []
            for ref in lists["opportunity_ids"]:
                ref = str(ref)
                if ref not in by_id:
                    errors.append(f"product_source_audit[{pid}].{lane}: references unknown "
                                  f"opportunity {ref!r}")
                elif by_id[ref].get("lane") != lane:
                    errors.append(f"product_source_audit[{pid}].{lane}: opportunity {ref!r} is a "
                                  f"{by_id[ref].get('lane')!r}-lane opportunity and cannot satisfy "
                                  f"the {lane} lane")
                else:
                    same_lane_refs.append(ref)

            # ANCHOR THE LANE TO THE REPO, AND DERIVE RATHER THAN TRUST. `current_methods` must
            # mirror actual wiring, `unobserved_methods` must equal the repo-derived unobserved
            # subset, and where wiring exists the state itself is derived. Without this the lane is
            # prose and every downstream judgement inherits the fiction.
            cfg = official_config.get(pid, {})
            derived = derive_lane_wiring(pid, lane, official_config, official_health,
                                         registered_methods, health_rows, health_usable)
            for method in lists["current_methods"]:
                method = str(method)
                if lane == "official":
                    if not cfg.get("enabled"):
                        errors.append(f"product_source_audit[{pid}].official: claims current method "
                                      f"{method!r} but the product has no ENABLED ingestion source")
                    elif method != cfg.get("adapter"):
                        errors.append(f"product_source_audit[{pid}].official: current method "
                                      f"{method!r} is not the configured adapter "
                                      f"{cfg.get('adapter')!r}")
                elif method not in registered_methods.get(pid, set()):
                    errors.append(f"product_source_audit[{pid}].consensus: current method "
                                  f"{method!r} is not registered in "
                                  "collector_ownership.ALLOWED_METHODS, so it cannot be operational")
            if sorted(str(m) for m in lists["current_methods"]) != sorted(derived["wired"]):
                errors.append(f"product_source_audit[{pid}].{lane}: current_methods "
                              f"{sorted(str(m) for m in lists['current_methods'])} != repo wiring "
                              f"{sorted(derived['wired'])}")

            # --- unobserved_methods: derived, never trusted ---
            unobs = lists["unobserved_methods"]
            declared = sorted(str(m) for m in unobs)
            actual = sorted(derived["unobserved"])
            for method in declared:
                if method not in derived["wired"]:
                    errors.append(f"product_source_audit[{pid}].{lane}: unobserved_methods lists "
                                  f"{method!r}, which is not current repo wiring for this lane")
                elif method not in actual:
                    errors.append(f"product_source_audit[{pid}].{lane}: {method!r} HAS an "
                                  "authoritative health observation and cannot be listed as "
                                  "unobserved")
            for method in actual:
                if method not in declared:
                    errors.append(f"product_source_audit[{pid}].{lane}: {method!r} is wired with NO "
                                  "health observation and must appear in unobserved_methods")

            # --- derived state wins wherever wiring exists ---
            if derived["derived_state"] and state != derived["derived_state"]:
                errors.append(f"product_source_audit[{pid}].{lane}: state {state!r} != repo-derived "
                              f"{derived['derived_state']!r}")
            if state == "configured_unobserved" and not lists["current_methods"]:
                errors.append(f"product_source_audit[{pid}].{lane}: 'configured_unobserved' requires "
                              "at least one current method -- it means wired but never observed")
            # And the inverse for PENDING: something already registered is not pending.
            for method in lists["pending_methods"]:
                method = str(method)
                if lane == "consensus" and method in registered_methods.get(pid, set()):
                    errors.append(f"product_source_audit[{pid}].consensus: pending method "
                                  f"{method!r} is already registered -- it is current, not pending")
                if lane == "official" and cfg.get("enabled") and method == cfg.get("adapter"):
                    errors.append(f"product_source_audit[{pid}].official: pending method "
                                  f"{method!r} is the enabled adapter -- it is current, not pending")

            if lists["unobserved_methods"]:
                unobserved_lane_count += 1
            has_source = bool(lists["current_methods"]) or bool(lists["pending_methods"])
            # HISTORY IS NOT HEALTH. A lane the repo books Degraded/Failing/Manual watch may not be
            # recorded as a healthy production source.
            if lane == "official" and state == "production_source_present":
                status = official_health.get(pid, "")
                if status in UNHEALTHY_OFFICIAL_STATUSES:
                    errors.append(f"product_source_audit[{pid}].official: "
                                  f"'production_source_present' contradicts source_health "
                                  f"{status!r} -- use 'production_source_degraded'")
            if state in AUDIT_STATES_OBSERVED and not lists["current_methods"]:
                errors.append(f"product_source_audit[{pid}].{lane}: state {state!r} requires at "
                              "least one current_methods entry")
            if state == "pending_production_source" and not lists["pending_methods"]:
                errors.append(f"product_source_audit[{pid}].{lane}: 'pending_production_source' "
                              "requires at least one pending_methods entry")
            if state == "opportunities_identified" and not same_lane_refs:
                errors.append(f"product_source_audit[{pid}].{lane}: 'opportunities_identified' "
                              f"requires at least one {lane}-lane opportunity")
            # THE SEMANTIC RULE. "no viable source found" means no viable source exists for this
            # lane. It may never mean "we have one and cannot find another" -- that is
            # diversification debt and belongs in diversification_state.
            if state == "no_viable_source_found" and has_source:
                errors.append(f"product_source_audit[{pid}].{lane}: 'no_viable_source_found' is "
                              "false while a current or pending method exists -- use "
                              "diversification_state 'no_viable_additional_source_found' instead")
            if state == "needs_source_research" and has_source:
                errors.append(f"product_source_audit[{pid}].{lane}: 'needs_source_research' "
                              "contradicts an existing current/pending method")

            div = str(block.get("diversification_state"))
            if div not in AUDIT_DIVERSIFICATION_STATES:
                errors.append(f"product_source_audit[{pid}].{lane}: diversification_state "
                              f"{block.get('diversification_state')!r} invalid")
            div_counts[div] = div_counts.get(div, 0) + 1
            # Diversification only becomes a question once execution has been OBSERVED. An
            # unobserved or pending lane has not established that its FIRST source works, so
            # calling it single-source debt would be premature.
            if state in AUDIT_STATES_OBSERVED and div == "not_applicable":
                errors.append(f"product_source_audit[{pid}].{lane}: execution is observed, so "
                              "diversification_state cannot be 'not_applicable'")
            if state not in AUDIT_STATES_OBSERVED and div != "not_applicable":
                errors.append(f"product_source_audit[{pid}].{lane}: execution is not observed "
                              f"({state}), so diversification_state must be 'not_applicable' "
                              f"(got {div!r})")

    # EVERY configured product must be audited. A validator that permanently reports the same
    # warnings teaches everyone to ignore warnings, and the products it would skip are exactly the
    # ones most likely to be forgotten. needs_source_research with an empty list is the honest
    # answer and costs nothing.
    for pid in sorted(configured_products - set(audit)):
        errors.append(f"product_source_audit: missing entry for configured product {pid}")
    for pid in [str(p) for p in strategic]:
        if pid not in configured_products:
            errors.append(f"strategic_priority_products: {pid} is not a configured product")

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
        cid_audit = audit.get(cid) or {}
        cid_unobserved = any(
            (cid_audit.get(ln) or {}).get("state") == "configured_unobserved"
            for ln in AUDIT_LANES)
        derived, reasons = derive_readiness(
            c, by_id, today, enabled_ingestion_products, record_counts, official_health,
            cid_unobserved)
        # A prove_source plan whose next action is production wiring contradicts itself: the point
        # of prove_source is that the source is not proven yet.
        if derived != "ready_to_build":
            hit = leading_action_is_activation(c.get("recommended_next_step"))
            if hit:
                errors.append(f"{cid}: readiness is {derived!r} but recommended_next_step reads as "
                              f"production activation ({hit!r}) -- the next action must be a probe")
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
    print(f"  source-audit coverage: {len(audit)}/{len(configured_products)} configured products")
    print(f"    official lane : {audit_state_counts['official']}")
    print(f"    consensus lane: {audit_state_counts['consensus']}")
    print(f"    diversification: {div_counts}")
    print(f"    lanes carrying unobserved_methods: {unobserved_lane_count}"
          f"   fully-unobserved lanes: {audit_state_counts['official'].get('configured_unobserved', 0)}"
          f" official + {audit_state_counts['consensus'].get('configured_unobserved', 0)} consensus")
    print(f"  configured products: {len(configured_products)}   "
          f"enabled-ingestion products: {len(enabled_ingestion_products)}   "
          f"products with generated records: {len(record_counts)}   "
          f"declared strategic: {len(strategic)}")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    print(f"  {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(validate())
