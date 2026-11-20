from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .layoffs_history import canonical_factor_id


PROPOSAL_SCHEMA = "layoffs-history-acceptance-proposal-1.0.0"
BATCH_SCHEMA = "layoffs-source-candidate-batch-1.0.0"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MATCH_FIELDS = {
    "sourceId": "source_id",
    "sourceSeriesId": "source_series_id",
    "unit": "unit",
    "frequency": "frequency",
    "geography": "geography",
    "seasonalAdjustment": "seasonal_adjustment",
}
REQUIRED_RULE_FIELDS = {
    "ruleId",
    "canonicalFactorId",
    "sourceId",
    "sourceSeriesId",
    "unit",
    "frequency",
    "geography",
    "seasonalAdjustment",
    "parserVersion",
    "validatorProfileId",
    "rightsPolicyId",
    "currentAndFutureDecision",
    "descriptiveHistoricalDecision",
    "descriptiveBackfillWindow",
    "forecastVintageDecision",
}


def load_acceptance_proposal(path: Path) -> dict[str, Any]:
    proposal = json.loads(path.read_text(encoding="utf-8"))
    if proposal.get("schemaVersion") != PROPOSAL_SCHEMA:
        raise ValueError("acceptance proposal schema is unsupported")
    if proposal.get("status") != "PENDING_TAYLOR_DECISION":
        raise ValueError("acceptance proposal crossed the Taylor decision boundary")
    if proposal.get("authority") != "NONE" or proposal.get("activationEffect") != "NONE":
        raise ValueError("an unapproved proposal cannot carry authority or activation effect")
    if proposal.get("automaticRoutinePromotionEnabled") is not False:
        raise ValueError("an unapproved proposal cannot enable routine promotion")
    if proposal.get("defaultDecision") != "REJECT_UNLESS_EXPLICITLY_LISTED":
        raise ValueError("acceptance proposal must fail closed")
    if proposal.get("globalConditions", {}).get("acceptedAt") is not None:
        raise ValueError("an unapproved proposal cannot have an acceptance time")
    rules = proposal.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("acceptance proposal must contain exact-series rules")
    seen_rules: set[str] = set()
    seen_series: set[tuple[str, str]] = set()
    profiles = {row["validatorProfileId"]: row for row in proposal.get("validatorProfiles", [])}
    for rule in rules:
        if not isinstance(rule, dict) or not REQUIRED_RULE_FIELDS.issubset(rule):
            raise ValueError("acceptance proposal rule is incomplete")
        if rule["ruleId"] in seen_rules:
            raise ValueError("acceptance proposal rule IDs must be unique")
        series_key = (rule["sourceId"], rule["sourceSeriesId"])
        if series_key in seen_series:
            raise ValueError("acceptance proposal exact-series identities must be unique")
        seen_rules.add(rule["ruleId"])
        seen_series.add(series_key)
        profile = profiles.get(rule["validatorProfileId"])
        if not profile or profile.get("parserVersion") != rule["parserVersion"]:
            raise ValueError("acceptance rule lacks its exact validator profile")
    return proposal


def load_vintage_matrix(path: Path) -> dict[str, Any]:
    matrix = json.loads(path.read_text(encoding="utf-8"))
    if matrix.get("schemaVersion") != "layoffs-vintage-capability-1.0.0":
        raise ValueError("vintage capability matrix schema is unsupported")
    if matrix.get("activationEffect") != "NONE":
        raise ValueError("vintage research cannot activate observations")
    seen: set[tuple[str, str]] = set()
    for row in matrix.get("series", []):
        key = (row["sourceId"], row["sourceSeriesId"])
        if key in seen:
            raise ValueError("vintage capability series identities must be unique")
        seen.add(key)
    return matrix


def simulate_acceptance(
    batch: dict[str, Any],
    proposal: dict[str, Any],
    rights_registry: dict[str, Any],
    vintage_matrix: dict[str, Any],
) -> dict[str, Any]:
    """Calibrate exact-series rules without accepting or writing any observation."""

    _validate_batch_boundary(batch)
    if proposal.get("authority") != "NONE" or proposal.get("automaticRoutinePromotionEnabled") is not False:
        raise ValueError("simulation requires a non-authoritative proposal")
    candidates = batch["candidates"]
    rules = proposal["rules"]
    rights_by_source = {row["source_id"]: row for row in rights_registry.get("policies", [])}
    vintages = {(row["sourceId"], row["sourceSeriesId"]): row for row in vintage_matrix.get("series", [])}
    parser_by_hash = {
        row["sha256"]: row.get("parser_version")
        for row in batch.get("rawArtifacts", [])
        if isinstance(row, dict) and row.get("sha256")
    }
    required_rights = proposal["globalConditions"]["requiredRightsOperations"]

    counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    series_stats: dict[tuple[str, str], Counter[str]] = {}
    outside_stats: Counter[tuple[str, str]] = Counter()
    validation_failures: list[dict[str, Any]] = []

    for candidate in candidates:
        errors = _candidate_errors(candidate, parser_by_hash)
        if errors:
            counts["invalidCandidates"] += 1
            reason_counts.update(errors)
            validation_failures.append({
                "observationId": candidate.get("observation_id"),
                "sourceSeriesId": candidate.get("source_series_id"),
                "errors": errors,
            })
            continue
        matches = [
            rule for rule in rules
            if rule["sourceId"] == candidate["source_id"]
            and rule["sourceSeriesId"] == candidate["source_series_id"]
        ]
        if len(matches) > 1:
            counts["ambiguousMatches"] += 1
            reason_counts["AMBIGUOUS_EXACT_SERIES_RULE"] += 1
            continue
        if not matches:
            counts["outsideProposedScope"] += 1
            outside_stats[(candidate["source_id"], candidate["source_series_id"])] += 1
            continue

        rule = matches[0]
        key = (rule["sourceId"], rule["sourceSeriesId"])
        stats = series_stats.setdefault(key, Counter())
        constraint_errors = _rule_constraint_errors(rule, candidate)
        if constraint_errors:
            counts["constraintRejectedWithinProposedScope"] += 1
            stats["rejected"] += 1
            reason_counts.update(constraint_errors)
            stats.update(constraint_errors)
            validation_failures.append({
                "observationId": candidate.get("observation_id"),
                "sourceSeriesId": candidate.get("source_series_id"),
                "errors": constraint_errors,
            })
            continue
        counts["structuralMatches"] += 1
        stats["structuralMatches"] += 1

        if parser_by_hash.get(candidate["artifact_sha256"]) != rule["parserVersion"]:
            counts["blockedWithinProposedScope"] += 1
            stats["blocked"] += 1
            stats["PARSER_VERSION_MISMATCH"] += 1
            reason_counts["PARSER_VERSION_MISMATCH"] += 1
            continue

        rights = rights_by_source.get(rule["sourceId"])
        if rule.get("rightsPolicyId") != rule["sourceId"] or not _rights_allow(rights, required_rights):
            counts["blockedWithinProposedScope"] += 1
            stats["blocked"] += 1
            stats["MISSING_EXPLICIT_ALLOW_RIGHTS_POLICY"] += 1
            reason_counts["MISSING_EXPLICIT_ALLOW_RIGHTS_POLICY"] += 1
            continue

        if str(rule["currentAndFutureDecision"]).startswith("CONDITIONAL_"):
            counts["contingentWithinProposedScope"] += 1
            counts["descriptiveHistoryCandidatesAfterPreconditions"] += 1
            counts["forecastVintageIneligible"] += 1
            stats["contingent"] += 1
            stats["descriptiveHistoryCandidatesAfterPreconditions"] += 1
            stats["forecastVintageIneligible"] += 1
            stats["EXISTING_ACCEPTED_SEED_MIGRATION_AND_FRESHNESS_REQUIRED"] += 1
            reason_counts["EXISTING_ACCEPTED_SEED_MIGRATION_AND_FRESHNESS_REQUIRED"] += 1
            reason_counts["EXACT_ARCHIVE_VINTAGE_EVIDENCE_ABSENT"] += 1
            continue

        counts["decisionReadyIfTaylorApproves"] += 1
        counts["descriptiveHistoryCandidates"] += 1
        counts["descriptiveHistoryCandidatesAfterPreconditions"] += 1
        stats["decisionReadyIfTaylorApproves"] += 1
        stats["descriptiveHistoryCandidates"] += 1
        stats["descriptiveHistoryCandidatesAfterPreconditions"] += 1
        if _forecast_vintage_eligible(candidate, vintages.get(key)):
            counts["forecastVintageEligible"] += 1
            stats["forecastVintageEligible"] += 1
        else:
            counts["forecastVintageIneligible"] += 1
            stats["forecastVintageIneligible"] += 1
            reason_counts["EXACT_ARCHIVE_VINTAGE_EVIDENCE_ABSENT"] += 1

    by_series = []
    for rule in rules:
        key = (rule["sourceId"], rule["sourceSeriesId"])
        stats = series_stats.get(key, Counter())
        vintage = vintages.get(key, {})
        by_series.append({
            "ruleId": rule["ruleId"],
            "canonicalFactorId": rule["canonicalFactorId"],
            "sourceId": rule["sourceId"],
            "sourceSeriesId": rule["sourceSeriesId"],
            "candidateRows": stats["structuralMatches"],
            "decisionReadyIfTaylorApproves": stats["decisionReadyIfTaylorApproves"],
            "blocked": stats["blocked"],
            "contingent": stats["contingent"],
            "rejected": stats["rejected"],
            "blockReasons": sorted(key for key in stats if key.isupper() and stats[key]),
            "descriptiveHistoryCandidates": stats["descriptiveHistoryCandidates"],
            "descriptiveHistoryCandidatesAfterPreconditions": stats["descriptiveHistoryCandidatesAfterPreconditions"],
            "forecastVintageEligible": stats["forecastVintageEligible"],
            "currentVintageCapability": vintage.get("currentLevel", "UNASSESSED"),
            "officialVintageCeiling": vintage.get("officialCeiling", "UNASSESSED"),
        })

    decision_ready_series = sum(row["decisionReadyIfTaylorApproves"] > 0 for row in by_series)
    comparable_ready_series = sum(row["decisionReadyIfTaylorApproves"] >= 2 for row in by_series)
    descriptive_series_after_preconditions = sum(
        row["descriptiveHistoryCandidatesAfterPreconditions"] > 0 for row in by_series
    )
    comparable_series_after_preconditions = sum(
        row["descriptiveHistoryCandidatesAfterPreconditions"] >= 2 for row in by_series
    )
    structurally_comparable_series = sum(row["candidateRows"] >= 2 for row in by_series)
    total = len(candidates)
    accounted = (
        counts["invalidCandidates"]
        + counts["ambiguousMatches"]
        + counts["outsideProposedScope"]
        + counts["constraintRejectedWithinProposedScope"]
        + counts["blockedWithinProposedScope"]
        + counts["contingentWithinProposedScope"]
        + counts["decisionReadyIfTaylorApproves"]
    )
    if accounted != total:
        raise ValueError("acceptance simulation did not account for every candidate")

    report = {
        "schemaVersion": "layoffs-acceptance-simulation-1.0.0",
        "simulatedAt": batch.get("generatedAt"),
        "authority": "NONE",
        "activationEffect": "NONE",
        "input": {
            "batchSchemaVersion": batch["schemaVersion"],
            "batchRunId": batch.get("runId"),
            "batchCandidates": total,
            "proposalRules": len(rules),
            "batchPayloadSha256": _sha(batch),
            "sourceDiagnostics": batch.get("sourceDiagnostics", {}),
        },
        "counts": {
            "structuralMatches": counts["structuralMatches"],
            "decisionReadyIfTaylorApproves": counts["decisionReadyIfTaylorApproves"],
            "blockedWithinProposedScope": counts["blockedWithinProposedScope"],
            "contingentWithinProposedScope": counts["contingentWithinProposedScope"],
            "outsideProposedScope": counts["outsideProposedScope"],
            "constraintRejectedWithinProposedScope": counts["constraintRejectedWithinProposedScope"],
            "invalidCandidates": counts["invalidCandidates"],
            "ambiguousMatches": counts["ambiguousMatches"],
            "descriptiveHistoryCandidates": counts["descriptiveHistoryCandidates"],
            "descriptiveHistoryCandidatesAfterPreconditions": counts["descriptiveHistoryCandidatesAfterPreconditions"],
            "forecastVintageEligible": counts["forecastVintageEligible"],
            "forecastVintageIneligible": counts["forecastVintageIneligible"],
            "decisionReadySeries": decision_ready_series,
            "comparableHistoryReadySeries": comparable_ready_series,
            "descriptiveSeriesAfterPreconditions": descriptive_series_after_preconditions,
            "comparableHistoryReadySeriesAfterPreconditions": comparable_series_after_preconditions,
            "structurallyComparableSeriesIfAllBlockersResolve": structurally_comparable_series,
            "rejectedOrHeldByCurrentPreconditions": (
                counts["constraintRejectedWithinProposedScope"]
                + counts["blockedWithinProposedScope"]
                + counts["contingentWithinProposedScope"]
            ),
            "acceptedObservationsWritten": 0,
        },
        "reasonCounts": dict(sorted(reason_counts.items())),
        "bySeries": by_series,
        "outsideProposedScope": [
            {"sourceId": source_id, "sourceSeriesId": series_id, "candidateRows": count}
            for (source_id, series_id), count in sorted(outside_stats.items())
        ],
        "validationFailures": validation_failures,
        "forecastLeakageBoundary": {
            "currentBatchClass": "CURRENT_REVISED_HISTORY",
            "forecastUse": "FORBIDDEN",
            "requiredEligibleClasses": ["ORIGINAL_RELEASE_VALUE", "VINTAGE_RECONSTRUCTED"],
            "note": "Official archive capability is not row-level vintage evidence. Every forecast-as-of observation must independently satisfy the archived-artifact contract."
        },
        "decisionBoundary": "This simulation is calibration evidence only. It does not modify history_acceptance.json, add acceptedTime, publish history, or authorize routine promotion."
    }
    report["reportSha256"] = _sha(report)
    return report


def _validate_batch_boundary(batch: dict[str, Any]) -> None:
    if batch.get("schemaVersion") != BATCH_SCHEMA:
        raise ValueError("candidate batch schema is unsupported")
    if batch.get("activationStatus") != "NOT_ACCEPTED_NOT_PUBLISHABLE":
        raise ValueError("candidate batch crossed its staging boundary")
    if not isinstance(batch.get("candidates"), list):
        raise ValueError("candidate batch has no candidate list")


def _candidate_errors(candidate: dict[str, Any], parser_by_hash: dict[str, str | None]) -> list[str]:
    required = {
        "observation_id", "canonical_factor", "source_id", "source_series_id", "release_id",
        "artifact_sha256", "value", "unit", "frequency", "geography", "seasonal_adjustment",
        "observation_period", "public_time", "retrieved_time", "accepted_time",
        "publication_time_kind", "provenance_url", "evidence_url", "methodology_url",
    }
    errors: list[str] = []
    if not required.issubset(candidate):
        return ["INCOMPLETE_CANDIDATE"]
    if candidate["accepted_time"] is not None or candidate.get("publication_eligible") is not False:
        errors.append("CANDIDATE_ALREADY_CROSSED_ACCEPTANCE_BOUNDARY")
    artifact_hash = candidate["artifact_sha256"]
    if not isinstance(artifact_hash, str) or not SHA256.fullmatch(artifact_hash):
        errors.append("INVALID_ARTIFACT_SHA256")
    elif artifact_hash not in parser_by_hash:
        errors.append("RAW_ARTIFACT_NOT_DECLARED")
    for field in ("provenance_url", "evidence_url", "methodology_url"):
        if not isinstance(candidate[field], str) or not candidate[field].startswith("https://"):
            errors.append(f"NON_HTTPS_{field.upper()}")
    try:
        if _utc(candidate["public_time"]) > _utc(candidate["retrieved_time"]):
            errors.append("PUBLIC_TIME_AFTER_RETRIEVAL_TIME")
    except ValueError:
        errors.append("INVALID_TIME")
    if candidate["publication_time_kind"] not in {"official", "conservative_retrieval_bound"}:
        errors.append("UNSUPPORTED_PUBLICATION_TIME_KIND")
    return errors


def _rule_constraint_errors(rule: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if rule["canonicalFactorId"] != canonical_factor_id(candidate["canonical_factor"]):
        errors.append("INCOMPATIBLE_CANONICAL_FACTOR")
    for field, candidate_field in MATCH_FIELDS.items():
        if field in {"sourceId", "sourceSeriesId"}:
            continue
        if rule[field] != candidate.get(candidate_field):
            errors.append(f"{field.upper()}_MISMATCH")
    return errors


def _rights_allow(policy: dict[str, Any] | None, operations: list[str]) -> bool:
    if not policy:
        return False
    decisions = policy.get("decisions", {})
    return all(decisions.get(operation) == "ALLOW" for operation in operations)


def _forecast_vintage_eligible(candidate: dict[str, Any], capability: dict[str, Any] | None) -> bool:
    if not capability or not str(capability.get("officialCeiling", "")).startswith("LEVEL_2"):
        return False
    if candidate.get("forecast_vintage_eligible") is not True:
        return False
    if candidate.get("history_use_class") not in {"ORIGINAL_RELEASE_VALUE", "VINTAGE_RECONSTRUCTED"}:
        return False
    evidence = candidate.get("vintage_evidence")
    if not isinstance(evidence, dict):
        return False
    required = {"archive_url", "artifact_sha256", "release_header_time", "table_selector"}
    if not required.issubset(evidence):
        return False
    return (
        str(evidence["archive_url"]).startswith("https://")
        and bool(SHA256.fullmatch(str(evidence["artifact_sha256"])))
        and _utc(evidence["release_header_time"]) <= _utc(candidate["retrieved_time"])
        and bool(evidence["table_selector"])
    )


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _sha(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
