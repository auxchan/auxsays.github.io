# Phase 1D — Completion Report

**Phase:** 1D — DaVinci Source Discovery and Consensus Write-Back Design  
**Date completed:** 2026-05-12  
**Status:** COMPLETE — research and documentation only, no production changes

---

## Deliverables Written

| File | Description |
|---|---|
| `reports/phase1d-consensus-pipeline-dataflow.md` | Full pipeline data-flow map from ingest → evidence → generated records → layout rendering |
| `methodology/phase1d-davinci-consensus-writeback-design.md` | Required evidence row fields, write-back output fields, 10 safety gates, and implementation option analysis |
| `methodology/phase1d-davinci-version-normalization-design.md` | Canonical version forms, alias table, rejection rules, test cases |
| `reports/phase1d-blackmagic-devtools-trace-plan.md` | Step-by-step operator guide for browser DevTools network inspection of Blackmagic pages |
| `reports/phase1d-davinci-user-report-source-decision.md` | Community source evaluation: Reddit OAuth2, Reddit RSS, Blackmagic forum, VideoHelp, manual review |
| `reports/phase1d-davinci-ui-evidence-label-risk.md` | Layout rendering analysis, active UI risks, Phase 1E recommendations |

---

## Protection Confirmation

- `consensus_evidence.yml` — not modified
- `source_health.yml` — not modified
- `patch_ingestion_sources.yml` — not modified
- `patch_ingest_state.json` — not modified
- `auxsays/updates/generated/` — no records modified
- `auxsays/_layouts/` — no layouts modified
- `.github/workflows/` — not modified
- All production scripts — not modified

Workspace is CLEAN. Only `.project-control/` files were added.

---

## Key Findings

### Architecture

**Critical write-back gap confirmed:** There is no path from `consensus_evidence.yml` evidence rows to DaVinci generated records. `build_consensus_from_evidence.py` writes to gitignored `consensus_status.json` which nothing reads. The OBS pipeline bypasses this gap by combining evidence collection and record write-back in `collect_obs_reports.py`. No DaVinci equivalent exists.

**Official parser confirmed failing:** `refresh_linked_official_bodies()` runs against DaVinci records even when `enabled: false` (it scans all existing records). All 5 attempts in the DaVinci Beta 1 record show `official-source-parser-failed` — confirmed from Phase 1C that Blackmagic pages return a JavaScript SPA shell to non-browser fetchers.

**`fetch_davinci_updates.py` is dead code:** Writes to `patch_state.json` (wrong path), sets a hardcoded `current_consensus: "Moderate"`, has no pipeline role.

### Evidence Access

**Reddit OAuth2:** The only viable automated community source. Blocked at HTML level but public OAuth2 API exists. Requires credential decision in Phase 1E.

**Reddit RSS:** Accessible but insufficient — no version search, truncated bodies. Use as activity signal only, not evidence.

**Blackmagic forum:** Hard 403 on all requests. Do not implement circumvention.

**VideoHelp:** Unknown access status — must probe before committing in Phase 1E.

### UI Risk

**Homepage active risk:** DaVinci Resolve 21 Public Beta 1 appears in the homepage Patch Signals section under bucket 5 because `known_issues_present: true` triggers `has_evidence_signal = true`. The label shows `Insufficient data • known issues` which implies actionable evidence. This is misleading — the known_issues flag reflects advisory complaint themes, not confirmed reports. **Not corrected in Phase 1D.**

**Record page:** The `official_only_zero_reports` layout override is working correctly. The verdict override to "No AUXSAYS recommendation yet." suppresses both `quick_verdict` and `update_decision_label`. However, `practical_recommendations` still renders with "WAIT" language, contradicting the verdict. **Not corrected in Phase 1D.**

### Version Normalization

The current `version_pattern` in the ingestion config fails all Blackmagic-format strings. Canonical form for the Beta 1 record is `'21 Public Beta 1'`. A pre-processing normalization utility is required before any evidence rows can be safely written and matched. Community shorthands like `21b1`, `DR21`, `v21` need normalization or rejection rules. Exact-match only — no fuzzy version matching.

### Write-Back Safety Gates

10 gates defined. Gate 1 (count matches evidence rows) is the most critical. Gate 5 (silence = zero, not a bug) prevents existing 0-count records from being incorrectly reset. All gates must fail closed with non-zero exit.

**Recommended implementation for Phase 1E:** `apply_consensus_to_records.py` — a generic script reading `consensus_evidence.yml` directly, aggregating, and writing evidence-derived fields only. NOT the adapter-provided count path (Phase 1B root cause).

---

## Phase 1E Prerequisites

Before Phase 1E can begin evidence collection for DaVinci:

1. DevTools trace complete — confirm whether Blackmagic has an unauthenticated content API
2. Evidence source decision — Reddit OAuth2 credential approval OR VideoHelp probe OK OR manual review confirmed
3. Version normalization utility implemented and tested against existing OBS rows
4. `apply_consensus_to_records.py` implemented with all 10 safety gates, tested in dry-run
5. At least one DaVinci evidence row confirmed valid in consensus_evidence.yml
6. Homepage `manual_watch` exclusion filter decision made (Rec 2 in UI risk report)
