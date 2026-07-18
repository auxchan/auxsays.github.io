---
layout: aux-update
title: GitHub / Copilot GitHub Copilot app now available in the usage metrics API official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/github-copilot-app-now-available-in-the-usage-metrics-api/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-17-github-copilot-app-now-available-in-the-usage-metrics-api
update_download_url: ''
update_version: GitHub Copilot app now available in the usage metrics API
update_logo_text: GIT
update_published_at: '2026-07-17T22:05:11Z'
update_last_checked: '2026-07-18T03:41:31Z'
source_last_checked: '2026-07-18T19:49:21Z'
official_body_last_checked: '2026-07-18T19:49:21Z'
record_last_updated: '2026-07-18T03:41:31Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub Copilot app now available in the usage metrics API
update_detail_title: GitHub / Copilot GitHub Copilot app now available in the usage metrics API
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub Copilot app now available in the usage metrics API has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub Copilot app now available in the usage metrics API.
release_summary: "The Copilot usage metrics API now reports the GitHub Copilot app usage in the enterprise and organization\
  \ 1-day and 28-day reports. This gives enterprise and organization admins visibility into the app’s activity alongside the\
  \ IDE, chat, code review, and coding agent metrics they already retrieve.\n\n\n What’s new\n The enterprise and organization\
  \ reports now include two new fields:\n\n\n\n daily_active_copilot_app_users : The number of distinct users active in the\
  \ Copilot app on a given day.\n totals_by_copilot_app : A dedicated GitHub Copilot app section reporting session_count ,\
  \ request_count , prompt_count , and a token_usage breakdown (i.e., output_tokens_sum , prompt_tokens_sum , and avg_tokens_per_request\
  \ ).\n\n Why this matters\n The GitHub Copilot app activity was not previously represented in usage reporting. With these\
  \ fields, enterprise and organization admins can see how broadly the app is being adopted (e.g., distinct active users,\
  \ session and request volume, and token consumption) in the same API they already use for the rest of their Copilot usage\
  \ metrics.\n\n\n Important notes\n\n These fields appear in the enterprise and organization 1-day and 28-day reports.\n\
  \ The GitHub Copilot app usage is reported in its own totals_by_copilot_app section and is kept separate from the generic\
  \ feature, model, and language totals, as well as from lines-of-code metrics.\n Enterprises or organizations with no GitHub\
  \ Copilot app activity report null for both daily_active_copilot_app_users and totals_by_copilot_app , so existing integrations\
  \ are unaffected.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post GitHub Copilot\
  \ app now available in the usage metrics API appeared first on The GitHub Blog ."
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
- at: '2026-07-17T22:05:11Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-18T03:41:36Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-17-github-copilot-app-now-available-in-the-usage-metrics-api
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-18T03:41:31Z'
  url: https://github.blog/changelog/2026-07-17-github-copilot-app-now-available-in-the-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-18T08:28:54Z'
  url: https://github.blog/changelog/2026-07-17-github-copilot-app-now-available-in-the-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-18T14:02:27Z'
  url: https://github.blog/changelog/2026-07-17-github-copilot-app-now-available-in-the-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-18T19:49:21Z'
  url: https://github.blog/changelog/2026-07-17-github-copilot-app-now-available-in-the-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The Copilot usage metrics API now reports the GitHub Copilot app usage in the enterprise and organization\
  \ 1-day and 28-day reports. This gives enterprise and organization admins visibility into the app’s activity alongside the\
  \ IDE, chat, code review, and coding agent metrics they already retrieve.\n\n\n What’s new\n The enterprise and organization\
  \ reports now include two new fields:\n\n\n\n daily_active_copilot_app_users : The number of distinct users active in the\
  \ Copilot app on a given day.\n totals_by_copilot_app : A dedicated GitHub Copilot app section reporting session_count ,\
  \ request_count , prompt_count , and a token_usage breakdown (i.e., output_tokens_sum , prompt_tokens_sum , and avg_tokens_per_request\
  \ ).\n\n Why this matters\n The GitHub Copilot app activity was not previously represented in usage reporting. With these\
  \ fields, enterprise and organization admins can see how broadly the app is being adopted (e.g., distinct active users,\
  \ session and request volume, and token consumption) in the same API they already use for the rest of their Copilot usage\
  \ metrics.\n\n\n Important notes\n\n These fields appear in the enterprise and organization 1-day and 28-day reports.\n\
  \ The GitHub Copilot app usage is reported in its own totals_by_copilot_app section and is kept separate from the generic\
  \ feature, model, and language totals, as well as from lines-of-code metrics.\n Enterprises or organizations with no GitHub\
  \ Copilot app activity report null for both daily_active_copilot_app_users and totals_by_copilot_app , so existing integrations\
  \ are unaffected.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post GitHub Copilot\
  \ app now available in the usage metrics API appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
