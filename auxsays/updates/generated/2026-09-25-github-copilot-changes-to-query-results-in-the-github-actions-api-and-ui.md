---
layout: aux-update
title: GitHub / Copilot Changes to query results in the GitHub Actions API and UI official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Changes to query results in the GitHub Actions
  API and UI.
permalink: /updates/github/github/changes-to-query-results-in-the-github-actions-api-and-ui/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-25-changes-to-query-results-in-the-github-actions-api-and-ui
update_download_url: ''
update_version: Changes to query results in the GitHub Actions API and UI
update_logo_text: GIT
update_published_at: '2026-09-25T18:17:06Z'
update_last_checked: '2026-09-25T19:25:21Z'
source_last_checked: '2026-09-25T19:25:21Z'
official_body_last_checked: '2026-09-25T19:25:21Z'
record_last_updated: '2026-09-25T19:25:21Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Changes to query results in the GitHub Actions API and UI
update_detail_title: GitHub / Copilot Changes to query results in the GitHub Actions API and UI
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Changes to query results in the GitHub Actions API and UI has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Changes to query results in the GitHub Actions API and UI.
release_summary: "Queries for workflow runs in the GitHub Actions API and UI now return a less precise but more accurate count\
  \ of records when you search by workflow, event, status, branch, or actor. We will continue to return paginated results\
  \ of up to 1,000 items. However, if the number of found records exceeds 2,500, we will report “2,500+” instead of attempting\
  \ to return the exact number of records. This is because queries that retrieve more than 2,500 records frequently timeout\
  \ and return the number of records found before the timeout rather than the true count. By implementing this limit, our\
  \ counts will be more accurate and we will improve performance for customers.\n\n\n If your integrations or scripts rely\
  \ on retrieving more than 2,500 matching workflow runs from a single query, narrow your filters (e.g., by adding a date\
  \ range) to retrieve the specific runs you need. This change is rolling out now on github.com and GitHub Enterprise Cloud.\n\
  \n\n\n The post Changes to query results in the GitHub Actions API and UI appeared first on The GitHub Blog ."
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
- at: '2026-09-25T18:17:06Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-25T19:25:32Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-25-changes-to-query-results-in-the-github-actions-api-and-ui
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-25T19:25:21Z'
  url: https://github.blog/changelog/2026-09-25-changes-to-query-results-in-the-github-actions-api-and-ui
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Queries for workflow runs in the GitHub Actions API and UI now return a less precise but more\
  \ accurate count of records when you search by workflow, event, status, branch, or actor. We will continue to return paginated\
  \ results of up to 1,000 items. However, if the number of found records exceeds 2,500, we will report “2,500+” instead of\
  \ attempting to return the exact number of records. This is because queries that retrieve more than 2,500 records frequently\
  \ timeout and return the number of records found before the timeout rather than the true count. By implementing this limit,\
  \ our counts will be more accurate and we will improve performance for customers.\n\n\n If your integrations or scripts\
  \ rely on retrieving more than 2,500 matching workflow runs from a single query, narrow your filters (e.g., by adding a\
  \ date range) to retrieve the specific runs you need. This change is rolling out now on github.com and GitHub Enterprise\
  \ Cloud.\n\n\n\n The post Changes to query results in the GitHub Actions API and UI appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
