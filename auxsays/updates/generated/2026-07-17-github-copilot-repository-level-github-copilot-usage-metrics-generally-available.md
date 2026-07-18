---
layout: aux-update
title: GitHub / Copilot Repository-level GitHub Copilot usage metrics generally available official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/repository-level-github-copilot-usage-metrics-generally-available/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-17-repository-level-github-copilot-usage-metrics-generally-available
update_download_url: ''
update_version: Repository-level GitHub Copilot usage metrics generally available
update_logo_text: GIT
update_published_at: '2026-07-17T22:05:18Z'
update_last_checked: '2026-07-18T03:41:31Z'
source_last_checked: '2026-07-18T14:02:27Z'
official_body_last_checked: '2026-07-18T14:02:27Z'
record_last_updated: '2026-07-18T03:41:31Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Repository-level GitHub Copilot usage metrics generally available
update_detail_title: GitHub / Copilot Repository-level GitHub Copilot usage metrics generally available
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Repository-level GitHub Copilot usage metrics generally available has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Repository-level GitHub Copilot usage metrics generally available.
release_summary: "The Copilot usage metrics REST API now reports repository-level activity. Two new endpoints return a daily,\
  \ per-repository breakdown of pull request activity for Copilot coding agent and Copilot code review. They do this for both\
  \ enterprise and organization reports.\n\n\n What’s new\n Two new endpoints return a per-repository report for a single\
  \ day:\n\n\n\n GET /enterprises/{enterprise}/copilot/metrics/reports/repos-1-day?day=YYYY-MM-DD\n GET /orgs/{org}/copilot/metrics/reports/repos-1-day?day=YYYY-MM-DD\n\
  \n Each response returns the following activity:\n\n\n\n Pull requests created and merged by Copilot coding agent.\n Pull\
  \ requests reviewed by Copilot code review, with suggestion counts broken down by comment type.\n\n Why this matters\n Until\
  \ now, Copilot usage metrics stopped at the organization and user level. Repository-level reporting lets you see exactly\
  \ where Copilot coding agent and Copilot code review are driving pull request activity across your codebase. This is the\
  \ foundation for repository insights and AI-readiness reporting, so you can target enablement at the repositories that stand\
  \ to benefit most.\n\n\n Important notes\n Enterprise owners and billing managers, organization owners, and anyone with\
  \ a custom organization or enterprise role that grants the View Copilot Metrics permission can access these reports. The\
  \ Copilot usage metrics policy must be enabled to support this functionality.\n\n\n Visit the Copilot usage metrics API\
  \ documentation to get started.\n\n\n\n The post Repository-level GitHub Copilot usage metrics generally available appeared\
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
- at: '2026-07-17T22:05:18Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-18T03:41:34Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-17-repository-level-github-copilot-usage-metrics-generally-available
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-18T03:41:31Z'
  url: https://github.blog/changelog/2026-07-17-repository-level-github-copilot-usage-metrics-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-18T08:28:54Z'
  url: https://github.blog/changelog/2026-07-17-repository-level-github-copilot-usage-metrics-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-18T14:02:27Z'
  url: https://github.blog/changelog/2026-07-17-repository-level-github-copilot-usage-metrics-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The Copilot usage metrics REST API now reports repository-level activity. Two new endpoints return\
  \ a daily, per-repository breakdown of pull request activity for Copilot coding agent and Copilot code review. They do this\
  \ for both enterprise and organization reports.\n\n\n What’s new\n Two new endpoints return a per-repository report for\
  \ a single day:\n\n\n\n GET /enterprises/{enterprise}/copilot/metrics/reports/repos-1-day?day=YYYY-MM-DD\n GET /orgs/{org}/copilot/metrics/reports/repos-1-day?day=YYYY-MM-DD\n\
  \n Each response returns the following activity:\n\n\n\n Pull requests created and merged by Copilot coding agent.\n Pull\
  \ requests reviewed by Copilot code review, with suggestion counts broken down by comment type.\n\n Why this matters\n Until\
  \ now, Copilot usage metrics stopped at the organization and user level. Repository-level reporting lets you see exactly\
  \ where Copilot coding agent and Copilot code review are driving pull request activity across your codebase. This is the\
  \ foundation for repository insights and AI-readiness reporting, so you can target enablement at the repositories that stand\
  \ to benefit most.\n\n\n Important notes\n Enterprise owners and billing managers, organization owners, and anyone with\
  \ a custom organization or enterprise role that grants the View Copilot Metrics permission can access these reports. The\
  \ Copilot usage metrics policy must be enabled to support this functionality.\n\n\n Visit the Copilot usage metrics API\
  \ documentation to get started.\n\n\n\n The post Repository-level GitHub Copilot usage metrics generally available appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
