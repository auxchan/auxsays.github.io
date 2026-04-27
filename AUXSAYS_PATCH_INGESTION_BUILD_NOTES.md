# AUXSAYS Patch Ingestion Build Notes

This build adds the first official-source ingestion framework without changing the public visual design.

## Added

- `auxsays/_data/patch_ingestion_sources.yml`
  - Full 33-source ingestion matrix/config generated from the repo source list.
  - Only the first five recommended sources are enabled:
    - OBS Studio
    - ComfyUI
    - Figma
    - GitHub / Copilot
    - Netlify

- `auxsays/scripts/patch_ingest.py`
  - Main ingestion runner.
  - Uses enabled sources by default.
  - Supports `--source`, `--dry-run`, `--all`, and `--overwrite-existing`.
  - Does not overwrite existing generated Markdown records unless explicitly told to.

- `auxsays/scripts/adapters/`
  - `github_releases.py`
  - `rss_feed.py`
  - `html_changelog.py`
  - placeholder wrappers for later adapter expansion

- `auxsays/scripts/lib/`
  - HTTP, normalization, state, and Markdown record writing helpers.

- `auxsays/_data/patch_ingest_state.json`
  - Dedicated ingestion state file separate from the existing public-facing `patch_state.json`.

- `.github/workflows/patch-ingest.yml`
  - Scheduled official ingestion workflow.
  - Manual workflow dispatch supports optional `source` and `dry_run`.

## Changed

- Deprecated the old scheduled OBS and DaVinci workflows so they no longer conflict with the unified ingestion workflow.
- Retained the old scripts for reference.
- Fixed a syntax issue in the old OBS script and changed its fallback consensus default away from `Moderate`.

## Local use

From the repo root:

```bash
pip install -r auxsays/scripts/requirements-ingest.txt
python auxsays/scripts/patch_ingest.py --dry-run
python auxsays/scripts/patch_ingest.py --source obs-studio --dry-run
```

## GitHub Desktop flow

1. Extract this ZIP.
2. Open the extracted folder.
3. Drag the contents into your local `auxsays.github.io` repo folder.
4. Allow overwrite/replace.
5. Open GitHub Desktop.
6. Review changed files.
7. Commit and push.
