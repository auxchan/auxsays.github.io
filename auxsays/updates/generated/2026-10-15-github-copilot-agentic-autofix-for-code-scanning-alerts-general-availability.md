---
layout: aux-update
title: GitHub / Copilot Agentic autofix for code scanning alerts general availability official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Agentic autofix for code scanning alerts general
  availability.
permalink: /updates/github/github/agentic-autofix-for-code-scanning-alerts-general-availability/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-15-agentic-autofix-for-code-scanning-alerts-general-availability
update_download_url: ''
update_version: Agentic autofix for code scanning alerts general availability
update_logo_text: GIT
update_published_at: '2026-10-15T13:49:20Z'
update_last_checked: '2026-10-15T19:52:48Z'
source_last_checked: '2026-10-15T19:52:48Z'
official_body_last_checked: '2026-10-15T19:52:48Z'
record_last_updated: '2026-10-15T19:52:48Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Agentic autofix for code scanning alerts general availability
update_detail_title: GitHub / Copilot Agentic autofix for code scanning alerts general availability
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Agentic autofix for code scanning alerts general availability has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Agentic autofix for code scanning alerts general availability.
release_summary: "Agentic autofix for code scanning alerts is now generally available. It remediates alerts by working across\
  \ your codebase the way a developer would: it explores relevant files, proposes a fix, and reruns CodeQL to confirm the\
  \ fix closes the alert before opening a pull request for your review. Agentic autofix is available to GitHub Code Security\
  \ and GitHub Advanced Security customers on GitHub Enterprise Cloud, including GitHub Enterprise Cloud with data residency.\n\
  \n\n How it works\n When you assign a code scanning alert to Copilot, it:\n\n\n\n Explores relevant files across your codebase.\n\
  \ Generates a proposed fix.\n Validates the fix works by rerunning CodeQL.\n Iterates if needed, then opens a draft pull\
  \ request ready for your review.\n\n The pull request includes a summary of the fix, why it closes the alert, and the validation\
  \ steps Copilot took to confirm that it works. When the pull request containing the fix is ready, you can instruct Copilot\
  \ to make further changes to it by commenting on the pull request or interacting with the session in the Agents tab of your\
  \ repository.\n\n\n How to use it\n When enabled, agentic autofix replaces the free Generate Fix option on individual code\
  \ scanning alerts with an Assign to Copilot button.\n\n\n You can use agentic autofix:\n\n\n\n From any code scanning alert\
  \ on the repository’s default branch, by assigning the alert to Copilot.\n In the list of security alerts in your repository\
  \ or security campaign, by selecting up to 25 alerts for Copilot to fix together in a single pull request.\n Via the Update\
  \ a Code Scanning Alert REST API by setting assignees to [\"copilot-swe-agent[bot]\"] .\n\n Agentic autofix supports code\
  \ scanning alerts on the repository’s default branch. Alerts detected only on pull requests or other branches cannot be\
  \ assigned to Copilot.\n\n\n Access\n Agentic autofix requires an enterprise administrator to enable access to it via the\
  \ new “Agentic autofix” policy in Advanced Security policies.\n\n\n Once the policy is enabled by an enterprise administrator,\
  \ an organization or repository administrator can turn on agentic autofix in the Code Security settings for the organization\
  \ or the repository.\n\n\n Access also requires a Copilot billing method to be defined.\n\n\n Billing\n Agentic autofix\
  \ for code scanning alerts consumes AI Credits from your Code Security budget and GitHub Actions minutes. AI Credit usage\
  \ will be displayed in the “AI usage” section of enterprise billing and licensing as the “Advanced Security” product. You\
  \ can also set SKU level budgets for Code Security AI credits. Learn more about Copilot usage-based billing .\n\n\n Learn\
  \ more\n Learn more about agentic autofix in the documentation .\n\n\n Join the discussion within the GitHub Community .\n\
  \n\n\n The post Agentic autofix for code scanning alerts general availability appeared first on The GitHub Blog ."
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
- at: '2026-10-15T13:49:20Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-15T19:53:05Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-15-agentic-autofix-for-code-scanning-alerts-general-availability
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-15T19:52:48Z'
  url: https://github.blog/changelog/2026-10-15-agentic-autofix-for-code-scanning-alerts-general-availability
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Agentic autofix for code scanning alerts is now generally available. It remediates alerts by working\
  \ across your codebase the way a developer would: it explores relevant files, proposes a fix, and reruns CodeQL to confirm\
  \ the fix closes the alert before opening a pull request for your review. Agentic autofix is available to GitHub Code Security\
  \ and GitHub Advanced Security customers on GitHub Enterprise Cloud, including GitHub Enterprise Cloud with data residency.\n\
  \n\n How it works\n When you assign a code scanning alert to Copilot, it:\n\n\n\n Explores relevant files across your codebase.\n\
  \ Generates a proposed fix.\n Validates the fix works by rerunning CodeQL.\n Iterates if needed, then opens a draft pull\
  \ request ready for your review.\n\n The pull request includes a summary of the fix, why it closes the alert, and the validation\
  \ steps Copilot took to confirm that it works. When the pull request containing the fix is ready, you can instruct Copilot\
  \ to make further changes to it by commenting on the pull request or interacting with the session in the Agents tab of your\
  \ repository.\n\n\n How to use it\n When enabled, agentic autofix replaces the free Generate Fix option on individual code\
  \ scanning alerts with an Assign to Copilot button.\n\n\n You can use agentic autofix:\n\n\n\n From any code scanning alert\
  \ on the repository’s default branch, by assigning the alert to Copilot.\n In the list of security alerts in your repository\
  \ or security campaign, by selecting up to 25 alerts for Copilot to fix together in a single pull request.\n Via the Update\
  \ a Code Scanning Alert REST API by setting assignees to [\"copilot-swe-agent[bot]\"] .\n\n Agentic autofix supports code\
  \ scanning alerts on the repository’s default branch. Alerts detected only on pull requests or other branches cannot be\
  \ assigned to Copilot.\n\n\n Access\n Agentic autofix requires an enterprise administrator to enable access to it via the\
  \ new “Agentic autofix” policy in Advanced Security policies.\n\n\n Once the policy is enabled by an enterprise administrator,\
  \ an organization or repository administrator can turn on agentic autofix in the Code Security settings for the organization\
  \ or the repository.\n\n\n Access also requires a Copilot billing method to be defined.\n\n\n Billing\n Agentic autofix\
  \ for code scanning alerts consumes AI Credits from your Code Security budget and GitHub Actions minutes. AI Credit usage\
  \ will be displayed in the “AI usage” section of enterprise billing and licensing as the “Advanced Security” product. You\
  \ can also set SKU level budgets for Code Security AI credits. Learn more about Copilot usage-based billing .\n\n\n Learn\
  \ more\n Learn more about agentic autofix in the documentation .\n\n\n Join the discussion within the GitHub Community .\n\
  \n\n\n The post Agentic autofix for code scanning alerts general availability appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
