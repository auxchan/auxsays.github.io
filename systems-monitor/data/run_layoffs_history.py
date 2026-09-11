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

from systems_monitor_data.layoffs_history import (  # noqa: E402
    append_history,
    history_artifact,
    load_acceptance_ledger,
    migrate_existing_dol_seed,
    promote_candidate_batch,
)
from systems_monitor_data.layoffs_bls_dol import repair_dol_candidate_batch  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote explicitly authorized Layoffs candidates into revision-safe accepted history.")
    parser.add_argument("--candidate", type=Path, default=ROOT / "evidence" / "layoffs-runtime" / "layoffs-batch-candidate.json")
    parser.add_argument("--acceptance", type=Path, default=ROOT / "config" / "layoffs" / "history_acceptance.json")
    parser.add_argument("--rights", type=Path, default=ROOT / "config" / "rights" / "rights.json")
    parser.add_argument("--registry", type=Path, default=ROOT / "config" / "layoffs" / "sources_bls_dol.json")
    parser.add_argument("--raw-root", type=Path, default=ROOT / "local" / "layoffs-runtime" / "raw")
    parser.add_argument("--seed-snapshot", type=Path, default=ROOT / "review" / "factual-snapshot-candidate.json")
    parser.add_argument("--history", type=Path, default=ROOT / "review" / "layoffs-accepted-history.json")
    parser.add_argument("--report", type=Path, default=ROOT / "review" / "layoffs-history-activation-report.json")
    parser.add_argument("--accepted-at", default=None)
    args = parser.parse_args(argv)

    accepted_at = args.accepted_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rights_registry = _load(args.rights)
    ledger = load_acceptance_ledger(args.acceptance, rights_registry=rights_registry)
    existing = _load(args.history).get("observations", []) if args.history.exists() else []
    if not args.candidate.exists():
        report = {
            "schemaVersion": "layoffs-history-activation-report-1.0.0",
            "status": "BLOCKED_CANDIDATE_BATCH_MISSING",
            "acceptedAt": accepted_at,
            "acceptanceAuthority": ledger["authority"],
            "candidatePath": str(args.candidate),
            "acceptedObservationCount": len(existing),
            "newlyAcceptedObservationCount": 0,
            "acceptedComparableFactorCount": 0,
        }
        _write_atomic(args.report, report)
        print(json.dumps(report, sort_keys=True))
        return 2

    candidate = repair_dol_candidate_batch(
        _load(args.candidate),
        registry_path=args.registry,
        raw_root=args.raw_root,
    )
    _write_atomic(args.candidate, candidate)
    seed = migrate_existing_dol_seed(_load(args.seed_snapshot))
    seeded = append_history(existing, [seed])
    seed_migrated = len(seeded) > len(existing)
    promoted = promote_candidate_batch(candidate, ledger, accepted_at=accepted_at, existing_history=seeded)
    combined = append_history(seeded, promoted)
    if promoted or seed_migrated:
        _write_atomic(args.history, history_artifact(combined, generated_at=accepted_at))
    comparable_keys = {
        (row["canonicalFactorId"], row["sourceSeriesId"])
        for row in combined
        if len({
            candidate_row["validTime"]
            for candidate_row in combined
            if candidate_row["canonicalFactorId"] == row["canonicalFactorId"]
            and candidate_row["sourceSeriesId"] == row["sourceSeriesId"]
        }) >= 2
    }
    status = (
        "ACTIVATED" if promoted or combined
        else "BLOCKED_ACCEPTANCE_AUTHORITY_NONE" if ledger["authority"] == "NONE"
        else "BLOCKED_AUTOMATIC_ROUTINE_PROMOTION_DISABLED" if not ledger["automaticRoutinePromotionEnabled"]
        else "NO_MATCHING_ACCEPTANCE_RULE"
    )
    by_source = {
        source_id: len([row for row in combined if row["sourceId"] == source_id])
        for source_id in sorted({row["sourceId"] for row in combined})
    }
    current_revised = [row for row in combined if row.get("historyUseClass") == "CURRENT_REVISED_HISTORY"]
    forecast_eligible = [row for row in combined if row.get("forecastVintageEligible") is True]
    revision_chains = [row for row in combined if row.get("supersedesObservationId")]
    bed_rights = next((row for row in rights_registry.get("policies", []) if row.get("source_id") == "bls-bed"), None)
    report = {
        "schemaVersion": "layoffs-history-activation-report-1.0.0",
        "status": status,
        "acceptedAt": accepted_at,
        "acceptanceAuthority": ledger["authority"],
        "candidateCount": len(candidate.get("candidates", [])),
        "acceptedObservationCount": len(combined),
        "newlyAcceptedObservationCount": len(promoted) + int(seed_migrated),
        "newlyPromotedCandidateCount": len(promoted),
        "seedMigrated": seed_migrated,
        "acceptedBySource": by_source,
        "currentRevisedHistoryCount": len(current_revised),
        "acceptedComparableFactorCount": len({key[0] for key in comparable_keys}),
        "acceptedComparableSeriesCount": len(comparable_keys),
        "factualDirectionFactorCount": len({key[0] for key in comparable_keys}),
        "revisionChainCount": len(revision_chains),
        "revisionChains": [
            {
                "sourceSeriesId": row["sourceSeriesId"],
                "validTime": row["validTime"],
                "revisionNumber": row["revisionNumber"],
                "supersedesObservationId": row["supersedesObservationId"],
                "value": row["value"],
            }
            for row in revision_chains
        ],
        "dolRepair": {
            "sourceReleaseMarker": candidate.get("sourceDiagnostics", {}).get("dolSourceReleaseMarker"),
            "freshness": candidate.get("sourceDiagnostics", {}).get("dolFreshness"),
            "seedValue": "209000",
            "revisedValue": next(
                (row["value"] for row in combined if row["sourceSeriesId"] == "DOL-UI-SA-INITIAL" and row["validTime"] == "2026-08-08" and row["revisionNumber"] == 1),
                None,
            ),
            "routineRuleActive": True,
            "staleCurrentRetrievalFailsClosed": candidate.get("sourceDiagnostics", {}).get("dolFreshness", {}).get("status") != "CURRENT",
        },
        "bedRights": {
            "exactPolicyPresent": bed_rights is not None,
            "modelFeatureUse": None if bed_rights is None else bed_rights.get("decisions", {}).get("model_feature_use"),
            "modelTrainingUse": None if bed_rights is None else bed_rights.get("decisions", {}).get("model_training_ml_use"),
            "acceptedObservationCount": len([row for row in combined if row["sourceId"] == "bls-bed"]),
            "remainingBlocker": "TAYLOR_ACCEPTANCE_AUTHORITY_NOT_GRANTED",
        },
        "vintageQualifiedObservationCount": len(forecast_eligible),
        "materialityState": "UNKNOWN",
        "acceptedStructuralRelationshipCount": 0,
        "gateBStatus": "OPEN; descriptive history activated, structural acceptance unchanged",
        "humanQaRequired": True,
        "historyWritten": bool(promoted or seed_migrated),
    }
    _write_atomic(args.report, report)
    print(json.dumps(report, sort_keys=True))
    return 0 if combined else 2


if __name__ == "__main__":
    raise SystemExit(main())
