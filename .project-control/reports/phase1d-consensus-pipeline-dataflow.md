# Phase 1D — Consensus Pipeline Data-Flow Map

**Phase:** 1D  
**Date:** 2026-05-12  
**Read-only:** Yes. No records, state files, or evidence rows were modified.

---

## 1. Baseline Facts (Task 0)

| Check | Finding |
|---|---|
| Workspace clean? | **Yes** — `git status --short` returns empty |
| `consensus_evidence.yml` contains any DaVinci rows? | **No** — only `adobe-premiere-pro` and `obs-studio` rows exist |
| DaVinci ingestion disabled? | **Yes** — `enabled: false` in `patch_ingestion_sources.yml` line 1403 |
| DaVinci records currently 0-count official_only/manual_watch? | **Yes** — both records show `confirmed_patch_specific_report_count: 0`, `evidence_state: official_only`, `intelligence_stage: manual_watch` |
| Any production script writes DaVinci evidence rows? | **No** — no DaVinci collector exists |
| Any production script writes consensus_status counts back into DaVinci generated records? | **No** — the write-back mechanism does not exist for DaVinci |
| `fetch_davinci_updates.py` does what? | **Trivial stub** — writes to `patch_state.json` (not `patch_ingest_state.json`); sets a hardcoded `current_consensus: "Moderate"` value in a legacy state dict; has no pipeline role |

---

## 2. Pipeline Data-Flow — Current Architecture

### 2.1 Stage 1: Official Source Ingestion

```
patch_ingestion_sources.yml
        │
        ▼  (enabled: true sources only, or all via --all)
patch_ingest.py
        │
        ├─ adapter_module(adapter_name)  ← loads adapters/*.py
        │         │
        │         └─ returns list of record dicts (version, body, date, url, ...)
        │
        ├─ refresh_linked_official_bodies()
        │    ← runs for ALL existing generated records that have no body yet
        │    ← this is why DaVinci records show repeated official-source-parser-failed attempts
        │       even though DaVinci ingestion is disabled (enabled: false only skips new record creation)
        │
        └─ write_update_record.write_record(output_dir, record, overwrite_existing=False)
             │
             ├─ if record exists: refresh_existing_record()
             │    → updates: source_last_checked, official_source_attempts, source_url, body (if new)
             │    → PROTECTED: does NOT overwrite evidence fields, report counts, consensus label
             │
             └─ if new: build_front_matter() → write new .md
                  → sets report_count from record.get("report_count") or 0
                  → evidence_state = "official_only" (if report_count == 0)
                  → consensus_collection_status = "deferred_official_only" (if report_count == 0)
```

**Key facts:**
- `write_update_record.py` does NOT read `consensus_evidence.yml` or `consensus_status.json`.
- It uses only data from the adapter record dict.
- It has no awareness of structured evidence at all.
- `report_count` flows from the adapter record or defaults to 0.
- The protected-field mechanism in `refresh_existing_record` preserves manually set or evidence-backed values — but it also means no automatic sync from evidence to generated records during refresh.

### 2.2 Stage 2: Evidence Collection (OBS path — the only active path)

```
collect_obs_reports.py  ← OBS-specific, runs in obs-evidence-collection.yml GitHub Action
        │
        ├─ search GitHub Issues API: obsproject/obs-studio
        │    ← version-scoped search: exact match required in title or body
        │
        ├─ classifies each issue: accepted / rejected
        │    ← rejection criteria: developer-only, no-repro, off-topic, version mismatch
        │
        ├─ writes rows to consensus_evidence.yml
        │    ← appends new rows with: product_id, update_version, source_url, sentiment, severity,
        │       issue_theme, patch_version_matched, counted, captured_at
        │
        └─ update_obs_record(record_path, count, captured_at)
             ← DIRECTLY updates generated .md for the matching OBS version
             ← writes: update_report_count, confirmed_patch_specific_report_count,
                        evidence_last_checked, record_last_updated
             ← does NOT go through build_consensus_from_evidence.py
             ← does NOT go through consensus_status.json
```

**Critical observation:** `collect_obs_reports.py` is a combined collector + writer. It writes evidence to `consensus_evidence.yml` AND immediately writes counts back to the generated record in a single run. There is NO intermediate aggregation step via `build_consensus_from_evidence.py`. The OBS pipeline bypasses `consensus_status.json` entirely.

### 2.3 Stage 3: build_consensus_from_evidence.py

```
consensus_evidence.yml
        │
        ▼
build_consensus_from_evidence.py
        │
        ├─ loads all evidence rows
        ├─ validates: product_id, version, sentiment, severity, counted flag, patch_version_matched
        ├─ groups by (product_id, update_version)
        ├─ aggregates: report_count, sentiment counts, issue themes, severity summary
        ├─ computes: consensus_label, confidence, evidence_state ("pilot_sample")
        │
        └─ writes consensus_status.json  ← GITIGNORED (excluded from git by .gitignore line 13)
             │
             └─ ← NOTHING reads this file in any production script ←
```

**Critical finding:** `consensus_status.json` is gitignored. No production script reads it. It is written only as a diagnostic/audit output. It does NOT trigger any write-back to generated records. The `build_consensus_from_evidence.py → consensus_status.json` path is a dead end in the current architecture.

### 2.4 Stage 4: audit_consensus_evidence.py

```
consensus_evidence.yml + generated/*.md
        │
        ▼
audit_consensus_evidence.py  ← READ ONLY, no writes
        │
        ├─ loads evidence rows, groups by (product_id, update_version)
        ├─ scans generated records, reads report counts
        ├─ detects mismatches: generated_report_count ≠ structured_evidence_count
        ├─ detects: evidence rows without matching generated record
        ├─ detects: stale freshness timestamps
        │
        └─ returns audit dict (JSON or text)  ← does not modify any file
```

### 2.5 Stage 5: consensus_refresh.py

```
generated/*.md
        │
        ▼
consensus_refresh.py  ← READ ONLY, audit only
        │
        ├─ classifies each record: policy compliance, collection_status, count
        ├─ flags: missing_or_legacy_consensus_policy
        ├─ flags: record_has_reports_but_collection_status_not_static_or_live
        │
        └─ returns audit JSON / text  ← does not modify any file
```

### 2.6 Stage 6: Jekyll layout rendering

```
generated/*.md (front matter)
        │
        ▼
aux-update.html layout
        │
        ├─ reads: update_report_count, evidence_state, consensus_collection_status,
        │         known_issues_present, complaint_themes, quick_verdict,
        │         update_decision_label, practical_recommendations
        │
        ├─ derives: evidence_state display class ("Official source only" | "Verified reports" | "Live consensus")
        ├─ derives: official_only_zero_reports flag
        │    ← if true: overrides decision_label → "No AUXSAYS recommendation yet."
        │    ← if true: overrides verdict_text → "Official source captured. No confirmed patch-specific reports have been counted."
        │
        ├─ renders: known_issues_label ("Yes" if known_issues_present or complaint_themes.size > 0)
        ├─ renders: practical_recommendations block if (official_only_zero_reports OR has_practical_recommendations)
        │    ← RISK: practical_recommendations render even when official_only_zero_reports=true
        │       and the recommendations say "WAIT" — contradicting the layout's own verdict override
        │
        └─ renders: report count badge, evidence state badge, consensus label
```

---

## 3. Structured Flow Diagram

```
                    OFFICIAL SOURCE PATH
                    ──────────────────────────────────────
patch_ingestion_sources.yml
    │ enabled: true
    ▼
patch_ingest.py → adapter → write_update_record.py
                                        │
                                        ▼
                             generated/*.md  [report_count=0, evidence_state=official_only]

                    EVIDENCE PATH (OBS ONLY — combined collector+writer)
                    ──────────────────────────────────────
collect_obs_reports.py
    ├─────────────────────────────────────────────────► consensus_evidence.yml
    └─────────────────────────────────────────────────► generated/obs-*.md [report_count=N]

                    AUDIT PATH (read-only)
                    ──────────────────────────────────────
consensus_evidence.yml + generated/*.md
    ▼
audit_consensus_evidence.py → [stdout / JSON] (no writes)
build_consensus_from_evidence.py → consensus_status.json [GITIGNORED, unread by any pipeline]
consensus_refresh.py → [stdout / JSON] (no writes)

                    DAVINCI CURRENT PATH
                    ──────────────────────────────────────
patch_ingestion_sources.yml [enabled: false]
    │ enabled: false — skips new record creation
    │ refresh_linked_official_bodies() still runs → parser fails → logs attempts in official_source_attempts
    ▼
generated/davinci-*.md [report_count=0, evidence_state=official_only, body='']
    │
    ▼
audit_consensus_evidence.py → no mismatch found (because report_count=0, evidence rows=0, counts match)

                    DAVINCI MISSING PATH (does not exist yet)
                    ──────────────────────────────────────
[?] davinci evidence collector  ←── MISSING
    └── [?] consensus_evidence.yml DaVinci rows  ←── MISSING
              └── [?] write-back to generated/davinci-*.md  ←── MISSING
```

---

## 4. Where Counts Can Drift From Evidence

| Drift mechanism | Currently prevented? | Notes |
|---|---|---|
| Adapter provides `report_count > 0` on new record write | Partially — only if adapter is correct | write_update_record.py accepts any report_count from adapter without evidence check |
| Manual edit sets `update_report_count` in generated .md | **Not prevented** — no write-back guard | Phase 1B root cause: the 7-report value was manually authored |
| `refresh_existing_record` does not overwrite evidence fields | Yes — protected | The refresh path skips report counts; but it cannot restore correct values if already wrong |
| `collect_obs_reports.update_obs_record` sets count directly | OBS only — count comes from live GitHub API | Risk: if GitHub API is unavailable or returns wrong results, count is wrong |
| `build_consensus_from_evidence.py` does not write back | N/A — it never writes to generated records | consensus_status.json is orphaned |
| `audit_consensus_evidence.py` does not correct mismatches | Correct — it is read-only | Mismatches are reported but not fixed automatically |

### 4.1 Current DaVinci drift risk

DaVinci records currently have `report_count=0` and `evidence_rows=0`. The audit script sees no mismatch. This is the correct state. The risk is that:
1. A future adapter run provides a nonzero `report_count` from the adapter record itself (not from evidence rows).
2. A manual edit sets a nonzero count.

Neither is currently happening. The Phase 1B correction eliminated the only existing drift.

---

## 5. Where Validation Catches Mismatches

| Script | What it catches | What it misses |
|---|---|---|
| `qa_patch_records.py` | Intelligence stage validity, official_only coherence warnings | Does NOT compare report counts vs. evidence rows |
| `audit_consensus_evidence.py` | report_count ≠ evidence row count; evidence rows without matching generated record | Does NOT prevent mismatches from occurring; only reports them |
| `validate_ingestion_sources.py` | Source config syntax, field presence | No report count validation |
| `consensus_refresh.py` | Policy compliance flags | Does not compare counts vs. evidence |

**Validation gap:** No script currently prevents a nonzero report count from being written to a generated record without matching `consensus_evidence.yml` rows. `audit_consensus_evidence.py` will DETECT the mismatch after the fact, but it cannot prevent it and does not auto-correct it.

---

## 6. Answers to Required Questions

### Q1: If valid DaVinci evidence rows existed today, would they aggregate?

**Yes, partially.** `build_consensus_from_evidence.py` would aggregate them into `consensus_status.json`. The aggregation logic is product-ID and version agnostic — it works for any `(product_id, update_version)` pair. DaVinci rows would produce correct aggregate objects in `consensus_status.json`.

However, version matching is a problem: the current DaVinci Beta 1 record has `update_version: '21 Public Beta 1'`. Evidence rows would need to carry exactly `update_version: '21 Public Beta 1'` to match. If evidence rows carry `'DaVinci Resolve 21 Public Beta 1'` or `'21'` or `'21.0'`, they would produce a separate unmatched aggregate entry and would not match the existing generated record.

### Q2: If they aggregated, would public DaVinci generated records update automatically?

**No.** There is NO automatic write-back from `consensus_status.json` (or `consensus_evidence.yml`) to DaVinci generated records. The OBS pipeline has its own combined write-back in `collect_obs_reports.py`. DaVinci has no equivalent. `build_consensus_from_evidence.py` writes only to gitignored `consensus_status.json` which nothing reads.

### Q3: What exact write-back gap exists?

The missing component is a script that:
1. Reads `consensus_status.json` (or re-aggregates from `consensus_evidence.yml` directly)
2. For each `(product_id, update_version)` aggregate, finds the matching generated .md
3. Updates: `update_report_count`, `confirmed_patch_specific_report_count`, `evidence_state`, `evidence_state_label`, `consensus_collection_status`, `update_consensus_label`, `update_consensus_confidence`, `evidence_last_checked`
4. Does NOT overwrite: `official_patch_notes_body`, `official_summary`, `quick_verdict`, `practical_recommendations`, `complaint_themes` (editorially set fields)
5. Validates: count matches evidence row count before writing (fail closed)
6. Runs dry-run before live write

This script does not exist. OBS bypasses this gap by having `collect_obs_reports.py` perform the write-back directly as part of collection. DaVinci needs either this generic write-back script or a similar combined collector+writer pattern.
