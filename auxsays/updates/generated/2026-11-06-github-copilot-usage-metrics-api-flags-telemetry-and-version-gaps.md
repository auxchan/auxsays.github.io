---
layout: aux-update
title: GitHub / Copilot Usage metrics API flags telemetry and version gaps official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Usage metrics API flags telemetry and version
  gaps.
permalink: /updates/github/github/usage-metrics-api-flags-telemetry-and-version-gaps/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-05-usage-metrics-api-flags-telemetry-and-version-gaps
update_download_url: ''
update_version: Usage metrics API flags telemetry and version gaps
update_logo_text: GIT
update_published_at: '2026-11-06T00:08:31Z'
update_last_checked: '2026-11-06T09:21:50Z'
source_last_checked: '2026-11-06T21:56:47Z'
official_body_last_checked: '2026-11-06T21:56:47Z'
record_last_updated: '2026-11-06T09:21:50Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Usage metrics API flags telemetry and version gaps
update_detail_title: GitHub / Copilot Usage metrics API flags telemetry and version gaps
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Usage metrics API flags telemetry and version gaps has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Usage metrics API flags telemetry and version gaps.
release_summary: "The Copilot usage metrics API now shows which users are missing client telemetry or are running IDE or extension\
  \ versions below the usage metrics minimums. New per-user fields appear in enterprise and organization user reports, and\
  \ daily affected-user counts appear in enterprise and organization reports.\n\n\n What’s new\n\n client_telemetry_present\
  \ : Whether client telemetry was received for the user that day. false means Copilot saw the user’s activity, but no usage\
  \ events arrived from their editor.\n usage_metrics_requirements : Lists each of the user’s IDEs and Copilot extensions\
  \ as met , unmet , or unknown against the minimum supported versions .\n missing_client_telemetry_user_count : The number\
  \ of users that day with client_telemetry_present set to false .\n below_usage_metrics_minimum_user_count : The number of\
  \ users that day with at least one IDE or extension below the minimum version.\n\n Why this matters\n Users without client\
  \ telemetry still count as active, but their reports lack detail such as lines of code, feature breakdowns, and model breakdowns.\
  \ Common causes include outdated editors or extensions, disabled IDE telemetry, and proxies or firewalls that block events.\
  \ These fields show how many users are affected and who to follow up with. This way you can close gaps without opening a\
  \ support ticket.\n\n\n Important notes\n\n Scope: User fields appear in enterprise and organization user reports (1-day\
  \ and 28-day). Counts appear in enterprise and organization 1-day reports and in each day_totals entry of 28-day reports.\n\
  \ Access: These fields are available to enterprise owners, enterprise billing managers, organization owners, and anyone\
  \ with a custom organization or enterprise role that grants the View Copilot Metrics permission. The Copilot usage metrics\
  \ policy must be enabled.\n Daily counts: Each count covers a single day. A user can be counted in both missing_client_telemetry_user_count\
  \ and below_usage_metrics_minimum_user_count , so don’t add the two counts together. Don’t add counts across days to count\
  \ unique users.\n Independent signals: A user can meet every version minimum and still be missing telemetry (e.g., they’re\
  \ behind a proxy).\n Unavailable values: Null or omitted values mean the data is unavailable, not false or zero. Days before\
  \ this release have no values.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post Usage\
  \ metrics API flags telemetry and version gaps appeared first on The GitHub Blog ."
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
- at: '2026-11-06T00:08:31Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-06T09:22:02Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-05-usage-metrics-api-flags-telemetry-and-version-gaps
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-06T09:21:50Z'
  url: https://github.blog/changelog/2026-11-05-usage-metrics-api-flags-telemetry-and-version-gaps
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-06T21:56:47Z'
  url: https://github.blog/changelog/2026-11-05-usage-metrics-api-flags-telemetry-and-version-gaps
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The Copilot usage metrics API now shows which users are missing client telemetry or are running\
  \ IDE or extension versions below the usage metrics minimums. New per-user fields appear in enterprise and organization\
  \ user reports, and daily affected-user counts appear in enterprise and organization reports.\n\n\n What’s new\n\n client_telemetry_present\
  \ : Whether client telemetry was received for the user that day. false means Copilot saw the user’s activity, but no usage\
  \ events arrived from their editor.\n usage_metrics_requirements : Lists each of the user’s IDEs and Copilot extensions\
  \ as met , unmet , or unknown against the minimum supported versions .\n missing_client_telemetry_user_count : The number\
  \ of users that day with client_telemetry_present set to false .\n below_usage_metrics_minimum_user_count : The number of\
  \ users that day with at least one IDE or extension below the minimum version.\n\n Why this matters\n Users without client\
  \ telemetry still count as active, but their reports lack detail such as lines of code, feature breakdowns, and model breakdowns.\
  \ Common causes include outdated editors or extensions, disabled IDE telemetry, and proxies or firewalls that block events.\
  \ These fields show how many users are affected and who to follow up with. This way you can close gaps without opening a\
  \ support ticket.\n\n\n Important notes\n\n Scope: User fields appear in enterprise and organization user reports (1-day\
  \ and 28-day). Counts appear in enterprise and organization 1-day reports and in each day_totals entry of 28-day reports.\n\
  \ Access: These fields are available to enterprise owners, enterprise billing managers, organization owners, and anyone\
  \ with a custom organization or enterprise role that grants the View Copilot Metrics permission. The Copilot usage metrics\
  \ policy must be enabled.\n Daily counts: Each count covers a single day. A user can be counted in both missing_client_telemetry_user_count\
  \ and below_usage_metrics_minimum_user_count , so don’t add the two counts together. Don’t add counts across days to count\
  \ unique users.\n Independent signals: A user can meet every version minimum and still be missing telemetry (e.g., they’re\
  \ behind a proxy).\n Unavailable values: Null or omitted values mean the data is unavailable, not false or zero. Days before\
  \ this release have no values.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post Usage\
  \ metrics API flags telemetry and version gaps appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
