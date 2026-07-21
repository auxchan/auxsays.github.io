---
layout: aux-update
title: 'GitHub / Copilot Copilot code review: Customization and configurability improvements official update breakdown'
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/copilot-code-review-customization-and-configurability-improvements/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-17-copilot-code-review-customization-and-configurability-improvements
update_download_url: ''
update_version: 'Copilot code review: Customization and configurability improvements'
update_logo_text: GIT
update_published_at: '2026-07-17T21:08:30Z'
update_last_checked: '2026-07-21T08:49:13Z'
source_last_checked: '2026-07-21T08:49:13Z'
official_body_last_checked: '2026-07-21T08:49:13Z'
record_last_updated: '2026-07-21T08:49:13Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot Copilot code review: Customization and configurability improvements'
update_detail_title: 'GitHub / Copilot Copilot code review: Customization and configurability improvements'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot Copilot code review: Customization and configurability improvements has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot Copilot code review: Customization and configurability improvements.'
release_summary: "Copilot code review now utilizes a firewall, custom setup steps, and independent runner configurations.\
  \ It now reads custom instructions from the head branch to allow for easy testing and validation of custom instructions.\
  \ These changes give administrators and developers more control over how Copilot code review runs in their environment.\n\
  \n\n Expanding custom instructions, now easier to validate\n \U0001F4DD Custom instructions now read from the head branch\n\
  \ Custom instructions are now read from the head branch of the pull request instead of the base branch. This includes copilot-instructions.md\
  \ , *.instructions.md , agent skills, and AGENTS.md . This means you can iterate on and test custom instructions in a feature\
  \ branch without needing to merge them first.\n\n\n \U0001F4C4 Expanded custom instructions file support\n Copilot code\
  \ review now reads REVIEW.md , GEMINI.md , and CLAUDE.md files from your repository, so your customizations are understood\
  \ regardless of where they live. If your team already maintains review guidelines or model-specific instructions in these\
  \ files, Copilot code review will automatically pick them up and incorporate them into its review process.\n\n\n \U0001F527\
  \ Custom setup steps\n You can now configure the environment available to Copilot code review during runtime using a copilot-code-review.yml\
  \ file in your .github/workflows/ directory. This lets you install dependencies, configure runners on the repository level\
  \ independently of Copilot cloud agent, set up tooling, or run any preparation steps that Copilot code review needs to produce\
  \ the reviews you desire for your repository.\n\n\n\n Add a copilot-code-review.yml file to your repository to define setup\
  \ steps specific to Copilot code review.\n If no copilot-code-review.yml file exists, Copilot code review will fall back\
  \ to your existing copilot-setup-steps.yml file if one is present.\n\n To learn more about how to set up a copilot-code-review.yml\
  \ file, see our documentation on setting the Copilot code review environment .\n\n\n \U0001F6E1️ Firewall support\n Copilot\
  \ code review now runs behind a firewall by default, restricting network access during a review. The firewall is configurable\
  \ separately from Copilot cloud agent in repository and organization settings, giving you independent control over each\
  \ agent’s network access.\n\n\n\n The firewall is enabled by default for all repositories.\n To configure this setting in\
  \ your repository, navigate to your repository settings, then go to Copilot → Internet access .\n\n\n ⚠️ Self-hosted runners\
  \ do not currently support the firewall. If you have self-hosted runners configured for Copilot code review, your reviews\
  \ will continue to run as usual without the firewall.\n\n\n\n\n\n\n ⚙️ Organization runner configuration updates for Copilot\
  \ code review\n Copilot code review and Copilot cloud agent previously shared a single runner configuration at the organization\
  \ level. That configuration is now split into two separate sections on the Runner type settings page in your organization\
  \ settings, allowing you to independently choose different runner types for each agent.\n\n\n To update your configuration,\
  \ navigate to your organization settings, then go to Copilot → Runner type .\n\n\n\n\n\n\n The post Copilot code review:\
  \ Customization and configurability improvements appeared first on The GitHub Blog ."
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
- at: '2026-07-17T21:08:30Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-21T08:49:15Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-17-copilot-code-review-customization-and-configurability-improvements
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-21T08:49:13Z'
  url: https://github.blog/changelog/2026-07-17-copilot-code-review-customization-and-configurability-improvements
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Copilot code review now utilizes a firewall, custom setup steps, and independent runner configurations.\
  \ It now reads custom instructions from the head branch to allow for easy testing and validation of custom instructions.\
  \ These changes give administrators and developers more control over how Copilot code review runs in their environment.\n\
  \n\n Expanding custom instructions, now easier to validate\n \U0001F4DD Custom instructions now read from the head branch\n\
  \ Custom instructions are now read from the head branch of the pull request instead of the base branch. This includes copilot-instructions.md\
  \ , *.instructions.md , agent skills, and AGENTS.md . This means you can iterate on and test custom instructions in a feature\
  \ branch without needing to merge them first.\n\n\n \U0001F4C4 Expanded custom instructions file support\n Copilot code\
  \ review now reads REVIEW.md , GEMINI.md , and CLAUDE.md files from your repository, so your customizations are understood\
  \ regardless of where they live. If your team already maintains review guidelines or model-specific instructions in these\
  \ files, Copilot code review will automatically pick them up and incorporate them into its review process.\n\n\n \U0001F527\
  \ Custom setup steps\n You can now configure the environment available to Copilot code review during runtime using a copilot-code-review.yml\
  \ file in your .github/workflows/ directory. This lets you install dependencies, configure runners on the repository level\
  \ independently of Copilot cloud agent, set up tooling, or run any preparation steps that Copilot code review needs to produce\
  \ the reviews you desire for your repository.\n\n\n\n Add a copilot-code-review.yml file to your repository to define setup\
  \ steps specific to Copilot code review.\n If no copilot-code-review.yml file exists, Copilot code review will fall back\
  \ to your existing copilot-setup-steps.yml file if one is present.\n\n To learn more about how to set up a copilot-code-review.yml\
  \ file, see our documentation on setting the Copilot code review environment .\n\n\n \U0001F6E1️ Firewall support\n Copilot\
  \ code review now runs behind a firewall by default, restricting network access during a review. The firewall is configurable\
  \ separately from Copilot cloud agent in repository and organization settings, giving you independent control over each\
  \ agent’s network access.\n\n\n\n The firewall is enabled by default for all repositories.\n To configure this setting in\
  \ your repository, navigate to your repository settings, then go to Copilot → Internet access .\n\n\n ⚠️ Self-hosted runners\
  \ do not currently support the firewall. If you have self-hosted runners configured for Copilot code review, your reviews\
  \ will continue to run as usual without the firewall.\n\n\n\n\n\n\n ⚙️ Organization runner configuration updates for Copilot\
  \ code review\n Copilot code review and Copilot cloud agent previously shared a single runner configuration at the organization\
  \ level. That configuration is now split into two separate sections on the Runner type settings page in your organization\
  \ settings, allowing you to independently choose different runner types for each agent.\n\n\n To update your configuration,\
  \ navigate to your organization settings, then go to Copilot → Runner type .\n\n\n\n\n\n\n The post Copilot code review:\
  \ Customization and configurability improvements appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
