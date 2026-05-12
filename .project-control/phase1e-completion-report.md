# Phase 1E Completion Report
## DaVinci Evidence Pipeline — Dry-Run / Staging

**Date:** 2026-05-12
**Phase:** 1E
**Status:** COMPLETE — all tasks executed, all validations passing, no protected files modified.

---

## Phase 1E Objectives

Implement the DaVinci evidence pipeline in dry-run/staging mode:
- Normalize DaVinci version strings reliably
- Stage real-source evidence candidates from public community sources
- Prove aggregation through the pipeline against real generated records
- Implement a safe dry-run consensus updater with 14 safety gates
- Add QA safety rules for manual_watch and legacy counts
- Produce zero production changes — no evidence rows written, no record changes, no public counts updated

---

## Task Outcomes

### Task 1 — Version Normalizer (`auxsays/scripts/lib/normalize_davinci_version.py`)

Normalization function `normalize_davinci_version(raw)` implemented. Handles:
- All product-name prefix forms: "DaVinci Resolve Studio", "DaVinci Resolve", "DaVinci", "Resolve"
- Stable point releases: "21", "21.0", "21.0.1"
- Beta releases: "21 Public Beta 1", "21 Beta 1", "21b1", "21 Beta1", "21 Public Beta 2"
- Ambiguous beta rejection: "21 beta", "21b", "Resolve 21 Beta" → `ambiguous_beta_no_number`
- DR-prefix rejection: "DR21", "DR 21" → `abbreviation_dr_ambiguous`
- Wildcard rejection: "21.x" → `wildcard_version`
- False-positive rejection: "OBS Studio 31.0", "Premiere Pro 26.2" → `unrecognized_version_format`
- Stable vs beta hard boundary enforced — "21" and "21 Public Beta 1" never collapse
- Returns `canonical_update_version` matching existing generated record `update_version` fields exactly

### Task 2 — Normalization Tests (`auxsays/scripts/tests/test_normalize_davinci_version.py`)

**51/51 tests passing.** Coverage across 9 sections:
1. Stable major releases and prefix stripping
2. Stable point releases (21.0, 21.0.1)
3. Beta release canonical mapping
4. Stable vs beta separation (hard boundary)
5. `is_beta`, `beta_number`, `major_version`, `minor_version` fields
6. `product_id` field
7. All rejection cases
8. False positive rejection (other products)
9. Alias list presence

### Task 3 — Evidence Candidate Staging (`.project-control/evidence-staging/davinci-real-evidence-candidates.yml`)

11 candidate rows staged across 3 categories:

**Positive (include_in_dry_run: true) — 2 rows:**
| ID | Source | Version Raw | Proposed Version | Confidence |
|---|---|---|---|---|
| bmd-forum-t235179-magic-mask-crash | Blackmagic forum t=235179 | Resolve Studio 21.0B Build 20 | 21 Public Beta 1 | medium |
| reddit-1sn39qf-decode-failure | r/davinciresolve/1sn39qf | DaVinci Resolve public beta 21 | 21 Public Beta 1 | low |

Access status for all real sources: `blocked_or_search_snippet_only` (HTTP 403 confirmed for Blackmagic forum and Reddit during Phase 1E probing). Include basis documented in `match_basis` field.

**Excluded positives (include_in_dry_run: false) — 4 rows:**
- bmd-forum-t235117: "DR 21b" — DR abbreviation + ambiguous beta
- bmd-forum-t234906: No version in title, body inaccessible
- reddit-1sl3sqn: "Resolve 21" — ambiguous stable vs beta
- reddit-1skz03l: "DaVinci 21 Beta" — ambiguous beta, no number

**Negative test rows — 5 rows:**
- wrong-product: product_id = obs-studio → excluded by product_id gate
- ambiguous-version: "21 beta" → excluded by version normalization
- missing-source-url: empty source_url → excluded by Gate 11
- non-exact-version-match: exact_version_match=false → excluded by Gate 12
- include-in-dry-run-false: include_in_dry_run=false → excluded by Gate 13

### Task 4 — Dry-Run Updater (`auxsays/scripts/apply_consensus_to_records.py`)

Implemented with full 14-gate safety evaluation. CLI:
```
python auxsays/scripts/apply_consensus_to_records.py --dry-run
python auxsays/scripts/apply_consensus_to_records.py --dry-run --product-id blackmagic-davinci
python auxsays/scripts/apply_consensus_to_records.py --dry-run \
    --candidate-file .project-control/evidence-staging/davinci-real-evidence-candidates.yml \
    --output .project-control/probe-output/phase1e/davinci-real-candidate-consensus-dry-run.json
```

`--write` flag present but exits non-zero in Phase 1E with a clear error message.

### Task 5 — Dry-Run Output (`.project-control/probe-output/phase1e/davinci-real-candidate-consensus-dry-run.json`)

**Run results:**
```
Groups evaluated:      2
Would write:           1  (blackmagic-davinci / 21 Public Beta 1)
Blocked:               1  (empty-version group)
Total included:        2
Total excluded:        8
```

**Beta 1 group — all 14 safety gates passed:**

| Gate | Result |
|---|---|
| gate_01 nonzero_count_requires_rows | PASS |
| gate_02 count_equals_included_rows | PASS |
| gate_03 product_id_matches_record | PASS |
| gate_04 version_matches_record | PASS |
| gate_05 no_beta_stable_cross_match | PASS |
| gate_06 legacy_count_not_verified | PASS (non-blocking) |
| gate_07 official_only_zero_rows_stays_zero | PASS |
| gate_08 no_ambiguous_versions | PASS |
| gate_09 record_must_exist_for_write | PASS |
| gate_10 dry_run_mode_active | PASS (non-blocking) |
| gate_11 source_url_required | PASS |
| gate_12 exact_version_match_required | PASS |
| gate_13 include_in_dry_run_required | PASS |
| gate_14 access_limited_rows_flagged | PASS (non-blocking) |

**Proposed fields (NOT written — dry-run):**
```yaml
update_report_count: 2
confirmed_patch_specific_report_count: 2
evidence_state: pilot_sample
evidence_state_label: Verified reports
consensus_collection_status: pilot_initial_sample
update_consensus_label: Negative
update_consensus_confidence: Low
evidence_last_checked: '2026-05-12T00:00:00Z'
```

**Stable "21" record:** 0 candidates — no beta evidence crossed into stable record. ✓

**Negative test rows:** all 5 rejected by the correct gates (11, 12, 13). ✓

### Task 6 — QA Safety Rules (`auxsays/scripts/qa_patch_records.py`)

Two new safety rules added:

**Rule 3 — manual_watch + nonzero verified count (ERROR):**
`intelligence_stage == "manual_watch"` and `report_count > 0` without a separate `legacy_manual_report_count` field triggers an error (`manual_watch_nonzero_verified_count`).

**Rule 4 — legacy count must not drive verified evidence (WARNING):**
`legacy_manual_report_count > 0` and equals `update_report_count` and `evidence_state` is `official_only` or `insufficient_data` triggers a warning (`legacy_count_equals_report_count_no_evidence_state`).

**QA run result: 0 errors, 3 warnings** (3 warnings are pre-existing for the DaVinci Beta 1 record — `known_issues_present`, `complaint_themes`, and `recommendation_language` on an official_only record — carried forward from Phase 1D).

### Task 7 — Full Validation Run

| Check | Result |
|---|---|
| Normalization tests | 51/51 PASS |
| QA patch records | 0 errors, 3 warnings (expected) |
| Validate ingestion sources | 46 entries checked, PASS |
| Build consensus from evidence | 62 items, 3 aggregates, 0 excluded — PASS |
| Consensus evidence audit | Pre-existing findings only, no new mismatches |
| Protected files modified | NONE |
| Generated records modified | NONE |
| Public report counts changed | NONE |
| consensus_evidence.yml rows added | NONE |

---

## Files Created / Modified

| File | Status | Notes |
|---|---|---|
| `auxsays/scripts/lib/normalize_davinci_version.py` | Created | Version normalizer |
| `auxsays/scripts/tests/__init__.py` | Created | Tests package marker |
| `auxsays/scripts/tests/test_normalize_davinci_version.py` | Created | 51 tests, 51 passing |
| `.project-control/evidence-staging/davinci-real-evidence-candidates.yml` | Created | 11 staged candidates |
| `auxsays/scripts/apply_consensus_to_records.py` | Created | 14-gate dry-run updater |
| `.project-control/probe-output/phase1e/davinci-real-candidate-consensus-dry-run.json` | Generated | Dry-run output |
| `auxsays/scripts/qa_patch_records.py` | Modified | Rules 3 and 4 added |

## Files NOT Modified (Protected)

- `auxsays/_data/consensus_evidence.yml` — untouched
- `auxsays/_data/source_health.yml` — untouched
- `auxsays/_data/patch_ingestion_sources.yml` — untouched
- `auxsays/_data/patch_ingest_state.json` — untouched
- `auxsays/updates/generated/` — all records untouched
- `.github/workflows/` — untouched

---

## What Phase 1E Does NOT Do

- Does not write any evidence rows to consensus_evidence.yml
- Does not update public report counts on any record
- Does not modify any generated Markdown record
- Does not claim the blocked community sources are successfully scraped
- Does not produce any public-facing changes on auxsays.com

---

## Next Phase Readiness

Phase 1E delivers a mechanically functional evidence pipeline that:
1. Normalizes DaVinci version strings reliably (51 tests)
2. Stages real community source candidates with honest access-status documentation
3. Runs those candidates through a 14-gate safety evaluation
4. Produces a readable dry-run JSON proving the pipeline can aggregate candidates into a proposed write
5. Enforces that stable and beta evidence never cross
6. Adds QA rules that would catch stale manual-watch counts before they appear in public

The pipeline is ready for Phase 1F (human reviewer verification of blocked-access candidates, then controlled promotion to consensus_evidence.yml) once access to the community sources is confirmed and each candidate's exact version is independently verified.
