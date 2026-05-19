---
layout: aux-update
title: GitHub / Copilot Removal of code_scanning_upload field from rate_limit API endpoint official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/removal-of-code-scanning-upload-field-from-rate-limit-api-endpoint/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-19-removal-of-code_scanning_upload-field-from-rate_limit-api-endpoint
update_download_url: ''
update_version: Removal of code_scanning_upload field from rate_limit API endpoint
update_logo_text: GIT
update_published_at: '2026-05-19T10:40:26Z'
update_last_checked: '2026-05-19T15:53:12Z'
source_last_checked: '2026-05-19T15:53:12Z'
official_body_last_checked: '2026-05-19T15:53:12Z'
record_last_updated: '2026-05-19T15:53:12Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Removal of code_scanning_upload field from rate_limit API endpoint
update_detail_title: GitHub / Copilot Removal of code_scanning_upload field from rate_limit API endpoint
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Removal of code_scanning_upload field from rate_limit API endpoint has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Removal of code_scanning_upload field from rate_limit API endpoint.
release_summary: "As of May 19, 2026 , we have removed the code_scanning_upload field from the rate limit REST API endpoint\
  \ response.\n\n\n What changed\n The code_scanning_upload field no longer appears in the resources object of the rate_limit\
  \ API response. This field was removed because it displayed a separate rate limit category that was actually joined with\
  \ the core limit pool, causing confusion about actual rate limit status.\n\n\n Rate limits for code scanning uploads continue\
  \ to be governed by the standard core rate limit.\n\n\n If your integrations are affected\n If you have scripts or tools\
  \ that parse the /rate_limit endpoint and reference code_scanning_upload , update them to remove that reference. No alternative\
  \ field replacement is needed—use the core rate limit values instead.\n\n\n For more information, see Rate limits for the\
  \ REST API .\n\n\n\n The post Removal of code_scanning_upload field from rate_limit API endpoint appeared first on The GitHub\
  \ Blog ."
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
- at: '2026-05-19T10:40:26Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-19T15:53:13Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-19-removal-of-code_scanning_upload-field-from-rate_limit-api-endpoint
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-19T15:53:12Z'
  url: https://github.blog/changelog/2026-05-19-removal-of-code_scanning_upload-field-from-rate_limit-api-endpoint
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "As of May 19, 2026 , we have removed the code_scanning_upload field from the rate limit REST API\
  \ endpoint response.\n\n\n What changed\n The code_scanning_upload field no longer appears in the resources object of the\
  \ rate_limit API response. This field was removed because it displayed a separate rate limit category that was actually\
  \ joined with the core limit pool, causing confusion about actual rate limit status.\n\n\n Rate limits for code scanning\
  \ uploads continue to be governed by the standard core rate limit.\n\n\n If your integrations are affected\n If you have\
  \ scripts or tools that parse the /rate_limit endpoint and reference code_scanning_upload , update them to remove that reference.\
  \ No alternative field replacement is needed—use the core rate limit values instead.\n\n\n For more information, see Rate\
  \ limits for the REST API .\n\n\n\n The post Removal of code_scanning_upload field from rate_limit API endpoint appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
