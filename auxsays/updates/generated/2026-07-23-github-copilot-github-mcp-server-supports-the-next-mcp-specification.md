---
layout: aux-update
title: GitHub / Copilot GitHub MCP Server supports the next MCP specification official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/github-mcp-server-supports-the-next-mcp-specification/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-23-github-mcp-server-supports-the-next-mcp-specification
update_download_url: ''
update_version: GitHub MCP Server supports the next MCP specification
update_logo_text: GIT
update_published_at: '2026-07-23T20:38:22Z'
update_last_checked: '2026-07-24T08:45:16Z'
source_last_checked: '2026-07-24T08:45:16Z'
official_body_last_checked: '2026-07-24T08:45:16Z'
record_last_updated: '2026-07-24T08:45:16Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub MCP Server supports the next MCP specification
update_detail_title: GitHub / Copilot GitHub MCP Server supports the next MCP specification
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub MCP Server supports the next MCP specification has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub MCP Server supports the next MCP specification.
release_summary: "The MCP protocol is going stateless on 28th July 2026, and the GitHub MCP Server supports the latest spec\
  \ ahead of the official release.\n\n\n What’s changing\n\n The new stateless core means MCP deployments are now easy to\
  \ scale.\n Extensions unlock innovation (e.g., MCP apps and Enterprise Managed Auth, both of which are already supported\
  \ by VS Code).\n Sessions and initialize are both removed, so you can connect to servers faster and easier. Clients can\
  \ also complete the handshake in parallel.\n You’ll see more remote servers supporting features like elicitation thanks\
  \ to multi round-trip requests.\n\n Since all tier 1 SDKs have preserved backwards compatibility and they have all already\
  \ shipped beta support, you don’t need to do anything to maintain support. The GitHub MCP server uses the official Go SDK\
  \ .\n\n\n For GitHub MCP Server, we made three changes:\n\n\n\n Removed Redis sessions : Database writes on initialize are\
  \ gone, and database reads are gone from every call, which makes things snappier without users losing anything.\n\n\n Avoided\
  \ deep packet inspection : We need to read some values from MCP requests for logging and secret scanning. In the new spec\
  \ we can do that from HTTP headers guaranteed to be present. That means no more inspecting the payload of every single request\
  \ before the SDK does.\n\n\n\n\n Upgraded our elicitation implementation : Our stdio MCP server uses URL elicitation for\
  \ easy user login. In the new protocol version, each step is a separate HTTP request. To make this work with old and new\
  \ clients, the Go SDK provides a wrapper that makes both mechanisms work.\n\n\n\n\n In addition, MCP added official conformance\
  \ tests. Strict validation helps agents to verify their work. To use this, point Copilot at your codebase and provide access\
  \ to:\n\n\n\n The conformance suite\n The draft spec documentation\n Any tier 1 SDK implementation\n\n This is a huge boost\
  \ to all tiers of the official SDK, and to bespoke clients and servers too, because AI assisted development is much easier\
  \ to verify with these tests.\n\n\n GitHub support\n GitHub MCP Server already supports the latest spec ahead of the official\
  \ release.\n\n\n Additional info\n To learn more, see the blog post about this release .\n\n\n\n The post GitHub MCP Server\
  \ supports the next MCP specification appeared first on The GitHub Blog ."
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
- at: '2026-07-23T20:38:22Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-24T08:45:24Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-23-github-mcp-server-supports-the-next-mcp-specification
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-24T08:45:16Z'
  url: https://github.blog/changelog/2026-07-23-github-mcp-server-supports-the-next-mcp-specification
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The MCP protocol is going stateless on 28th July 2026, and the GitHub MCP Server supports the\
  \ latest spec ahead of the official release.\n\n\n What’s changing\n\n The new stateless core means MCP deployments are\
  \ now easy to scale.\n Extensions unlock innovation (e.g., MCP apps and Enterprise Managed Auth, both of which are already\
  \ supported by VS Code).\n Sessions and initialize are both removed, so you can connect to servers faster and easier. Clients\
  \ can also complete the handshake in parallel.\n You’ll see more remote servers supporting features like elicitation thanks\
  \ to multi round-trip requests.\n\n Since all tier 1 SDKs have preserved backwards compatibility and they have all already\
  \ shipped beta support, you don’t need to do anything to maintain support. The GitHub MCP server uses the official Go SDK\
  \ .\n\n\n For GitHub MCP Server, we made three changes:\n\n\n\n Removed Redis sessions : Database writes on initialize are\
  \ gone, and database reads are gone from every call, which makes things snappier without users losing anything.\n\n\n Avoided\
  \ deep packet inspection : We need to read some values from MCP requests for logging and secret scanning. In the new spec\
  \ we can do that from HTTP headers guaranteed to be present. That means no more inspecting the payload of every single request\
  \ before the SDK does.\n\n\n\n\n Upgraded our elicitation implementation : Our stdio MCP server uses URL elicitation for\
  \ easy user login. In the new protocol version, each step is a separate HTTP request. To make this work with old and new\
  \ clients, the Go SDK provides a wrapper that makes both mechanisms work.\n\n\n\n\n In addition, MCP added official conformance\
  \ tests. Strict validation helps agents to verify their work. To use this, point Copilot at your codebase and provide access\
  \ to:\n\n\n\n The conformance suite\n The draft spec documentation\n Any tier 1 SDK implementation\n\n This is a huge boost\
  \ to all tiers of the official SDK, and to bespoke clients and servers too, because AI assisted development is much easier\
  \ to verify with these tests.\n\n\n GitHub support\n GitHub MCP Server already supports the latest spec ahead of the official\
  \ release.\n\n\n Additional info\n To learn more, see the blog post about this release .\n\n\n\n The post GitHub MCP Server\
  \ supports the next MCP specification appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
