# Phase 1D — DaVinci Consensus Write-Back Design

**Phase:** 1D  
**Date:** 2026-05-12  
**Status:** Design only — no production implementation in Phase 1D.

---

## 1. Problem Statement

There is currently no mechanism that updates DaVinci generated records from structured evidence. The OBS pipeline uses `collect_obs_reports.py` as a combined collector+writer. No equivalent exists for DaVinci. `build_consensus_from_evidence.py` writes to a gitignored, unread intermediate file and never touches generated records.

This design specifies what a safe write-back mechanism must include.

---

## 2. Required Input Fields (per evidence row in consensus_evidence.yml)

Each evidence row that contributes to a DaVinci aggregate must carry:

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | Required | Unique row identifier — prevents duplicate counting |
| `product_id` | string | Required | Must be exactly `blackmagic-davinci` — no variants |
| `update_version` | string | Required | Canonical form only (see §6, version normalization) |
| `source_url` | string | Required | The URL of the source post or page |
| `source_type` | string | Required | e.g., `reddit_post`, `forum_thread`, `community_report` |
| `source_name` | string | Required | Human-readable source label |
| `report_text_excerpt` | string | Required | Sufficient text to confirm patch-specificity |
| `patch_version_matched` | bool | Required | Must be `true` to be counted |
| `exact_version_match` | string | Optional | Basis for match: `title`, `body`, `inferred` |
| `counted` | bool | Required | Must be `true`; `false` excludes from count |
| `sentiment` | string | Required | `positive` / `moderate` / `negative` |
| `severity` | string | Optional | `low` / `medium` / `high` / `critical` |
| `issue_theme` | string | Optional | Short theme label, e.g., `gpu_crash`, `playback_stutter` |
| `workflow_area` | string | Optional | e.g., `color_grading`, `cut_page`, `fusion` |
| `platform` | string | Optional | `windows`, `mac`, `linux`, `unknown` |
| `captured_at` | ISO 8601 string | Required | When this row was written |
| `source_weight` | int | Optional | Default `1` — equal weighting policy |
| `exclusion_reason` | string | Conditional | Required if `counted: false` |

**Hard requirements:**
- `patch_version_matched: true` is the gate. A row without this explicitly set is not counted.
- `update_version` must match the generated record's `update_version` exactly (after normalization).
- `product_id: blackmagic-davinci` must match exactly.
- `counted: true` is not optional — rows without it are treated as `counted: false`.

---

## 3. Required Aggregate Output Fields (per generated record update)

The write-back must update these fields in the generated record:

| Front-matter field | Source | Write condition |
|---|---|---|
| `update_report_count` | `len(counted_rows)` | Always set from evidence aggregate |
| `confirmed_patch_specific_report_count` | Same as above | Must equal `update_report_count` |
| `evidence_state` | Derived from count and threshold | See §4 |
| `evidence_state_label` | Derived from `evidence_state` | See §4 |
| `consensus_collection_status` | Derived from state | See §4 |
| `update_consensus_label` | `build_consensus_from_evidence.consensus_label()` | Negative / Moderate / Positive / Insufficient data |
| `update_consensus_confidence` | `build_consensus_from_evidence.confidence()` | Low / Low-Medium / Medium |
| `consensus_report_count_label` | Constant: `"confirmed patch-specific reports"` | Always |
| `evidence_last_checked` | `max(captured_at)` across counted rows | Always |
| `record_last_updated` | Write timestamp | Always |

**Fields the write-back must NEVER overwrite:**

| Field | Reason |
|---|---|
| `official_patch_notes_body` | Set by official source adapter |
| `official_summary` | Editorial content |
| `quick_verdict` | Editorial decision label |
| `update_decision_label` | Editorial |
| `update_decision_body` | Editorial |
| `practical_recommendations` | Editorial advisory content |
| `complaint_themes` | Editorial advisory content |
| `legacy_manual_report_count` | Preserved Phase 1B field, must not be overwritten |
| `record_note` | Editorial note |
| `permalink` | URL must not change |
| `layout` | Never |
| `company_id` / `product_id` | Identity fields |
| `update_version` | Must not be updated by evidence write-back |

### 3.1 Evidence state derivation rules

| Condition | `evidence_state` | `evidence_state_label` | `consensus_collection_status` | `intelligence_stage` |
|---|---|---|---|---|
| `counted_rows == 0` | `official_only` | `Official source only` | `deferred_official_only` | `manual_watch` |
| `0 < counted_rows < 8` | `pilot_sample` | `Verified reports` | `pilot_initial_sample` | `pilot` |
| `counted_rows >= 8` | `pilot_sample` | `Verified reports` | `pilot_initial_sample` | `pilot` |
| `consensus_live` (future) | `consensus_live` | `Live consensus` | `live_consensus` | `consensus_live` |

**Note:** `intelligence_stage` must only change from `manual_watch` to `pilot` or `consensus_live` when counted evidence rows exist AND the write-back has been validated. The stage must NOT advance speculatively.

---

## 4. Required Safety Gates

All of these gates must be enforced. If any gate fails, the write-back must abort with a non-zero exit code and log a clear error. It must not write a partial update.

### Gate 1 — No nonzero report count without matching consensus_evidence.yml rows

Before writing `update_report_count: N`, verify that `N` equals the count of rows in `consensus_evidence.yml` where `product_id == 'blackmagic-davinci'` AND `update_version == <target_version>` AND `counted == true` AND `patch_version_matched == true`.

```python
def gate_count_matches_evidence(target_count: int, counted_rows: list) -> bool:
    return target_count == len(counted_rows)
```

If `target_count != len(counted_rows)`: **abort, do not write**.

### Gate 2 — No "Verified reports" label without evidence rows

If `counted_rows == 0`, the write-back must set `evidence_state: official_only`. It must never write `evidence_state: pilot_sample` or `evidence_state_label: "Verified reports"` when there are zero counted rows.

### Gate 3 — No pilot_sample state without evidence rows

Same as Gate 2 — `consensus_collection_status: pilot_initial_sample` requires at least one counted row.

### Gate 4 — legacy_manual_report_count must never drive verified counts

The `legacy_manual_report_count` field (if present) must be excluded from all count aggregation. It is a preserved historical annotation, not a live evidence count. The write-back must not read this field.

### Gate 5 — official_only records with 0 evidence rows remain 0

If `build_consensus_from_evidence.py` produces zero aggregate entries for `blackmagic-davinci`, the write-back must not touch report counts on existing generated records. Silence in the aggregate is not a bug — it means no evidence has been collected.

### Gate 6 — Generated record counts must match audit expectations after write

After write-back, run `audit_consensus_evidence.py` in validation mode. If it reports a mismatch, flag it. (Cannot auto-fix post-write — the write must be correct the first time.)

### Gate 7 — Dry-run preview before write-back

The write-back script must support `--dry-run` that shows what would be written without touching any file. The GitHub Actions workflow should run dry-run first and only proceed if dry-run succeeds.

### Gate 8 — Explicit product/version match required

The write-back must match evidence rows to generated records by exact `(product_id, update_version)` tuple. It must not use fuzzy matching or version prefix matching. If no exact match exists in the generated records for a given aggregate, log a warning and skip — do not create a new record.

### Gate 9 — Fail closed if version normalization is ambiguous

If the write-back finds multiple aggregate entries that could match a single generated record (e.g., evidence rows with `update_version: '21 Public Beta 1'` AND rows with `update_version: 'DaVinci Resolve 21 Public Beta 1'`), it must abort rather than pick one. Version normalization must have already resolved this before the write-back runs.

### Gate 10 — Pre-normalization required for DaVinci versions

Before any write-back, a pre-normalization pass must confirm that all DaVinci evidence rows use the canonical version form (see §5 and version normalization design). Rows with non-canonical versions must be excluded with `exclusion_reason: 'version_normalization_required'` and not counted.

---

## 5. Proposed Implementation Options

### Option A — Generic consensus-status-to-generated-record updater (RECOMMENDED)

**Description:** A new script `auxsays/scripts/apply_consensus_to_records.py` that:
1. Reads `consensus_evidence.yml` directly (not `consensus_status.json`)
2. Aggregates by `(product_id, update_version)` using the same logic as `build_consensus_from_evidence.py`
3. For each aggregate, finds the matching generated .md by `(product_id, update_version)` exact match
4. Validates all 10 gates
5. Writes only the evidence-derived fields (see §3)
6. Supports `--dry-run`, `--product-id`, `--version` filters for surgical application

**Why it reads consensus_evidence.yml directly instead of consensus_status.json:**
- `consensus_status.json` is gitignored and may not exist
- Direct reading avoids a stale intermediate file
- The aggregation is trivial and idempotent

**Schema:**
```python
# Pseudocode — Phase 1E implementation target
def apply_consensus(product_id: str, version: str, dry_run: bool = True) -> dict:
    rows = load_evidence_rows(product_id=product_id, update_version=version)
    counted = [r for r in rows if r.get("counted") is not False and r.get("patch_version_matched") is True]
    # Gate 1: count must match
    assert len(counted) >= 0  # always passes — this is the ground truth
    record_path = find_generated_record(product_id=product_id, version=version)
    if record_path is None:
        raise RecordNotFoundError(f"No generated record for {product_id} {version}")
    existing = load_front_matter(record_path)
    existing_count = existing.get("confirmed_patch_specific_report_count") or 0
    if existing_count != 0 and len(counted) == 0:
        raise GateFailure("Gate 5: existing nonzero count but zero evidence rows — abort")
    updates = build_evidence_updates(counted)  # see §3
    if dry_run:
        return {"would_write": updates, "path": record_path}
    write_evidence_fields(record_path, updates, protected_fields=PROTECTED_FIELDS)
    return {"written": updates, "path": record_path}
```

**Pros:** Generic, reusable for any product. Builds on existing aggregation logic. Safe gate structure.  
**Cons:** Requires a new production script. Needs CI/CD workflow integration.

### Option B — DaVinci-specific combined collector+writer (modeled on collect_obs_reports.py)

**Description:** A new `collect_davinci_reports.py` that combines evidence collection (from Reddit OAuth2 or another source) with direct write-back to DaVinci generated records, following the OBS pattern.

**Pros:** Follows existing pattern. Tightly couples version matching to collection.  
**Cons:** Requires a working DaVinci evidence source (blocked until source is resolved). Cannot be used for manual evidence rows that already exist in `consensus_evidence.yml`. Duplicates aggregation logic.

### Option C — adapter-provided report_count path (NOT RECOMMENDED)

**Description:** Pass `report_count` from the ingest adapter directly into `write_update_record.write_record()`.

**Problem:** `write_update_record.py` does not validate the count against `consensus_evidence.yml`. Any count the adapter returns is accepted. This is exactly the failure mode that created the Phase 1B problem. **Do not use this approach.**

### Option D — manual-review staged file path (FALLBACK)

**Description:** Operator manually edits a staging YAML file with proposed evidence updates. A validation script checks the staging file against `consensus_evidence.yml` before applying. Useful as a bridge before automated collection is available.

**Pros:** Can apply evidence from manually curated rows without a live collector. Preserves all gates.  
**Cons:** Requires operator involvement on every update. Not scalable.

---

## 6. Recommendation

**For Phase 1E, implement Option A:** a generic `apply_consensus_to_records.py` script that reads `consensus_evidence.yml` directly, applies all safety gates, and writes only evidence-derived fields to generated records.

**Prerequisites before Phase 1E implementation:**
1. DaVinci version normalization must be resolved (canonical form locked)
2. At least one DaVinci evidence source must be confirmed accessible
3. At least one DaVinci evidence row must exist in `consensus_evidence.yml` for testing
4. The script must be tested against the existing OBS rows first (where ground truth is known)

**Do NOT implement Option C (adapter-provided count).** This is the root cause of Phase 1B and must not be repeated.

**Do NOT advance DaVinci to `pilot_sample` or `consensus_live` without Gate 1 passing.** The current 0-count state is correct and honest. Advancing without evidence is the failure mode this entire phase is designed to prevent.
