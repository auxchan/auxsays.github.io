---
layout: aux-update
title: GitHub / Copilot Usage metrics API adds pull request review stages official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Usage metrics API adds pull request review stages.
permalink: /updates/github/github/usage-metrics-api-adds-pull-request-review-stages/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-25-usage-metrics-api-adds-pull-request-review-stages
update_download_url: ''
update_version: Usage metrics API adds pull request review stages
update_logo_text: GIT
update_published_at: '2026-09-25T21:09:40Z'
update_last_checked: '2026-09-25T23:47:05Z'
source_last_checked: '2026-09-25T23:47:05Z'
official_body_last_checked: '2026-09-25T23:47:05Z'
record_last_updated: '2026-09-25T23:47:05Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Usage metrics API adds pull request review stages
update_detail_title: GitHub / Copilot Usage metrics API adds pull request review stages
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Usage metrics API adds pull request review stages has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Usage metrics API adds pull request review stages.
release_summary: "The enterprise and organization repository-level Copilot usage metrics reports now break down how long pull\
  \ requests spend in each stage of review. A new pull_request_review_times array on each repos-1-day row reports a median\
  \ and a 90th percentile for the time from ready for review to first review, first review to final review, and final review\
  \ to merge.\n\n\n What’s new\n Each entry in pull_request_review_times includes:\n\n\n\n authored_by and reviewed_by : Who\
  \ opened and who reviewed the pull requests in this entry. Both are human in this release.\n total_merged : The number of\
  \ qualifying pull requests merged in the repository that day.\n median_minutes_ready_to_first_review and p90_minutes_ready_to_first_review\
  \ : Time from the pull request becoming ready for review to its first review.\n median_minutes_first_to_final_review and\
  \ p90_minutes_first_to_final_review : Time between the first and final review.\n median_minutes_final_review_to_merge and\
  \ p90_minutes_final_review_to_merge : Time from the final review to merge.\n\n Durations are in minutes and attributed to\
  \ the day the pull request merged. The existing pull_requests fields are unchanged.\n\n\n Why this matters\n Teams can already\
  \ see when pull requests take a long time to merge, but not where the time goes. Splitting the wait into three stages shows\
  \ whether a pull request is waiting for someone to look at it, waiting on back-and-forth between reviewers, or sitting approved\
  \ and unmerged. Each of those points to a different fix, and the 90th percentile beside the median shows when a handful\
  \ of slow pull requests is driving the delay.\n\n\n Important notes\n\n Availability: Present in the enterprise and organization\
  \ repos-1-day reports.\n What is counted: Pull requests that a person opened and at least one other person reviewed. Only\
  \ human reviews are timed. Reviews from Copilot code review, other bots, and the author are ignored, so a pull request reviewed\
  \ by both a person and Copilot code review is still included. As a result, pull_request_review_times[].total_merged is usually\
  \ lower than pull_requests.total_merged , which also counts pull requests merged without any reviews.\n No backfill: Data\
  \ builds forward from the release date, so early days will be thin. Pull requests that became ready for review before September\
  \ 21, 2026 are left out of this section but still count toward pull_requests.total_merged .\n A quiet day is an empty array,\
  \ not a zero: The array is [] on days a repository merged no qualifying pull requests. The first-to-final review stage is\
  \ 0 when pull requests receive a single review.\n Access: Enterprise owners and billing managers, organization owners, and\
  \ anyone with a custom organization or enterprise role that grants the View Copilot Metrics permission can access these\
  \ reports. The Copilot usage metrics policy must be enabled.\n\n Visit the Copilot usage metrics API documentation to get\
  \ started.\n\n\n\n The post Usage metrics API adds pull request review stages appeared first on The GitHub Blog ."
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
- at: '2026-09-25T21:09:40Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-25T23:47:15Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-25-usage-metrics-api-adds-pull-request-review-stages
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-25T23:47:05Z'
  url: https://github.blog/changelog/2026-09-25-usage-metrics-api-adds-pull-request-review-stages
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The enterprise and organization repository-level Copilot usage metrics reports now break down\
  \ how long pull requests spend in each stage of review. A new pull_request_review_times array on each repos-1-day row reports\
  \ a median and a 90th percentile for the time from ready for review to first review, first review to final review, and final\
  \ review to merge.\n\n\n What’s new\n Each entry in pull_request_review_times includes:\n\n\n\n authored_by and reviewed_by\
  \ : Who opened and who reviewed the pull requests in this entry. Both are human in this release.\n total_merged : The number\
  \ of qualifying pull requests merged in the repository that day.\n median_minutes_ready_to_first_review and p90_minutes_ready_to_first_review\
  \ : Time from the pull request becoming ready for review to its first review.\n median_minutes_first_to_final_review and\
  \ p90_minutes_first_to_final_review : Time between the first and final review.\n median_minutes_final_review_to_merge and\
  \ p90_minutes_final_review_to_merge : Time from the final review to merge.\n\n Durations are in minutes and attributed to\
  \ the day the pull request merged. The existing pull_requests fields are unchanged.\n\n\n Why this matters\n Teams can already\
  \ see when pull requests take a long time to merge, but not where the time goes. Splitting the wait into three stages shows\
  \ whether a pull request is waiting for someone to look at it, waiting on back-and-forth between reviewers, or sitting approved\
  \ and unmerged. Each of those points to a different fix, and the 90th percentile beside the median shows when a handful\
  \ of slow pull requests is driving the delay.\n\n\n Important notes\n\n Availability: Present in the enterprise and organization\
  \ repos-1-day reports.\n What is counted: Pull requests that a person opened and at least one other person reviewed. Only\
  \ human reviews are timed. Reviews from Copilot code review, other bots, and the author are ignored, so a pull request reviewed\
  \ by both a person and Copilot code review is still included. As a result, pull_request_review_times[].total_merged is usually\
  \ lower than pull_requests.total_merged , which also counts pull requests merged without any reviews.\n No backfill: Data\
  \ builds forward from the release date, so early days will be thin. Pull requests that became ready for review before September\
  \ 21, 2026 are left out of this section but still count toward pull_requests.total_merged .\n A quiet day is an empty array,\
  \ not a zero: The array is [] on days a repository merged no qualifying pull requests. The first-to-final review stage is\
  \ 0 when pull requests receive a single review.\n Access: Enterprise owners and billing managers, organization owners, and\
  \ anyone with a custom organization or enterprise role that grants the View Copilot Metrics permission can access these\
  \ reports. The Copilot usage metrics policy must be enabled.\n\n Visit the Copilot usage metrics API documentation to get\
  \ started.\n\n\n\n The post Usage metrics API adds pull request review stages appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
