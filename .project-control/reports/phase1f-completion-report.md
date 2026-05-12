# Phase 1F Completion Report — DaVinci Candidate Verification and Evidence Promotion

## Summary

Phase 1F moved DaVinci Resolve 21 Public Beta 1 from dry-run-only candidate evidence to production structured evidence and a controlled generated-record write-back.

Public result after this transfer is committed and deployed:

- `DaVinci Resolve 21 Public Beta 1` should show **2 confirmed patch-specific reports**.
- Stable `DaVinci Resolve 21` remains at **0 confirmed reports**.

## Files changed

| File | Classification | Purpose |
|---|---|---|
| `auxsays/_data/consensus_evidence.yml` | Allowed production evidence change | Added exactly two approved `blackmagic-davinci` evidence rows for `21 Public Beta 1`. |
| `auxsays/scripts/apply_consensus_to_records.py` | Production script/tooling change | Fixed production evidence gating and added guarded write-back mode. |
| `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md` | Allowed generated-record write-back change | Updated Beta 1 report count and evidence state from official-only/0 to verified reports/2. |
| `.project-control/probe-output/phase1f/davinci-consensus-after-promotion-dry-run.json` | Internal audit output | Dry-run result after adding the two evidence rows and before write-back. |
| `.project-control/probe-output/phase1f/davinci-consensus-writeback-result.json` | Internal audit output | Controlled write-back result. |
| `.project-control/probe-output/phase1f/davinci-final-dry-run.json` | Internal audit output | Final dry-run result after write-back. |
| `.project-control/probe-output/phase1f/audit-after-promotion.json` | Internal audit output | Consensus audit JSON after promotion. |
| `.project-control/reports/phase1f-completion-report.md` | Internal report | This report. |

## Evidence rows promoted

Exactly two `blackmagic-davinci` rows were added to `consensus_evidence.yml`.

### 1. Blackmagic Design forum Magic Mask crash

- ID: `blackmagic-davinci-21-public-beta-1-bmd-forum-t235179-magic-mask-crash`
- URL: `https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235179`
- Product: `blackmagic-davinci`
- Version: `21 Public Beta 1`
- Issue: Resolve Studio 21.0B Build 20 crashes when creating Magic Mask.
- Match basis: user-verified page body/title/build text.
- Counted: `true`
- Patch version matched: `true`
- Sentiment: `negative`
- Severity: `high`

### 2. Reddit decode/render failure

- ID: `blackmagic-davinci-21-public-beta-1-reddit-1sn39qf-decode-failure`
- URL: `https://www.reddit.com/r/davinciresolve/comments/1sn39qf/davinci_resolve_failed_to_decode_video_frame_when/`
- Product: `blackmagic-davinci`
- Version: `21 Public Beta 1`
- Issue: DaVinci Resolve public beta 21 failed to decode video frame when rendering.
- Match basis: user-verified post body/title/version context.
- Counted: `true`
- Patch version matched: `true`
- Sentiment: `negative`
- Severity: `medium`

## Dry-run before write-back

Command:

```bash
python auxsays/scripts/apply_consensus_to_records.py --dry-run --product-id blackmagic-davinci --output .project-control/probe-output/phase1f/davinci-consensus-after-promotion-dry-run.json
```

Result:

- `blackmagic-davinci / 21 Public Beta 1` matched the Beta 1 generated record.
- Included evidence rows: `2`
- Excluded rows: `0`
- Proposed report count: `2`
- Proposed evidence state: `pilot_sample`
- Proposed collection status: `pilot_initial_sample`
- Proposed consensus label: `Negative`
- Proposed confidence: `Low`
- Stable `DaVinci Resolve 21` did not receive Beta 1 evidence.

## Controlled write-back

Command:

```bash
python auxsays/scripts/apply_consensus_to_records.py --write --confirm-write --product-id blackmagic-davinci --update-version "21 Public Beta 1" --output .project-control/probe-output/phase1f/davinci-consensus-writeback-result.json
```

Write-back safeguards:

- `--write` requires `--confirm-write`.
- `--write` requires explicit `--product-id`.
- `--write` requires explicit `--update-version`.
- Candidate staging files cannot be used for write mode.
- Nonzero count requires matching production evidence rows.
- Count must equal qualifying evidence-row count.
- Product ID and update version must match the generated record.
- Beta and stable records cannot cross-match.
- `legacy_manual_report_count` does not contribute to verified count.
- No write proceeds if no matching generated record exists.
- Phase 1F write-back is limited to `blackmagic-davinci / 21 Public Beta 1`.

## Generated record write-back result

Only this generated record was changed:

`auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md`

Important field changes:

| Field | Before | After |
|---|---:|---:|
| `update_report_count` | `0` | `2` |
| `confirmed_patch_specific_report_count` | `0` | `2` |
| `evidence_state` | `official_only` | `pilot_sample` |
| `evidence_state_label` | `Official source only` | `Verified reports` |
| `update_consensus_label` | `Insufficient data` | `Negative` |
| `update_consensus_confidence` | `Low` | `Low` |
| `intelligence_stage` | `manual_watch` | `pilot` |
| `consensus_collection_status` | `deferred_official_only` | `pilot_initial_sample` |
| `legacy_manual_report_count` | `7` | `7`, preserved as historical/manual context only |

A `Verified reports` status event was appended.

## Stable DaVinci 21 status

`auxsays/updates/generated/2026-04-14-davinci-resolve-21.md` was not changed.

It remains:

- `update_report_count: 0`
- `confirmed_patch_specific_report_count: 0`
- `evidence_state: official_only`

## Validation results

Commands run in this environment:

| Command | Result |
|---|---|
| `python auxsays/scripts/validate_ingestion_sources.py` | Passed, 46 entries checked. |
| `python auxsays/scripts/qa_patch_records.py` | Passed, 0 errors, 0 warnings. |
| `python auxsays/scripts/build_consensus_from_evidence.py` | Passed, 65 evidence items, 4 aggregate rows, 0 excluded. |
| `python auxsays/scripts/audit_consensus_evidence.py --json --strict` | Exited nonzero due to pre-existing unrelated Premiere/stale-record findings; DaVinci count mismatch was not present. Output saved to `.project-control/probe-output/phase1f/audit-after-promotion.json`. |
| `python auxsays/scripts/validate_logo_assets.py` | Passed. |
| `python auxsays/scripts/tests/test_normalize_davinci_version.py` | Passed, 51/51 tests. |
| `bundle exec jekyll build --trace` | Not available in this environment because `bundle` is not installed. GitHub Actions should perform the authoritative Jekyll build after push. |

## Confirmations

- Exactly two `blackmagic-davinci` rows were added to `consensus_evidence.yml`.
- No unapproved Phase 1E candidate rows were promoted.
- No negative test rows were promoted.
- Stable DaVinci 21 stayed at 0.
- DaVinci Beta 1 now has 2 verified reports.
- `legacy_manual_report_count: 7` was preserved but did not contribute to verified counts.
- DaVinci ingestion remains disabled.
- No scraper was implemented.
- No GitHub Actions workflows were modified.
- No credentials, cookies, OAuth tokens, or API keys were added.

## Recommended next phase

Phase 1G should verify the deployed page and then continue adding/validating real DaVinci evidence sources. The immediate next checks are:

1. Confirm GitHub Actions deploys successfully.
2. Confirm the live DaVinci Beta 1 page shows 2 reports.
3. Confirm stable DaVinci 21 remains at 0.
4. Add additional verified DaVinci evidence rows only after source/body review.
