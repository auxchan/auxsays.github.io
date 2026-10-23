---
layout: aux-update
title: GitHub / Copilot Custom skills, agents, and MCP servers in usage metrics API official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Custom skills, agents, and MCP servers in usage
  metrics API.
permalink: /updates/github/github/custom-skills-agents-and-mcp-servers-in-usage-metrics-api/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-22-custom-skills-agents-and-mcp-servers-in-usage-metrics-api
update_download_url: ''
update_version: Custom skills, agents, and MCP servers in usage metrics API
update_logo_text: GIT
update_published_at: '2026-10-22T22:19:17Z'
update_last_checked: '2026-10-23T00:12:51Z'
source_last_checked: '2026-10-23T19:54:21Z'
official_body_last_checked: '2026-10-23T19:54:21Z'
record_last_updated: '2026-10-23T00:12:51Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Custom skills, agents, and MCP servers in usage metrics API
update_detail_title: GitHub / Copilot Custom skills, agents, and MCP servers in usage metrics API
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Custom skills, agents, and MCP servers in usage metrics API has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Custom skills, agents, and MCP servers in usage metrics API.
release_summary: "Copilot usage metrics now show the names of the skills, custom agents, Model Context Protocol (MCP) servers,\
  \ slash commands, and plugins that your organization creates, instead of grouping them under other or custom . This builds\
  \ on the agentic CLI customization metrics released in September.\n\n\n What’s new\n\n Named entries: In enterprise and\
  \ organization reports, including per-user 1-day and 28-day reports, aggregated 1-day reports, and day_totals in aggregated\
  \ 28-day reports, the totals_by_skill , totals_by_custom_agent , totals_by_mcp , totals_by_slash_cmd , and totals_by_plugin\
  \ arrays now show the configured name of a customer-defined item instead of other or custom .\n More entries: Each totals_by_*\
  \ list now includes up to 25 entries per record, up from five, so you can see more of the long tail of customizations your\
  \ developers use. Any remaining activity is combined into a trailing other entry.\n Unchanged counts: interaction_count\
  \ and the distinct_*_use_count fields are calculated the same way as before.\n\n Why this matters\n The customizations that\
  \ matter most to an organization are often the ones its own teams build. Administrators can now see which internal skills,\
  \ custom agents, and MCP servers developers actually use, track adoption after rolling out a new one, and focus enablement\
  \ where it is needed.\n\n\n Important notes\n\n Coverage: Names are reported from Copilot CLI (interactive sessions and\
  \ prompt mode), the GitHub Copilot app, Agent Client Protocol (ACP) integrations such as JetBrains, and the Copilot SDK.\
  \ Prompt mode, the app, and ACP integrations require Copilot CLI 1.0.97 or later. The Copilot SDK requires v1.0.21 or later.\
  \ IDEs report names when their agent experiences run on the Copilot SDK v1.0.21 or later. Names aren’t reported from an\
  \ IDE’s built-in chat telemetry.\n Configured names: Names are reported as they are configured, trimmed and limited to 128\
  \ characters. Names that look like file paths stay grouped under other or custom . Review names before sharing reports outside\
  \ your organization.\n Accuracy: These metrics come from client telemetry and can undercount activity, for example when\
  \ clients are outdated or telemetry is blocked. Use them to understand trends and adoption rather than for exact accounting.\n\
  \ History: Names appear starting with report days processed after this release. Earlier days still show other or custom\
  \ .\n Access: Reports are available to enterprise owners and billing managers, organization owners, and anyone with a custom\
  \ organization or enterprise role that grants the “View Copilot Metrics” permission. The Copilot usage metrics policy must\
  \ be enabled.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post Custom skills, agents,\
  \ and MCP servers in usage metrics API appeared first on The GitHub Blog ."
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
- at: '2026-10-22T22:19:17Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-23T00:13:03Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-22-custom-skills-agents-and-mcp-servers-in-usage-metrics-api
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-23T00:12:51Z'
  url: https://github.blog/changelog/2026-10-22-custom-skills-agents-and-mcp-servers-in-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-23T07:19:20Z'
  url: https://github.blog/changelog/2026-10-22-custom-skills-agents-and-mcp-servers-in-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-23T14:11:28Z'
  url: https://github.blog/changelog/2026-10-22-custom-skills-agents-and-mcp-servers-in-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-23T19:54:21Z'
  url: https://github.blog/changelog/2026-10-22-custom-skills-agents-and-mcp-servers-in-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Copilot usage metrics now show the names of the skills, custom agents, Model Context Protocol\
  \ (MCP) servers, slash commands, and plugins that your organization creates, instead of grouping them under other or custom\
  \ . This builds on the agentic CLI customization metrics released in September.\n\n\n What’s new\n\n Named entries: In enterprise\
  \ and organization reports, including per-user 1-day and 28-day reports, aggregated 1-day reports, and day_totals in aggregated\
  \ 28-day reports, the totals_by_skill , totals_by_custom_agent , totals_by_mcp , totals_by_slash_cmd , and totals_by_plugin\
  \ arrays now show the configured name of a customer-defined item instead of other or custom .\n More entries: Each totals_by_*\
  \ list now includes up to 25 entries per record, up from five, so you can see more of the long tail of customizations your\
  \ developers use. Any remaining activity is combined into a trailing other entry.\n Unchanged counts: interaction_count\
  \ and the distinct_*_use_count fields are calculated the same way as before.\n\n Why this matters\n The customizations that\
  \ matter most to an organization are often the ones its own teams build. Administrators can now see which internal skills,\
  \ custom agents, and MCP servers developers actually use, track adoption after rolling out a new one, and focus enablement\
  \ where it is needed.\n\n\n Important notes\n\n Coverage: Names are reported from Copilot CLI (interactive sessions and\
  \ prompt mode), the GitHub Copilot app, Agent Client Protocol (ACP) integrations such as JetBrains, and the Copilot SDK.\
  \ Prompt mode, the app, and ACP integrations require Copilot CLI 1.0.97 or later. The Copilot SDK requires v1.0.21 or later.\
  \ IDEs report names when their agent experiences run on the Copilot SDK v1.0.21 or later. Names aren’t reported from an\
  \ IDE’s built-in chat telemetry.\n Configured names: Names are reported as they are configured, trimmed and limited to 128\
  \ characters. Names that look like file paths stay grouped under other or custom . Review names before sharing reports outside\
  \ your organization.\n Accuracy: These metrics come from client telemetry and can undercount activity, for example when\
  \ clients are outdated or telemetry is blocked. Use them to understand trends and adoption rather than for exact accounting.\n\
  \ History: Names appear starting with report days processed after this release. Earlier days still show other or custom\
  \ .\n Access: Reports are available to enterprise owners and billing managers, organization owners, and anyone with a custom\
  \ organization or enterprise role that grants the “View Copilot Metrics” permission. The Copilot usage metrics policy must\
  \ be enabled.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post Custom skills, agents,\
  \ and MCP servers in usage metrics API appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
