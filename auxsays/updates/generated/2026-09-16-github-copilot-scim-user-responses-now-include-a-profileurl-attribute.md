---
layout: aux-update
title: GitHub / Copilot SCIM user responses now include a profileUrl attribute official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for SCIM user responses now include a profileUrl
  attribute.
permalink: /updates/github/github/scim-user-responses-now-include-a-profileurl-attribute/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-16-scim-user-responses-now-include-a-profileurl-attribute
update_download_url: ''
update_version: SCIM user responses now include a profileUrl attribute
update_logo_text: GIT
update_published_at: '2026-09-16T20:19:58Z'
update_last_checked: '2026-09-16T23:31:27Z'
source_last_checked: '2026-09-17T07:07:26Z'
official_body_last_checked: '2026-09-17T07:07:26Z'
record_last_updated: '2026-09-16T23:31:27Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot SCIM user responses now include a profileUrl attribute
update_detail_title: GitHub / Copilot SCIM user responses now include a profileUrl attribute
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot SCIM user responses now include a profileUrl attribute has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot SCIM user responses now include a profileUrl attribute.
release_summary: "SCIM user responses from GitHub now include the standard profileUrl attribute defined by RFC 7643, containing\
  \ the absolute URL of the GitHub account linked to the external identity.\n\n\n Previously, matching a SCIM record to the\
  \ corresponding GitHub account required extra lookups or inference. Identity providers and IT teams provisioning access\
  \ to GitHub through SCIM can now read profileUrl directly instead of working around the gap.\n\n\n\n profileUrl is returned\
  \ from the /Users endpoint and is consistently supported across both organization and enterprise SCIM responses.\n profileUrl\
  \ is omitted when an external identity isn’t yet linked to a GitHub user.\n The attribute is documented in the SCIM OpenAPI\
  \ schema and example responses.\n userName and other attributes continue to return the same values as before, so existing\
  \ SCIM, GraphQL, and identity management integrations aren’t affected.\n\n This is an additive change and no action is required\
  \ for existing integrations. If you want to use the new mapping, start reading profileUrl in your SCIM responses when it’s\
  \ present.\n\n\n Learn more in the REST API documentation for Enterprise SCIM and Org SCIM .\n\n\n\n The post SCIM user\
  \ responses now include a profileUrl attribute appeared first on The GitHub Blog ."
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
- at: '2026-09-16T20:19:58Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-16T23:31:46Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-16-scim-user-responses-now-include-a-profileurl-attribute
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-16T23:31:27Z'
  url: https://github.blog/changelog/2026-09-16-scim-user-responses-now-include-a-profileurl-attribute
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-17T01:52:34Z'
  url: https://github.blog/changelog/2026-09-16-scim-user-responses-now-include-a-profileurl-attribute
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-17T07:07:26Z'
  url: https://github.blog/changelog/2026-09-16-scim-user-responses-now-include-a-profileurl-attribute
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "SCIM user responses from GitHub now include the standard profileUrl attribute defined by RFC 7643,\
  \ containing the absolute URL of the GitHub account linked to the external identity.\n\n\n Previously, matching a SCIM record\
  \ to the corresponding GitHub account required extra lookups or inference. Identity providers and IT teams provisioning\
  \ access to GitHub through SCIM can now read profileUrl directly instead of working around the gap.\n\n\n\n profileUrl is\
  \ returned from the /Users endpoint and is consistently supported across both organization and enterprise SCIM responses.\n\
  \ profileUrl is omitted when an external identity isn’t yet linked to a GitHub user.\n The attribute is documented in the\
  \ SCIM OpenAPI schema and example responses.\n userName and other attributes continue to return the same values as before,\
  \ so existing SCIM, GraphQL, and identity management integrations aren’t affected.\n\n This is an additive change and no\
  \ action is required for existing integrations. If you want to use the new mapping, start reading profileUrl in your SCIM\
  \ responses when it’s present.\n\n\n Learn more in the REST API documentation for Enterprise SCIM and Org SCIM .\n\n\n\n\
  \ The post SCIM user responses now include a profileUrl attribute appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
