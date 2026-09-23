---
layout: aux-update
title: GitHub / Copilot Local sandboxing in the GitHub Copilot app official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Local sandboxing in the GitHub Copilot app.
permalink: /updates/github/github/local-sandboxing-in-the-github-copilot-app/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-23-local-sandboxing-in-the-github-copilot-app
update_download_url: ''
update_version: Local sandboxing in the GitHub Copilot app
update_logo_text: GIT
update_published_at: '2026-09-23T15:00:57Z'
update_last_checked: '2026-09-23T19:17:46Z'
source_last_checked: '2026-09-23T19:17:46Z'
official_body_last_checked: '2026-09-23T19:17:46Z'
record_last_updated: '2026-09-23T19:17:46Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Local sandboxing in the GitHub Copilot app
update_detail_title: GitHub / Copilot Local sandboxing in the GitHub Copilot app
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Local sandboxing in the GitHub Copilot app has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Local sandboxing in the GitHub Copilot app.
release_summary: "Local sandboxing helps reduce the potential impact of unintended commands by limiting access to files, network\
  \ resources, and credentials on your machine. In the GitHub Copilot app, you configure it per project for local repository\
  \ and working tree sessions.\n\n\n The project’s sandbox settings include:\n\n\n\n Filesystem: Additional read/write, additional\
  \ read-only, and denied folder lists.\n Network: Outbound internet and local network settings.\n Credentials: Git credentials\
  \ for authenticated HTTPS git operations, and GitHub CLI credentials for GitHub CLI authentication.\n\n These project settings\
  \ describe the policy that the app requests when a sandboxed session starts. The effective policy can be more restrictive\
  \ when enterprise-managed settings apply.\n\n\n If your operating system cannot enforce the requested policy, the sandboxed\
  \ shell fails with an error rather than running without a sandbox.\n\n\n Get started\n Local sandboxing is off by default.\
  \ Open the app settings, select your project, and turn on Sandbox new sessions under “Sandbox”. This applies to new sessions\
  \ in the project, not sessions already running. Changes to filesystem, network, and credential settings apply to new sessions\
  \ or when an existing session restarts.\n\n\n To enable sandboxing for an active local session, enter /sandbox on . This\
  \ changes that session without changing the project default.\n\n\n Local sandboxing does not apply to cloud sandbox sessions\
  \ or sessions running on a remote host. GitHub Copilot app and Copilot CLI sandbox settings are configured separately.\n\
  \n\n Local sandboxing is in public preview and subject to change.\n\n\n Learn more about configuring local sandboxing in\
  \ the GitHub Copilot app .\n\n\n\n The post Local sandboxing in the GitHub Copilot app appeared first on The GitHub Blog\
  \ ."
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
- at: '2026-09-23T15:00:57Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-23T19:17:51Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-23-local-sandboxing-in-the-github-copilot-app
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-23T19:17:46Z'
  url: https://github.blog/changelog/2026-09-23-local-sandboxing-in-the-github-copilot-app
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Local sandboxing helps reduce the potential impact of unintended commands by limiting access to\
  \ files, network resources, and credentials on your machine. In the GitHub Copilot app, you configure it per project for\
  \ local repository and working tree sessions.\n\n\n The project’s sandbox settings include:\n\n\n\n Filesystem: Additional\
  \ read/write, additional read-only, and denied folder lists.\n Network: Outbound internet and local network settings.\n\
  \ Credentials: Git credentials for authenticated HTTPS git operations, and GitHub CLI credentials for GitHub CLI authentication.\n\
  \n These project settings describe the policy that the app requests when a sandboxed session starts. The effective policy\
  \ can be more restrictive when enterprise-managed settings apply.\n\n\n If your operating system cannot enforce the requested\
  \ policy, the sandboxed shell fails with an error rather than running without a sandbox.\n\n\n Get started\n Local sandboxing\
  \ is off by default. Open the app settings, select your project, and turn on Sandbox new sessions under “Sandbox”. This\
  \ applies to new sessions in the project, not sessions already running. Changes to filesystem, network, and credential settings\
  \ apply to new sessions or when an existing session restarts.\n\n\n To enable sandboxing for an active local session, enter\
  \ /sandbox on . This changes that session without changing the project default.\n\n\n Local sandboxing does not apply to\
  \ cloud sandbox sessions or sessions running on a remote host. GitHub Copilot app and Copilot CLI sandbox settings are configured\
  \ separately.\n\n\n Local sandboxing is in public preview and subject to change.\n\n\n Learn more about configuring local\
  \ sandboxing in the GitHub Copilot app .\n\n\n\n The post Local sandboxing in the GitHub Copilot app appeared first on The\
  \ GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
