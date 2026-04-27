# AUXSAYS Patch Ingestion Build Notes

## Current build status

This build keeps the first five official-source adapters enabled:

1. OBS Studio — GitHub releases
2. ComfyUI — GitHub releases
3. Figma — RSS feed
4. GitHub / Copilot — RSS feed
5. Netlify — HTML changelog, narrowed to true dated changelog detail URLs only

## Fixes in this integration pass

- Removed two bad Netlify generated records that were created from tag/archive pages:
  - `2026-04-27-netlify-posts-tagged-ax.md`
  - `2026-04-27-netlify-posts-tagged-sdk.md`
- Cleared the bad Netlify record IDs from `patch_ingest_state.json`.
- Tightened `html_changelog.py` so Netlify only accepts dated changelog detail URLs matching:
  - `/changelog/YYYY/MM/DD/slug/`
- Disabled broad listing-page snapshot generation unless a source explicitly opts into it with:
  - `allow_listing_snapshot: true`
- Updated `patch-ingest.yml` so a successful ingestion commit triggers a Pages build and deploy inside the same workflow.
- Kept dry-run behavior non-mutating: dry runs do not commit and do not deploy.

## GitHub Actions behavior

The ingestion workflow still runs every six hours:

```yaml
schedule:
  - cron: "17 */6 * * *"
```

Manual runs are still supported through `workflow_dispatch`.

If ingestion produces no repo changes, the workflow exits without deploying.
If ingestion creates or removes generated Patch records, the workflow commits the changes, checks out the updated `main`, builds Jekyll, and deploys GitHub Pages from the same workflow.

## Notes

The Node.js 20 warning shown by GitHub Actions is a GitHub-hosted action runtime migration warning. The workflows explicitly opt into Node 24 with:

```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
```

Some official GitHub actions may still report the warning until their internal action metadata is updated upstream.
