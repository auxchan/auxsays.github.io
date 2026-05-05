---
layout: aux-update
title: GitHub / Copilot Dependency scanning with GitHub MCP Server is in public preview official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/dependency-scanning-with-github-mcp-server-is-in-public-preview/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-05-dependency-scanning-with-github-mcp-server-is-in-public-preview
update_download_url: ''
update_version: Dependency scanning with GitHub MCP Server is in public preview
update_logo_text: GIT
update_published_at: '2026-05-05T20:45:38Z'
update_last_checked: '2026-05-05T21:45:07Z'
source_last_checked: '2026-05-05T21:45:07Z'
official_body_last_checked: '2026-05-05T21:45:07Z'
record_last_updated: '2026-05-05T21:45:07Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Dependency scanning with GitHub MCP Server is in public preview
update_detail_title: GitHub / Copilot Dependency scanning with GitHub MCP Server is in public preview
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Dependency scanning with GitHub MCP Server is in public preview has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Dependency scanning with GitHub MCP Server is in public preview.
release_summary: "The GitHub MCP Server can now scan your code changes for vulnerable dependencies before you commit or open\
  \ a pull request. You’ll catch known vulnerabilities while you write code with MCP-compatible IDEs and AI coding agents.\
  \ It’s now in public preview for repositories with Dependabot alerts enabled.\n\n\n How it works\n The dependency vulnerability\
  \ scanning tools ship as part of the GitHub MCP Server’s dependabot toolset. Once enabled, your AI coding agent can run\
  \ dependency vulnerability scanning based on your prompts. When you ask the agent to check for vulnerable dependencies,\
  \ it invokes the toolset, sends dependency information to the GitHub Advisory Database, and returns structured results with\
  \ affected packages, severity, and recommended fixed versions. For more thorough post-commit checks, the toolset can also\
  \ run the Dependabot CLI locally to diff dependency graphs before and after your changes.\n\n\n Get started\n\n Set up the\
  \ GitHub MCP Server in your developer environment and enable the dependabot toolset:\n\n In GitHub Copilot CLI, the GitHub\
  \ MCP Server is preinstalled. Run copilot --add-github-mcp-toolset dependabot to enable the dependabot toolset for your\
  \ session.\n In Visual Studio Code, add \"X-MCP-Toolsets\": \"dependabot\" to your GitHub MCP Server headers, or pick Dependabot\
  \ from the toolset selector in Copilot Chat.\n\n\n Install the advanced-security plugin for GitHub Copilot for a more tailored\
  \ dependency vulnerability scanning experience. For example:\n\n In GitHub Copilot CLI , run /plugin install advanced-security@copilot-plugins\
  \ .\n In Visual Studio Code, install the advanced-security agent plugin , then use /dependency-scanning in Copilot Chat\
  \ to start your prompt.\n\n\n Ask your agent to scan your current changes for vulnerable dependencies before you commit.\n\
  \n Here’s an example prompt you can use: Scan the dependencies I added on this branch for known vulnerabilities and tell\
  \ me which versions to upgrade to before I commit.\n\n\n Learn more\n\n Dependabot .\n GitHub Advisory Database .\n GitHub\
  \ MCP Server .\n\n Join the discussion within GitHub Community .\n\n\n\n The post Dependency scanning with GitHub MCP Server\
  \ is in public preview appeared first on The GitHub Blog ."
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
- at: '2026-05-05T20:45:38Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-05T21:45:07Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-05-dependency-scanning-with-github-mcp-server-is-in-public-preview
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-05T21:45:07Z'
  url: https://github.blog/changelog/2026-05-05-dependency-scanning-with-github-mcp-server-is-in-public-preview
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The GitHub MCP Server can now scan your code changes for vulnerable dependencies before you commit\
  \ or open a pull request. You’ll catch known vulnerabilities while you write code with MCP-compatible IDEs and AI coding\
  \ agents. It’s now in public preview for repositories with Dependabot alerts enabled.\n\n\n How it works\n The dependency\
  \ vulnerability scanning tools ship as part of the GitHub MCP Server’s dependabot toolset. Once enabled, your AI coding\
  \ agent can run dependency vulnerability scanning based on your prompts. When you ask the agent to check for vulnerable\
  \ dependencies, it invokes the toolset, sends dependency information to the GitHub Advisory Database, and returns structured\
  \ results with affected packages, severity, and recommended fixed versions. For more thorough post-commit checks, the toolset\
  \ can also run the Dependabot CLI locally to diff dependency graphs before and after your changes.\n\n\n Get started\n\n\
  \ Set up the GitHub MCP Server in your developer environment and enable the dependabot toolset:\n\n In GitHub Copilot CLI,\
  \ the GitHub MCP Server is preinstalled. Run copilot --add-github-mcp-toolset dependabot to enable the dependabot toolset\
  \ for your session.\n In Visual Studio Code, add \"X-MCP-Toolsets\": \"dependabot\" to your GitHub MCP Server headers, or\
  \ pick Dependabot from the toolset selector in Copilot Chat.\n\n\n Install the advanced-security plugin for GitHub Copilot\
  \ for a more tailored dependency vulnerability scanning experience. For example:\n\n In GitHub Copilot CLI , run /plugin\
  \ install advanced-security@copilot-plugins .\n In Visual Studio Code, install the advanced-security agent plugin , then\
  \ use /dependency-scanning in Copilot Chat to start your prompt.\n\n\n Ask your agent to scan your current changes for vulnerable\
  \ dependencies before you commit.\n\n Here’s an example prompt you can use: Scan the dependencies I added on this branch\
  \ for known vulnerabilities and tell me which versions to upgrade to before I commit.\n\n\n Learn more\n\n Dependabot .\n\
  \ GitHub Advisory Database .\n GitHub MCP Server .\n\n Join the discussion within GitHub Community .\n\n\n\n The post Dependency\
  \ scanning with GitHub MCP Server is in public preview appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
