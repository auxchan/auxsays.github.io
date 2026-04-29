# AUXSAYS Source Config Guardrail Repair

This repair does not rewrite generated state.

## Files changed

- `.github/workflows/patch-ingest.yml`
- `auxsays/scripts/validate_ingestion_sources.py`
- `auxsays/scripts/lib/http.py`

## Purpose

Adds a validation gate before ingestion so contaminated source configs fail fast instead of producing bad source-health output.

The validator checks:

- non-Adobe products cannot contain Adobe URLs in official/feed/API/secondary fields
- URLs cannot end in malformed punctuation such as `:`
- enabled sources must have an official URL
- ingestion blocks must have adapter/type
- keywords must remain a list of strings or null
- request blocks must remain objects when present

The HTTP helper also changes error formatting from:

`Timeout while fetching URL: error`

to:

`Timeout while fetching official source URL [URL] — error`

This prevents GitHub logs from making a valid URL look like it ends with a colon.
