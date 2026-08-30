# AUXSAYS Liquid `blank` Guard Audit

## Root cause

`liquid-4.0.4/lib/liquid/expression.rb:20` maps the `blank` literal to
`MethodLiteral.new(:blank?, '')`. `Condition#equal_variables` resolves a `MethodLiteral` via
`other.respond_to?(:blank?)` and returns `nil` when it does not. Neither `liquid-4.0.4` nor
`jekyll-4.4.1` defines `String#blank?`, and there is no ActiveSupport in the Gemfile. Therefore:

    {% if x != blank %}   is ALWAYS TRUE    -- for every value, including '' and nil
    {% if x == blank %}   is ALWAYS FALSE

Every else-branch behind such a guard is dead code. Reproduce with the installed gem:

    ruby -e 'require "liquid"; puts Liquid::Template.parse("[{% if v != blank %}X{% endif %}]").render("v" => "").inspect'
    => "[X]"     (should be "[]")

`x != ''` alone is **not** the fix — `nil != ''` is also true. The working idiom normalises first:

    {% assign b = x | default: '' %}{% if b != '' %}

`default` replaces nil, false **and** the empty string. Note that `nil`, `null`, `false` and
`empty` are *not* affected: they are real Liquid literals (or, for `empty`, a `MethodLiteral`
backed by `String#empty?`), so comparisons against them work correctly and were left alone.

## Scope

108 `blank` comparisons across 10 templates. 59 fixed, 49 left in place as provably inert.

| template | before | after | fixed |
| --- | ---: | ---: | ---: |
| `_layouts/aux-home.html` | 9 | 0 | 9 |
| `_layouts/aux-update.html` | 61 | 23 | 38 |
| `_layouts/aux-updates.html` | 14 | 12 | 2 |
| `_includes/patch-table-row.html` | 3 | 0 | 3 |
| `_includes/monitoring-status.html` | 6 | 3 | 3 |
| `_includes/patch-latest-signals.html` | 2 | 1 | 1 |
| `updates/methodology/index.md` | 7 | 4 | 3 |
| `_layouts/aux-patch-company.html` | 2 | 2 | 0 |
| `_layouts/aux-patch-product.html` | 2 | 2 | 0 |
| `_layouts/aux-patch-version.html` | 2 | 2 | 0 |

## Symptoms confirmed on the live site (auxsays.com, before the fix)

Each was verified by fetching the published page, not inferred from the template.

| where | live evidence | population |
| --- | --- | --- |
| `/updates/methodology/` Notes cell | 309 cells rendering `<span><small>…`, note demoted, primary slot empty | 309 / 1116 method rows have an empty `blocked_reason` |
| `/` recent articles | 2 × `<img class="featured-card-image" src="">`, 0 placeholder spans | all 3 posts carry no image key |
| `/updates/adobe/adobe-acrobat-pro/` Verdict column | 35 of 134 verdict cells rendered empty | 868 / 905 records have no `update_decision_label` |
| update detail — download link | `<a href="">Download page</a>` | 733 / 905 records store `update_download_url: ''` |
| update detail — attribution | `in these notes:</strong> .` (stray period, no value) | 902 / 905 records have no `official_app_attribution_label` |
| update detail — channel pill | `<span class="update-meta-pill__value"></span>` | all three `*_label` channel fields absent on ~every record |
| update detail — file size | empty pill **and** `<dt>File size</dt><dd></dd>` | 850 / 905 records store `patch_file_size: ''` |
| update detail — checksum | a whole `<details>` "Checksum" section with an empty body | 889 / 905 records store an empty `official_checksums_body` |
| update detail — evidence date | `Last evidence checked: ` with no value; `Not recorded` appeared **0** times sitewide | 781 / 905 records resolve no evidence timestamp |
| update detail — recommendation | `<p class="update-decision-recommendation"></p>` | 87 records reach it with no `update_decision_body` |
| citations | `<cite>obsproject/obs-studio. (). <` | 187 / 570 accepted report rows have an empty `source_date` |

Two further fixes are correctness repairs with no current output change, made because the guarded
value is a local **initialised to `''` as a sentinel** — i.e. it exists in order to be empty:

- `monitoring-status.html` `mon_latest_raw` / `m_checked` — the `Not recorded` fallback and the
  future-timestamp rejection were both unreachable.
- `patch-latest-signals.html` `staged_html` (a `capture`) — the "No tracked software yet" empty
  state could not fire on its own terms. It is also gated by `latest_count == 0`, which is why no
  live symptom was visible.

`aux-update.html`'s `issue_cluster_text == blank` sites are the same class: the accumulator starts
as `''`, so the first cluster took the *else* branch and produced a leading `", "` — which a
downstream `slice`/`replace` sanitiser happened to strip. Output was already correct by accident;
it is now correct by construction, and the sanitiser is retained.

## Left in place — inert, with evidence

These guard values that are **never empty** anywhere in the corpus, so their false branch is
unreachable for a data reason rather than a Liquid one. Rewriting them would have been an untested
diff across every public template for no behavioural change.

`scripts/tests/test_blank_guard_emptiness.py` prints the full list with live counts on every run
and **fails** the moment the data makes any of them matter. Summary:

| guarded value | population | empty |
| --- | --- | ---: |
| `page.update_detail_title`, `update_feed_title`, `update_source_url`, `official_patch_notes_source_url`, `update_source_name`, `update_published_at`, `update_version` | 905 update records | 0 |
| `summary_text` (`release_summary` → `official_summary` → `description`) | 905 update records | 0 |
| `item.update_feed_title`, `update_product`, `update_version`, `update_source_url` (feed cards) | 905 update records | 0 |
| `source.source_name`, `source.source_url`, `source_issue`, `source_workflow` | 570 accepted report rows | 0 |
| `issue_label` (`issue` → `issue_theme` → `theme`) | 277 issue rows | 0 |
| `source_type_key` | 570 accepted report rows | 0 |
| `product.source_url`, `product_name_clean`, `product_url_clean`, `cstate` | 47 products | 0 |
| `resolved_update_logo_path` | 47 products / 35 companies | 0 |
| `item.last_run`, `m.last_run` | 1116 method-health rows | 0 |
| `item.last_checked`, `item.polling_frequency`, `item.last_error_display` | 37 source-health rows | 0 |
| `item.update_published_at`, `item.target_channel` (version landing) | 22 build records | 0 |
| `include.published_at` | 905 update records | 0 |

Three sites are not attributable to a data field and are reported, not failed, by the census:

- `event.note` — `rendered_history_events` resolves from three front-matter keys, all absent on all
  905 records, so the loop never runs.
- `evidence_summary` (×2, `aux-updates.html`) — derived by `replace` chains from
  `update_consensus_summary`. Replaying those chains over all 124 records that have a summary
  produces an empty result **0** times.

## Gate that was pinning the bug

`scripts/qa_patch_records.py` asserted the literal string `{% if file_size_pill_value != blank %}`
under the rule name `file_size_pill_value_guard_missing` — i.e. the gate required the broken guard.
It now asserts the rule's stated intent (an emptiness test) and separately rejects the always-true
family, so the rule enforces what its message claims. `test_product_page_layout.py`'s verdict-chain
assertion pinned `item.update_consensus_summary contains ':'` verbatim and was likewise rewritten to
assert the fallback's *branch order* and reachability rather than one spelling.

## Files changed

- `auxsays/_layouts/aux-home.html`, `aux-update.html`, `aux-updates.html`
- `auxsays/_includes/patch-table-row.html`, `monitoring-status.html`, `patch-latest-signals.html`
- `auxsays/updates/methodology/index.md`
- `auxsays/scripts/qa_patch_records.py`
- `auxsays/scripts/tests/test_blank_guard_emptiness.py` (new)
- `auxsays/scripts/tests/test_product_page_layout.py`,
  `test_public_method_health_presentation.py` (assertions/comments corrected)

Ingestion, consensus scoring, evidence acceptance and patch identity are untouched.

## Verification

- `qa_patch_records.py`, `validate_ingestion_sources.py`, `validate_evidence_method_health.py`,
  `validate_logo_assets.py` — all pass; QA reports 0 errors and 0 warnings, identical to `main`.
- Every edited template parses under the real `liquid` gem (Jekyll itself cannot run here —
  `http_parser.rb` is missing — so the parse check is what stands in for a build).
- `test_blank_guard_emptiness.py` 44/44, `test_public_method_health_presentation.py` 72/72,
  `test_product_page_layout.py` 53/53, `test_monitoring_status.py` 37/37,
  `test_qa_patch_records.py` 30/30.
- Both new guard assertions were shown to be non-vacuous by reverting the fix and observing them
  fail.
