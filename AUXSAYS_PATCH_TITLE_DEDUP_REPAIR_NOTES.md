# AUXSAYS Patch Title Dedup Repair

## Issue
The Patch Feed card title template used a chained Liquid filter expression:

```liquid
{{ item.update_feed_title | default: item.update_product | append: ' ' | append: item.update_version }}
```

In Liquid, the `append` filters still ran after `default`, so records with `update_feed_title` already containing the version rendered duplicated titles like:

- `DaVinci Resolve 21 Public Beta 1 21 Public Beta 1`
- `OBS Studio 32.1.1 32.1.1`

## Fix
`auxsays/_layouts/aux-updates.html` now assigns `card_title` explicitly:

1. Use `update_feed_title` if present.
2. Otherwise use `update_product + update_version`.
3. Otherwise fall back to product or page title.

This fixes both current and archived Patch Feed cards.
