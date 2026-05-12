# Phase 1G Completion Report — DaVinci Evidence Candidate Workflow

## Summary

Phase 1G added a manual-review DaVinci evidence candidate workflow for both current DaVinci records:

- Stable / Studio 21: `auxsays/updates/generated/2026-04-14-davinci-resolve-21.md`
- Public Beta 1: `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md`

The collector stages candidates for review only. It does not write `consensus_evidence.yml`, generated records, workflows, schedules, credentials, or tokens.

## Files Changed

| File | Purpose |
|---|---|
| `auxsays/scripts/collect_davinci_candidates.py` | New conservative manual-review candidate collector for stable, beta, or both DaVinci targets. |
| `.project-control/evidence-staging/phase1g-davinci-source-profile.yml` | Manual source profile and promotion policy for DaVinci evidence review. |
| `.project-control/evidence-staging/phase1g-davinci-candidates.yml` | Collector output for the Phase 1G seed set. |
| `.project-control/probe-output/phase1g/davinci-candidate-collector-result.json` | Machine-readable collector summary. |
| `.project-control/reports/phase1g-davinci-promotion-decision-log.md` | Manual promotion decision log for every candidate. |
| `.project-control/reports/phase1g-completion-report.md` | This completion report. |
| `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md` | Public note wording cleanup only; counts and evidence state were not changed. |

## Starting and Final Counts

| Record | Starting count | Final count |
|---|---:|---:|
| Stable DaVinci Resolve 21 | 0 | 0 |
| DaVinci Resolve 21 Public Beta 1 | 2 | 2 |

## Candidate Summary

Candidate count by source:

| Source type | Count |
|---|---:|
| `blackmagic_forum` | 6 |
| `reddit_community_report` | 4 |
| `community_discovery` | 3 |
| `release_metadata` | 1 |

Candidate count by target record:

| Target record | Count |
|---|---:|
| `stable` | 2 |
| `beta` | 2 |
| `future` | 1 |
| `ambiguous` | 9 |

Decision counts:

| Decision | Count |
|---|---:|
| `promote_now` | 0 |
| `needs_user_verification` | 7 |
| `duplicate_existing_evidence` | 2 |
| `future_update_not_current_record` | 1 |
| `ambiguous_version` | 4 |
| `reject` | 0 |

## Promotion Outcome

No candidate met the `promote_now` rules.

New evidence rows added: none.

Generated records updated by controlled write-back: none.

Existing Phase 1F evidence was detected as duplicate:

- `https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235179`
- `https://www.reddit.com/r/davinciresolve/comments/1sn39qf/davinci_resolve_failed_to_decode_video_frame_when/`

## Cross-Match Confirmation

- Stable 21 candidates remain targeted only to `stable`.
- Public Beta 1 candidates remain targeted only to `beta`.
- `21.0b2` / Public Beta 2 was classified as `future_update_not_current_record`.
- Ambiguous, blocked, discovery-only, release-metadata, and body-inaccessible rows are not eligible for either current record.
- No stable evidence was added to Beta 1.
- No Beta 1 evidence was added to stable 21.

## Safety Confirmations

- DaVinci ingestion remains disabled/manual-watch in `auxsays/_data/patch_ingestion_sources.yml`.
- `.github/workflows/davinci-updates.yml` remains workflow-dispatch only and deprecated.
- No GitHub workflow was changed.
- No scheduled DaVinci scraper was added.
- No credentials, cookies, OAuth tokens, API keys, or secrets were added.
- No ZIP files were created.
- No push was performed.

## Validation Results

| Command | Result |
|---|---|
| `python auxsays/scripts/validate_ingestion_sources.py` | Blocked in local environment: `ModuleNotFoundError: No module named 'yaml'`. |
| `python auxsays/scripts/qa_patch_records.py` | Blocked in local environment: `ModuleNotFoundError: No module named 'yaml'`. |
| `python auxsays/scripts/build_consensus_from_evidence.py` | Blocked in local environment: `ModuleNotFoundError: No module named 'yaml'`. |
| `python auxsays/scripts/audit_consensus_evidence.py --json --strict` | Ran with built-in fallback parser and exited nonzero due pre-existing non-DaVinci audit findings: Premiere Pro 26.2 claims 7 reports while structured evidence has 3, plus stale freshness findings. DaVinci Beta 1 matched 2 structured evidence rows; stable DaVinci 21 remained 0. |
| `python auxsays/scripts/collect_davinci_candidates.py --dry-run --target both --output .project-control/evidence-staging/phase1g-davinci-candidates.yml` | Passed; staged 14 candidates; `promote_now_count: 0`. |
| `python auxsays/scripts/apply_consensus_to_records.py --dry-run --product-id blackmagic-davinci --output .project-control/probe-output/phase1g/davinci-final-dry-run.json` | Blocked in local environment: `ModuleNotFoundError: No module named 'yaml'`. No final dry-run JSON was created. |
| `cd auxsays && bundle exec jekyll build --trace` | Blocked in local environment: `bundle` is not installed/on PATH. |

## Environment Limitation

The bundled Python available in this environment does not include PyYAML. Attempts to install PyYAML were blocked by filesystem permission errors, so YAML-dependent validation scripts could not complete locally. A temporary `.project-control/.pip-tmp/` directory was created during the failed install attempt; the sandbox refused deletion afterward.

## Recommended Next Step

Manually review the seven `needs_user_verification` candidates. Promote only rows where the page body or user-provided body text confirms an actual issue report and an exact current-record version match (`21` for stable, `21 Public Beta 1` for Beta 1).
