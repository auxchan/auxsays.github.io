---
layout: aux-update
title: GitHub / Copilot Copilot impact dashboard now shows feature engagement official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Copilot impact dashboard now shows feature engagement.
permalink: /updates/github/github/copilot-impact-dashboard-now-shows-feature-engagement/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-17-copilot-impact-dashboard-now-shows-feature-engagement
update_download_url: ''
update_version: Copilot impact dashboard now shows feature engagement
update_logo_text: GIT
update_published_at: '2026-09-17T21:47:27Z'
update_last_checked: '2026-09-17T23:40:30Z'
source_last_checked: '2026-09-18T13:29:34Z'
official_body_last_checked: '2026-09-18T13:29:34Z'
record_last_updated: '2026-09-17T23:40:30Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Copilot impact dashboard now shows feature engagement
update_detail_title: GitHub / Copilot Copilot impact dashboard now shows feature engagement
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Copilot impact dashboard now shows feature engagement has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Copilot impact dashboard now shows feature engagement.
release_summary: "The Copilot impact dashboard now shows how many active users regularly use key Copilot features. Enterprise\
  \ administrators can quickly see which experiences are widely adopted and which may need more enablement. Enterprise and\
  \ organization report APIs now include the same 28-day feature engagement breakdown, along with an AI adoption phase reporting\
  \ improvement that adds each phase’s full rolling 28-day population as of each report day.\n\n\n What’s new\n\n Copilot\
  \ impact dashboard: Shows how many active users engaged with each included feature on at least two days during the 28-day\
  \ period.\n copilot_feature_engagement : Adds the dashboard’s active-user total and feature engagement counts to enterprise\
  \ and organization 28-day aggregate reports.\n totals_by_feature : Breaks engagement down by code completion, agent edit,\
  \ passive Copilot code review, active Copilot code review, Copilot cloud agent, Copilot CLI, and Copilot app.\n users_in_phase_28d\
  \ : Reports the full rolling 28-day population classified into each AI adoption phase as of that day. The existing total_engaged_users\
  \ field continues to only report users in the phase who were active that day.\n\n Why this matters\n Enterprise leaders\
  \ can see which Copilot features are becoming part of developers’ regular workflows and focus training or configuration\
  \ changes where adoption is lower.\n\n\n Previously, AI adoption phase breakdowns only showed the number of users in each\
  \ phase who were active on a given day. They now also include the full rolling 28-day phase population as of that day.\n\
  \n\n Important notes\n\n Feature engagement is available in enterprise and organization 28-day aggregate reports and is\
  \ not added to user-level reports. A user can be counted under more than one feature.\n Active Copilot code review means\
  \ a user manually requested a Copilot review or applied a Copilot review suggestion. Passive Copilot code review means Copilot\
  \ was automatically assigned to review the user’s pull request without the user actively engaging with the review.\n users_in_phase_28d\
  \ and total_engaged_users are aggregate counts and do not identify individual users. users_in_phase_28d is omitted when\
  \ the phase population was not measured. A value of 0 means the phase was measured and had no users.\n The copilot_feature_engagement\
  \ object can be absent or null when the calculation is unavailable.\n The data is available to enterprise owners and billing\
  \ managers, organization owners, and anyone with a custom organization or enterprise role that grants the View Copilot Metrics\
  \ permission. The Copilot usage metrics policy must be enabled.\n\n Visit the Copilot usage metrics API documentation to\
  \ get started.\n\n\n\n The post Copilot impact dashboard now shows feature engagement appeared first on The GitHub Blog\
  \ ."
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
- at: '2026-09-17T21:47:27Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-17T23:40:40Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-17-copilot-impact-dashboard-now-shows-feature-engagement
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-17T23:40:30Z'
  url: https://github.blog/changelog/2026-09-17-copilot-impact-dashboard-now-shows-feature-engagement
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-18T06:57:05Z'
  url: https://github.blog/changelog/2026-09-17-copilot-impact-dashboard-now-shows-feature-engagement
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-18T13:29:34Z'
  url: https://github.blog/changelog/2026-09-17-copilot-impact-dashboard-now-shows-feature-engagement
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The Copilot impact dashboard now shows how many active users regularly use key Copilot features.\
  \ Enterprise administrators can quickly see which experiences are widely adopted and which may need more enablement. Enterprise\
  \ and organization report APIs now include the same 28-day feature engagement breakdown, along with an AI adoption phase\
  \ reporting improvement that adds each phase’s full rolling 28-day population as of each report day.\n\n\n What’s new\n\n\
  \ Copilot impact dashboard: Shows how many active users engaged with each included feature on at least two days during the\
  \ 28-day period.\n copilot_feature_engagement : Adds the dashboard’s active-user total and feature engagement counts to\
  \ enterprise and organization 28-day aggregate reports.\n totals_by_feature : Breaks engagement down by code completion,\
  \ agent edit, passive Copilot code review, active Copilot code review, Copilot cloud agent, Copilot CLI, and Copilot app.\n\
  \ users_in_phase_28d : Reports the full rolling 28-day population classified into each AI adoption phase as of that day.\
  \ The existing total_engaged_users field continues to only report users in the phase who were active that day.\n\n Why this\
  \ matters\n Enterprise leaders can see which Copilot features are becoming part of developers’ regular workflows and focus\
  \ training or configuration changes where adoption is lower.\n\n\n Previously, AI adoption phase breakdowns only showed\
  \ the number of users in each phase who were active on a given day. They now also include the full rolling 28-day phase\
  \ population as of that day.\n\n\n Important notes\n\n Feature engagement is available in enterprise and organization 28-day\
  \ aggregate reports and is not added to user-level reports. A user can be counted under more than one feature.\n Active\
  \ Copilot code review means a user manually requested a Copilot review or applied a Copilot review suggestion. Passive Copilot\
  \ code review means Copilot was automatically assigned to review the user’s pull request without the user actively engaging\
  \ with the review.\n users_in_phase_28d and total_engaged_users are aggregate counts and do not identify individual users.\
  \ users_in_phase_28d is omitted when the phase population was not measured. A value of 0 means the phase was measured and\
  \ had no users.\n The copilot_feature_engagement object can be absent or null when the calculation is unavailable.\n The\
  \ data is available to enterprise owners and billing managers, organization owners, and anyone with a custom organization\
  \ or enterprise role that grants the View Copilot Metrics permission. The Copilot usage metrics policy must be enabled.\n\
  \n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post Copilot impact dashboard now shows\
  \ feature engagement appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
