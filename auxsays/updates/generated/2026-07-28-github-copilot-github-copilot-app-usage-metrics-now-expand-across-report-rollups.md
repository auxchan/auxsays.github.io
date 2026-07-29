---
layout: aux-update
title: GitHub / Copilot GitHub Copilot app usage metrics now expand across report rollups official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/github-copilot-app-usage-metrics-now-expand-across-report-rollups/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-28-github-copilot-app-usage-metrics-now-expand-across-report-rollups
update_download_url: ''
update_version: GitHub Copilot app usage metrics now expand across report rollups
update_logo_text: GIT
update_published_at: '2026-07-28T23:35:01Z'
update_last_checked: '2026-07-29T05:08:20Z'
source_last_checked: '2026-07-29T09:13:23Z'
official_body_last_checked: '2026-07-29T09:13:23Z'
record_last_updated: '2026-07-29T05:08:20Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub Copilot app usage metrics now expand across report rollups
update_detail_title: GitHub / Copilot GitHub Copilot app usage metrics now expand across report rollups
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub Copilot app usage metrics now expand across report rollups has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub Copilot app usage metrics now expand across report rollups.
release_summary: "Copilot app usage is now reported across much more of the Copilot usage metrics API.\n\n\n Individual Copilot\
  \ app activity is now attributed to users in the enterprise-user and organization-user reports. In addition, Copilot app\
  \ coding activity is now broken out in the feature, model, and language rollups alongside every other Copilot surface.\n\
  \n\n This builds on the earlier release that brought the Copilot app into the usage metrics API with enterprise-level Copilot\
  \ app totals.\n\n\n What’s new\n\n used_copilot_app : Whether a user was active in the Copilot app on a given day.\n totals_by_copilot_app\
  \ : A per-user section reporting session_count , request_count , prompt_count , and a token_usage breakdown of output_tokens_sum\
  \ , prompt_tokens_sum , and avg_tokens_per_request .\n copilot_app feature value : Copilot app activity now appears in totals_by_feature\
  \ , totals_by_model_feature , totals_by_language_feature , and totals_by_language_model , so you can see which models and\
  \ languages Copilot app work happens in.\n Code activity and lines-of-code metrics : Top-level code generation, code acceptance,\
  \ lines added, and lines deleted totals now include Copilot app activity.\n daily_active_users : Now counts users who were\
  \ only active in the Copilot app.\n\n Why this matters\n Copilot app usage was previously only visible as a standalone enterprise\
  \ and organization-level total, so you could see that the Copilot app was being used but not who was using it or what it\
  \ produced. With Copilot app activity attributed to individual users and folded into the standard breakdowns, you can identify\
  \ your Copilot app adopters, and measure the code the Copilot app generates.\n\n\n You can also compare the Copilot app\
  \ against the IDE, chat, code review, and coding agent surfaces using the same fields you already consume.\n\n\n Important\
  \ notes\n\n used_copilot_app and the user-level totals_by_copilot_app section are available in the enterprise-user and organization-user\
  \ 1-day and 28-day reports. The copilot_app feature value and the code activity, lines-of-code, and daily_active_users changes\
  \ apply to the enterprise, organization, and user reports for both the 1-day and 28-day windows.\n These metrics are available\
  \ to enterprise owners and billing managers, organization owners, and anyone with a custom organization or enterprise role\
  \ that grants the View Copilot Metrics permission. The Copilot usage metrics policy must be enabled.\n The changes are backward\
  \ compatible. Users and entities with no Copilot app activity omit totals_by_copilot_app and produce no copilot_app breakdown\
  \ entries, and existing fields keep their current shape.\n\n Visit the Copilot usage metrics API documentation to get started.\n\
  \n\n\n The post GitHub Copilot app usage metrics now expand across report rollups appeared first on The GitHub Blog ."
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
- at: '2026-07-28T23:35:01Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-29T05:08:25Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-28-github-copilot-app-usage-metrics-now-expand-across-report-rollups
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-29T05:08:20Z'
  url: https://github.blog/changelog/2026-07-28-github-copilot-app-usage-metrics-now-expand-across-report-rollups
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-29T09:13:23Z'
  url: https://github.blog/changelog/2026-07-28-github-copilot-app-usage-metrics-now-expand-across-report-rollups
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Copilot app usage is now reported across much more of the Copilot usage metrics API.\n\n\n Individual\
  \ Copilot app activity is now attributed to users in the enterprise-user and organization-user reports. In addition, Copilot\
  \ app coding activity is now broken out in the feature, model, and language rollups alongside every other Copilot surface.\n\
  \n\n This builds on the earlier release that brought the Copilot app into the usage metrics API with enterprise-level Copilot\
  \ app totals.\n\n\n What’s new\n\n used_copilot_app : Whether a user was active in the Copilot app on a given day.\n totals_by_copilot_app\
  \ : A per-user section reporting session_count , request_count , prompt_count , and a token_usage breakdown of output_tokens_sum\
  \ , prompt_tokens_sum , and avg_tokens_per_request .\n copilot_app feature value : Copilot app activity now appears in totals_by_feature\
  \ , totals_by_model_feature , totals_by_language_feature , and totals_by_language_model , so you can see which models and\
  \ languages Copilot app work happens in.\n Code activity and lines-of-code metrics : Top-level code generation, code acceptance,\
  \ lines added, and lines deleted totals now include Copilot app activity.\n daily_active_users : Now counts users who were\
  \ only active in the Copilot app.\n\n Why this matters\n Copilot app usage was previously only visible as a standalone enterprise\
  \ and organization-level total, so you could see that the Copilot app was being used but not who was using it or what it\
  \ produced. With Copilot app activity attributed to individual users and folded into the standard breakdowns, you can identify\
  \ your Copilot app adopters, and measure the code the Copilot app generates.\n\n\n You can also compare the Copilot app\
  \ against the IDE, chat, code review, and coding agent surfaces using the same fields you already consume.\n\n\n Important\
  \ notes\n\n used_copilot_app and the user-level totals_by_copilot_app section are available in the enterprise-user and organization-user\
  \ 1-day and 28-day reports. The copilot_app feature value and the code activity, lines-of-code, and daily_active_users changes\
  \ apply to the enterprise, organization, and user reports for both the 1-day and 28-day windows.\n These metrics are available\
  \ to enterprise owners and billing managers, organization owners, and anyone with a custom organization or enterprise role\
  \ that grants the View Copilot Metrics permission. The Copilot usage metrics policy must be enabled.\n The changes are backward\
  \ compatible. Users and entities with no Copilot app activity omit totals_by_copilot_app and produce no copilot_app breakdown\
  \ entries, and existing fields keep their current shape.\n\n Visit the Copilot usage metrics API documentation to get started.\n\
  \n\n\n The post GitHub Copilot app usage metrics now expand across report rollups appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
