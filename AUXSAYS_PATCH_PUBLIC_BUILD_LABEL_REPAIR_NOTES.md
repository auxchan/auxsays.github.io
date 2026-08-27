# AUXSAYS Public Build Label Repair

## Issue

A build-aware product ships several builds under one marketing version, and `patch_identity`
treats those as **different patches**. The public label did not.

`write_update_record._public_version_label` produces `2607 (Build 20228.20110)` — but it runs
**only on the create path**, and `refresh_existing_record` never rewrites the four fields it feeds
(`title`, `description`, `update_feed_title`, `update_detail_title`; none of them appear in
`OFFICIAL_ISSUE_FIELDS`, `WINDOWS_IDENTITY_FIELDS` or `OPTIONAL_STRUCTURED_FIELDS`).

The corpus was therefore split. 20 `microsoft-powerpoint` records written before the writer learned
about builds carried a bare version forever:

```yaml
title: Microsoft PowerPoint 2607 official update breakdown
description: Official Microsoft PowerPoint update record captured from Microsoft.
update_feed_title: Microsoft PowerPoint 2607
```

…while the two 2608 records written after it already carried `2608 (Build 20326.20100)`. Every one
of those strings renders immediately beside a **per-build** monitoring status
(`aux-updates.html`, `aux-update.html`), so the reader saw a health verdict for one exact build next
to a headline that would not say which build it was — and the next sibling build to ingest under an
older version would arrive build-labelled while its sibling stayed bare.

## Decision

Three options were on the table. The fix is **(b) with a narrow (c)**, and (a) was rejected outright.

**(a) Add the four fields to a refresh path — rejected.** `refresh_existing_record` only runs for a
record still present in the live vendor source. The 2024 and 2025 PowerPoint records will never
appear on the Current Channel page again, so a self-healing refresh would repair the newest records
— the ones the write path already gets right — and none of the ones that are actually wrong.

**(b) Render the build at template level — adopted, for every surface a template owns.** A new
shared include, `_includes/patch-public-label.html`, appends the build from the record's own
`target_build` at render time. It needs no data migration and no write-path change, and because the
label is derived from the canonical identity rather than stored beside it, **it cannot drift again**.
Wired into all five rendered headlines: the detail H1, both patch-feed card titles, the home signal
card, and the detail-page citation.

**(c) A deterministic repair of `title` and `description` — adopted, only where (b) cannot reach.**
`aux-base.html:6` renders `{% seo %}`, and jekyll-seo-tag reads `page.title` / `page.description`
straight off the front matter to build `<title>`, `og:title`, `og:description` and the meta
description. No layout can override what that plugin reads, so those two fields are repaired in the
data or not at all — and leaving them bare would ship a page whose `<h1>` states a build its own
`<title>` does not.

`update_feed_title` / `update_detail_title` were deliberately **left out of the repair**: they are
AUXSAYS presentation fields that our own layouts render, so the include supplies their build.

## What changed

| Surface | Mechanism |
| --- | --- |
| Detail H1, detail citation | `patch-public-label.html` from `page.target_build` |
| Patch feed cards (both grids) | `patch-public-label.html` from `item.target_build` |
| Home signal card | `patch-public-label.html` from `item.target_build` |
| `<title>`, `og:title`, meta description | stored `title` / `description`, repaired once |

- `auxsays/_includes/patch-public-label.html` — new; additive, idempotent, silent without evidence.
- `auxsays/_layouts/aux-update.html`, `aux-updates.html`, `aux-home.html` — call it.
- `auxsays/scripts/normalize_public_build_labels.py` — new; `--apply` repairs, no flag reports.
- `auxsays/scripts/qa_patch_records.py` — new `public_label_missing_build` **error**.
- 20 `microsoft-powerpoint` records — two lines each, nothing else.

## Constraints held

- **No manufactured attribution.** A build-aware record with no `target_build` is reported and left
  alone; there is no inference, no vendor lookup, no re-ingestion. The build always comes from the
  record being labelled.
- **No consensus write authority for titles.** `title` remains in `PROTECTED_FIELDS` and stays out
  of `CONSENSUS_COHERENCE_FIELDS`, so the consensus lane still cannot rewrite a title. Pinned by a
  test.
- **Version-only products are byte-identical.** Proven by rendering, not asserted: a version-only
  record renders exactly as a template with the include call removed. No `(Build )`, no empty
  parens, no inherited sibling build. 883 records unaffected.
- **The repair is additive.** It rewrites a field only when the stored value is byte-identical to a
  label this repo's own writer produced for that exact record. A hand-authored title is reported and
  left untouched; its engine-written description is still repaired.
- **One authority for the string.** The repaired value is asserted equal to what
  `write_update_record.build_front_matter` produces for the same record.
- **No historical backfill.** No record was re-fetched, re-ingested or regenerated. The diff is
  exactly 40 lines across 20 files: one `title`, one `description` each.

## Not changed, on purpose

`aux-updates.html` renders `<span>Version {{ item.update_version }}</span>` in the card meta row,
and `aux-update.html` renders a Version meta pill, both without a build. Left as they are: the
version pill states the marketing version, the headline beside it now states the exact patch.
Appending the build to both would duplicate it on the same card.

## Gotcha found while building this

**Liquid parses tags inside a `{% comment %}` block.** A literal `{% if x != blank %}` written as an
example inside the include's documentation is not a comment — it is a syntax error that aborts the
whole render (`'endcomment' is not a valid delimiter for if tags`). The include documents the guard
idiom in prose without tag delimiters, and a test now checks every comment block in the four touched
templates for smuggled `{%` / `{{`.

## Verification

- `test_public_build_label_presentation.py` — 89/89. Renders the **verbatim shipped** include and
  layout slices through the real liquid gem (with a minimal shim for Jekyll's
  `{% include file.html k=v %}` syntax), including a non-vacuity proof that the two 2608 siblings
  were indistinguishable before the fix and are distinguishable after.
- Gates: `qa_patch_records.py` (0 errors), `validate_ingestion_sources.py`,
  `validate_evidence_method_health.py`, `validate_logo_assets.py` — all pass.
- Full `auxsays/scripts/tests` sweep: only the three known pre-existing failures
  (`test_davinci_verified_reports` 66/68, `test_teams_record_cleanup` 5/6,
  `test_adobe_premiere_collector` network timeout).
- A real `jekyll build` could not run in this environment (missing `eventmachine` gem), the same
  environmental gap that makes `test_monitoring_status_render` skip.
