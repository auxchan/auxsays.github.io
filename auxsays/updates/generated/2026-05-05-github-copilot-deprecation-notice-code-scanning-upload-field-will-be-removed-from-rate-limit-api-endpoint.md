---
layout: aux-update
title: 'GitHub / Copilot Deprecation notice: code_scanning_upload field will be removed from rate_limit API endpoint official
  update breakdown'
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/deprecation-notice-code-scanning-upload-field-will-be-removed-from-rate-limit-api-endpoint/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-05-deprecation-notice-code_scanning_upload-field-will-be-removed-from-rate_limit-api-endpoint
update_download_url: ''
update_version: 'Deprecation notice: code_scanning_upload field will be removed from rate_limit API endpoint'
update_logo_text: GIT
update_published_at: '2026-05-05T13:14:30Z'
update_last_checked: '2026-05-05T17:09:54Z'
source_last_checked: '2026-05-05T17:09:54Z'
official_body_last_checked: '2026-05-05T17:09:54Z'
record_last_updated: '2026-05-05T17:09:54Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot Deprecation notice: code_scanning_upload field will be removed from rate_limit API endpoint'
update_detail_title: 'GitHub / Copilot Deprecation notice: code_scanning_upload field will be removed from rate_limit API
  endpoint'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot Deprecation notice: code_scanning_upload field will be removed from rate_limit API endpoint
  has an official AUXSAYS record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot Deprecation notice: code_scanning_upload field will be removed from rate_limit
  API endpoint.'
release_summary: "On May 19, 2026 , we’ll remove the code_scanning_upload field from the rate_limit REST API endpoint response.\n\
  \n\n Why did we make this change?\n The code_scanning_upload field in the rate_limit response has been a source of confusion.\
  \ While it appeared as a separate rate limit category, it shares the same limit pool as core . This led customers to incorrectly\
  \ interpret their rate limit status.\n\n\n What you need to do\n If your code or scripts parse the /rate_limit endpoint\
  \ and reference the code_scanning_upload field, update them before May 19, 2026 to avoid failures.\n\n\n Before:\n\n\n {\n\
  \ \"resources\": {\n \"core\": { \"limit\": 5000, \"used\": 1, \"remaining\": 4999, \"reset\": 1372700873 },\n \"code_scanning_upload\"\
  : { \"limit\": 5000, \"used\": 1, \"remaining\": 4999, \"reset\": 1372700873 }\n }\n}\n\n After May 19, 2026:\n\n\n {\n\
  \ \"resources\": {\n \"core\": { \"limit\": 5000, \"used\": 1, \"remaining\": 4999, \"reset\": 1372700873 }\n }\n}\n\n The\
  \ standard core rate limit continues to govern GitHub code scanning uploads. No replacement field is needed.\n\n\n For more\
  \ information about rate limits, see Rate limits for the REST API .\n\n\n\n The post Deprecation notice: code_scanning_upload\
  \ field will be removed from rate_limit API endpoint appeared first on The GitHub Blog ."
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
- at: '2026-05-05T13:14:30Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-05T17:09:54Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-05-deprecation-notice-code_scanning_upload-field-will-be-removed-from-rate_limit-api-endpoint
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-05T17:09:54Z'
  url: https://github.blog/changelog/2026-05-05-deprecation-notice-code_scanning_upload-field-will-be-removed-from-rate_limit-api-endpoint
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "On May 19, 2026 , we’ll remove the code_scanning_upload field from the rate_limit REST API endpoint\
  \ response.\n\n\n Why did we make this change?\n The code_scanning_upload field in the rate_limit response has been a source\
  \ of confusion. While it appeared as a separate rate limit category, it shares the same limit pool as core . This led customers\
  \ to incorrectly interpret their rate limit status.\n\n\n What you need to do\n If your code or scripts parse the /rate_limit\
  \ endpoint and reference the code_scanning_upload field, update them before May 19, 2026 to avoid failures.\n\n\n Before:\n\
  \n\n {\n \"resources\": {\n \"core\": { \"limit\": 5000, \"used\": 1, \"remaining\": 4999, \"reset\": 1372700873 },\n \"\
  code_scanning_upload\": { \"limit\": 5000, \"used\": 1, \"remaining\": 4999, \"reset\": 1372700873 }\n }\n}\n\n After May\
  \ 19, 2026:\n\n\n {\n \"resources\": {\n \"core\": { \"limit\": 5000, \"used\": 1, \"remaining\": 4999, \"reset\": 1372700873\
  \ }\n }\n}\n\n The standard core rate limit continues to govern GitHub code scanning uploads. No replacement field is needed.\n\
  \n\n For more information about rate limits, see Rate limits for the REST API .\n\n\n\n The post Deprecation notice: code_scanning_upload\
  \ field will be removed from rate_limit API endpoint appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
