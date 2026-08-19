---
layout: aux-update
title: GitHub / Copilot Enterprise managed settings in GitHub Copilot for JetBrains official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/enterprise-managed-settings-in-github-copilot-for-jetbrains/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-18-enterprise-managed-settings-in-github-copilot-for-jetbrains
update_download_url: ''
update_version: Enterprise managed settings in GitHub Copilot for JetBrains
update_logo_text: GIT
update_published_at: '2026-08-18T23:33:07Z'
update_last_checked: '2026-08-19T16:46:12Z'
source_last_checked: '2026-08-19T20:05:14Z'
official_body_last_checked: '2026-08-19T20:05:14Z'
record_last_updated: '2026-08-19T16:46:12Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Enterprise managed settings in GitHub Copilot for JetBrains
update_detail_title: GitHub / Copilot Enterprise managed settings in GitHub Copilot for JetBrains
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Enterprise managed settings in GitHub Copilot for JetBrains has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Enterprise managed settings in GitHub Copilot for JetBrains.
release_summary: "GitHub Copilot for JetBrains now supports enterprise managed settings for plugin governance, MCP server\
  \ access, OpenTelemetry, and permission modes. Administrators can now apply consistent controls for everyone on your enterprise’s\
  \ Copilot plan.\n\n\n Enterprise-managed plugin governance\n Administrators can manage Copilot plugins and their marketplaces\
  \ in JetBrains IDEs. The supported settings provide three controls:\n\n\n\n Enabled plugins: Use enabledPlugins to require\
  \ a plugin to be enabled or disabled.\n Additional marketplaces: Use extraKnownMarketplaces to make approved plugin sources\
  \ available.\n Restricted marketplaces: Use strictKnownMarketplaces to limit installation to approved sources.\n\n MCP server\
  \ allowlist\n Administrators can use allowedMcpServers and deniedMcpServers to centrally control which MCP servers developers\
  \ can connect to from GitHub Copilot for JetBrains. This brings centrally managed MCP governance into JetBrains IDEs and\
  \ prevents connections to servers outside the enterprise allowlist.\n\n\n Managed OpenTelemetry\n Administrators can centrally\
  \ configure OpenTelemetry for Copilot in JetBrains IDEs, including the collector endpoint, protocol, service name, resource\
  \ attributes, and content-capture policy. Managed values take precedence over developer settings, so telemetry is consistently\
  \ routed to the approved collector.\n\n\n Developers can review the applied configuration under Settings > Tools > GitHub\
  \ Copilot > Chat > OpenTelemetry .\n\n\n Organization-controlled permission modes\n Administrators can set permissions.disableBypassPermissionsMode\
  \ to disable to prevent the Copilot agent in JetBrains from using Bypass Approvals or Autopilot .\n\n\n Try it out\n Try\
  \ the latest version of the GitHub Copilot plugin for JetBrains and share your feedback. For more details on enterprise\
  \ managed settings, see enterprise managed settings reference .\n\n\n Share your feedback\n Your feedback drives improvements.\
  \ We’d love to hear about your experience in the following channels:\n\n\n\n In-product feedback: Use the feedback options\
  \ within your JetBrains IDE.\n Feedback repository: Share your experience in the Copilot IntelliJ feedback repository .\n\
  \ GitHub Community: Join the discussion in GitHub Community .\n\n\n The post Enterprise managed settings in GitHub Copilot\
  \ for JetBrains appeared first on The GitHub Blog ."
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
- at: '2026-08-18T23:33:07Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-19T16:46:24Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-18-enterprise-managed-settings-in-github-copilot-for-jetbrains
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-19T16:46:12Z'
  url: https://github.blog/changelog/2026-08-18-enterprise-managed-settings-in-github-copilot-for-jetbrains
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-19T20:05:14Z'
  url: https://github.blog/changelog/2026-08-18-enterprise-managed-settings-in-github-copilot-for-jetbrains
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub Copilot for JetBrains now supports enterprise managed settings for plugin governance, MCP\
  \ server access, OpenTelemetry, and permission modes. Administrators can now apply consistent controls for everyone on your\
  \ enterprise’s Copilot plan.\n\n\n Enterprise-managed plugin governance\n Administrators can manage Copilot plugins and\
  \ their marketplaces in JetBrains IDEs. The supported settings provide three controls:\n\n\n\n Enabled plugins: Use enabledPlugins\
  \ to require a plugin to be enabled or disabled.\n Additional marketplaces: Use extraKnownMarketplaces to make approved\
  \ plugin sources available.\n Restricted marketplaces: Use strictKnownMarketplaces to limit installation to approved sources.\n\
  \n MCP server allowlist\n Administrators can use allowedMcpServers and deniedMcpServers to centrally control which MCP servers\
  \ developers can connect to from GitHub Copilot for JetBrains. This brings centrally managed MCP governance into JetBrains\
  \ IDEs and prevents connections to servers outside the enterprise allowlist.\n\n\n Managed OpenTelemetry\n Administrators\
  \ can centrally configure OpenTelemetry for Copilot in JetBrains IDEs, including the collector endpoint, protocol, service\
  \ name, resource attributes, and content-capture policy. Managed values take precedence over developer settings, so telemetry\
  \ is consistently routed to the approved collector.\n\n\n Developers can review the applied configuration under Settings\
  \ > Tools > GitHub Copilot > Chat > OpenTelemetry .\n\n\n Organization-controlled permission modes\n Administrators can\
  \ set permissions.disableBypassPermissionsMode to disable to prevent the Copilot agent in JetBrains from using Bypass Approvals\
  \ or Autopilot .\n\n\n Try it out\n Try the latest version of the GitHub Copilot plugin for JetBrains and share your feedback.\
  \ For more details on enterprise managed settings, see enterprise managed settings reference .\n\n\n Share your feedback\n\
  \ Your feedback drives improvements. We’d love to hear about your experience in the following channels:\n\n\n\n In-product\
  \ feedback: Use the feedback options within your JetBrains IDE.\n Feedback repository: Share your experience in the Copilot\
  \ IntelliJ feedback repository .\n GitHub Community: Join the discussion in GitHub Community .\n\n\n The post Enterprise\
  \ managed settings in GitHub Copilot for JetBrains appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
