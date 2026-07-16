---
layout: aux-update
title: GitHub / Copilot REST API endpoints for Visual Studio Subscription management official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/rest-api-endpoints-for-visual-studio-subscription-management/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-16-rest-api-endpoints-for-visual-studio-subscription-management
update_download_url: ''
update_version: REST API endpoints for Visual Studio Subscription management
update_logo_text: GIT
update_published_at: '2026-07-16T18:06:52Z'
update_last_checked: '2026-07-16T19:35:56Z'
source_last_checked: '2026-07-16T19:35:56Z'
official_body_last_checked: '2026-07-16T19:35:56Z'
record_last_updated: '2026-07-16T19:35:56Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot REST API endpoints for Visual Studio Subscription management
update_detail_title: GitHub / Copilot REST API endpoints for Visual Studio Subscription management
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot REST API endpoints for Visual Studio Subscription management has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot REST API endpoints for Visual Studio Subscription management.
release_summary: "GitHub Enterprise Cloud admins can now use the following REST API endpoints to programmatically manage Visual\
  \ Studio Subscription (VSS) assignments:\n\n\n\n GET /enterprises/{enterprise}/visual-studio-subscriptions : Returns all\
  \ VSS assignments for an enterprise, including whether each assignment has been matched to a GitHub user.\n PUT /enterprises/{enterprise}/visual-studio-subscriptions\
  \ : Maps a VSS UPN to a GitHub handle, enabling bulk programmatic matching.\n DELETE /enterprises/{enterprise}/visual-studio-subscriptions/{visual_studio_subscription_id}\
  \ : Removes a manual match between a Visual Studio subscription and a GitHub user, allowing admins to correct mistaken assignments\
  \ or programmatically rematch subscriptions.\n\n These endpoints are especially useful for organizations where VSS UPN formats\
  \ do not align with SCIM identities, a scenario that prevents automatic matching and previously required tedious manual\
  \ resolution in the UI. Admins can now supply a UPN-to-GitHub-handle crosswalk and script bulk-matching operations.\n\n\n\
  \n The post REST API endpoints for Visual Studio Subscription management appeared first on The GitHub Blog ."
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
- at: '2026-07-16T18:06:52Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-16T19:36:00Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-16-rest-api-endpoints-for-visual-studio-subscription-management
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-16T19:35:56Z'
  url: https://github.blog/changelog/2026-07-16-rest-api-endpoints-for-visual-studio-subscription-management
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub Enterprise Cloud admins can now use the following REST API endpoints to programmatically\
  \ manage Visual Studio Subscription (VSS) assignments:\n\n\n\n GET /enterprises/{enterprise}/visual-studio-subscriptions\
  \ : Returns all VSS assignments for an enterprise, including whether each assignment has been matched to a GitHub user.\n\
  \ PUT /enterprises/{enterprise}/visual-studio-subscriptions : Maps a VSS UPN to a GitHub handle, enabling bulk programmatic\
  \ matching.\n DELETE /enterprises/{enterprise}/visual-studio-subscriptions/{visual_studio_subscription_id} : Removes a manual\
  \ match between a Visual Studio subscription and a GitHub user, allowing admins to correct mistaken assignments or programmatically\
  \ rematch subscriptions.\n\n These endpoints are especially useful for organizations where VSS UPN formats do not align\
  \ with SCIM identities, a scenario that prevents automatic matching and previously required tedious manual resolution in\
  \ the UI. Admins can now supply a UPN-to-GitHub-handle crosswalk and script bulk-matching operations.\n\n\n\n The post REST\
  \ API endpoints for Visual Studio Subscription management appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
