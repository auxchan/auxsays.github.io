# AUXSAYS Patch Ingestion

This folder now contains the first official-source ingestion framework for the AUXSAYS Patch Feed.

## Current build status

Enabled first-pass adapters:

1. OBS Studio — `github_releases`
2. ComfyUI — `github_releases`
3. Figma — `rss_feed`
4. GitHub / Copilot — `rss_feed`
5. Netlify — `html_changelog`

The remaining tracked Company/Software sources are represented in:

```text
auxsays/_data/patch_ingestion_sources.yml
```

They are intentionally disabled until their parser profiles are hardened.

## Run locally from repo root

```bash
pip install -r auxsays/scripts/requirements-ingest.txt
python auxsays/scripts/patch_ingest.py
```

## Run a single source

```bash
python auxsays/scripts/patch_ingest.py --source obs-studio
python auxsays/scripts/patch_ingest.py --source comfyui
```

## Dry run

```bash
python auxsays/scripts/patch_ingest.py --dry-run
```

## Important constraints

- Official ingestion only.
- Confirmed patch-specific consensus is deferred.
- Existing generated Markdown records are not overwritten by default.
- State is stored separately in `_data/patch_ingest_state.json` so it does not collide with the site's existing `_data/patch_state.json`.
- Only enable additional sources after testing the adapter against the official source format.
