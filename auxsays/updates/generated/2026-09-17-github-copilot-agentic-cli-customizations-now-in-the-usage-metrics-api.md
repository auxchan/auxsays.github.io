---
layout: aux-update
title: GitHub / Copilot Agentic CLI customizations now in the usage metrics API official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Agentic CLI customizations now in the usage
  metrics API.
permalink: /updates/github/github/agentic-cli-customizations-now-in-the-usage-metrics-api/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-17-agentic-cli-customizations-now-in-the-usage-metrics-api
update_download_url: ''
update_version: Agentic CLI customizations now in the usage metrics API
update_logo_text: GIT
update_published_at: '2026-09-17T21:08:50Z'
update_last_checked: '2026-09-17T23:40:30Z'
source_last_checked: '2026-09-18T13:29:34Z'
official_body_last_checked: '2026-09-18T13:29:34Z'
record_last_updated: '2026-09-17T23:40:30Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Agentic CLI customizations now in the usage metrics API
update_detail_title: GitHub / Copilot Agentic CLI customizations now in the usage metrics API
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Agentic CLI customizations now in the usage metrics API has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Agentic CLI customizations now in the usage metrics API.
release_summary: "GitHub Copilot expands existing CLI report coverage with agentic activity metrics for skills, custom agents,\
  \ Model Context Protocol (MCP) servers, slash commands, and plugins.\n\n\n What’s new\n The fields appear in enterprise\
  \ and organization per-user and aggregate 1-day reports, per-user 28-day reports, and the day_totals entries in aggregate\
  \ 28-day reports.\n\n\n In a per-user report, the fields answer two questions about that user’s activity. In an aggregate\
  \ report, they answer the same questions across the enterprise or organization:\n\n\n\n Which items are used most? The totals_by_skill\
  \ , totals_by_custom_agent , totals_by_mcp , totals_by_slash_cmd , and totals_by_plugin arrays list up to five items with\
  \ the most recorded activity. Each entry includes an interaction_count . Depending on the category, this counts invocations\
  \ for skills, slash commands, and plugin skills, plus custom agent starts and MCP server connection attempts.\n How many\
  \ different items were used? The distinct_skill_use_count , distinct_custom_agent_use_count , distinct_mcp_use_count , distinct_slash_cmd_use_count\
  \ , and distinct_plugin_use_count fields count the number of different items used. In a per-user report, each item that\
  \ user used counts once. In an aggregate report, each item used by anyone in the enterprise or organization counts once,\
  \ not once per user. These counts include items outside the top five, and comparing them over time shows whether the variety\
  \ of items in use is growing.\n\n Why this matters\n Enterprise and organization administrators are now able to identify\
  \ which Copilot CLI customizations are gaining traction, find enablement gaps, and focus investment on automations that\
  \ developers find valuable.\n\n\n Important notes\n\n Names for recognized GitHub-provided items are shown. To protect privacy,\
  \ customer-defined names are not shown. Skills, custom agents, MCP servers, and plugins are grouped under other . Copilot\
  \ CLI telemetry already groups customer-defined slash commands under custom , so reports use that label for slash commands.\n\
  \ For MCP servers, interaction_count increases only when Copilot CLI attempts to connect or reconnect to the server. Successful\
  \ and failed attempts both count. Calling tools from the same connected server multiple times does not increase the count.\n\
  \ Plugin metrics count only skill invocations associated with a plugin. Every plugin interaction therefore also appears\
  \ in the skill totals, but skill interactions that do not come from a plugin appear only in the skill totals. Because the\
  \ plugin totals are a subset of the skill totals, you should not add the two together.\n Empty arrays and zero counts indicate\
  \ no matching activity. The fields are null or absent when customization data is unavailable.\n Reports are available to\
  \ enterprise owners and billing managers, organization owners, and anyone with a custom organization or enterprise role\
  \ that grants the View Copilot Metrics permission. The Copilot usage metrics policy must be enabled.\n\n Visit the Copilot\
  \ usage metrics API documentation to get started.\n\n\n\n The post Agentic CLI customizations now in the usage metrics API\
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
- at: '2026-09-17T21:08:50Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-17T23:40:50Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-17-agentic-cli-customizations-now-in-the-usage-metrics-api
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-17T23:40:30Z'
  url: https://github.blog/changelog/2026-09-17-agentic-cli-customizations-now-in-the-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-18T06:57:05Z'
  url: https://github.blog/changelog/2026-09-17-agentic-cli-customizations-now-in-the-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-18T13:29:34Z'
  url: https://github.blog/changelog/2026-09-17-agentic-cli-customizations-now-in-the-usage-metrics-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub Copilot expands existing CLI report coverage with agentic activity metrics for skills,\
  \ custom agents, Model Context Protocol (MCP) servers, slash commands, and plugins.\n\n\n What’s new\n The fields appear\
  \ in enterprise and organization per-user and aggregate 1-day reports, per-user 28-day reports, and the day_totals entries\
  \ in aggregate 28-day reports.\n\n\n In a per-user report, the fields answer two questions about that user’s activity. In\
  \ an aggregate report, they answer the same questions across the enterprise or organization:\n\n\n\n Which items are used\
  \ most? The totals_by_skill , totals_by_custom_agent , totals_by_mcp , totals_by_slash_cmd , and totals_by_plugin arrays\
  \ list up to five items with the most recorded activity. Each entry includes an interaction_count . Depending on the category,\
  \ this counts invocations for skills, slash commands, and plugin skills, plus custom agent starts and MCP server connection\
  \ attempts.\n How many different items were used? The distinct_skill_use_count , distinct_custom_agent_use_count , distinct_mcp_use_count\
  \ , distinct_slash_cmd_use_count , and distinct_plugin_use_count fields count the number of different items used. In a per-user\
  \ report, each item that user used counts once. In an aggregate report, each item used by anyone in the enterprise or organization\
  \ counts once, not once per user. These counts include items outside the top five, and comparing them over time shows whether\
  \ the variety of items in use is growing.\n\n Why this matters\n Enterprise and organization administrators are now able\
  \ to identify which Copilot CLI customizations are gaining traction, find enablement gaps, and focus investment on automations\
  \ that developers find valuable.\n\n\n Important notes\n\n Names for recognized GitHub-provided items are shown. To protect\
  \ privacy, customer-defined names are not shown. Skills, custom agents, MCP servers, and plugins are grouped under other\
  \ . Copilot CLI telemetry already groups customer-defined slash commands under custom , so reports use that label for slash\
  \ commands.\n For MCP servers, interaction_count increases only when Copilot CLI attempts to connect or reconnect to the\
  \ server. Successful and failed attempts both count. Calling tools from the same connected server multiple times does not\
  \ increase the count.\n Plugin metrics count only skill invocations associated with a plugin. Every plugin interaction therefore\
  \ also appears in the skill totals, but skill interactions that do not come from a plugin appear only in the skill totals.\
  \ Because the plugin totals are a subset of the skill totals, you should not add the two together.\n Empty arrays and zero\
  \ counts indicate no matching activity. The fields are null or absent when customization data is unavailable.\n Reports\
  \ are available to enterprise owners and billing managers, organization owners, and anyone with a custom organization or\
  \ enterprise role that grants the View Copilot Metrics permission. The Copilot usage metrics policy must be enabled.\n\n\
  \ Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post Agentic CLI customizations now in the\
  \ usage metrics API appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
