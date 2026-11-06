from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


REPLAY_MODES = {"PUBLICLY_AVAILABLE_AS_OF", "OPERATIONALLY_KNOWN_AS_OF", "LATEST_REVISED_TRUTH", "FORECAST_AS_OF"}
FORECAST_HISTORY_CLASSES = {"ORIGINAL_RELEASE_VALUE", "VINTAGE_RECONSTRUCTED"}
REQUIRED_RIGHTS_OPERATIONS = (
    "ingestion",
    "raw_retention",
    "derived_retention",
    "transformation",
    "internal_analytical_use",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_RULE_FIELDS = {
    "ruleId",
    "authority",
    "acceptedAt",
    "canonicalFactorId",
    "sourceId",
    "sourceSeriesId",
    "unit",
    "frequency",
    "geography",
    "seasonalAdjustment",
    "effectiveFrom",
    "parserVersion",
    "validatorProfileId",
    "rightsPolicyId",
    "rawArtifactSourceId",
    "methodologyUrl",
    "allowedPublicationTimeKinds",
    "allowedRevisionStatuses",
    "descriptiveBackfillAuthority",
    "descriptiveBackfillStart",
    "descriptiveBackfillEnd",
    "historyUseClass",
    "forecastVintageEligible",
    "requiresCurrentSourceFreshness",
}
COMPARABILITY_FIELDS = (
    "canonicalFactorId",
    "sourceId",
    "sourceSeriesId",
    "unit",
    "frequency",
    "geography",
    "seasonalAdjustment",
)
CANONICAL_ALIASES = {
    "layoffs-discharges-level": "layoffs-and-discharges",
    "layoffs-discharges-rate": "layoffs-and-discharges",
    "initial-ui-claims": "initial-claims",
    "continued-ui-claims": "continued-claims-insured-unemployment",
    "insured-unemployment-rate": "continued-claims-insured-unemployment",
    "closing-establishment-losses": "establishment-closures",
    "establishment-death-job-losses": "establishment-deaths",
    "bds-job-destruction": "gross-job-losses",
    "bds-job-destruction-continuers": "establishment-contractions",
    "bds-job-destruction-deaths": "establishment-closures",
    "bds-establishment-exits": "establishment-deaths",
    "bds-firm-deaths": "firm-deaths",
    "bds-firm-death-establishments": "firm-age-size-vulnerability",
    "bds-firm-death-employment": "firm-death-shutdown-stress",
    "payroll-growth": "total-nonfarm-payroll-change",
    "business-formation": "business-formations-within-4-quarters",
    "business-formations-four-quarters": "business-formations-within-4-quarters",
    "business-formations": "business-formations-within-4-quarters",
    "regional-employment-growth": "state-level-payroll-growth-breadth",
}


def load_acceptance_ledger(path: Path, *, rights_registry: dict[str, Any] | None = None) -> dict[str, Any]:
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("schemaVersion") != "layoffs-history-acceptance-1.0.0":
        raise ValueError("history acceptance ledger schema is unsupported")
    if ledger.get("defaultDecision") != "REJECT_UNLESS_EXPLICITLY_LISTED":
        raise ValueError("history acceptance must fail closed")
    rules = ledger.get("rules")
    if not isinstance(rules, list):
        raise ValueError("history acceptance rules must be a list")
    if not isinstance(ledger.get("automaticRoutinePromotionEnabled"), bool):
        raise ValueError("history acceptance ledger must declare routine-promotion state")
    if ledger.get("authority") == "NONE" and rules:
        raise ValueError("an authority-free ledger cannot promote observations")
    if ledger.get("authority") != "NONE" and rights_registry is None:
        raise ValueError("an active acceptance ledger requires the central rights registry")
    rights_by_source = {
        row.get("source_id"): row
        for row in (rights_registry or {}).get("policies", [])
        if isinstance(row, dict)
    }
    profiles = {row.get("validatorProfileId"): row for row in ledger.get("validatorProfiles", []) if isinstance(row, dict)}
    accepted_authorities = {ledger.get("authority"), *ledger.get("inheritedAuthorities", [])}
    if any(not isinstance(authority, str) or authority in {"", "NONE"} for authority in accepted_authorities):
        raise ValueError("history acceptance authority chain is invalid")
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict) or not REQUIRED_RULE_FIELDS.issubset(rule):
            raise ValueError("history acceptance rule is incomplete")
        if rule["ruleId"] in seen:
            raise ValueError("history acceptance rule IDs must be unique")
        seen.add(rule["ruleId"])
        _utc(rule["acceptedAt"])
        _utc(rule["effectiveFrom"])
        if rule["authority"] not in accepted_authorities:
            raise ValueError("history acceptance rule lacks authority or accepted rights")
        if rule["rightsPolicyId"] != rule["sourceId"]:
            raise ValueError("history acceptance rule lacks an exact source rights policy")
        rights = rights_by_source.get(rule["rightsPolicyId"])
        if not rights or any(rights.get("decisions", {}).get(operation) != "ALLOW" for operation in REQUIRED_RIGHTS_OPERATIONS):
            raise ValueError("history acceptance rule does not pass the central rights registry")
        profile = profiles.get(rule["validatorProfileId"])
        if not profile or profile.get("parserVersion") != rule["parserVersion"] or profile.get("methodologyUrl") != rule["methodologyUrl"]:
            raise ValueError("history acceptance rule lacks its exact validator profile")
        allowed_parser_versions = set(rule.get("allowedParserVersions", [rule["parserVersion"]]))
        allowed_profile_ids = set(rule.get("allowedValidatorProfileIds", [rule["validatorProfileId"]]))
        profiled_parser_versions = {
            profiles[profile_id].get("parserVersion")
            for profile_id in allowed_profile_ids
            if profile_id in profiles and profiles[profile_id].get("methodologyUrl") == rule["methodologyUrl"]
        }
        if allowed_parser_versions != profiled_parser_versions:
            raise ValueError("history acceptance alternate parser lacks an exact validator profile")
        if not isinstance(rule["allowedPublicationTimeKinds"], list) or not rule["allowedPublicationTimeKinds"]:
            raise ValueError("history acceptance rule lacks publication-time bounds")
        if not isinstance(rule["allowedRevisionStatuses"], list) or not rule["allowedRevisionStatuses"]:
            raise ValueError("history acceptance rule lacks revision bounds")
        if rule["descriptiveBackfillAuthority"] not in accepted_authorities:
            raise ValueError("history acceptance backfill lacks authority")
        _period_key(rule["descriptiveBackfillStart"], rule["frequency"])
        _period_key(rule["descriptiveBackfillEnd"], rule["frequency"])
        if _period_key(rule["descriptiveBackfillStart"], rule["frequency"]) > _period_key(rule["descriptiveBackfillEnd"], rule["frequency"]):
            raise ValueError("history acceptance backfill window is inverted")
        if rule["historyUseClass"] != "CURRENT_REVISED_HISTORY" or rule["forecastVintageEligible"] is not False:
            raise ValueError("Taylor authority is bounded to descriptive current-revised history")
        if not isinstance(rule["requiresCurrentSourceFreshness"], bool):
            raise ValueError("history acceptance rule must declare its freshness gate")
        if rule.get("forecastVintageEligible"):
            if rule.get("historyUseClass") not in FORECAST_HISTORY_CLASSES or not rule.get("vintageEvidenceId"):
                raise ValueError("forecast-vintage acceptance rule lacks exact vintage authority")
    return ledger


def promote_candidate_batch(
    batch: dict[str, Any],
    ledger: dict[str, Any],
    *,
    accepted_at: str,
    existing_history: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Promote only explicitly covered candidates; retrieval alone never accepts data."""

    _utc(accepted_at)
    if batch.get("activationStatus") != "NOT_ACCEPTED_NOT_PUBLISHABLE":
        raise ValueError("candidate batch crossed its staging boundary")
    if batch.get("schemaVersion") != "layoffs-source-candidate-batch-1.0.0":
        raise ValueError("candidate batch schema is unsupported")
    candidates = batch.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidate batch has no candidate list")
    if ledger.get("authority") == "NONE" or not ledger.get("automaticRoutinePromotionEnabled", False):
        return []
    rules = ledger.get("rules", [])
    history = [dict(row) for row in existing_history]
    for row in history:
        _validate_accepted_observation(row)
    raw_by_hash = {
        row.get("sha256"): row
        for row in batch.get("rawArtifacts", [])
        if isinstance(row, dict) and row.get("sha256")
    }
    promoted: list[dict[str, Any]] = []
    for candidate in candidates:
        matches = [rule for rule in rules if _rule_matches(rule, candidate)]
        if not matches:
            identity_matches = [
                rule for rule in rules
                if rule["sourceId"] == candidate.get("source_id")
                and rule["sourceSeriesId"] == candidate.get("source_series_id")
            ]
            if identity_matches:
                raise ValueError("manual_review_needed: candidate metadata is outside exact authority")
            continue
        if len(matches) != 1:
            raise ValueError("candidate is covered by multiple acceptance rules")
        rule = matches[0]
        _validate_candidate_against_rule(candidate, rule, raw_by_hash)
        mode = _acceptance_mode(candidate, rule)
        if mode is None:
            continue
        if mode == "ROUTINE" and rule["requiresCurrentSourceFreshness"]:
            freshness = batch.get("sourceDiagnostics", {}).get("dolFreshness", {})
            if freshness.get("status") != "CURRENT":
                continue
        if _utc(rule["acceptedAt"]) > _utc(accepted_at):
            raise ValueError("runner acceptance time precedes rule acceptance")
        semantic_prior = next((
            row for row in history + promoted
            if row.get("canonicalFactorId") == canonical_factor_id(candidate["canonical_factor"])
            and row.get("sourceSeriesId") == candidate["source_series_id"]
            and row.get("validTime") == candidate["observation_period"]
            and row.get("value") == str(_decimal(candidate["value"]))
        ), None)
        if semantic_prior is not None and rule.get("historyUseClass") == "CURRENT_REVISED_HISTORY":
            continue
        identity = _accepted_identity(candidate)
        prior = next((row for row in history + promoted if row.get("observationId") == identity), None)
        if prior is not None:
            if not _candidate_matches_accepted(candidate, rule, prior):
                raise ValueError("immutable observation identity was reused with different content")
            continue
        observation = _accepted_observation(candidate, rule, accepted_at, history + promoted)
        promoted.append(observation)
    return promoted


def bound_candidate_batch_to_series(batch: dict[str, Any], source_series_ids: Iterable[str]) -> dict[str, Any]:
    """Return an acceptance-neutral batch restricted to exact governed IDs."""

    requested = {series_id for series_id in source_series_ids if isinstance(series_id, str) and series_id}
    if not requested:
        raise ValueError("exact-series activation scope cannot be empty")
    candidates = batch.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidate batch has no candidate list")
    available = {row.get("source_series_id") for row in candidates if isinstance(row, dict)}
    missing = requested - available
    if missing:
        raise ValueError(f"exact-series activation scope is absent from candidate batch: {sorted(missing)}")
    bounded = dict(batch)
    bounded["candidates"] = [row for row in candidates if row.get("source_series_id") in requested]
    bounded["activationScope"] = {
        "mode": "EXACT_SOURCE_SERIES_IDS",
        "sourceSeriesIds": sorted(requested),
    }
    return bounded


def append_history(
    existing: Iterable[dict[str, Any]],
    incoming: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append immutable vintages, rejecting identity reuse with changed content."""

    result = [dict(row) for row in existing]
    for row in result:
        _validate_accepted_observation(row)
    by_id = {row["observationId"]: row for row in result}
    for row in incoming:
        _validate_accepted_observation(row)
        prior = by_id.get(row["observationId"])
        if prior is not None:
            if prior.get("objectHash") != row.get("objectHash"):
                raise ValueError("immutable observation identity was reused with different content")
            continue
        result.append(dict(row))
        by_id[row["observationId"]] = row
    result.sort(key=lambda row: (_period_key(row["validTime"], row["frequency"]), row["acceptedTime"], row["revisionNumber"]))
    return result


def observations_as_of(
    history: Iterable[dict[str, Any]],
    *,
    cutoff: str | None,
    mode: str,
) -> list[dict[str, Any]]:
    if mode not in REPLAY_MODES:
        raise ValueError("unknown replay mode")
    if mode != "LATEST_REVISED_TRUTH" and cutoff is None:
        raise ValueError("as-of replay requires a cutoff")
    cutoff_time = _utc(cutoff) if cutoff is not None else None
    eligible: list[dict[str, Any]] = []
    for row in history:
        _validate_accepted_observation(row)
        if mode in {"PUBLICLY_AVAILABLE_AS_OF", "FORECAST_AS_OF"} and _utc(row["publicTime"]) > cutoff_time:
            continue
        if mode == "OPERATIONALLY_KNOWN_AS_OF" and _utc(row["acceptedTime"]) > cutoff_time:
            continue
        if mode == "FORECAST_AS_OF" and not _forecast_row_eligible(row):
            continue
        eligible.append(dict(row))
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in eligible:
        key = (row["canonicalFactorId"], row["sourceSeriesId"], row["validTime"])
        current = latest.get(key)
        if current is None or _revision_key(row, mode) > _revision_key(current, mode):
            latest[key] = row
    return sorted(latest.values(), key=lambda row: (row["canonicalFactorId"], row["sourceSeriesId"], _period_key(row["validTime"], row["frequency"])))


def comparable_change(
    history: Iterable[dict[str, Any]],
    *,
    canonical_factor_id: str,
    source_series_id: str,
    mode: str = "LATEST_REVISED_TRUTH",
    cutoff: str | None = None,
    materiality_profiles: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    visible = observations_as_of(history, cutoff=cutoff, mode=mode)
    selected = [
        row for row in visible
        if row["canonicalFactorId"] == canonical_factor_id and row["sourceSeriesId"] == source_series_id
    ]
    if not selected:
        return None
    tuples = {tuple(row[field] for field in COMPARABILITY_FIELDS) for row in selected}
    if len(tuples) != 1:
        raise ValueError("series history mixes non-comparable definitions")
    selected.sort(key=lambda row: _period_key(row["validTime"], row["frequency"]))
    if len(selected) < 2:
        return None
    previous, current = selected[-2], selected[-1]
    current_value = _decimal(current["value"])
    previous_value = _decimal(previous["value"])
    delta = current_value - previous_value
    percent = None if previous_value == 0 else (delta / abs(previous_value)) * Decimal("100")
    direction = "UP" if delta > 0 else "DOWN" if delta < 0 else "FLAT"
    materiality = _materiality(current, delta, percent, materiality_profiles)
    return {
        "schemaVersion": "layoffs-comparable-change-1.0.0",
        "canonicalFactorId": canonical_factor_id,
        "sourceSeriesId": source_series_id,
        "frequency": current["frequency"],
        "currentObservationId": current["observationId"],
        "previousObservationId": previous["observationId"],
        "currentPeriod": current["validTime"],
        "previousPeriod": previous["validTime"],
        "currentValue": str(current_value),
        "previousValue": str(previous_value),
        "absoluteDelta": str(delta),
        "percentDelta": None if percent is None else str(percent.quantize(Decimal("0.0001"))),
        "direction": direction,
        "directionGlyph": {"UP": "↑", "DOWN": "↓", "FLAT": "→"}[direction],
        "magnitude": {
            "absoluteDelta": str(delta),
            "percentDelta": None if percent is None else str(percent.quantize(Decimal("0.0001"))),
            "unit": current["unit"],
        },
        "revisionFlag": current["revisionNumber"] > 0,
        "materiality": materiality,
        "destinationImpact": {
            "status": "UNKNOWN",
            "reason": "NO_ACCEPTED_DESTINATION_CONTEXT_RELATIONSHIP",
        },
        "forecastVintageEligible": _forecast_row_eligible(previous) and _forecast_row_eligible(current),
        "replayMode": mode,
        "knowledgeCutoff": cutoff,
        "economicSignalEligible": False,
    }


def deterministic_interpretation(
    change: dict[str, Any],
    *,
    source_measure: str,
    relevance: str,
) -> dict[str, str]:
    if change.get("economicSignalEligible") is not False:
        raise ValueError("history interpretation cannot become an economic impact signal")
    current = change["currentValue"]
    previous = change["previousValue"]
    delta = change["absoluteDelta"]
    return {
        "WHAT_CHANGED": f"The accepted observation moved {change['direction'].lower()} at its native {change['frequency']} cadence.",
        "HOW_MUCH": f"The value changed by {delta}, from {previous} to {current}.",
        "COMPARED_WITH_WHAT": f"{change['currentPeriod']} is compared with the previous accepted compatible period, {change['previousPeriod']}.",
        "WHAT_THE_SOURCE_MEASURES": source_measure,
        "WHY_RELEVANT": relevance,
        "WHAT_AUXSAYS_CANNOT_CLAIM": "This change does not establish causality, destination impact, or a forecast.",
    }


def history_artifact(history: Iterable[dict[str, Any]], *, generated_at: str) -> dict[str, Any]:
    _utc(generated_at)
    rows = append_history([], history)
    payload = {
        "schemaVersion": "layoffs-accepted-history-1.0.0",
        "publicationClass": "INTERNAL_ACCEPTED_EVIDENCE",
        "generatedAt": generated_at,
        "observations": rows,
    }
    payload["payloadSha256"] = _sha(payload)
    return payload


def migrate_existing_dol_seed(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Migrate the one already accepted 209,000 claims record without broadening it."""

    payload = snapshot.get("payload", {})
    metrics = payload.get("extensions", {}).get("auxsays.phase2.metrics", [])
    metric = next((row for row in metrics if row.get("id") == "US_LABOR_INITIAL_UI_CLAIMS"), None)
    if not metric:
        raise ValueError("accepted DOL seed metric is missing")
    if (
        metric.get("value") != 209000
        or metric.get("validTime") != "2026-08-08"
        or metric.get("sourceRefs") != ["dol-ui-claims"]
        or metric.get("sourceSeriesIds") != ["DOL-UI-SA-INITIAL"]
    ):
        raise ValueError("accepted DOL seed no longer matches the authorized identity")
    provenance_ids = metric.get("provenanceRefs", [])
    provenance_registry = payload.get("extensions", {}).get("auxsays.phase3.provenance", {})
    if len(provenance_ids) != 1 or provenance_ids[0] not in provenance_registry:
        raise ValueError("accepted DOL seed provenance is missing")
    provenance = provenance_registry[provenance_ids[0]]
    source = payload.get("sources", {}).get("dol-ui-claims", {})
    if (
        provenance.get("sourceId") != "dol-ui-claims"
        or provenance.get("seriesIds") != ["DOL-UI-SA-INITIAL"]
        or provenance.get("vintageId") != "DOL-UI-2026-08-13-advance"
        or provenance.get("revisionNumber") != 0
    ):
        raise ValueError("accepted DOL seed provenance changed")
    row = {
        "observationId": hashlib.sha256(
            b"factor:canonical:initial-claims|DOL-UI-SA-INITIAL|DOL-UI-2026-08-13-advance|2026-08-08"
        ).hexdigest(),
        "canonicalFactorId": "factor:canonical:initial-claims",
        "sourceId": "dol-ui-claims",
        "sourceSeriesId": "DOL-UI-SA-INITIAL",
        "releaseId": "DOL-UI-2026-08-13-advance",
        "artifactSha256": provenance["artifactSha256"],
        "value": "209000",
        "unit": "claims",
        "frequency": "weekly",
        "geography": "US",
        "seasonalAdjustment": "seasonally adjusted",
        "validTime": "2026-08-08",
        "publicTime": provenance["publishedAt"],
        "retrievedTime": provenance["retrievedAt"],
        "acceptedTime": provenance["acceptedAt"],
        "vintageId": provenance["vintageId"],
        "revisionNumber": 0,
        "supersedesObservationId": None,
        "publicationTimeKind": "official",
        "provenanceUrl": provenance["evidenceUrl"],
        "evidenceUrl": provenance["evidenceUrl"],
        "methodologyUrl": source["methodologyUrl"],
        "acceptanceRuleId": "MIGRATED_EXISTING_ACCEPTED_DOL_UI_2026_08_08",
        "acceptanceAuthority": "HUMAN_ACCEPTED_FACTUAL_SNAPSHOT_2026_08_18",
        "rightsState": "ALLOW",
        "historyUseClass": "ORIGINAL_RELEASE_VALUE",
        "forecastVintageEligible": False,
        "vintageEvidenceId": None,
        "sourceRevisionStatus": "advance",
    }
    row["objectHash"] = _sha(row)
    _validate_accepted_observation(row)
    return row


def _rule_matches(rule: dict[str, Any], candidate: dict[str, Any]) -> bool:
    mapping = {
        "sourceId": "source_id",
        "sourceSeriesId": "source_series_id",
        "unit": "unit",
        "frequency": "frequency",
        "geography": "geography",
        "seasonalAdjustment": "seasonal_adjustment",
    }
    return rule["canonicalFactorId"] == canonical_factor_id(candidate["canonical_factor"]) and all(
        rule[key] == candidate.get(candidate_key) for key, candidate_key in mapping.items()
    )


def _validate_candidate_against_rule(
    candidate: dict[str, Any],
    rule: dict[str, Any],
    raw_by_hash: dict[str, dict[str, Any]],
) -> None:
    if candidate.get("accepted_time") is not None or candidate.get("publication_eligible") is not False:
        raise ValueError("candidate already crossed the acceptance boundary")
    raw = raw_by_hash.get(candidate.get("artifact_sha256"))
    if not raw:
        raise ValueError("candidate raw artifact is not declared")
    allowed_parser_versions = set(rule.get("allowedParserVersions", [rule["parserVersion"]]))
    if raw.get("source_id") != rule["rawArtifactSourceId"] or raw.get("parser_version") not in allowed_parser_versions:
        raise ValueError("candidate parser or raw source is outside authority")
    if candidate.get("methodology_url") != rule["methodologyUrl"]:
        raise ValueError("candidate methodology is outside authority")
    if candidate.get("publication_time_kind") not in rule["allowedPublicationTimeKinds"]:
        raise ValueError("candidate publication-time kind is outside authority")
    if candidate.get("revision_status") not in rule["allowedRevisionStatuses"]:
        raise ValueError("candidate revision status is outside authority")
    for field in ("provenance_url", "evidence_url", "methodology_url"):
        if not str(candidate.get(field, "")).startswith("https://"):
            raise ValueError("accepted candidates require HTTPS evidence")
    if not str(candidate.get("release_id", "")).strip():
        raise ValueError("candidate release identity is missing")


def _acceptance_mode(candidate: dict[str, Any], rule: dict[str, Any]) -> str | None:
    if _utc(candidate["retrieved_time"]) >= _utc(rule["effectiveFrom"]):
        return "ROUTINE"
    period = _period_key(candidate["observation_period"], rule["frequency"])
    if (
        rule["descriptiveBackfillAuthority"] == rule["authority"]
        and _period_key(rule["descriptiveBackfillStart"], rule["frequency"])
        <= period
        <= _period_key(rule["descriptiveBackfillEnd"], rule["frequency"])
    ):
        return "DESCRIPTIVE_BACKFILL"
    return None


def _accepted_identity(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(
        f"{canonical_factor_id(candidate['canonical_factor'])}|{candidate['source_series_id']}|{candidate['release_id']}|{candidate['observation_period']}".encode("utf-8")
    ).hexdigest()


def _candidate_matches_accepted(candidate: dict[str, Any], rule: dict[str, Any], row: dict[str, Any]) -> bool:
    expected = {
        "canonicalFactorId": canonical_factor_id(candidate["canonical_factor"]),
        "sourceId": candidate["source_id"],
        "sourceSeriesId": candidate["source_series_id"],
        "releaseId": candidate["release_id"],
        "artifactSha256": candidate["artifact_sha256"],
        "value": str(_decimal(candidate["value"])),
        "unit": candidate["unit"],
        "frequency": candidate["frequency"],
        "geography": candidate["geography"],
        "seasonalAdjustment": candidate["seasonal_adjustment"],
        "validTime": candidate["observation_period"],
        "publicTime": candidate["public_time"],
        "retrievedTime": candidate["retrieved_time"],
        "publicationTimeKind": candidate["publication_time_kind"],
        "provenanceUrl": candidate["provenance_url"],
        "evidenceUrl": candidate["evidence_url"],
        "methodologyUrl": candidate["methodology_url"],
        "acceptanceRuleId": rule["ruleId"],
        "acceptanceAuthority": rule["authority"],
        "rightsState": "ALLOW",
        "historyUseClass": rule["historyUseClass"],
        "forecastVintageEligible": False,
        "sourceRevisionStatus": candidate["revision_status"],
    }
    if str(candidate.get("release_id", "")).startswith("DOL-UI-r539cyNational-observation-"):
        # r539cy's report execution date changes its raw bytes and retrieval
        # timestamps without changing the populated observation. The stable
        # semantic identity above makes an exact later retrieval idempotent;
        # the originally accepted transport evidence remains immutable.
        for transport_field in ("artifactSha256", "publicTime", "retrievedTime"):
            expected.pop(transport_field)
    return all(row.get(key) == value for key, value in expected.items())


def _accepted_observation(
    candidate: dict[str, Any],
    rule: dict[str, Any],
    accepted_at: str,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    public_time = candidate["public_time"]
    retrieved_time = candidate["retrieved_time"]
    if not (_utc(public_time) <= _utc(retrieved_time) <= _utc(accepted_at)):
        raise ValueError("candidate violates public/retrieved/accepted time ordering")
    siblings = [
        row for row in history
        if row.get("canonicalFactorId") == canonical_factor_id(candidate["canonical_factor"])
        and row.get("sourceSeriesId") == candidate["source_series_id"]
        and row.get("validTime") == candidate["observation_period"]
    ]
    siblings.sort(key=lambda row: (row["revisionNumber"], row["acceptedTime"]))
    revision_number = 0 if not siblings else siblings[-1]["revisionNumber"] + 1
    supersedes = None if not siblings else siblings[-1]["observationId"]
    identity = _accepted_identity(candidate)
    row = {
        "observationId": identity,
        "canonicalFactorId": canonical_factor_id(candidate["canonical_factor"]),
        "sourceId": candidate["source_id"],
        "sourceSeriesId": candidate["source_series_id"],
        "releaseId": candidate["release_id"],
        "artifactSha256": candidate["artifact_sha256"],
        "value": str(_decimal(candidate["value"])),
        "unit": candidate["unit"],
        "frequency": candidate["frequency"],
        "geography": candidate["geography"],
        "seasonalAdjustment": candidate["seasonal_adjustment"],
        "validTime": candidate["observation_period"],
        "publicTime": public_time,
        "retrievedTime": retrieved_time,
        "acceptedTime": accepted_at,
        "vintageId": candidate["release_id"],
        "revisionNumber": revision_number,
        "supersedesObservationId": supersedes,
        "publicationTimeKind": candidate["publication_time_kind"],
        "provenanceUrl": candidate["provenance_url"],
        "evidenceUrl": candidate["evidence_url"],
        "methodologyUrl": candidate["methodology_url"],
        "acceptanceRuleId": rule["ruleId"],
        "acceptanceAuthority": rule["authority"],
        "rightsState": "ALLOW",
        "historyUseClass": rule.get("historyUseClass", "CURRENT_REVISED_HISTORY"),
        "forecastVintageEligible": bool(rule.get("forecastVintageEligible", False)),
        "vintageEvidenceId": rule.get("vintageEvidenceId"),
        "sourceRevisionStatus": candidate.get("revision_status", "UNKNOWN"),
        "acquisitionMethod": candidate.get("acquisition_method", "UNSPECIFIED"),
    }
    row["objectHash"] = _sha(row)
    _validate_accepted_observation(row)
    return row


def _validate_accepted_observation(row: dict[str, Any]) -> None:
    required = {
        "observationId", "canonicalFactorId", "sourceId", "sourceSeriesId", "releaseId",
        "artifactSha256", "value", "unit", "frequency", "geography", "seasonalAdjustment",
        "validTime", "publicTime", "retrievedTime", "acceptedTime", "vintageId",
        "revisionNumber", "supersedesObservationId", "provenanceUrl", "acceptanceRuleId",
        "acceptanceAuthority", "rightsState", "objectHash",
    }
    if not required.issubset(row):
        raise ValueError("accepted history observation is incomplete")
    if row["rightsState"] != "ALLOW" or row["acceptanceAuthority"] in {"", "NONE"}:
        raise ValueError("accepted history observation lacks authority or rights")
    if not SHA256.fullmatch(row["artifactSha256"]):
        raise ValueError("accepted history observation has an invalid evidence hash")
    if not row["provenanceUrl"].startswith("https://"):
        raise ValueError("accepted history observation requires HTTPS provenance")
    if not (_utc(row["publicTime"]) <= _utc(row["retrievedTime"]) <= _utc(row["acceptedTime"])):
        raise ValueError("accepted observation time ordering is invalid")
    if row.get("forecastVintageEligible"):
        if row.get("historyUseClass") not in FORECAST_HISTORY_CLASSES:
            raise ValueError("forecast-eligible observation has an ineligible history class")
        if row.get("publicationTimeKind") != "official" or not row.get("vintageEvidenceId"):
            raise ValueError("forecast-eligible observation lacks official vintage evidence")
    _decimal(row["value"])
    _period_key(row["validTime"], row["frequency"])
    expected = _sha({key: value for key, value in row.items() if key != "objectHash"})
    if row["objectHash"] != expected:
        raise ValueError("accepted observation object hash is invalid")


def _materiality(
    current: dict[str, Any],
    delta: Decimal,
    percent: Decimal | None,
    registry: dict[str, Any] | None,
) -> dict[str, Any]:
    if not registry or registry.get("authority") == "NONE" or registry.get("status") != "ACCEPTED":
        return {"status": "UNKNOWN", "reason": "UNAVAILABLE_PENDING_GOVERNANCE", "profileId": None}
    matches = [
        row for row in registry.get("profiles", [])
        if row.get("decisionStatus") == "ACCEPTED"
        and row.get("authority") == registry.get("authority")
        and row.get("canonicalFactorId") == current["canonicalFactorId"]
        and row.get("sourceSeriesId") == current["sourceSeriesId"]
        and row.get("frequency") == current["frequency"]
        and row.get("unit") == current["unit"]
        and row.get("geography") == current["geography"]
        and row.get("seasonalAdjustment") == current["seasonalAdjustment"]
        and row.get("profileVersion")
        and row.get("effectiveFrom")
    ]
    if len(matches) != 1:
        return {"status": "UNKNOWN", "reason": "NO_UNIQUE_PROFILE", "profileId": None}
    profile = matches[0]
    try:
        _utc(profile["effectiveFrom"])
    except ValueError:
        return {"status": "UNKNOWN", "reason": "INVALID_PROFILE_EFFECTIVE_TIME", "profileId": None}
    threshold = _decimal(profile["absoluteDeltaThreshold"])
    if not threshold.is_finite() or threshold <= 0 or not profile.get("profileId"):
        return {"status": "UNKNOWN", "reason": "INVALID_GOVERNED_THRESHOLD", "profileId": None}
    status = "MATERIAL" if abs(delta) >= threshold else "NOT_MATERIAL"
    return {"status": status, "reason": "ABSOLUTE_DELTA_THRESHOLD", "profileId": profile["profileId"], "threshold": str(threshold)}


def _revision_key(row: dict[str, Any], mode: str) -> tuple[Any, ...]:
    if mode in {"PUBLICLY_AVAILABLE_AS_OF", "FORECAST_AS_OF"}:
        return (_utc(row["publicTime"]), row["revisionNumber"], row["observationId"])
    return (_utc(row["acceptedTime"]), row["revisionNumber"], row["observationId"])


def _forecast_row_eligible(row: dict[str, Any]) -> bool:
    return (
        row.get("forecastVintageEligible") is True
        and row.get("historyUseClass") in FORECAST_HISTORY_CLASSES
        and row.get("publicationTimeKind") == "official"
        and bool(row.get("vintageEvidenceId"))
    )


def _period_key(value: str, frequency: str) -> tuple[int, int, int]:
    if frequency == "weekly":
        parsed = date.fromisoformat(value)
        return parsed.year, parsed.month, parsed.day
    if frequency == "monthly":
        parsed = datetime.strptime(value, "%Y-%m")
        return parsed.year, parsed.month, 1
    if frequency == "quarterly":
        year, quarter = value.split("-Q")
        if int(quarter) not in {1, 2, 3, 4}:
            raise ValueError("quarter must be 1 through 4")
        return int(year), int(quarter) * 3, 1
    if frequency == "annual":
        return int(value), 1, 1
    raise ValueError("unsupported native cadence")


def canonical_factor_id(value: str) -> str:
    slug = value.removeprefix("factor:canonical:").removeprefix("factor:")
    return f"factor:canonical:{CANONICAL_ALIASES.get(slug, slug)}"


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("observation value is not numeric") from exc


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
