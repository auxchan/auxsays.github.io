from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systems_monitor_data.layoffs_bls_dol import collect_layoffs_bls_dol_candidates
from systems_monitor_data.layoffs_update import atomic_activate, build_review_snapshot, credential_state, source_due


SOURCE_FACTOR_ALIASES = {
    "layoffs-discharges-level": "layoffs-and-discharges",
    "layoffs-discharges-rate": "layoffs-and-discharges",
    "initial-ui-claims": "initial-claims",
    "continued-ui-claims": "continued-claims-insured-unemployment",
    "insured-unemployment-rate": "continued-claims-insured-unemployment",
    "closing-establishment-losses": "establishment-closures",
    "establishment-death-job-losses": "jobs-lost-at-establishment-deaths",
    "bds-job-destruction-continuers": "establishment-contractions",
    "bds-job-destruction-deaths": "establishment-closures",
    "bds-firm-deaths": "firm-deaths",
    "bds-firm-death-establishments": "firm-age-size-vulnerability",
    "bds-firm-death-employment": "firm-death-shutdown-stress",
    "business-formations-four-quarters": "business-formation",
    "business-formations": "business-formation",
    "industry-payroll-contraction": "payroll-contraction-breadth",
    "establishment-deaths": "jobs-lost-at-establishment-deaths",
    "business-bankruptcy-stress": "business-bankruptcy-filings-12-month-total",
    "business-bankruptcy-filings": "business-bankruptcy-filings-12-month-total",
    "real-output-growth": "real-gdp-growth",
    "consumer-demand": "real-personal-consumption-expenditures-growth",
    "disaster-operational-shock": "fema-disaster-declaration",
}

SOURCE_DATASETS = {
    "bls-jolts": "Job Openings and Labor Turnover Survey",
    "bls-cps": "Current Population Survey",
    "bls-ces": "Current Employment Statistics",
    "bls-bed": "Business Employment Dynamics",
    "dol-ui-claims": "Unemployment Insurance Weekly Claims",
}

STATE_PRIORITY = {"SOURCE_IDENTIFIED": 0, "BLOCKED": 1, "SOURCE_ENABLED_PENDING_ACCEPTANCE": 2, "ACCEPTED": 3}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_factor_id(configured: str, taxonomy: dict) -> str:
    slug = configured.removeprefix("factor:canonical:").removeprefix("factor:")
    slug = SOURCE_FACTOR_ALIASES.get(slug, slug)
    candidate = f"factor:canonical:{slug}"
    return taxonomy.get("canonicalFactorMigrations", {}).get(candidate, candidate)


def accepted_observations_by_series(accepted_history: dict) -> dict[str, dict]:
    current: dict[str, dict] = {}
    for row in accepted_history["observations"]:
        series_id = row["sourceSeriesId"]
        rank = (row["validTime"], int(row.get("revisionNumber", 0)), row["acceptedTime"])
        previous = current.get(series_id)
        if previous is None or rank > (previous["validTime"], int(previous.get("revisionNumber", 0)), previous["acceptedTime"]):
            current[series_id] = row
    return current


def factor_states(bls_dol: dict, census: dict, context: dict, fema: dict, taxonomy: dict, accepted_history: dict, health: dict[str, dict]) -> list[dict]:
    rows: dict[str, dict] = {}
    default_state = {"activationState": "SOURCE_IDENTIFIED", "health": "disabled", "reasonCode": "SOURCE_PROFILE_NOT_SCHEDULED"}
    accepted_by_series = accepted_observations_by_series(accepted_history)
    publishers = {row["source_id"]: row["publisher"] for row in bls_dol["source_profiles"]}

    def retain_strongest(row: dict) -> None:
        existing = rows.get(row["canonicalFactorId"])
        if existing is None or STATE_PRIORITY[row["activationState"]] > STATE_PRIORITY[existing["activationState"]]:
            rows[row["canonicalFactorId"]] = row

    for series in bls_dol["series"]:
        source_id = series["source_id"]
        state = health[source_id]
        factor_id = canonical_factor_id(series["canonical_factor"], taxonomy)
        accepted = accepted_by_series.get(series["series_id"]) if series["activation_state"] == "ACCEPTED_EXISTING" else None
        activation_state = "ACCEPTED" if accepted else "SOURCE_ENABLED_PENDING_ACCEPTANCE" if state["health"] == "success" or state["activationState"] == "ACCEPTED" else state["activationState"]
        row = {
            "sourceId": source_id,
            "canonicalFactorId": factor_id,
            "activationState": activation_state,
            "health": state["health"],
            "reasonCode": "EXISTING_ACCEPTED_HISTORY_REUSED" if accepted else state.get("reasonCode", "AWAITING_SOURCE_ACCEPTANCE"),
            "candidateSeriesId": series["series_id"],
            "evidenceUrl": series["human_evidence_url"],
        }
        if accepted:
            row.update({
                "displayValue": accepted["value"],
                "unit": accepted["unit"],
                "period": accepted["validTime"],
                "publisher": publishers[source_id],
                "dataset": SOURCE_DATASETS[source_id],
                "seriesId": accepted["sourceSeriesId"],
                "acceptedAt": accepted["acceptedTime"],
            })
        retain_strongest(row)
    for source in census["sources"]:
        state = health.get(source["source_id"], default_state)
        for series in source["series"]:
            for placement in series["placement_candidates"]:
                factor_id = canonical_factor_id(f"factor:{placement}", taxonomy)
                retain_strongest({
                    "sourceId": source["source_id"], "canonicalFactorId": factor_id,
                    "activationState": state["activationState"], "health": state["health"],
                    "reasonCode": state.get("reasonCode", "AWAITING_SOURCE_ACCEPTANCE"),
                    "candidateSeriesId": series["source_series_id"], "evidenceUrl": source["evidence_url"],
                })
    for source in context["sources"]:
        state = health.get(source["source_id"], default_state)
        for series in source.get("series", []):
            factor_id = canonical_factor_id(series["canonical_factor"], taxonomy)
            retain_strongest({
                "sourceId": source["source_id"], "canonicalFactorId": factor_id,
                "activationState": state["activationState"], "health": state["health"],
                "reasonCode": state.get("reasonCode", "AWAITING_SOURCE_ACCEPTANCE"),
                "candidateSeriesId": series["source_series_id"], "evidenceUrl": source["evidence_url"],
            })
        for candidate in source.get("selector_candidates", []):
            factor_id = canonical_factor_id(candidate["canonical_factor"], taxonomy)
            retain_strongest({
                "sourceId": source["source_id"], "canonicalFactorId": factor_id,
                "activationState": "BLOCKED", "health": "blocked",
                "reasonCode": source["selector_status"], "evidenceUrl": source["evidence_url"],
            })
    for source in fema["sources"]:
        state = health.get(source["sourceId"], default_state)
        factor_id = canonical_factor_id(source["canonicalFactorId"], taxonomy)
        retain_strongest({
            "sourceId": source["sourceId"], "canonicalFactorId": factor_id,
            "activationState": state["activationState"], "health": state["health"],
            "reasonCode": state.get("reasonCode", "EVENT_SOURCE_IDENTIFIED_PENDING_ACCEPTANCE"),
            "candidateSeriesId": source["datasetSelector"], "evidenceUrl": source["evidenceUrl"],
        })
    return list(rows.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Cadence-aware Layoffs branch evaluator and immutable review-snapshot publisher.")
    parser.add_argument("--runtime-root", type=Path, default=ROOT / "evidence" / "layoffs-runtime")
    parser.add_argument("--active-snapshot", type=Path, default=ROOT / "review" / "layoffs-live-branch-review-snapshot.json")
    parser.add_argument("--state-path", type=Path, default=ROOT / "review" / "layoffs-source-evaluator-state.json")
    parser.add_argument("--now", default=None)
    parser.add_argument("--no-network", action="store_true", help="Build deterministic blocked/identified review state without retrieval.")
    args = parser.parse_args()

    generated_at = args.now or utc_now()
    config = ROOT / "config" / "layoffs"
    taxonomy = load(config / "taxonomy.json")
    relationships = load(config / "relationships.json")
    scheduler = load(config / "scheduler.json")
    bls_dol = load(config / "sources_bls_dol.json")
    census = load(config / "sources_census.json")
    context = load(config / "sources_bea_fed_courts.json")
    fema = load(config / "sources_fema.json")
    accepted_history = load(ROOT / "review" / "layoffs-accepted-history.json")
    previous = load(args.state_path) if args.state_path.exists() else {"sources": {}}
    health: dict[str, dict] = {}
    due_sources: list[str] = []
    accepted_source_ids = {row["source_id"] for row in bls_dol["series"] if row["activation_state"] == "ACCEPTED_EXISTING"}

    for source in scheduler["sources"]:
        source_id = source["sourceId"]
        prior = previous.get("sources", {}).get(source_id, {})
        blocked = credential_state(source)
        due = source_due(source, generated_at, prior.get("lastAttemptAt"))
        if blocked:
            health[source_id] = {**blocked, "reasonCode": blocked["reasonCode"], "lastAttemptAt": prior.get("lastAttemptAt")}
        elif not due:
            health[source_id] = {"activationState": prior.get("activationState", "SOURCE_IDENTIFIED"), "health": prior.get("health", "success"), "reasonCode": "NOT_DUE", "lastAttemptAt": prior.get("lastAttemptAt")}
        else:
            due_sources.append(source_id)
            accepted_history_available = source_id in accepted_source_ids
            health[source_id] = {"activationState": "ACCEPTED" if accepted_history_available else "SOURCE_IDENTIFIED", "health": "disabled" if args.no_network else "manual_review_needed", "reasonCode": "ACCEPTED_HISTORY_AVAILABLE_NETWORK_DISABLED_REVIEW_BUILD" if args.no_network and accepted_history_available else "NETWORK_DISABLED_REVIEW_BUILD" if args.no_network else "RETRIEVAL_PENDING", "lastAttemptAt": prior.get("lastAttemptAt")}

    bls_family = {"bls-jolts", "bls-cps", "bls-ces", "bls-bed", "dol-ui-claims"}
    if not args.no_network and bls_family.intersection(due_sources):
        try:
            batch = collect_layoffs_bls_dol_candidates(
                registry_path=config / "sources_bls_dol.json", raw_root=args.runtime_root / "raw",
                candidate_path=args.runtime_root / "layoffs-batch-candidate.json",
            )
            for source_id in bls_family:
                health[source_id] = {"activationState": "ACCEPTED" if source_id in accepted_source_ids else "SOURCE_ENABLED_PENDING_ACCEPTANCE", "health": "success", "reasonCode": "ACCEPTED_HISTORY_WITH_NEW_CANDIDATE_BATCH_PENDING" if source_id in accepted_source_ids else "CANDIDATE_BATCH_RETRIEVED_NOT_ACCEPTED", "lastAttemptAt": generated_at, "candidateCount": len(batch["candidates"])}
        except Exception as exc:
            for source_id in bls_family.intersection(due_sources):
                accepted_history_available = source_id in accepted_source_ids
                health[source_id] = {"activationState": "ACCEPTED" if accepted_history_available else "SOURCE_IDENTIFIED", "health": "broken", "reasonCode": f"ACCEPTED_HISTORY_AVAILABLE_{type(exc).__name__}" if accepted_history_available else type(exc).__name__, "lastAttemptAt": generated_at}

    for source_id in due_sources:
        if source_id not in bls_family and not args.no_network:
            health[source_id] = {"activationState": health[source_id]["activationState"], "health": "manual_review_needed", "reasonCode": "ADAPTER_REQUIRES_ACCEPTED_SELECTOR_OR_DEDICATED_RUNNER", "lastAttemptAt": generated_at}

    source_states = factor_states(bls_dol, census, context, fema, taxonomy, accepted_history, health)
    snapshot = build_review_snapshot(taxonomy=taxonomy, source_states=source_states, relationships=relationships["relationships"], generated_at=generated_at, source_health=health)
    result = atomic_activate(snapshot, args.active_snapshot)
    state = {"schemaVersion": "layoffs-source-evaluator-state-1.0.0", "evaluatedAt": generated_at, "sources": health}
    args.state_path.parent.mkdir(parents=True, exist_ok=True)
    args.state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**result, "dueSources": due_sources, "acceptedObservationRefs": snapshot["acceptedObservationRefs"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
