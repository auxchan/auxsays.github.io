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

On Windows, create a local virtual environment and run scripts through that
environment instead of relying on a global `python` command:

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

Official ingestion remains mutating unless run with `--dry-run`:

```powershell
.\.venv\Scripts\python.exe auxsays\scripts\patch_ingest.py --dry-run
```

## Run a single source

```powershell
.\.venv\Scripts\python.exe auxsays\scripts\patch_ingest.py --source obs-studio --dry-run
.\.venv\Scripts\python.exe auxsays\scripts\patch_ingest.py --source comfyui --dry-run
```

## Dry run

```powershell
.\.venv\Scripts\python.exe auxsays\scripts\patch_ingest.py --dry-run
```

## Important constraints

- Official ingestion only.
- Confirmed patch-specific consensus is deferred.
- Existing generated Markdown records are not overwritten by default.
- State is stored separately in `_data/patch_ingest_state.json` so it does not collide with the site's existing `_data/patch_state.json`.
- Only enable additional sources after testing the adapter against the official source format.
