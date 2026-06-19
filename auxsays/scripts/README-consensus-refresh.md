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

## Local validation setup on Windows

From the repo root, create a local virtual environment and install the shared
script dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe auxsays\scripts\validate_evidence_method_health.py
.\.venv\Scripts\python.exe auxsays\scripts\audit_consensus_evidence.py --json --strict
```

If `py` is not recognized, install or repair Python 3.12+ for Windows and enable
the Python Launcher, or use the full path to the installed Python executable.
After venv creation, prefer `.\.venv\Scripts\python.exe` instead of relying on
global `python`.

`scripts/audit_consensus_evidence.py` compares generated Patch record report counts with the structured rows in `auxsays/_data/consensus_evidence.yml`. It reports records that claim confirmed reports without matching structured evidence, records where evidence exists but counts differ, and missing or stale evidence freshness dates.

The audit separates findings into severity categories:

- `integrity_errors`: report-count mismatches, generated report counts without structured evidence, structured evidence without a matching generated record, slug/version mismatches, and core schema problems.
- `evidence_freshness_errors`: missing or stale `evidence_last_checked` on report-bearing records.
- `record_freshness_warnings`: stale generated-record freshness metadata.
- `source_freshness_advisories`: source checks that happened after the generated record timestamp.

`--strict` fails on `integrity_errors` and `evidence_freshness_errors`. Broad source-check advisories remain visible without being treated as report-count integrity failures.

This audit is not a collector. It does not fetch Reddit, forums, GitHub Issues, Adobe Community, or any other public community source. A page should say `Live consensus` only after a real collector exists and its structured evidence backs the displayed counts.

`scripts/collect_obs_reports.py` is the first manual pilot collector. It is scoped to OBS Studio 32.1.2 and reads only GitHub Issues from `obsproject/obs-studio`. It is not scheduled and it is not full live consensus.
