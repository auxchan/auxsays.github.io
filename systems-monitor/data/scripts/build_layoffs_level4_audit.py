from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


ALIASES = {
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
    "business-formations-four-quarters": "business-formation",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def build_audit(config_root: Path) -> dict[str, Any]:
    taxonomy = load(config_root / "layoffs" / "taxonomy.json")
    classes = load(config_root / "layoffs" / "level4_claim_classes.json")
    bls_dol = load(config_root / "layoffs" / "sources_bls_dol.json")
    census = load(config_root / "layoffs" / "sources_census.json")
    context = load(config_root / "layoffs" / "sources_bea_fed_courts.json")

    class_by_id = {row["canonicalFactorId"]: row for row in classes["factors"]}
    child_ids = {row["canonicalFactorId"] for group in taxonomy["groups"] for row in group["placements"]}
    slug_to_id: dict[str, str] = {}
    state: dict[str, dict[str, Any]] = {}
    paths: dict[str, list[str]] = {factor_id: [] for factor_id in child_ids}
    labels: dict[str, str] = {}

    for group in taxonomy["groups"]:
        slug_to_id[group["id"]] = group["canonicalFactorId"]
        state.setdefault(group["canonicalFactorId"], _blank_state(group["canonicalFactorId"], group["label"], "LEVEL3_PARENT"))
        labels[group["canonicalFactorId"]] = group["label"]
        for placement in group["placements"]:
            factor_id = placement["canonicalFactorId"]
            slug_to_id[factor_id.replace("factor:canonical:", "")] = factor_id
            state.setdefault(factor_id, _blank_state(factor_id, placement["label"], "LEVEL4_CANONICAL"))
            labels.setdefault(factor_id, placement["label"])
            paths[factor_id].append(f"{group['label']} > {placement['label']}")

    def canonical_id(configured: str) -> str:
        slug = re.sub(r"^factor:(?:canonical:)?", "", configured)
        slug = ALIASES.get(slug, slug)
        return slug_to_id.get(slug, f"factor:canonical:{slug}")

    for row in bls_dol["series"]:
        factor_id = canonical_id(row["canonical_factor"])
        record = state.setdefault(factor_id, _blank_state(factor_id, row["label"], "SOURCE_ONLY"))
        role = _role_for(factor_id, class_by_id, source_id=row["source_id"], source_only=factor_id not in child_ids)
        record["sourceBindings"].append(_binding(
            source_id=row["source_id"], selector=row["series_id"], role=role,
            status="EXACT_SELECTOR", exact=True, origin="sources_bls_dol.json",
        ))
        record["activationState"] = "ACCEPTED" if row["activation_state"] == "ACCEPTED_EXISTING" else "SOURCE_ENABLED_PENDING_ACCEPTANCE"

    for source in census["sources"]:
        for row in source["series"]:
            for placement in row["placement_candidates"]:
                factor_id = canonical_id(f"factor:{placement}")
                record = state.setdefault(factor_id, _blank_state(factor_id, row["label"], "SOURCE_ONLY"))
                role = _role_for(
                    factor_id, class_by_id, source_id=source["source_id"],
                    source_only=factor_id not in child_ids,
                    alternate=bool(record["sourceBindings"]),
                )
                record["sourceBindings"].append(_binding(
                    source_id=source["source_id"], selector=row["source_series_id"], role=role,
                    status="EXACT_SELECTOR", exact=True, origin="sources_census.json",
                ))
                record["activationState"] = "BLOCKED"

    for source in context["sources"]:
        for row in source.get("series", []):
            factor_id = canonical_id(row["canonical_factor"])
            record = state.setdefault(factor_id, _blank_state(factor_id, row["label"], "SOURCE_ONLY"))
            record["sourceBindings"].append(_binding(
                source_id=source["source_id"], selector=row["source_series_id"],
                role=_role_for(factor_id, class_by_id, source_id=source["source_id"], source_only=factor_id not in child_ids, alternate=bool(record["sourceBindings"])),
                status="EXACT_SELECTOR", exact=True, origin="sources_bea_fed_courts.json",
            ))
            record["activationState"] = "SOURCE_ENABLED_PENDING_ACCEPTANCE"
        for row in source.get("selector_candidates", []):
            factor_id = canonical_id(row["canonical_factor"])
            record = state.setdefault(factor_id, _blank_state(factor_id, row["required_decision"], "SOURCE_ONLY"))
            record["sourceBindings"].append(_binding(
                source_id=source["source_id"], selector="selector-pending",
                role=_role_for(factor_id, class_by_id, source_id=source["source_id"], source_only=factor_id not in child_ids, alternate=bool(record["sourceBindings"])),
                status="SELECTOR_PENDING", exact=False, origin="sources_bea_fed_courts.json",
            ))
            record["activationState"] = "BLOCKED"

    canonical_rows = []
    for factor_id in sorted(child_ids):
        classification = class_by_id.get(factor_id)
        if classification is None:
            raise ValueError(f"unclassified canonical factor: {factor_id}")
        record = state[factor_id]
        canonical_rows.append({
            "canonicalFactorId": factor_id,
            "label": labels[factor_id],
            "definition": classification["rationale"],
            "placementCount": len(paths[factor_id]),
            "placementPaths": paths[factor_id],
            "claimClass": classification["claimClass"],
            "sourceStatus": record["activationState"],
            "exactSelectorStatus": "EXACT" if any(row["exactSelector"] for row in record["sourceBindings"]) else "PENDING_OR_UNMAPPED",
            "sourceBindings": record["sourceBindings"],
            "promotionBlocker": classification.get("promotionBlocker", "Observation acceptance and comparable history remain pending."),
        })

    records = [state[key] for key in sorted(state)]
    activation_counts = Counter(row["activationState"] for row in records)
    role_counts = Counter(binding["role"] for row in records for binding in row["sourceBindings"])
    orphan_ids = [row["canonicalFactorId"] for row in records if row["recordKind"] == "SOURCE_ONLY"]
    if len(records) != 77 or len(canonical_rows) != 64:
        raise ValueError("Layoffs source audit no longer matches the reviewed 77-state/64-factor boundary")
    return {
        "schemaVersion": "layoffs-level4-canonical-audit-1.0.0",
        "generatedAt": "2026-09-09T00:00:00Z",
        "authority": "REVIEW_EVIDENCE_ONLY",
        "promotionAuthority": "NONE",
        "counts": {
            "level3Parents": len(taxonomy["groups"]),
            "level4Placements": sum(len(group["placements"]) for group in taxonomy["groups"]),
            "canonicalLevel4Factors": len(canonical_rows),
            "factorSourceStateRecords": len(records),
            "recordsWithSourceBindings": sum(bool(row["sourceBindings"]) for row in records),
            "sourceIdentifiedPlaceholders": sum(not row["sourceBindings"] for row in records),
            "expandedSourceBindings": sum(len(row["sourceBindings"]) for row in records),
            "sourceOnlyRecords": len(orphan_ids),
            "activationStates": dict(sorted(activation_counts.items())),
            "sourceRoles": dict(sorted(role_counts.items())),
        },
        "reconciliation": {
            "explanation": "The reported 77 are UI-side factor/source state records, not 77 unique Level-4 factors and not 77 acquisition adapters. They comprise in-taxonomy Level-3/Level-4 identities plus source-only records created by configured series that do not resolve to a current taxonomy identity.",
            "actualCanonicalLevel4FactorCount": 64,
            "actualExpandedAcquisitionBindingCount": sum(len(row["sourceBindings"]) for row in records),
            "sourceIdentifiedRecordsWithoutBinding": [row["canonicalFactorId"] for row in records if not row["sourceBindings"]],
            "sourceOnlyRecords": orphan_ids,
            "requiredCleanup": "Source-only records must be canonicalized, retained explicitly as CALC input, or removed through review before this pattern is copied to other branches."
        },
        "canonicalFactors": canonical_rows,
        "factorSourceStateRecords": records,
    }


def _blank_state(factor_id: str, label: str, kind: str) -> dict[str, Any]:
    return {
        "canonicalFactorId": factor_id,
        "label": label,
        "recordKind": kind,
        "activationState": "SOURCE_IDENTIFIED",
        "sourceBindings": [],
    }


def _binding(*, source_id: str, selector: str, role: str, status: str, exact: bool, origin: str) -> dict[str, Any]:
    return {
        "sourceId": source_id,
        "selector": selector,
        "role": role,
        "status": status,
        "exactSelector": exact,
        "origin": origin,
        "whyNeeded": _role_reason(role),
    }


def _role_for(
    factor_id: str,
    classes: dict[str, dict[str, Any]],
    *,
    source_id: str,
    source_only: bool,
    alternate: bool = False,
) -> str:
    if source_only:
        if factor_id in {"factor:canonical:business-formations"}:
            return "LEGACY_DUPLICATE_SHOULD_REMOVE"
        return "CALC_INPUT"
    claim_class = classes[factor_id]["claimClass"]
    if alternate:
        return "ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE"
    if claim_class == "A_DIRECT_OBS":
        return "PRIMARY_OBSERVATION_SOURCE"
    if claim_class == "B_CALC":
        return "CALC_INPUT"
    if claim_class == "C_EVENT_OR_STRUCTURAL":
        return "STRUCTURAL_SOURCE"
    if factor_id == "factor:canonical:industry-credit-conditions" and source_id == "fed-sloos":
        return "FALLBACK_ACQUISITION_METHOD"
    return "LEGACY_DUPLICATE_SHOULD_REMOVE"


def _role_reason(role: str) -> str:
    return {
        "PRIMARY_OBSERVATION_SOURCE": "Direct official measurement candidate for this canonical factor.",
        "SECONDARY_CORROBORATING_SOURCE": "Independent official evidence used only for corroboration.",
        "CALC_INPUT": "Official input retained for a future governed deterministic calculation.",
        "STRUCTURAL_SOURCE": "Official event or structural evidence; not a scalar observation.",
        "FALLBACK_ACQUISITION_METHOD": "Context-only fallback that cannot satisfy the canonical scope directly.",
        "ALTERNATE_GEOGRAPHIC_INDUSTRY_SCOPE": "Separate official scope that must not be merged with the primary series.",
        "LEGACY_DUPLICATE_SHOULD_REMOVE": "Ambiguous, duplicate, or taxonomy-mismatched binding requiring review removal or canonicalization.",
    }[role]


def render_markdown(audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    lines = [
        "# Layoffs Level-4 Canonical Audit",
        "",
        "Status: **REVIEW EVIDENCE — NO OBSERVATION OR RELATIONSHIP PROMOTION**",
        "",
        "## Recalculated boundary",
        "",
        f"- {counts['level4Placements']} reviewed Layoffs Level-4 placements.",
        f"- {counts['canonicalLevel4Factors']} canonical Level-4 factors.",
        f"- {counts['factorSourceStateRecords']} UI-side factor/source state records.",
        f"- {counts['expandedSourceBindings']} expanded acquisition bindings across {counts['recordsWithSourceBindings']} records.",
        f"- {counts['sourceIdentifiedPlaceholders']} source-identified placeholders without a configured binding.",
        f"- {counts['sourceOnlyRecords']} configured source identities outside the current taxonomy.",
        "",
        "The historical `77 source profiles` label was imprecise: 77 is the size of the UI-side factor/source-state map, not the number of canonical factors or acquisition adapters. The machine-readable reconciliation is `data/config/layoffs/level4_source_profile_roles.json`.",
        "",
        "## All 64 canonical factors",
        "",
        "| Factor | Class | Placements | Source state | Selector | Sources |",
        "|---|---|---:|---|---|---|",
    ]
    for row in audit["canonicalFactors"]:
        sources = "; ".join(f"{item['sourceId']} ({item['role']})" for item in row["sourceBindings"]) or "No configured binding"
        lines.append(
            f"| `{row['canonicalFactorId']}` — {row['label']} | {row['claimClass']} | {row['placementCount']} | {row['sourceStatus']} | {row['exactSelectorStatus']} | {sources} |"
        )
    lines += [
        "",
        "## Reconciled 77-record state map",
        "",
        "| Canonical/source-state record | Kind | State | Source bindings | Roles |",
        "|---|---|---|---|---|",
    ]
    for row in audit["factorSourceStateRecords"]:
        sources = "; ".join(f"{item['sourceId']}:{item['selector']}" for item in row["sourceBindings"]) or "—"
        roles = "; ".join(item["role"] for item in row["sourceBindings"]) or "UNMAPPED_SOURCE_IDENTIFIED_PLACEHOLDER"
        lines.append(f"| `{row['canonicalFactorId']}` | {row['recordKind']} | {row['activationState']} | {sources} | {roles} |")
    lines += [
        "",
        "## Required cleanup before reuse on the other nine branches",
        "",
        "The following source-only records do not resolve to a current taxonomy identity and therefore cannot remain unexplained:",
        "",
    ]
    lines.extend(f"- `{factor_id}`" for factor_id in audit["reconciliation"]["sourceOnlyRecords"])
    lines += [
        "",
        "`business-formations` is a legacy plural alias and should canonicalize to the singular factor after review. The four BED gain/opening records and four Courts chapter records are useful calculation/corroboration inputs, but they are not current Level-4 placements and must remain explicitly typed as such.",
        "",
        "## Promotion boundary",
        "",
        "A/B/C/D classification, source identity, selector readiness, and collector availability do not accept an observation, calculation, history, or relationship. Human Level-4 QA remains pending.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic Layoffs Level-4 canonical/source reconciliation audit.")
    parser.add_argument("--config-root", type=Path, default=Path("systems-monitor/data/config"))
    parser.add_argument("--output", type=Path, default=Path("systems-monitor/data/config/layoffs/level4_source_profile_roles.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("systems-monitor/data/review/LAYOFF_LEVEL4_CANONICAL_AUDIT.md"))
    args = parser.parse_args(argv)
    audit = build_audit(args.config_root)
    write_atomic(args.output, audit)
    write_text_atomic(args.markdown_output, render_markdown(audit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
