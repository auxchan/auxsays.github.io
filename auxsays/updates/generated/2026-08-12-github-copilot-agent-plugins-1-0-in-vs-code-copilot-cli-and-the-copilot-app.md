---
layout: aux-update
title: GitHub / Copilot Agent Plugins 1.0 in VS Code, Copilot CLI, and the Copilot app official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app
update_download_url: ''
update_version: Agent Plugins 1.0 in VS Code, Copilot CLI, and the Copilot app
update_logo_text: GIT
update_published_at: '2026-08-12T18:39:11Z'
update_last_checked: '2026-08-12T20:43:03Z'
source_last_checked: '2026-08-13T20:28:29Z'
official_body_last_checked: '2026-08-13T20:28:29Z'
record_last_updated: '2026-08-12T20:43:03Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Agent Plugins 1.0 in VS Code, Copilot CLI, and the Copilot app
update_detail_title: GitHub / Copilot Agent Plugins 1.0 in VS Code, Copilot CLI, and the Copilot app
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Agent Plugins 1.0 in VS Code, Copilot CLI, and the Copilot app has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Agent Plugins 1.0 in VS Code, Copilot CLI, and the Copilot app.
release_summary: "You can now build a plugin once and use it across all compatible agent clients. We published Agent Plugins\
  \ 1.0 on August 6 with AWS, Anysphere, Microsoft, OpenAI, and Vercel. Google also joined as a core maintainer on the same\
  \ day. Agent Plugins 1.0 is an open standard that packages agent skills and MCP servers into one installable plugin that\
  \ is governed independently of any single vendor.\n\n\n Publishing a plugin for several agents was already possible, but\
  \ it cost you duplication. A plugin can bundle a skill with an MCP server, such as a deployment runbook and its tool integration.\
  \ While the skill and the server underneath were the same for every client, the packaging around them wasn’t, so you maintained\
  \ a separate manifest and directory layout for each one.\n\n\n Support is generally available in VS Code, Copilot CLI, the\
  \ GitHub Copilot SDK, and the GitHub Copilot app, on all Copilot plans.\n\n\n What you can do\n\n Install spec plugins from\
  \ a marketplace. You can find plugins in the Awesome Copilot marketplace , available by default in VS Code, Copilot CLI,\
  \ and the Copilot app.\n Share one plugin across tools. Compatible clients can discover the skills and MCP server configuration\
  \ they support from the same package.\n Keep your existing plugins. Existing GitHub Copilot plugins that don’t target Agent\
  \ Plugins 1.0 remain supported, with no migration required.\n\n Building or migrating a plugin\n If you maintain a plugin,\
  \ adopting the spec is mostly manifest work:\n\n\n\n Add $schema to plugin.json\n Keep skills under skills/ and MCP configuration\
  \ in mcp.json\n Move Copilot-specific files into the com.github.copilot/ directory, which other clients ignore\n\n That\
  \ last step is what keeps a plugin portable without giving anything up. The spec standardizes skills and MCP servers, so\
  \ Copilot capabilities beyond those live in the namespaced directory. Custom agents, commands, rules, and hooks load from\
  \ there across VS Code, Copilot CLI, and the Copilot app, and the CLI and app also load extensions such as canvases. One\
  \ package stays portable and keeps its Copilot behavior.\n\n\n See Build an Agent Plugin for the minimal package and where\
  \ each component goes, or start from the example plugin and migration guide .\n\n\n Govern plugins with the settings you\
  \ already use\n As plugins become portable across tools, organizations need a consistent way to manage which plugins are\
  \ available to developers. Copilot Business and Enterprise customers can use existing enterprise managed settings across\
  \ VS Code, Copilot CLI, the GitHub Copilot app, and Copilot cloud agent.\n\n\n In managed-settings.json , use enabledPlugins\
  \ to automatically install or block specific plugins, extraKnownMarketplaces to add marketplaces available to developers,\
  \ and strictKnownMarketplaces to restrict installation to managed marketplaces. Enterprise values establish a baseline,\
  \ and plugin and marketplace settings combine additively with approved team-specific overrides. To learn more, see our docs\
  \ on setting overrides for specific teams .\n\n\n If you already manage these plugin settings for supported Copilot clients,\
  \ they also apply to Agent Plugins 1.0. No separate Agent Plugins policy is required.\n\n\n Plugins can also carry MCP server\
  \ configurations, so pair this with MCP allowlists, which approve or block individual servers by URL, command, or name.\n\
  \n\n Learn more\n\n Plugins in VS Code\n Finding and installing plugins in Copilot CLI\n About GitHub Copilot plugins\n\
  \ Published Agent Plugins 1.0 specification\n\n\n The post Agent Plugins 1.0 in VS Code, Copilot CLI, and the Copilot app\
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
- at: '2026-08-12T18:39:11Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-12T20:43:08Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-12T20:43:03Z'
  url: https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-13T04:05:20Z'
  url: https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-13T14:56:50Z'
  url: https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-13T20:28:29Z'
  url: https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now build a plugin once and use it across all compatible agent clients. We published Agent\
  \ Plugins 1.0 on August 6 with AWS, Anysphere, Microsoft, OpenAI, and Vercel. Google also joined as a core maintainer on\
  \ the same day. Agent Plugins 1.0 is an open standard that packages agent skills and MCP servers into one installable plugin\
  \ that is governed independently of any single vendor.\n\n\n Publishing a plugin for several agents was already possible,\
  \ but it cost you duplication. A plugin can bundle a skill with an MCP server, such as a deployment runbook and its tool\
  \ integration. While the skill and the server underneath were the same for every client, the packaging around them wasn’t,\
  \ so you maintained a separate manifest and directory layout for each one.\n\n\n Support is generally available in VS Code,\
  \ Copilot CLI, the GitHub Copilot SDK, and the GitHub Copilot app, on all Copilot plans.\n\n\n What you can do\n\n Install\
  \ spec plugins from a marketplace. You can find plugins in the Awesome Copilot marketplace , available by default in VS\
  \ Code, Copilot CLI, and the Copilot app.\n Share one plugin across tools. Compatible clients can discover the skills and\
  \ MCP server configuration they support from the same package.\n Keep your existing plugins. Existing GitHub Copilot plugins\
  \ that don’t target Agent Plugins 1.0 remain supported, with no migration required.\n\n Building or migrating a plugin\n\
  \ If you maintain a plugin, adopting the spec is mostly manifest work:\n\n\n\n Add $schema to plugin.json\n Keep skills\
  \ under skills/ and MCP configuration in mcp.json\n Move Copilot-specific files into the com.github.copilot/ directory,\
  \ which other clients ignore\n\n That last step is what keeps a plugin portable without giving anything up. The spec standardizes\
  \ skills and MCP servers, so Copilot capabilities beyond those live in the namespaced directory. Custom agents, commands,\
  \ rules, and hooks load from there across VS Code, Copilot CLI, and the Copilot app, and the CLI and app also load extensions\
  \ such as canvases. One package stays portable and keeps its Copilot behavior.\n\n\n See Build an Agent Plugin for the minimal\
  \ package and where each component goes, or start from the example plugin and migration guide .\n\n\n Govern plugins with\
  \ the settings you already use\n As plugins become portable across tools, organizations need a consistent way to manage\
  \ which plugins are available to developers. Copilot Business and Enterprise customers can use existing enterprise managed\
  \ settings across VS Code, Copilot CLI, the GitHub Copilot app, and Copilot cloud agent.\n\n\n In managed-settings.json\
  \ , use enabledPlugins to automatically install or block specific plugins, extraKnownMarketplaces to add marketplaces available\
  \ to developers, and strictKnownMarketplaces to restrict installation to managed marketplaces. Enterprise values establish\
  \ a baseline, and plugin and marketplace settings combine additively with approved team-specific overrides. To learn more,\
  \ see our docs on setting overrides for specific teams .\n\n\n If you already manage these plugin settings for supported\
  \ Copilot clients, they also apply to Agent Plugins 1.0. No separate Agent Plugins policy is required.\n\n\n Plugins can\
  \ also carry MCP server configurations, so pair this with MCP allowlists, which approve or block individual servers by URL,\
  \ command, or name.\n\n\n Learn more\n\n Plugins in VS Code\n Finding and installing plugins in Copilot CLI\n About GitHub\
  \ Copilot plugins\n Published Agent Plugins 1.0 specification\n\n\n The post Agent Plugins 1.0 in VS Code, Copilot CLI,\
  \ and the Copilot app appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
