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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def factor_states(bls_dol: dict, census: dict, context: dict, health: dict[str, dict]) -> list[dict]:
    rows: dict[str, dict] = {}
    default_state = {"activationState": "SOURCE_IDENTIFIED", "health": "disabled", "reasonCode": "SOURCE_PROFILE_NOT_SCHEDULED"}
    for series in bls_dol["series"]:
        source_id = series["source_id"]
        state = health[source_id]
        rows[series["canonical_factor"]] = {
            "sourceId": source_id,
            "canonicalFactorId": series["canonical_factor"],
            "activationState": "SOURCE_ENABLED_PENDING_ACCEPTANCE" if state["health"] == "success" else state["activationState"],
            "health": state["health"],
            "reasonCode": state.get("reasonCode", "AWAITING_SOURCE_ACCEPTANCE"),
            "candidateSeriesId": series["series_id"],
            "evidenceUrl": series["human_evidence_url"],
        }
    for source in census["sources"]:
        state = health.get(source["source_id"], default_state)
        for series in source["series"]:
            for placement in series["placement_candidates"]:
                factor_id = f"factor:canonical:{placement}"
                rows.setdefault(factor_id, {
                    "sourceId": source["source_id"], "canonicalFactorId": factor_id,
                    "activationState": state["activationState"], "health": state["health"],
                    "reasonCode": state.get("reasonCode", "AWAITING_SOURCE_ACCEPTANCE"),
                    "candidateSeriesId": series["source_series_id"], "evidenceUrl": source["evidence_url"],
                })
    for source in context["sources"]:
        state = health.get(source["source_id"], default_state)
        for series in source.get("series", []):
            rows.setdefault(series["canonical_factor"], {
                "sourceId": source["source_id"], "canonicalFactorId": series["canonical_factor"],
                "activationState": state["activationState"], "health": state["health"],
                "reasonCode": state.get("reasonCode", "AWAITING_SOURCE_ACCEPTANCE"),
                "candidateSeriesId": series["source_series_id"], "evidenceUrl": source["evidence_url"],
            })
        for candidate in source.get("selector_candidates", []):
            rows.setdefault(candidate["canonical_factor"], {
                "sourceId": source["source_id"], "canonicalFactorId": candidate["canonical_factor"],
                "activationState": "BLOCKED", "health": "blocked",
                "reasonCode": source["selector_status"], "evidenceUrl": source["evidence_url"],
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
    previous = load(args.state_path) if args.state_path.exists() else {"sources": {}}
    health: dict[str, dict] = {}
    due_sources: list[str] = []

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
            health[source_id] = {"activationState": "SOURCE_IDENTIFIED", "health": "disabled" if args.no_network else "manual_review_needed", "reasonCode": "NETWORK_DISABLED_REVIEW_BUILD" if args.no_network else "RETRIEVAL_PENDING", "lastAttemptAt": prior.get("lastAttemptAt")}

    bls_family = {"bls-jolts", "bls-cps", "bls-ces", "bls-bed", "dol-ui-claims"}
    if not args.no_network and bls_family.intersection(due_sources):
        try:
            batch = collect_layoffs_bls_dol_candidates(
                registry_path=config / "sources_bls_dol.json", raw_root=args.runtime_root / "raw",
                candidate_path=args.runtime_root / "layoffs-batch-candidate.json",
            )
            for source_id in bls_family:
                health[source_id] = {"activationState": "SOURCE_ENABLED_PENDING_ACCEPTANCE", "health": "success", "reasonCode": "CANDIDATE_BATCH_RETRIEVED_NOT_ACCEPTED", "lastAttemptAt": generated_at, "candidateCount": len(batch["candidates"])}
        except Exception as exc:
            for source_id in bls_family.intersection(due_sources):
                health[source_id] = {"activationState": "SOURCE_IDENTIFIED", "health": "broken", "reasonCode": type(exc).__name__, "lastAttemptAt": generated_at}

    for source_id in due_sources:
        if source_id not in bls_family and not args.no_network:
            health[source_id] = {"activationState": health[source_id]["activationState"], "health": "manual_review_needed", "reasonCode": "ADAPTER_REQUIRES_ACCEPTED_SELECTOR_OR_DEDICATED_RUNNER", "lastAttemptAt": generated_at}

    source_states = factor_states(bls_dol, census, context, health)
    snapshot = build_review_snapshot(taxonomy=taxonomy, source_states=source_states, relationships=relationships["relationships"], generated_at=generated_at, source_health=health)
    result = atomic_activate(snapshot, args.active_snapshot)
    state = {"schemaVersion": "layoffs-source-evaluator-state-1.0.0", "evaluatedAt": generated_at, "sources": health}
    args.state_path.parent.mkdir(parents=True, exist_ok=True)
    args.state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**result, "dueSources": due_sources, "acceptedObservationRefs": snapshot["acceptedObservationRefs"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
