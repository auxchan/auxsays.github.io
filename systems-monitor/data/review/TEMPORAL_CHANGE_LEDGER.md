# Temporal Change Ledger

Status: IMPLEMENTED FOR LOCAL REVIEW — HUMAN QA PENDING
As-of: 2026-08-18T20:00:00Z (current accepted PDI snapshot)

## Purpose

The temporal layer retains observation versions, distinguishes official publication time from AUXSAYS acceptance time, and produces a material change event only from two comparable accepted observations under a versioned native-cadence profile.

## Implemented model

- `ObservationVersion` is immutable and append-only.
- Exact retries are idempotent; reusing an observation identity with different content fails.
- `PUBLICLY_AVAILABLE_AS_OF` uses proven official publication time only.
- `OPERATIONALLY_KNOWN_AS_OF` uses AUXSAYS accepted time only.
- Advance, preliminary, revised, and final releases remain distinct records.
- Comparability requires the same factor, unit, geography, adjustment state, and cadence.
- No comparable reference, unchanged data, and immaterial movement do not produce an economic change event.
- Materiality thresholds are versioned and expressed in the source's native cadence.

## Current accepted evidence

The active public snapshot contains one current accepted point for each of the six displayed labor indicators. It therefore supports a deterministic “new official observation accepted” notice, but not a current increase/decrease claim. The DOL March 2024 revision evidence remains a separate historical replay example.

## Time windows

`Recent`, `24h`, `7d`, `30d`, `90d`, and `1y` queries use the same immutable notice set and explicit as-of time. A monthly source is never interpolated into hourly economic movement.

## Remaining blockers

Current material-change intelligence requires retained comparable prior observations and approved materiality profiles per factor. Those are not fabricated in this sprint.
