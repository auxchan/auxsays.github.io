# AUXSAYS Consensus Refresh

This is the global consensus standard for all Patch Feed records.

## Inclusion rule

A report is counted only when the specific patch/version is named in the report itself or in the parent discussion/thread title.

If the parent discussion title names the exact patch/version, replies inside that thread are treated as patch-specific unless the reply explicitly shifts to another version, another patch, or an unrelated issue.

## Exclusion rule

Low-context mentions are excluded entirely. They are not weak votes and they are not downweighted.

Examples excluded:

- "Resolve is broken after the update" outside a version-specific thread.
- "Premiere keeps crashing now" without a version or patch-specific parent context.
- Generic praise or complaints about a software product.

## Weighting

Every confirmed patch-specific report counts equally. Official forums, dedicated forums, GitHub discussions, Reddit, and other sources may be stored as source types for transparency, but source type does not multiply or discount the report.

## Current implementation status

`scripts/consensus_refresh.py` is currently an audit scaffold. It validates that generated Patch records are labeled with the global consensus policy. It does not scrape forums yet.

Official update ingestion remains separate from consensus refresh.

`scripts/audit_consensus_evidence.py` compares generated Patch record report counts with the structured rows in `auxsays/_data/consensus_evidence.yml`. It reports records that claim confirmed reports without matching structured evidence, records where evidence exists but counts differ, and missing or stale evidence freshness dates.

This audit is not a collector. It does not fetch Reddit, forums, GitHub Issues, Adobe Community, or any other public community source. A page should say `Live consensus` only after a real collector exists and its structured evidence backs the displayed counts.
