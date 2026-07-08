---
layout: aux-update
title: GitHub / Copilot Add review cycles and time to adoption phases in the usage API official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/add-review-cycles-and-time-to-adoption-phases-in-the-usage-api/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-07-add-review-cycles-and-time-to-adoption-phases-in-the-usage-api
update_download_url: ''
update_version: Add review cycles and time to adoption phases in the usage API
update_logo_text: GIT
update_published_at: '2026-07-08T04:53:01Z'
update_last_checked: '2026-07-08T08:46:56Z'
source_last_checked: '2026-07-08T08:46:56Z'
official_body_last_checked: '2026-07-08T08:46:56Z'
record_last_updated: '2026-07-08T08:46:56Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Add review cycles and time to adoption phases in the usage API
update_detail_title: GitHub / Copilot Add review cycles and time to adoption phases in the usage API
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Add review cycles and time to adoption phases in the usage API has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Add review cycles and time to adoption phases in the usage API.
release_summary: "The Copilot usage metrics API now reports two additional code-review velocity metrics for each AI adoption\
  \ phase, extending the adoption phase cohorts fields available in the enterprise and organization reports. Alongside the\
  \ existing per-phase merge time and merge counts, you can now compare how quickly pull requests are reviewed and how many\
  \ review cycles they take across your adoption cohorts.\n\n\n What’s new\n Each phase entry in the totals_by_ai_adoption_phase\
  \ breakdown now includes two new fields:\n\n\n\n avg_pull_requests_minutes_to_review : The median time, in minutes, from\
  \ when a pull request is created to its first review.\n avg_pull_requests_review_cycles : The median number of review submissions\
  \ a pull request receives before it merges.\n\n Both metrics are scoped to merged pull requests and attributed to each pull\
  \ request’s merge day, so every pull request is counted exactly once. Pull requests that are reviewed but never merged do\
  \ not contribute to either metric.\n\n\n Why this matters\n Review latency and review-cycle counts are leading indicators\
  \ of engineering throughput. By breaking them out by AI adoption phase, you can see whether teams with deeper Copilot adoption\
  \ get their pull requests reviewed faster and iterate through fewer review cycles. This helps quantify the downstream impact\
  \ of Copilot on your review process and helps you target enablement where it moves the needle most.\n\n\n Important notes\n\
  \n These metrics appear in both the enterprise and organization 1-day and 28-day reports.\n Because they are scoped to merged\
  \ pull requests, review latency and cycle counts reflect work that actually landed.\n Phase definitions and cohort assignment\
  \ are unchanged. For details, see the adoption phase cohorts announcement .\n\n Visit the Copilot usage metrics API documentation\
  \ to get started.\n\n\n\n The post Add review cycles and time to adoption phases in the usage API appeared first on The\
  \ GitHub Blog ."
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
- at: '2026-07-08T04:53:01Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-08T08:46:58Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-07-add-review-cycles-and-time-to-adoption-phases-in-the-usage-api
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-08T08:46:56Z'
  url: https://github.blog/changelog/2026-07-07-add-review-cycles-and-time-to-adoption-phases-in-the-usage-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The Copilot usage metrics API now reports two additional code-review velocity metrics for each\
  \ AI adoption phase, extending the adoption phase cohorts fields available in the enterprise and organization reports. Alongside\
  \ the existing per-phase merge time and merge counts, you can now compare how quickly pull requests are reviewed and how\
  \ many review cycles they take across your adoption cohorts.\n\n\n What’s new\n Each phase entry in the totals_by_ai_adoption_phase\
  \ breakdown now includes two new fields:\n\n\n\n avg_pull_requests_minutes_to_review : The median time, in minutes, from\
  \ when a pull request is created to its first review.\n avg_pull_requests_review_cycles : The median number of review submissions\
  \ a pull request receives before it merges.\n\n Both metrics are scoped to merged pull requests and attributed to each pull\
  \ request’s merge day, so every pull request is counted exactly once. Pull requests that are reviewed but never merged do\
  \ not contribute to either metric.\n\n\n Why this matters\n Review latency and review-cycle counts are leading indicators\
  \ of engineering throughput. By breaking them out by AI adoption phase, you can see whether teams with deeper Copilot adoption\
  \ get their pull requests reviewed faster and iterate through fewer review cycles. This helps quantify the downstream impact\
  \ of Copilot on your review process and helps you target enablement where it moves the needle most.\n\n\n Important notes\n\
  \n These metrics appear in both the enterprise and organization 1-day and 28-day reports.\n Because they are scoped to merged\
  \ pull requests, review latency and cycle counts reflect work that actually landed.\n Phase definitions and cohort assignment\
  \ are unchanged. For details, see the adoption phase cohorts announcement .\n\n Visit the Copilot usage metrics API documentation\
  \ to get started.\n\n\n\n The post Add review cycles and time to adoption phases in the usage API appeared first on The\
  \ GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
