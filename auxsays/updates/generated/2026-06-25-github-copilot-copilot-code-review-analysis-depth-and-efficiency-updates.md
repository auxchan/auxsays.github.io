---
layout: aux-update
title: 'GitHub / Copilot Copilot code review: Analysis depth and efficiency updates official update breakdown'
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/copilot-code-review-analysis-depth-and-efficiency-updates/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-25-copilot-code-review-analysis-depth-and-efficiency-updates
update_download_url: ''
update_version: 'Copilot code review: Analysis depth and efficiency updates'
update_logo_text: GIT
update_published_at: '2026-06-25T21:41:18Z'
update_last_checked: '2026-06-26T04:43:03Z'
source_last_checked: '2026-06-26T14:49:11Z'
official_body_last_checked: '2026-06-26T14:49:11Z'
record_last_updated: '2026-06-26T04:43:03Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot Copilot code review: Analysis depth and efficiency updates'
update_detail_title: 'GitHub / Copilot Copilot code review: Analysis depth and efficiency updates'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot Copilot code review: Analysis depth and efficiency updates has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot Copilot code review: Analysis depth and efficiency updates.'
release_summary: "Copilot code review now uses the built-in file exploration tools available in the Copilot CLI and SDK, significantly\
  \ improving review cost efficiency with no change to your existing workflow. If you’re in the Medium analysis depth public\
  \ preview, you’ll also see some new updates centered around configurability and visibility of review depth.\n\n\n Configure\
  \ Medium analysis depth for your organization\n If you’re opted into the Medium review effort level public preview , you\
  \ now get two updates:\n\n\n\n Medium attribution in the pull request overview comment : Copilot code review now labels\
  \ medium analysis depth runs in its pull request overview comment so you can quickly confirm which level generated the review.\n\
  \n\n Organization-level default level setting : Organizations can now set a default review level for unconfigured repositories.\
  \ Repositories under an organization that has configured the default review level will continue to be able to override that\
  \ default setting if desired.\n\n\n\n\n\n\n\n Behind the scenes: CLI-based file tools in Copilot code review\n Copilot code\
  \ review now uses the grep , rg , glob and view tools from the Copilot CLI and SDK for exploring the source code in its\
  \ review path. These replace custom tools previously used for file exploration. This capability, along with careful tuning\
  \ of instructions behind the scenes, has resulted in a more focused review where Copilot finds the code that matters, quickly.\n\
  \n\n These efficiency gains have reduced Copilot code review costs by about 20% while maintaining the same standard of review\
  \ quality. This has been observed in both offline and online evaluation.\n\n\n\n The post Copilot code review: Analysis\
  \ depth and efficiency updates appeared first on The GitHub Blog ."
consensus_report: Confirmed patch-specific consensus collection is deferred. This page currently reflects official-source
  ingestion only.
evidence_state: official_only
evidence_state_label: Official source only
intelligence_stage: official_live
official_source_captured: true
confirmed_patch_specific_report_count: 0
evidence_last_checked: ''
known_issues_present: null
consensus_collection_status: deferred_official_only
consensus_match_policy: confirmed_patch_specific_reports_v1
consensus_match_policy_label: Confirmed patch-specific reports only
consensus_report_count_label: confirmed patch-specific reports
consensus_report_weighting: equal_per_confirmed_report
consensus_low_context_policy: excluded
complaint_themes: []
status_events:
- at: '2026-06-25T21:41:18Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-26T04:43:05Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-25-copilot-code-review-analysis-depth-and-efficiency-updates
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-26T04:43:03Z'
  url: https://github.blog/changelog/2026-06-25-copilot-code-review-analysis-depth-and-efficiency-updates
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-06-26T09:53:36Z'
  url: https://github.blog/changelog/2026-06-25-copilot-code-review-analysis-depth-and-efficiency-updates
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-06-26T14:49:11Z'
  url: https://github.blog/changelog/2026-06-25-copilot-code-review-analysis-depth-and-efficiency-updates
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Copilot code review now uses the built-in file exploration tools available in the Copilot CLI\
  \ and SDK, significantly improving review cost efficiency with no change to your existing workflow. If you’re in the Medium\
  \ analysis depth public preview, you’ll also see some new updates centered around configurability and visibility of review\
  \ depth.\n\n\n Configure Medium analysis depth for your organization\n If you’re opted into the Medium review effort level\
  \ public preview , you now get two updates:\n\n\n\n Medium attribution in the pull request overview comment : Copilot code\
  \ review now labels medium analysis depth runs in its pull request overview comment so you can quickly confirm which level\
  \ generated the review.\n\n\n Organization-level default level setting : Organizations can now set a default review level\
  \ for unconfigured repositories. Repositories under an organization that has configured the default review level will continue\
  \ to be able to override that default setting if desired.\n\n\n\n\n\n\n\n Behind the scenes: CLI-based file tools in Copilot\
  \ code review\n Copilot code review now uses the grep , rg , glob and view tools from the Copilot CLI and SDK for exploring\
  \ the source code in its review path. These replace custom tools previously used for file exploration. This capability,\
  \ along with careful tuning of instructions behind the scenes, has resulted in a more focused review where Copilot finds\
  \ the code that matters, quickly.\n\n\n These efficiency gains have reduced Copilot code review costs by about 20% while\
  \ maintaining the same standard of review quality. This has been observed in both offline and online evaluation.\n\n\n\n\
  \ The post Copilot code review: Analysis depth and efficiency updates appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
