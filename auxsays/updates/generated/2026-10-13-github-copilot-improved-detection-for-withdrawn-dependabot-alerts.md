---
layout: aux-update
title: GitHub / Copilot Improved detection for withdrawn Dependabot alerts official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Improved detection for withdrawn Dependabot
  alerts.
permalink: /updates/github/github/improved-detection-for-withdrawn-dependabot-alerts/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-13-improved-detection-for-withdrawn-dependabot-alerts
update_download_url: ''
update_version: Improved detection for withdrawn Dependabot alerts
update_logo_text: GIT
update_published_at: '2026-10-13T14:03:57Z'
update_last_checked: '2026-10-13T16:38:43Z'
source_last_checked: '2026-10-13T16:38:43Z'
official_body_last_checked: '2026-10-13T16:38:43Z'
record_last_updated: '2026-10-13T16:38:43Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Improved detection for withdrawn Dependabot alerts
update_detail_title: GitHub / Copilot Improved detection for withdrawn Dependabot alerts
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Improved detection for withdrawn Dependabot alerts has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Improved detection for withdrawn Dependabot alerts.
release_summary: "You can now more easily detect withdrawn Dependabot alerts. Dependabot withdraws and removes an alert when\
  \ the advisory or vulnerability that produced it is no longer valid. Two changes help you detect these withdrawals:\n\n\n\
  \n Webhooks: The dependabot_alert webhook event now includes a withdrawn action. The payload contains identifiers captured\
  \ before the alert was removed, such as the alert number, GHSA and CVE IDs, package, and manifest path. If you already subscribe\
  \ to dependabot_alert events, you’ll automatically receive these deliveries.\n REST API: Requests to get or update a withdrawn\
  \ alert now return 410 Gone instead of 404 Not Found , so you can tell a withdrawn alert apart from one that never existed.\n\
  \n These changes are available for all repositories on github.com and will be included in GitHub Enterprise Server 3.24.\n\
  \n\n Learn more about the dependabot_alert webhook event and the REST API endpoints for Dependabot alerts .\n\n\n\n The\
  \ post Improved detection for withdrawn Dependabot alerts appeared first on The GitHub Blog ."
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
- at: '2026-10-13T14:03:57Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-13T16:38:54Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-13-improved-detection-for-withdrawn-dependabot-alerts
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-13T16:38:43Z'
  url: https://github.blog/changelog/2026-10-13-improved-detection-for-withdrawn-dependabot-alerts
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now more easily detect withdrawn Dependabot alerts. Dependabot withdraws and removes an\
  \ alert when the advisory or vulnerability that produced it is no longer valid. Two changes help you detect these withdrawals:\n\
  \n\n\n Webhooks: The dependabot_alert webhook event now includes a withdrawn action. The payload contains identifiers captured\
  \ before the alert was removed, such as the alert number, GHSA and CVE IDs, package, and manifest path. If you already subscribe\
  \ to dependabot_alert events, you’ll automatically receive these deliveries.\n REST API: Requests to get or update a withdrawn\
  \ alert now return 410 Gone instead of 404 Not Found , so you can tell a withdrawn alert apart from one that never existed.\n\
  \n These changes are available for all repositories on github.com and will be included in GitHub Enterprise Server 3.24.\n\
  \n\n Learn more about the dependabot_alert webhook event and the REST API endpoints for Dependabot alerts .\n\n\n\n The\
  \ post Improved detection for withdrawn Dependabot alerts appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
