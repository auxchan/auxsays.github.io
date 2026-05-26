---
layout: aux-update
title: GitHub / Copilot Filter secret scanning approval requests by sort order and bypass status official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/filter-secret-scanning-approval-requests-by-sort-order-and-bypass-status/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-26-filter-secret-scanning-approval-requests-by-sort-order-and-bypass-status
update_download_url: ''
update_version: Filter secret scanning approval requests by sort order and bypass status
update_logo_text: GIT
update_published_at: '2026-05-26T16:01:21Z'
update_last_checked: '2026-05-26T16:12:34Z'
source_last_checked: '2026-05-26T16:12:34Z'
official_body_last_checked: '2026-05-26T16:12:34Z'
record_last_updated: '2026-05-26T16:12:34Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Filter secret scanning approval requests by sort order and bypass status
update_detail_title: GitHub / Copilot Filter secret scanning approval requests by sort order and bypass status
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Filter secret scanning approval requests by sort order and bypass status has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Filter secret scanning approval requests by sort order and bypass status.
release_summary: "This week, we’re rolling out two improvements to our delegated workflows for secret scanning.\n\n\n What’s\
  \ changing\n\n Sort bypass and dismissal requests in the UI: You can now choose between ascending and descending order for\
  \ approval request lists in the UI.\n New is_bypassed REST API filter: You can now filter by an is_bypassed query parameter\
  \ when listing alerts, closing a gap with filtering that was already available in the UI.\n\n These changes make it easier\
  \ for organizations to manage requests at scale.\n\n\n Sort bypass and dismissal requests\n Previously, push protection\
  \ bypass requests and alert dismissal requests appeared in a fixed order (newest-first). For large organizations, lack of\
  \ control over sorting made it challenging to manage high volumes of requests. You can now order requests by Newest , Oldest\
  \ , Recently updated , and Least recently updated directly in the filter UI bar, allowing security analysts and developers\
  \ to focus on soonest-expiring requests.\n\n\n Sorting is available at the repository, organization, and enterprise levels\
  \ for both push protection bypass requests and alert dismissal requests. This improvement makes it substantially easier\
  \ to manage requests at scale from the UI list view.\n\n\n\n\n\n\n\n New is_bypassed REST API filter\n Previously, the bypassed:true,false\
  \ qualifier was supported from the UI list view for push protection bypass requests, without an equivalent filter option\
  \ in the REST API. This improvement makes it easier to programmatically filter alerts by push protection bypasses without\
  \ additional processing.\n\n\n The secret scanning alerts API now accepts an is_bypassed boolean query parameter on all\
  \ three list endpoints:\n\n\n\n GET /repos/{owner}/{repo}/secret-scanning/alerts\n GET /orgs/{org}/secret-scanning/alerts\n\
  \ GET /enterprises/{enterprise}/secret-scanning/alerts\n\n Pass is_bypassed=true to return only alerts where push protection\
  \ was bypassed, or is_bypassed=false to exclude them.\n\n\n Learn more\n Learn more about secret scanning and the secret\
  \ scanning REST API in our documentation. These improvements were shaped by your feedback. Let us know what you think in\
  \ the community discussion .\n\n\n\n The post Filter secret scanning approval requests by sort order and bypass status appeared\
  \ first on The GitHub Blog ."
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
- at: '2026-05-26T16:01:21Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-26T16:12:36Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-26-filter-secret-scanning-approval-requests-by-sort-order-and-bypass-status
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-26T16:12:34Z'
  url: https://github.blog/changelog/2026-05-26-filter-secret-scanning-approval-requests-by-sort-order-and-bypass-status
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "This week, we’re rolling out two improvements to our delegated workflows for secret scanning.\n\
  \n\n What’s changing\n\n Sort bypass and dismissal requests in the UI: You can now choose between ascending and descending\
  \ order for approval request lists in the UI.\n New is_bypassed REST API filter: You can now filter by an is_bypassed query\
  \ parameter when listing alerts, closing a gap with filtering that was already available in the UI.\n\n These changes make\
  \ it easier for organizations to manage requests at scale.\n\n\n Sort bypass and dismissal requests\n Previously, push protection\
  \ bypass requests and alert dismissal requests appeared in a fixed order (newest-first). For large organizations, lack of\
  \ control over sorting made it challenging to manage high volumes of requests. You can now order requests by Newest , Oldest\
  \ , Recently updated , and Least recently updated directly in the filter UI bar, allowing security analysts and developers\
  \ to focus on soonest-expiring requests.\n\n\n Sorting is available at the repository, organization, and enterprise levels\
  \ for both push protection bypass requests and alert dismissal requests. This improvement makes it substantially easier\
  \ to manage requests at scale from the UI list view.\n\n\n\n\n\n\n\n New is_bypassed REST API filter\n Previously, the bypassed:true,false\
  \ qualifier was supported from the UI list view for push protection bypass requests, without an equivalent filter option\
  \ in the REST API. This improvement makes it easier to programmatically filter alerts by push protection bypasses without\
  \ additional processing.\n\n\n The secret scanning alerts API now accepts an is_bypassed boolean query parameter on all\
  \ three list endpoints:\n\n\n\n GET /repos/{owner}/{repo}/secret-scanning/alerts\n GET /orgs/{org}/secret-scanning/alerts\n\
  \ GET /enterprises/{enterprise}/secret-scanning/alerts\n\n Pass is_bypassed=true to return only alerts where push protection\
  \ was bypassed, or is_bypassed=false to exclude them.\n\n\n Learn more\n Learn more about secret scanning and the secret\
  \ scanning REST API in our documentation. These improvements were shaped by your feedback. Let us know what you think in\
  \ the community discussion .\n\n\n\n The post Filter secret scanning approval requests by sort order and bypass status appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
