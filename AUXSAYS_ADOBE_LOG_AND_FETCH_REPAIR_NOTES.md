# AUXSAYS Adobe Log and Fetch Repair

## Scope

This is a surgical repair for Adobe HelpX fetch diagnostics and fallback behavior.

Changed files:

- `auxsays/scripts/lib/http.py`
- `auxsays/scripts/patch_ingest.py`

No generated state files are included.

## Changes

1. Added a narrow curl fallback for `helpx.adobe.com` requests only.
2. Kept Adobe HelpX fetches bounded by the existing timeout settings.
3. Stopped top-level ingestion errors from printing raw URLs in GitHub Actions log headlines.
4. Added final URL sanitization in `patch_ingest.py` before storing or printing ingestion errors.
5. Preserved source URLs in source config and structured records instead of top-level error text.

## Expected GitHub Actions log style

Before:

```text
[ERROR] adobe-premiere-pro: Timeout while fetching official source URL [https://...] — The read operation timed out
```

After:

```text
[ERROR] adobe-premiere-pro: Timeout while fetching official Adobe source — The read operation timed out
```

If the curl fallback is attempted and fails, the headline remains URL-free.

## What this does not do

- Does not modify `patch_ingestion_sources.yml`
- Does not modify `source_health.yml`
- Does not modify `patch_ingest_state.json`
- Does not modify generated patch records
- Does not add or remove software products
