---
layout: aux-update
title: GitHub / Copilot Clearer names for secret scanning detector types official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/clearer-names-for-secret-scanning-detector-types/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-10-clearer-names-for-secret-scanning-detector-types
update_download_url: ''
update_version: Clearer names for secret scanning detector types
update_logo_text: GIT
update_published_at: '2026-07-10T20:06:10Z'
update_last_checked: '2026-07-11T08:16:22Z'
source_last_checked: '2026-07-11T08:16:22Z'
official_body_last_checked: '2026-07-11T08:16:22Z'
record_last_updated: '2026-07-11T08:16:22Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Clearer names for secret scanning detector types
update_detail_title: GitHub / Copilot Clearer names for secret scanning detector types
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Clearer names for secret scanning detector types has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Clearer names for secret scanning detector types.
release_summary: "To make secret scanning easier to understand, we’re updating the names we use for our detector types to\
  \ better reflect how each one finds secrets. This is a naming change only; detection behavior is exactly the same.\n\n\n\
  \n\n\n Before\n Now\n\n\n\n\n Non-provider patterns\n Generic patterns\n\n\n Copilot secret scanning\n AI-detected secrets\n\
  \n\n\n All existing product documentation links continue to work. We’ve added redirects and updated the terminology across\
  \ our documentation. There are no changes to webhook events, audit log events, or the REST API.\n\n\n There are two kinds\
  \ of secrets we detect:\n\n\n\n Provider secrets are issued by a specific service (e.g., an AWS key, a Stripe token).\n\
  \ Generic secrets aren’t tied to any provider (e.g., private keys, connection strings, passwords).\n\n There are two ways\
  \ we detect them:\n\n\n\n Patterns use deterministic detection (i.e., regular expressions combined with additional checks\
  \ like entropy analysis). Patterns reliably catch secrets with a recognizable structure and include both provider patterns\
  \ for provider secrets, as well as generic patterns like private keys and connection strings.\n AI-detected secrets use\
  \ AI to catch generic secrets that don’t follow a predictable format (e.g., passwords). The model reads the surrounding\
  \ code to find harder-to-detect unstructured secrets.\n\n Learn more\n Learn more about secret scanning and see the full\
  \ list of supported secrets in our documentation. Let us know what you think in the community discussion .\n\n\n\n The post\
  \ Clearer names for secret scanning detector types appeared first on The GitHub Blog ."
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
- at: '2026-07-10T20:06:10Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-11T08:16:26Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-10-clearer-names-for-secret-scanning-detector-types
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-11T08:16:22Z'
  url: https://github.blog/changelog/2026-07-10-clearer-names-for-secret-scanning-detector-types
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "To make secret scanning easier to understand, we’re updating the names we use for our detector\
  \ types to better reflect how each one finds secrets. This is a naming change only; detection behavior is exactly the same.\n\
  \n\n\n\n\n Before\n Now\n\n\n\n\n Non-provider patterns\n Generic patterns\n\n\n Copilot secret scanning\n AI-detected secrets\n\
  \n\n\n All existing product documentation links continue to work. We’ve added redirects and updated the terminology across\
  \ our documentation. There are no changes to webhook events, audit log events, or the REST API.\n\n\n There are two kinds\
  \ of secrets we detect:\n\n\n\n Provider secrets are issued by a specific service (e.g., an AWS key, a Stripe token).\n\
  \ Generic secrets aren’t tied to any provider (e.g., private keys, connection strings, passwords).\n\n There are two ways\
  \ we detect them:\n\n\n\n Patterns use deterministic detection (i.e., regular expressions combined with additional checks\
  \ like entropy analysis). Patterns reliably catch secrets with a recognizable structure and include both provider patterns\
  \ for provider secrets, as well as generic patterns like private keys and connection strings.\n AI-detected secrets use\
  \ AI to catch generic secrets that don’t follow a predictable format (e.g., passwords). The model reads the surrounding\
  \ code to find harder-to-detect unstructured secrets.\n\n Learn more\n Learn more about secret scanning and see the full\
  \ list of supported secrets in our documentation. Let us know what you think in the community discussion .\n\n\n\n The post\
  \ Clearer names for secret scanning detector types appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
