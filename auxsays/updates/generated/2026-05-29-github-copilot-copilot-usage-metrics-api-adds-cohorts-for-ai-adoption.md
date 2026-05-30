---
layout: aux-update
title: GitHub / Copilot Copilot usage metrics API adds cohorts for AI adoption official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/copilot-usage-metrics-api-adds-cohorts-for-ai-adoption/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-29-copilot-usage-metrics-api-adds-cohorts-for-ai-adoption
update_download_url: ''
update_version: Copilot usage metrics API adds cohorts for AI adoption
update_logo_text: GIT
update_published_at: '2026-05-29T21:03:00Z'
update_last_checked: '2026-05-30T04:29:11Z'
source_last_checked: '2026-05-30T08:41:48Z'
official_body_last_checked: '2026-05-30T08:41:48Z'
record_last_updated: '2026-05-30T04:29:11Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Copilot usage metrics API adds cohorts for AI adoption
update_detail_title: GitHub / Copilot Copilot usage metrics API adds cohorts for AI adoption
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Copilot usage metrics API adds cohorts for AI adoption has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Copilot usage metrics API adds cohorts for AI adoption.
release_summary: "To help you tell a deeper Copilot adoption story—not just who is active, but how they’re using Copilot—the\
  \ Copilot usage metrics API now classifies each engaged user into an AI adoption phase based on their Copilot product usage\
  \ over a rolling 28-day window. A new ai_adoption_phase field is available on user-level reports, and a new totals_by_ai_adoption_phase\
  \ array surfaces per-phase metrics on enterprise- and organization-level reports.\n\n\n What’s new\n Each engaged user is\
  \ assigned to one of four phases based on the Copilot surfaces they’ve used on at least two days in the last 28-day window:\n\
  \n\n\n Phase 0 — No cohort : User did not meet the engagement criteria for any phase.\n Phase 1 — Code first : User engaged\
  \ with code completion and/or IDE agent mode.\n Phase 2 — Agent first : User engaged with a single GitHub-based agent surface\
  \ (i.e., Copilot cloud agent, Copilot code review, or Copilot CLI).\n Phase 3 — Multi-agent : User engaged with two or more\
  \ GitHub-based agent surfaces, or with the new GitHub Copilot app.\n\n Each ai_adoption_phase value includes a version field\
  \ (starting at v1 ) so the classification logic can evolve as Copilot’s product surface grows, without breaking historical\
  \ context.\n\n\n On the enterprise- and organization-level reports, the new totals_by_ai_adoption_phase array groups engagement\
  \ and activity metrics by phase, including:\n\n\n\n Total engaged users (2-day-in-28 engagement window)\n User-initiated\
  \ interaction average\n Code generation and acceptance activity averages\n Lines of code added and deleted averages\n Pull\
  \ requests created, merged, and reviewed averages\n Median time-to-merge average\n\n Aggregated metrics report the average\
  \ per user within each phase rather than the sum.\n\n\n Why this matters\n\n Tell the maturity story: Move beyond simple\
  \ active-user counts and show which Copilot capabilities your developers are actually adopting.\n Track cohort progression:\
  \ Watch users graduate from code-first usage into agent-first and multi-agent workflows over time.\n Target enablement:\
  \ Focus training, documentation, and rollout programs on the phases where you see the biggest opportunity.\n\n Important\
  \ notes\n\n These metrics are available to enterprise administrators and organization owners who have access to Copilot\
  \ usage metrics through the REST API.\n You can use this release in combination with the teams filter ship for greater granularity.\n\
  \n Join the discussion within GitHub Community .\n\n\n\n The post Copilot usage metrics API adds cohorts for AI adoption\
  \ appeared first on The GitHub Blog ."
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
- at: '2026-05-29T21:03:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-30T04:29:12Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-29-copilot-usage-metrics-api-adds-cohorts-for-ai-adoption
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-30T04:29:11Z'
  url: https://github.blog/changelog/2026-05-29-copilot-usage-metrics-api-adds-cohorts-for-ai-adoption
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-30T08:41:48Z'
  url: https://github.blog/changelog/2026-05-29-copilot-usage-metrics-api-adds-cohorts-for-ai-adoption
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "To help you tell a deeper Copilot adoption story—not just who is active, but how they’re using\
  \ Copilot—the Copilot usage metrics API now classifies each engaged user into an AI adoption phase based on their Copilot\
  \ product usage over a rolling 28-day window. A new ai_adoption_phase field is available on user-level reports, and a new\
  \ totals_by_ai_adoption_phase array surfaces per-phase metrics on enterprise- and organization-level reports.\n\n\n What’s\
  \ new\n Each engaged user is assigned to one of four phases based on the Copilot surfaces they’ve used on at least two days\
  \ in the last 28-day window:\n\n\n\n Phase 0 — No cohort : User did not meet the engagement criteria for any phase.\n Phase\
  \ 1 — Code first : User engaged with code completion and/or IDE agent mode.\n Phase 2 — Agent first : User engaged with\
  \ a single GitHub-based agent surface (i.e., Copilot cloud agent, Copilot code review, or Copilot CLI).\n Phase 3 — Multi-agent\
  \ : User engaged with two or more GitHub-based agent surfaces, or with the new GitHub Copilot app.\n\n Each ai_adoption_phase\
  \ value includes a version field (starting at v1 ) so the classification logic can evolve as Copilot’s product surface grows,\
  \ without breaking historical context.\n\n\n On the enterprise- and organization-level reports, the new totals_by_ai_adoption_phase\
  \ array groups engagement and activity metrics by phase, including:\n\n\n\n Total engaged users (2-day-in-28 engagement\
  \ window)\n User-initiated interaction average\n Code generation and acceptance activity averages\n Lines of code added\
  \ and deleted averages\n Pull requests created, merged, and reviewed averages\n Median time-to-merge average\n\n Aggregated\
  \ metrics report the average per user within each phase rather than the sum.\n\n\n Why this matters\n\n Tell the maturity\
  \ story: Move beyond simple active-user counts and show which Copilot capabilities your developers are actually adopting.\n\
  \ Track cohort progression: Watch users graduate from code-first usage into agent-first and multi-agent workflows over time.\n\
  \ Target enablement: Focus training, documentation, and rollout programs on the phases where you see the biggest opportunity.\n\
  \n Important notes\n\n These metrics are available to enterprise administrators and organization owners who have access\
  \ to Copilot usage metrics through the REST API.\n You can use this release in combination with the teams filter ship for\
  \ greater granularity.\n\n Join the discussion within GitHub Community .\n\n\n\n The post Copilot usage metrics API adds\
  \ cohorts for AI adoption appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
