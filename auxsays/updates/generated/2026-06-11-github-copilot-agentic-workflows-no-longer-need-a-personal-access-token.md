---
layout: aux-update
title: GitHub / Copilot Agentic workflows no longer need a personal access token official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/agentic-workflows-no-longer-need-a-personal-access-token/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-11-agentic-workflows-no-longer-need-a-personal-access-token
update_download_url: ''
update_version: Agentic workflows no longer need a personal access token
update_logo_text: GIT
update_published_at: '2026-06-11T15:55:49Z'
update_last_checked: '2026-06-11T16:31:23Z'
source_last_checked: '2026-06-11T16:31:23Z'
official_body_last_checked: '2026-06-11T16:31:23Z'
record_last_updated: '2026-06-11T16:31:23Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Agentic workflows no longer need a personal access token
update_detail_title: GitHub / Copilot Agentic workflows no longer need a personal access token
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Agentic workflows no longer need a personal access token has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Agentic workflows no longer need a personal access token.
release_summary: "You can now use GitHub Agentic Workflows with GitHub Actions’s built-in GITHUB_TOKEN .\n\n\n This means\
  \ that you no longer need to create and store a personal access token (PAT), eliminating the operational and security risks\
  \ of managing long-lived PATs for automations at scale.\n\n\n When you use the Actions token in an agentic workflow running\
  \ in an organization-owned repository, AI credits consumed by your agentic workflow are billed directly to the organization.\n\
  \n\n Configuring organization billing for Copilot CLI in GitHub Agentic Workflows\n In order to use this feature, you must\
  \ enable the “Allow use of Copilot CLI billed to the organization” Copilot policy. This is enabled by default if you have\
  \ the existing “Copilot CLI” policy enabled.\n\n\n Once enabled, you can configure agentic workflows to bill directly to\
  \ the organization by adding copilot-requests: write to the permissions section in the frontmatter of your agentic workflow\
  \ markdown file, then compiling and pushing your updated lockfile.\n\n\n\n Note: You must be on the latest version of the\
  \ Agentic Workflows CLI. Use $ gh extension upgrade aw to upgrade.\n\n\n\n Controlling cost while billing to your organization\n\
  \ User-level inference budgets are not considered when billing directly to the organization, because the cost is not attributed\
  \ to a user. There are multiple ways to manage spend when using this billing method:\n\n\n\n Configure cost centers for\
  \ the relevant organizations. Cost centers allow cost attribution to groups of organizations, and budgets can be applied\
  \ to cost centers.\n Use the cost management tools in GitHub Agentic Workflows to monitor, manage, and cap token usage per\
  \ agentic workflow run.\n\n To learn more, see the GitHub Agentic Workflows documentation about authentication .\n\n\n This\
  \ feature is available for all Copilot plans: Copilot Free, Copilot Pro, Copilot Pro+, Copilot Business, and Copilot Enterprise.\n\
  \n\n\n The post Agentic workflows no longer need a personal access token appeared first on The GitHub Blog ."
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
- at: '2026-06-11T15:55:49Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-11T16:31:26Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-11-agentic-workflows-no-longer-need-a-personal-access-token
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-11T16:31:23Z'
  url: https://github.blog/changelog/2026-06-11-agentic-workflows-no-longer-need-a-personal-access-token
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now use GitHub Agentic Workflows with GitHub Actions’s built-in GITHUB_TOKEN .\n\n\n This\
  \ means that you no longer need to create and store a personal access token (PAT), eliminating the operational and security\
  \ risks of managing long-lived PATs for automations at scale.\n\n\n When you use the Actions token in an agentic workflow\
  \ running in an organization-owned repository, AI credits consumed by your agentic workflow are billed directly to the organization.\n\
  \n\n Configuring organization billing for Copilot CLI in GitHub Agentic Workflows\n In order to use this feature, you must\
  \ enable the “Allow use of Copilot CLI billed to the organization” Copilot policy. This is enabled by default if you have\
  \ the existing “Copilot CLI” policy enabled.\n\n\n Once enabled, you can configure agentic workflows to bill directly to\
  \ the organization by adding copilot-requests: write to the permissions section in the frontmatter of your agentic workflow\
  \ markdown file, then compiling and pushing your updated lockfile.\n\n\n\n Note: You must be on the latest version of the\
  \ Agentic Workflows CLI. Use $ gh extension upgrade aw to upgrade.\n\n\n\n Controlling cost while billing to your organization\n\
  \ User-level inference budgets are not considered when billing directly to the organization, because the cost is not attributed\
  \ to a user. There are multiple ways to manage spend when using this billing method:\n\n\n\n Configure cost centers for\
  \ the relevant organizations. Cost centers allow cost attribution to groups of organizations, and budgets can be applied\
  \ to cost centers.\n Use the cost management tools in GitHub Agentic Workflows to monitor, manage, and cap token usage per\
  \ agentic workflow run.\n\n To learn more, see the GitHub Agentic Workflows documentation about authentication .\n\n\n This\
  \ feature is available for all Copilot plans: Copilot Free, Copilot Pro, Copilot Pro+, Copilot Business, and Copilot Enterprise.\n\
  \n\n\n The post Agentic workflows no longer need a personal access token appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
