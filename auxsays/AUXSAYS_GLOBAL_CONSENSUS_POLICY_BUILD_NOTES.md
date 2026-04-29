# AUXSAYS Global Consensus Policy Build Notes

## Purpose

This build applies the global Patch Feed consensus standard across all update records and display templates.

## Global consensus rule

A report is counted only when the specific patch/version is named in the report itself or in the parent discussion/thread title.

If a parent discussion title names the exact patch/version, replies inside that discussion are treated as patch-specific unless the reply explicitly shifts to another version or unrelated issue.

Low-context mentions are excluded entirely. They are not weak votes and are not downweighted.

Every confirmed patch-specific report counts equally.

## Added

- `_data/consensus_rules.yml`
- `scripts/consensus_refresh.py`
- `scripts/README-consensus-refresh.md`
- `.github/workflows/consensus-audit.yml`

The consensus script is an audit scaffold. It does not scrape forums yet. It validates that generated Patch records use the global consensus metadata policy.

## Updated public wording

- `reports assessed` → `confirmed patch-specific reports`
- `matched reports` → `confirmed patch-specific reports`
- `User consensus` → `Patch-specific consensus`

Update pages now show a rule note explaining that reports are counted only when the patch/version is named directly or by the parent discussion title.

## DaVinci / Blackmagic visual repair

- Added/updated Blackmagic Design company logo mapping.
- Added/updated DaVinci Resolve product icon mapping.
- Added DaVinci Resolve UI backdrop asset.
- Updated DaVinci product metadata to match the same company → software → patch hierarchy used elsewhere.

## Important limitation

This build does not activate live community scraping. The existing report counts remain static initial samples until a future consensus-refresh collector is implemented for specific source types such as official forums, dedicated forums, GitHub Issues/Discussions, or subreddits.
