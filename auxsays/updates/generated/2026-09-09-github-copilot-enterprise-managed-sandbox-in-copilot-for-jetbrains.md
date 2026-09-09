---
layout: aux-update
title: GitHub / Copilot Enterprise-managed sandbox in Copilot for JetBrains official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Enterprise-managed sandbox in Copilot for JetBrains.
permalink: /updates/github/github/enterprise-managed-sandbox-in-copilot-for-jetbrains/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains
update_download_url: ''
update_version: Enterprise-managed sandbox in Copilot for JetBrains
update_logo_text: GIT
update_published_at: '2026-09-09T02:43:38Z'
update_last_checked: '2026-09-09T05:41:48Z'
source_last_checked: '2026-09-09T14:05:04Z'
official_body_last_checked: '2026-09-09T14:05:04Z'
record_last_updated: '2026-09-09T05:41:48Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Enterprise-managed sandbox in Copilot for JetBrains
update_detail_title: GitHub / Copilot Enterprise-managed sandbox in Copilot for JetBrains
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Enterprise-managed sandbox in Copilot for JetBrains has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Enterprise-managed sandbox in Copilot for JetBrains.
release_summary: "This update brings support for enterprise-managed sandbox policies, cross-file cursor jumps for next edit\
  \ suggestions, global project context in chat, enterprise policy diagnostics, and a new connection between terminal Copilot\
  \ CLI sessions and JetBrains IDEs. It also improves model selection, the chat experience, and reliability across MCP servers\
  \ and agent sessions.\n\n\n What’s new\n Enterprise-managed sandbox policies in public preview\n Enterprise administrators\
  \ can now centrally configure sandbox behavior for GitHub Copilot in JetBrains IDEs. Managed policies can control sandbox\
  \ enablement, filesystem and network access, proxy settings, developer-tool access, macOS Keychain access, and more.\n\n\
  \n Managed restrictions take precedence over user settings. Copilot locks affected controls in the IDE and identifies settings\
  \ managed by your organization, helping administrators enforce consistent development environment boundaries.\n\n\n The\
  \ sandbox settings under GitHub Copilot > Sandbox are visible when your organization enables the Editor Preview feature\
  \ flag or configures a managed setting to enable or disable the sandbox. If neither condition applies, the sandbox settings\
  \ do not appear.\n\n\n For more information, see Configuring local sandbox settings for GitHub Copilot .\n\n\n\n\n\n Cross-file\
  \ cursor jumps in next edit suggestions\n Next edit suggestions can now move your cursor across files, helping you navigate\
  \ and apply coordinated code suggestions throughout a project. When a suggested change continues in another file, you can\
  \ jump directly to the relevant location instead of finding it manually.\n\n\n Global project context in chat\n You can\
  \ now add global files and folders to chat context, making it faster to include information that applies across your project.\
  \ This reduces repetitive context setup and helps Copilot provide more relevant responses for changes that span multiple\
  \ areas.\n\n\n\n\n\n Enterprise policy diagnostics\n You can now use enterprise policy diagnostics to verify that policies\
  \ are correctly detected and enforced on your device. This makes it easier to confirm that your Copilot configuration follows\
  \ your organization’s requirements.\n\n\n\n\n\n Connect terminal Copilot CLI sessions to your IDE\n You can now use /ide\
  \ in GitHub Copilot CLI to connect a terminal session to your JetBrains IDE context, including selections, diagnostics,\
  \ and file references. This integration is in public preview and helps terminal-based workflows stay grounded in what you\
  \ are viewing and editing in the IDE.\n\n\n Copilot shell commands can also use environment variables from the IDE terminal\
  \ and the Python interpreter configured for your project. They can activate the project’s standard local Python virtual\
  \ environment, making connected command execution more consistent with your development environment.\n\n\n\n\n\n User experience\
  \ enhancements\n This release includes several interaction and navigation improvements for common workflows:\n\n\n\n Background\
  \ agent prompts : Improved the ask-user card to better accommodate long questions.\n Model selection : Refined model picker\
  \ behavior and BYOK grouping to make model choices easier to scan and select.\n Subagent models : Added support for selecting\
  \ the session model used by built-in subagents in the Copilot agent harness.\n Agent debug logs : Added section copy support\
  \ so you can share diagnostics and troubleshooting context faster.\n MCP configuration : Opened MCP configuration in the\
  \ originating project window for better continuity.\n Plugin updates : Improved update reminders to make new plugin versions\
  \ easier to discover.\n\n Quality improvements\n This release improves reliability across MCP servers and agent sessions,\
  \ including BYOK provider persistence, OAuth challenge continuity, restored server state, and GitHub Enterprise authentication.\
  \ It also resolves blank local chat sessions, incorrect working-set counts, working-set zoom and model picker interaction\
  \ issues, and read-only file editing issues. Additional fixes address Claude plan stop behavior, misleading diagnostics\
  \ for unopened files, stale global instructions in “Agent Customizations,” and chats becoming unresponsive after automatic\
  \ compaction.\n\n\n Generally Available\n OpenTelemetry settings in “GitHub Copilot – Chat” are now generally available\
  \ to all users.\n\n\n Try it out\n We encourage you to try out the latest version of the GitHub Copilot plugin and share\
  \ your feedback. Your input is invaluable in helping us refine and improve the product.\n\n\n Share your feedback\n We’d\
  \ love to hear about your experience in the following channels:\n\n\n\n In-product feedback: Use the feedback options within\
  \ your IDE.\n Feedback repository: Share your thoughts in the GitHub Copilot for JetBrains IDEs issues .\n\n\n The post\
  \ Enterprise-managed sandbox in Copilot for JetBrains appeared first on The GitHub Blog ."
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
- at: '2026-09-09T02:43:38Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-09T05:41:58Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-09T05:41:48Z'
  url: https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-09T14:05:04Z'
  url: https://github.blog/changelog/2026-09-08-enterprise-managed-sandbox-in-copilot-for-jetbrains
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "This update brings support for enterprise-managed sandbox policies, cross-file cursor jumps for\
  \ next edit suggestions, global project context in chat, enterprise policy diagnostics, and a new connection between terminal\
  \ Copilot CLI sessions and JetBrains IDEs. It also improves model selection, the chat experience, and reliability across\
  \ MCP servers and agent sessions.\n\n\n What’s new\n Enterprise-managed sandbox policies in public preview\n Enterprise\
  \ administrators can now centrally configure sandbox behavior for GitHub Copilot in JetBrains IDEs. Managed policies can\
  \ control sandbox enablement, filesystem and network access, proxy settings, developer-tool access, macOS Keychain access,\
  \ and more.\n\n\n Managed restrictions take precedence over user settings. Copilot locks affected controls in the IDE and\
  \ identifies settings managed by your organization, helping administrators enforce consistent development environment boundaries.\n\
  \n\n The sandbox settings under GitHub Copilot > Sandbox are visible when your organization enables the Editor Preview feature\
  \ flag or configures a managed setting to enable or disable the sandbox. If neither condition applies, the sandbox settings\
  \ do not appear.\n\n\n For more information, see Configuring local sandbox settings for GitHub Copilot .\n\n\n\n\n\n Cross-file\
  \ cursor jumps in next edit suggestions\n Next edit suggestions can now move your cursor across files, helping you navigate\
  \ and apply coordinated code suggestions throughout a project. When a suggested change continues in another file, you can\
  \ jump directly to the relevant location instead of finding it manually.\n\n\n Global project context in chat\n You can\
  \ now add global files and folders to chat context, making it faster to include information that applies across your project.\
  \ This reduces repetitive context setup and helps Copilot provide more relevant responses for changes that span multiple\
  \ areas.\n\n\n\n\n\n Enterprise policy diagnostics\n You can now use enterprise policy diagnostics to verify that policies\
  \ are correctly detected and enforced on your device. This makes it easier to confirm that your Copilot configuration follows\
  \ your organization’s requirements.\n\n\n\n\n\n Connect terminal Copilot CLI sessions to your IDE\n You can now use /ide\
  \ in GitHub Copilot CLI to connect a terminal session to your JetBrains IDE context, including selections, diagnostics,\
  \ and file references. This integration is in public preview and helps terminal-based workflows stay grounded in what you\
  \ are viewing and editing in the IDE.\n\n\n Copilot shell commands can also use environment variables from the IDE terminal\
  \ and the Python interpreter configured for your project. They can activate the project’s standard local Python virtual\
  \ environment, making connected command execution more consistent with your development environment.\n\n\n\n\n\n User experience\
  \ enhancements\n This release includes several interaction and navigation improvements for common workflows:\n\n\n\n Background\
  \ agent prompts : Improved the ask-user card to better accommodate long questions.\n Model selection : Refined model picker\
  \ behavior and BYOK grouping to make model choices easier to scan and select.\n Subagent models : Added support for selecting\
  \ the session model used by built-in subagents in the Copilot agent harness.\n Agent debug logs : Added section copy support\
  \ so you can share diagnostics and troubleshooting context faster.\n MCP configuration : Opened MCP configuration in the\
  \ originating project window for better continuity.\n Plugin updates : Improved update reminders to make new plugin versions\
  \ easier to discover.\n\n Quality improvements\n This release improves reliability across MCP servers and agent sessions,\
  \ including BYOK provider persistence, OAuth challenge continuity, restored server state, and GitHub Enterprise authentication.\
  \ It also resolves blank local chat sessions, incorrect working-set counts, working-set zoom and model picker interaction\
  \ issues, and read-only file editing issues. Additional fixes address Claude plan stop behavior, misleading diagnostics\
  \ for unopened files, stale global instructions in “Agent Customizations,” and chats becoming unresponsive after automatic\
  \ compaction.\n\n\n Generally Available\n OpenTelemetry settings in “GitHub Copilot – Chat” are now generally available\
  \ to all users.\n\n\n Try it out\n We encourage you to try out the latest version of the GitHub Copilot plugin and share\
  \ your feedback. Your input is invaluable in helping us refine and improve the product.\n\n\n Share your feedback\n We’d\
  \ love to hear about your experience in the following channels:\n\n\n\n In-product feedback: Use the feedback options within\
  \ your IDE.\n Feedback repository: Share your thoughts in the GitHub Copilot for JetBrains IDEs issues .\n\n\n The post\
  \ Enterprise-managed sandbox in Copilot for JetBrains appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
