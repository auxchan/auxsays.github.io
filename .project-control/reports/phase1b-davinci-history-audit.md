# Phase 1B — DaVinci History Audit Report

**Date:** 2026-05-12  
**Scope:** Read-only git history investigation. No files modified during this audit.

---

## 1. When the DaVinci Beta 1 7-Report Value Entered the Repo

The generated record `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md` appears in **exactly one commit** in the Replit repo history:

```
c8251e5  Phase 0: Make Jekyll/GitHub Pages repo Replit-preview-ready
```

This commit is the **first and only commit** that touched any generated record in this Replit workspace. Its message explicitly states: *"No generated records, state files, or GitHub Actions workflows modified."*

This means the file — including the `update_report_count: 7` — arrived **pre-committed** in the repository before any Replit work began. The value was not introduced by Phase 0, Phase 1A, or any Replit agent session. It was already present in the user's local repo (at `C:\GITHUB PROJECTS\auxsays.github.io`) and was carried into Replit as part of the initial repo upload.

**Git evidence:**
```
git log --oneline --all -- auxsays/updates/generated/
→  c8251e5 Phase 0: Make Jekyll/GitHub Pages repo Replit-preview-ready

git log --oneline --all -- auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md
→  c8251e5 Phase 0: Make Jekyll/GitHub Pages repo Replit-preview-ready
```

There is no earlier commit in this repo's history. The file predates all agent activity.

---

## 2. Whether Any Script or Workflow Created the 7-Report Value

**Finding: No script or workflow created this value.**

A full search of all scripts confirms:

- `fetch_davinci_updates.py` — 11-line dead stub. Does not call any evidence collection. Does not write records or set `update_report_count`. Not called by `patch_ingest.py`.
- `patch_ingest.py` — Skips any source with `adapter: manual_watch` or `enabled: false`. DaVinci ingestion is disabled (`enabled: false` in `patch_ingestion_sources.yml`). No DaVinci run has occurred.
- `build_consensus_from_evidence.py` — Reads `consensus_evidence.yml` and counts rows per `product_id`. There are zero rows for `product_id: blackmagic-davinci`. This script therefore cannot have set `update_report_count: 7`.
- `write_update_record.py` — Only writes records when called by the ingest pipeline. DaVinci ingestion is disabled.
- GitHub Actions workflows — The only workflow (`.github/workflows/`) runs the Jekyll build for GitHub Pages. It does not run Python evidence collectors.

**The value was set manually** — hand-authored in the YAML front matter of the record by whoever created it before the repo arrived in this Replit workspace.

---

## 3. Whether Any DaVinci Report-Gathering Was Disabled or Deprecated

**Finding: DaVinci report gathering was never fully implemented and is currently disabled.**

Evidence:
- `patch_ingestion_sources.yml`: DaVinci Resolve has `enabled: false` in its config entry.
- `fetch_davinci_updates.py`: The file exists but is a stub — it does not implement any fetch or parse logic. It is not called by `patch_ingest.py`.
- `html_changelog.py`: No `blackmagic_media_keyword_filter` parser branch exists. The profile name is referenced in config but has no matching implementation.
- There are no structured rows in `consensus_evidence.yml` for `product_id: blackmagic-davinci`.
- `source_health.yml`: No active DaVinci ingest run has been recorded with a success state.

The working hypothesis (confirmed): DaVinci ingestion was never production-ready. The stub file suggests an initial intent to build a collector that was never completed. Report gathering was either never started or paused before structured evidence was collected.

---

## 4. Whether Stable/Non-Beta DaVinci Ever Had Report Gathering Enabled

**Finding: No evidence that stable DaVinci ever had structured report gathering enabled.**

The stable record `2026-04-14-davinci-resolve-21.md` has:
- `legacy_consensus_score: 0`
- `legacy_consensus_score_percent: 50`
- No `update_report_count` field visible in the git-origin state

The Beta 1 record has `legacy_consensus_score: 6` and `legacy_consensus_score_percent: 53` alongside the 7-report count — these `legacy_consensus_score` fields suggest the value came from a **different, older scoring methodology** (not the current `consensus_evidence.yml` row-counting system). The stable record's score of 0/50 is consistent with a record that never had report gathering of any kind.

**No DaVinci stable or beta ingestion run appears in any commit, script output, or state file in this repo.**

---

## 5. Whether the 7-Report Count Has Any Traceable Evidence Source

**Finding: The 7-report count is not traceable to any structured evidence source.**

A complete grep of the repo for the value:

```bash
git grep -n "update_report_count: 7"
→  auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md
→  auxsays/updates/generated/2026-04-30-premiere-pro-26-2.md

git grep -n "7 confirmed"
→  (only in .project-control/ documentation files — no scripts, no source data)

git grep -n "confirmed_patch_specific_report_count: 7"
→  auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md
→  auxsays/updates/generated/2026-04-30-premiere-pro-26-2.md
```

The value appears in two records (DaVinci Beta 1 and Premiere Pro 26.2). Both appear to have been authored with the same manual count value. The `legacy_consensus_score: 6` field (not 7) is a separate older-system field and does not represent the same count.

There are **zero rows** in `consensus_evidence.yml` for `product_id: blackmagic-davinci`. The record's own `status_events` note says:

> "Consensus read based on 7 confirmed patch-specific reports."

But this note is the only record of this count. There is no supporting row in `consensus_evidence.yml`, no script output, no forum-scrape log, no audit trail. The note itself appears to have been written at the same time as the rest of the manually-authored front matter.

---

## 6. Classification of the 7-Report Value

**Classification: Legacy/manual — early pilot or pre-evidence manual estimate. Not evidence-backed. Not structured. Untraceable.**

Breakdown:
- **Not structured evidence-backed** — zero rows in `consensus_evidence.yml`
- **Likely legacy/manual** — the `legacy_consensus_score` field pattern, the manual `status_events` note, and the pre-Replit origin all point to manual authoring
- **Possibly early pilot** — the `consensus_collection_status: pilot_initial_sample` and `intelligence_stage: pilot` values suggest whoever created the record may have manually gathered 7 data points from the Blackmagic beta forum or similar source, then labelled it as a pilot sample
- **Not untrue** — the 7 reports may genuinely have existed at the time of authoring; there is no evidence they were invented. However, there is also no evidence they were counted using the current `confirmed_patch_specific_reports_v1` methodology (the field `consensus_match_policy` claims this policy but no rows in `consensus_evidence.yml` back it)
- **Cannot be verified or reproduced** under the current evidence system

The most accurate classification is: **legacy/manual, pre-evidence-system estimate. Plausibly based on real reports at time of authoring but not reproducible under the current methodology and not backed by structured rows.**

---

## 7. Safer Correction Choice

**Recommendation: Set verified count to 0 and preserve 7 as legacy/manual context, clearly labelled.**

Reasoning:

1. **Do not remove the 7 entirely.** The AGENTS.md principle is "Do not remove features just because they are incomplete. Fix the machinery or label the limitation." If the 7 reports may genuinely have existed, erasing them entirely loses historical context without gain. The goal is to stop the number being rendered as *evidence-backed*, not to deny it ever existed.

2. **Preserve it under a clearly separate field.** Adding `legacy_manual_report_count: 7` with an explanatory note field keeps the historical record visible to maintainers and agents while making clear it is not part of the current verified count system.

3. **Set `update_report_count: 0`.** The layout uses this field to render "X confirmed patch-specific reports" on the page. Setting it to 0 stops the misleading public display without destroying the historical value.

4. **Change `consensus_collection_status` and `evidence_state` to stop "Verified reports" from rendering.** Both fields independently trigger the "Verified reports" label in the layout. Both must be corrected.

The alternative (remove 7 entirely) is acceptable only if the project decides that unverifiable values should not be preserved in any form. Given the AGENTS.md stance on labelling rather than hiding, the preserve-as-legacy approach is safer and more honest.

---

## 8. Also-Affected Record Noted (Not Modified)

The Premiere Pro record `2026-04-30-premiere-pro-26-2.md` also has `update_report_count: 7` and `confirmed_patch_specific_report_count: 7`. However, that record has `AUXSAYS_PREMIERE_DATA_COMPLETENESS_SPRINT_NOTES.md` referencing "7 confirmed patch-specific Adobe Community report sources" — suggesting there may be an external reference document that backs the Premiere Pro count. That record was not examined in depth and is **not modified in Phase 1B** per the scope constraint.
