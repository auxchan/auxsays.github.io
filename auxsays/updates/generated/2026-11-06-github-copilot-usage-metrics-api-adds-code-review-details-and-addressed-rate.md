---
layout: aux-update
title: GitHub / Copilot Usage metrics API adds code review details and addressed rate official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Usage metrics API adds code review details and
  addressed rate.
permalink: /updates/github/github/usage-metrics-api-adds-code-review-details-and-addressed-rate/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-05-usage-metrics-api-adds-code-review-details-and-addressed-rate
update_download_url: ''
update_version: Usage metrics API adds code review details and addressed rate
update_logo_text: GIT
update_published_at: '2026-11-06T00:19:07Z'
update_last_checked: '2026-11-06T09:21:50Z'
source_last_checked: '2026-11-07T08:11:38Z'
official_body_last_checked: '2026-11-07T08:11:38Z'
record_last_updated: '2026-11-06T09:21:50Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Usage metrics API adds code review details and addressed rate
update_detail_title: GitHub / Copilot Usage metrics API adds code review details and addressed rate
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Usage metrics API adds code review details and addressed rate has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Usage metrics API adds code review details and addressed rate.
release_summary: "The enterprise and organization repository-level Copilot usage metrics reports now show what happens to\
  \ Copilot code review feedback. A new copilot_code_review object on each repos-1-day row reports how many Copilot-reviewed\
  \ pull requests merged without a later change request from a person and how many Copilot code review comments developers\
  \ acted on. With these you can track an addressed rate per repository.\n\n\n What’s new\n\n total_comments_evaluated : The\
  \ number of Copilot code review comments checked to see whether the developer acted on them.\n total_comments_addressed\
  \ : The number of evaluated comments the developer acted on, whether by applying the suggestion, asking Copilot to make\
  \ the fix, editing the code, or replying that the fix will come in a later pull request. Divide by total_comments_evaluated\
  \ for the addressed rate.\n review_comments_by_severity , review_comments_by_review_tier , review_comments_by_comment_type\
  \ , and review_comments_by_customization : Both counts broken down by severity (e.g., high , medium , low ), review tier\
  \ (e.g., lite , balanced , max ), comment type (e.g., bug , security , or custom for your repository’s own coding guidelines),\
  \ and customization (e.g., custom instructions, skills, MCP servers, or none).\n total_merged_no_human_change_request_after_review\
  \ : The number of merged pull requests that Copilot code review reviewed where no person requested changes after Copilot’s\
  \ first review.\n\n Why this matters\n The existing pull_requests fields show how often Copilot code review runs and how\
  \ often someone clicks to apply a suggestion, but developers act on most feedback in other ways. These fields show whether\
  \ developers act on Copilot code review feedback in each repository, which kinds of comments land, whether custom instructions,\
  \ skills, and MCP servers make a difference, and whether reviewers still request changes after Copilot reviews.\n\n\n Important\
  \ notes\n\n Scope: Present on every row of the enterprise and organization repos-1-day reports. Counts are 0 and arrays\
  \ are empty when a repository had no Copilot code review activity that day.\n Counted on merge: Comments are evaluated when\
  \ their pull request merges, so they count on the merge day, not the day Copilot posted them.\n Bot pull requests: Copilot\
  \ usually doesn’t evaluate comments on pull requests opened by bots, such as Copilot cloud agent. total_merged_no_human_change_request_after_review\
  \ still includes those pull requests.\n Different from suggestion counts: pull_requests.total_copilot_applied_suggestions\
  \ counts only ready-to-apply suggestions that someone applied. The new counts include every evaluated comment and count\
  \ them as addressed however the developer acted on them.\n Access: Enterprise owners, enterprise billing managers, organization\
  \ owners, and anyone with a custom organization or enterprise role that grants the View Copilot Metrics permission can access\
  \ these reports. The Copilot usage metrics policy must be enabled.\n\n Visit the Copilot usage metrics API documentation\
  \ to get started.\n\n\n\n The post Usage metrics API adds code review details and addressed rate appeared first on The GitHub\
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
- at: '2026-11-06T00:19:07Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-06T09:21:56Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-05-usage-metrics-api-adds-code-review-details-and-addressed-rate
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-06T09:21:50Z'
  url: https://github.blog/changelog/2026-11-05-usage-metrics-api-adds-code-review-details-and-addressed-rate
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-06T21:56:47Z'
  url: https://github.blog/changelog/2026-11-05-usage-metrics-api-adds-code-review-details-and-addressed-rate
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-07T08:11:38Z'
  url: https://github.blog/changelog/2026-11-05-usage-metrics-api-adds-code-review-details-and-addressed-rate
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The enterprise and organization repository-level Copilot usage metrics reports now show what happens\
  \ to Copilot code review feedback. A new copilot_code_review object on each repos-1-day row reports how many Copilot-reviewed\
  \ pull requests merged without a later change request from a person and how many Copilot code review comments developers\
  \ acted on. With these you can track an addressed rate per repository.\n\n\n What’s new\n\n total_comments_evaluated : The\
  \ number of Copilot code review comments checked to see whether the developer acted on them.\n total_comments_addressed\
  \ : The number of evaluated comments the developer acted on, whether by applying the suggestion, asking Copilot to make\
  \ the fix, editing the code, or replying that the fix will come in a later pull request. Divide by total_comments_evaluated\
  \ for the addressed rate.\n review_comments_by_severity , review_comments_by_review_tier , review_comments_by_comment_type\
  \ , and review_comments_by_customization : Both counts broken down by severity (e.g., high , medium , low ), review tier\
  \ (e.g., lite , balanced , max ), comment type (e.g., bug , security , or custom for your repository’s own coding guidelines),\
  \ and customization (e.g., custom instructions, skills, MCP servers, or none).\n total_merged_no_human_change_request_after_review\
  \ : The number of merged pull requests that Copilot code review reviewed where no person requested changes after Copilot’s\
  \ first review.\n\n Why this matters\n The existing pull_requests fields show how often Copilot code review runs and how\
  \ often someone clicks to apply a suggestion, but developers act on most feedback in other ways. These fields show whether\
  \ developers act on Copilot code review feedback in each repository, which kinds of comments land, whether custom instructions,\
  \ skills, and MCP servers make a difference, and whether reviewers still request changes after Copilot reviews.\n\n\n Important\
  \ notes\n\n Scope: Present on every row of the enterprise and organization repos-1-day reports. Counts are 0 and arrays\
  \ are empty when a repository had no Copilot code review activity that day.\n Counted on merge: Comments are evaluated when\
  \ their pull request merges, so they count on the merge day, not the day Copilot posted them.\n Bot pull requests: Copilot\
  \ usually doesn’t evaluate comments on pull requests opened by bots, such as Copilot cloud agent. total_merged_no_human_change_request_after_review\
  \ still includes those pull requests.\n Different from suggestion counts: pull_requests.total_copilot_applied_suggestions\
  \ counts only ready-to-apply suggestions that someone applied. The new counts include every evaluated comment and count\
  \ them as addressed however the developer acted on them.\n Access: Enterprise owners, enterprise billing managers, organization\
  \ owners, and anyone with a custom organization or enterprise role that grants the View Copilot Metrics permission can access\
  \ these reports. The Copilot usage metrics policy must be enabled.\n\n Visit the Copilot usage metrics API documentation\
  \ to get started.\n\n\n\n The post Usage metrics API adds code review details and addressed rate appeared first on The GitHub\
  \ Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
