---
layout: aux-update
title: GitHub / Copilot Stateless GitHub App installation tokens rolled out official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Stateless GitHub App installation tokens rolled
  out.
permalink: /updates/github/github/stateless-github-app-installation-tokens-rolled-out/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out
update_download_url: ''
update_version: Stateless GitHub App installation tokens rolled out
update_logo_text: GIT
update_published_at: '2026-10-02T22:18:23Z'
update_last_checked: '2026-10-03T00:52:11Z'
source_last_checked: '2026-10-06T16:02:05Z'
official_body_last_checked: '2026-10-06T16:02:05Z'
record_last_updated: '2026-10-03T00:52:11Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Stateless GitHub App installation tokens rolled out
update_detail_title: GitHub / Copilot Stateless GitHub App installation tokens rolled out
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Stateless GitHub App installation tokens rolled out has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Stateless GitHub App installation tokens rolled out.
release_summary: "The staged rollout of the stateless GitHub App installation token format, which began on April 27, 2026,\
  \ is complete. By default, all newly minted GitHub App installation tokens will be in the stateless ghs_APPID_JWT format,\
  \ which makes token issuance and validation faster and improves the reliability of the GitHub API.\n\n\n What’s changed\n\
  \ Installation tokens still start with the ghs_ prefix, but they’re now about 520 characters long instead of 40.\n\n\n Token\
  \ permissions, repository scoping, the one-hour expiration, and the installation access token REST API endpoint are unchanged.\
  \ Tokens minted before the change continue to work until they expire.\n\n\n What to expect going forward\n The temporary\
  \ X-GitHub-Stateless-S2S-Token request header, which we introduced so you could validate the new format on demand, will\
  \ be deprecated on November 30, 2026. After that date, GitHub will no longer respect the header, and all eligible apps will\
  \ always receive stateless tokens. To learn more about the temporary header, see our original changelog for its release\
  \ .\n\n\n Once you’ve validated your apps and workflows with both token formats, remove the header from your production\
  \ code before November 30, 2026.\n\n\n Check your integrations\n If you haven’t already, confirm that every system that\
  \ handles installation tokens treats them as opaque strings. Look for:\n\n\n\n Validation that requires tokens to be exactly\
  \ 40 characters or patterns written for the legacy format.\n Database columns, secret stores, or environment variables with\
  \ a fixed or small maximum length.\n Proxies, gateways, or middleware that truncate or reject long Authorization headers.\n\
  \ Logging and secret redaction rules that only match the legacy token pattern.\n\n To learn more, see Generating an installation\
  \ access token for a GitHub App .\n\n\n\n The post Stateless GitHub App installation tokens rolled out appeared first on\
  \ The GitHub Blog ."
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
- at: '2026-10-02T22:18:23Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-03T00:52:17Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-05T08:23:40Z'
  url: https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-05T17:20:47Z'
  url: https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-06T02:50:14Z'
  url: https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-06T09:06:56Z'
  url: https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-06T16:02:05Z'
  url: https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The staged rollout of the stateless GitHub App installation token format, which began on April\
  \ 27, 2026, is complete. By default, all newly minted GitHub App installation tokens will be in the stateless ghs_APPID_JWT\
  \ format, which makes token issuance and validation faster and improves the reliability of the GitHub API.\n\n\n What’s\
  \ changed\n Installation tokens still start with the ghs_ prefix, but they’re now about 520 characters long instead of 40.\n\
  \n\n Token permissions, repository scoping, the one-hour expiration, and the installation access token REST API endpoint\
  \ are unchanged. Tokens minted before the change continue to work until they expire.\n\n\n What to expect going forward\n\
  \ The temporary X-GitHub-Stateless-S2S-Token request header, which we introduced so you could validate the new format on\
  \ demand, will be deprecated on November 30, 2026. After that date, GitHub will no longer respect the header, and all eligible\
  \ apps will always receive stateless tokens. To learn more about the temporary header, see our original changelog for its\
  \ release .\n\n\n Once you’ve validated your apps and workflows with both token formats, remove the header from your production\
  \ code before November 30, 2026.\n\n\n Check your integrations\n If you haven’t already, confirm that every system that\
  \ handles installation tokens treats them as opaque strings. Look for:\n\n\n\n Validation that requires tokens to be exactly\
  \ 40 characters or patterns written for the legacy format.\n Database columns, secret stores, or environment variables with\
  \ a fixed or small maximum length.\n Proxies, gateways, or middleware that truncate or reject long Authorization headers.\n\
  \ Logging and secret redaction rules that only match the legacy token pattern.\n\n To learn more, see Generating an installation\
  \ access token for a GitHub App .\n\n\n\n The post Stateless GitHub App installation tokens rolled out appeared first on\
  \ The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
