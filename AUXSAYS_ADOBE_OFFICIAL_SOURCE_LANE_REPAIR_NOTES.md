# AUXSAYS Adobe Official Source Lane Repair

Scope: surgical repair for the Adobe Premiere Pro source lane.

Changed files:
- auxsays/_data/patch_ingestion_sources.yml
- auxsays/scripts/adapters/adobe_release_notes.py
- auxsays/scripts/lib/http.py
- auxsays/scripts/patch_ingest.py

Rationale:
- The Adobe HelpX release-notes URL is valid, but GitHub Actions repeatedly timed out while reading it with 0 bytes received.
- The active source lane now uses Adobe's official Community announcement for Premiere 26.2 as the primary fetch target.
- The HelpX release-notes URL remains as the secondary official reference.
- The adapter now supports page-level Adobe announcement parsing instead of requiring HelpX-style version headings.
- Top-level GitHub Actions error text is sanitized so raw URLs do not dominate log headlines.

Generated state intentionally excluded:
- auxsays/_data/source_health.yml
- auxsays/_data/patch_ingest_state.json
- auxsays/updates/generated/*
