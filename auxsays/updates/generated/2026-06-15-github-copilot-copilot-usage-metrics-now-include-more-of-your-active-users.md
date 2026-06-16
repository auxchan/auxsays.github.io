---
layout: aux-update
title: GitHub / Copilot Copilot usage metrics now include more of your active users official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/copilot-usage-metrics-now-include-more-of-your-active-users/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-15-copilot-usage-metrics-now-include-more-of-your-active-users
update_download_url: ''
update_version: Copilot usage metrics now include more of your active users
update_logo_text: GIT
update_published_at: '2026-06-15T21:30:13Z'
update_last_checked: '2026-06-16T11:37:09Z'
source_last_checked: '2026-06-16T11:37:09Z'
official_body_last_checked: '2026-06-16T11:37:09Z'
record_last_updated: '2026-06-16T11:37:09Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Copilot usage metrics now include more of your active users
update_detail_title: GitHub / Copilot Copilot usage metrics now include more of your active users
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Copilot usage metrics now include more of your active users has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Copilot usage metrics now include more of your active users.
release_summary: "Copilot usage metrics reports now draw on server-side telemetry in addition to client signals, so more of\
  \ your active Copilot users show up in reports. Enterprise usage reports returned by the Copilot usage metrics API now surface\
  \ active users that client-side telemetry alone would have missed, giving you a more complete and consistent picture of\
  \ who is using Copilot.\n\n\n What’s new\n Copilot usage reports have historically been built from client-side telemetry\
  \ emitted by IDEs and other clients. That telemetry is the richest source we have, but it does not always reach us. Network\
  \ conditions, proxy configurations, client settings, and other factors outside of your control or ours can prevent a client\
  \ from reporting activity. When that happened, an active, billed user could be absent from your reports.\n\n\n This update\
  \ incorporates additional server-side telemetry to identify active users. Any active user we can confirm from the server\
  \ side who was not already captured from client telemetry is now included in your enterprise single-day and 28-day reports,\
  \ increasing your daily active user (DAU) coverage.\n\n\n These newly surfaced users are fully identified and counted toward\
  \ your active user totals. What server-side telemetry does not yet carry is the rich, per-interaction detail that client\
  \ telemetry provides (i.e., the specific IDE, feature, model, and lines-of-code activity). So for these users, the high-level\
  \ counts go up while the detailed breakdowns stay empty until richer telemetry is available for them.\n\n\n What you’ll\
  \ see in a typical report\n Suppose an enterprise single-day report previously showed 1,000 daily active users, all sourced\
  \ from client telemetry. With this change, that same report might now show 1,050. The extra 50 are users we confirmed were\
  \ active from server-side telemetry but never received client telemetry for.\n\n\n In practice, your active user and DAU\
  \ counts immediately become more complete, while the dimensional breakdowns (such as totals_by_ide and totals_by_feature\
  \ ) won’t yet reflect these users, so a larger share of activity may appear unattributed. Top-level totals and breakdowns\
  \ for your existing users are unchanged.\n\n\n This is the first step in a broader effort to bring server-side signals into\
  \ Copilot metrics. Users surfaced from server-side telemetry are now included, and upcoming releases will progressively\
  \ attribute richer per-feature and per-surface detail to them, filling in those empty breakdowns over time.\n\n\n Why this\
  \ matters\n\n More consistency across your data: Usage reports line up more closely with what you see in the activity log\
  \ and billing, reducing the gaps that drive support escalations about “missing” users.\n Resilient by design: Combining\
  \ server-side and client-side signals means a single client-side hiccup no longer erases a user from your reports.\n\n Visit\
  \ our API documentation to learn more.\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post Copilot usage\
  \ metrics now include more of your active users appeared first on The GitHub Blog ."
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
- at: '2026-06-15T21:30:13Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-16T11:37:11Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-15-copilot-usage-metrics-now-include-more-of-your-active-users
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-16T11:37:09Z'
  url: https://github.blog/changelog/2026-06-15-copilot-usage-metrics-now-include-more-of-your-active-users
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Copilot usage metrics reports now draw on server-side telemetry in addition to client signals,\
  \ so more of your active Copilot users show up in reports. Enterprise usage reports returned by the Copilot usage metrics\
  \ API now surface active users that client-side telemetry alone would have missed, giving you a more complete and consistent\
  \ picture of who is using Copilot.\n\n\n What’s new\n Copilot usage reports have historically been built from client-side\
  \ telemetry emitted by IDEs and other clients. That telemetry is the richest source we have, but it does not always reach\
  \ us. Network conditions, proxy configurations, client settings, and other factors outside of your control or ours can prevent\
  \ a client from reporting activity. When that happened, an active, billed user could be absent from your reports.\n\n\n\
  \ This update incorporates additional server-side telemetry to identify active users. Any active user we can confirm from\
  \ the server side who was not already captured from client telemetry is now included in your enterprise single-day and 28-day\
  \ reports, increasing your daily active user (DAU) coverage.\n\n\n These newly surfaced users are fully identified and counted\
  \ toward your active user totals. What server-side telemetry does not yet carry is the rich, per-interaction detail that\
  \ client telemetry provides (i.e., the specific IDE, feature, model, and lines-of-code activity). So for these users, the\
  \ high-level counts go up while the detailed breakdowns stay empty until richer telemetry is available for them.\n\n\n What\
  \ you’ll see in a typical report\n Suppose an enterprise single-day report previously showed 1,000 daily active users, all\
  \ sourced from client telemetry. With this change, that same report might now show 1,050. The extra 50 are users we confirmed\
  \ were active from server-side telemetry but never received client telemetry for.\n\n\n In practice, your active user and\
  \ DAU counts immediately become more complete, while the dimensional breakdowns (such as totals_by_ide and totals_by_feature\
  \ ) won’t yet reflect these users, so a larger share of activity may appear unattributed. Top-level totals and breakdowns\
  \ for your existing users are unchanged.\n\n\n This is the first step in a broader effort to bring server-side signals into\
  \ Copilot metrics. Users surfaced from server-side telemetry are now included, and upcoming releases will progressively\
  \ attribute richer per-feature and per-surface detail to them, filling in those empty breakdowns over time.\n\n\n Why this\
  \ matters\n\n More consistency across your data: Usage reports line up more closely with what you see in the activity log\
  \ and billing, reducing the gaps that drive support escalations about “missing” users.\n Resilient by design: Combining\
  \ server-side and client-side signals means a single client-side hiccup no longer erases a user from your reports.\n\n Visit\
  \ our API documentation to learn more.\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post Copilot usage\
  \ metrics now include more of your active users appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
