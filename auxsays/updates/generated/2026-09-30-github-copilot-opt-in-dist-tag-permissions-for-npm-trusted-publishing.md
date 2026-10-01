---
layout: aux-update
title: GitHub / Copilot Opt-in dist-tag permissions for npm trusted publishing official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Opt-in dist-tag permissions for npm trusted
  publishing.
permalink: /updates/github/github/opt-in-dist-tag-permissions-for-npm-trusted-publishing/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-30-opt-in-dist-tag-permissions-for-npm-trusted-publishing
update_download_url: ''
update_version: Opt-in dist-tag permissions for npm trusted publishing
update_logo_text: GIT
update_published_at: '2026-09-30T21:03:09Z'
update_last_checked: '2026-10-01T00:30:35Z'
source_last_checked: '2026-10-01T06:58:18Z'
official_body_last_checked: '2026-10-01T06:58:18Z'
record_last_updated: '2026-10-01T00:30:35Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Opt-in dist-tag permissions for npm trusted publishing
update_detail_title: GitHub / Copilot Opt-in dist-tag permissions for npm trusted publishing
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Opt-in dist-tag permissions for npm trusted publishing has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Opt-in dist-tag permissions for npm trusted publishing.
release_summary: "Trusted publishing configurations for npm can now be granted permission to manage dist-tags (e.g., promoting\
  \ a version to latest , updating next and beta pointers) using short-lived OIDC credentials instead of a long-lived access\
  \ token.\n\n\n Previously, trusted publishing covered publishing and staging, but not dist-tag operations. That meant maintainers\
  \ who had otherwise fully moved to token-free, OIDC-based workflows still had to keep a granular access token around solely\
  \ to manage tags after a release or a rollback.\n\n\n\n Each trusted publishing configuration now has an opt-in Allow npm\
  \ dist-tag permission. It defaults to off for both new and existing configurations, so no configuration automatically gains\
  \ new capability.\n The permission is independent of direct publishing, so a staging-only configuration can also be granted\
  \ dist-tag management.\n A dist-tag operation is authorized if the incoming OIDC token matches any one configuration with\
  \ the permission enabled.\n Existing token-based dist-tag management continues to work unchanged.\n\n To use it, open your\
  \ package’s trusted publishing settings and enable Allow npm dist-tag on the configurations that should be able to manage\
  \ tags.\n\n\n Learn more about trusted publishers for npm.\n\n\n Join the discussion within our roadmap discussions .\n\n\
  \n\n The post Opt-in dist-tag permissions for npm trusted publishing appeared first on The GitHub Blog ."
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
- at: '2026-09-30T21:03:09Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-01T00:30:43Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-30-opt-in-dist-tag-permissions-for-npm-trusted-publishing
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-01T00:30:35Z'
  url: https://github.blog/changelog/2026-09-30-opt-in-dist-tag-permissions-for-npm-trusted-publishing
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-01T06:58:18Z'
  url: https://github.blog/changelog/2026-09-30-opt-in-dist-tag-permissions-for-npm-trusted-publishing
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Trusted publishing configurations for npm can now be granted permission to manage dist-tags (e.g.,\
  \ promoting a version to latest , updating next and beta pointers) using short-lived OIDC credentials instead of a long-lived\
  \ access token.\n\n\n Previously, trusted publishing covered publishing and staging, but not dist-tag operations. That meant\
  \ maintainers who had otherwise fully moved to token-free, OIDC-based workflows still had to keep a granular access token\
  \ around solely to manage tags after a release or a rollback.\n\n\n\n Each trusted publishing configuration now has an opt-in\
  \ Allow npm dist-tag permission. It defaults to off for both new and existing configurations, so no configuration automatically\
  \ gains new capability.\n The permission is independent of direct publishing, so a staging-only configuration can also be\
  \ granted dist-tag management.\n A dist-tag operation is authorized if the incoming OIDC token matches any one configuration\
  \ with the permission enabled.\n Existing token-based dist-tag management continues to work unchanged.\n\n To use it, open\
  \ your package’s trusted publishing settings and enable Allow npm dist-tag on the configurations that should be able to\
  \ manage tags.\n\n\n Learn more about trusted publishers for npm.\n\n\n Join the discussion within our roadmap discussions\
  \ .\n\n\n\n The post Opt-in dist-tag permissions for npm trusted publishing appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
