---
layout: aux-update
title: GitHub / Copilot Client telemetry user attribution and configurable capture official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Client telemetry user attribution and configurable
  capture.
permalink: /updates/github/github/client-telemetry-user-attribution-and-configurable-capture/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-12-client-telemetry-user-attribution-and-configurable-capture
update_download_url: ''
update_version: Client telemetry user attribution and configurable capture
update_logo_text: GIT
update_published_at: '2026-10-12T22:38:00Z'
update_last_checked: '2026-10-14T19:51:40Z'
source_last_checked: '2026-10-14T19:51:40Z'
official_body_last_checked: '2026-10-14T19:51:40Z'
record_last_updated: '2026-10-14T19:51:40Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Client telemetry user attribution and configurable capture
update_detail_title: GitHub / Copilot Client telemetry user attribution and configurable capture
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Client telemetry user attribution and configurable capture has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Client telemetry user attribution and configurable capture.
release_summary: "Enterprise administrators can now use telemetry in managed settings to attribute GitHub Copilot activity\
  \ to a user without collecting their prompts, responses, or tool content.\n\n\n The telemetry.capture.identity setting adds\
  \ three attributes to OpenTelemetry (OTel) data:\n\n\n\n user.name : The authenticated Copilot account name, currently the\
  \ GitHub login.\n process.user.name : The local operating-system account.\n host.name : The local machine name.\n\n Identity\
  \ capture is off by default and remains separate from the existing pseudonymous user identifier. Fine-grained capture controls\
  \ are available in Copilot CLI, the GitHub Copilot app, and VS Code sessions using Agent Host.\n\n\n Administrators can\
  \ also independently control five additional capture classes:\n\n\n\n prompts : User, system, and developer prompts and\
  \ supported input context.\n responses : Assistant responses and supported reasoning content.\n toolArguments : Raw tool\
  \ arguments, commands, tool schemas, and identifiers for tools, MCP servers, plugins, and hooks.\n toolOutput : Tool results\
  \ and execution-error details.\n policyDetail : Raw policy details such as sandbox filesystem paths.\n\n Every capture class\
  \ is off by default. Explicit managed values take precedence over local settings, SDK configuration, and environment variables.\
  \ The existing captureContent setting remains available as a legacy shorthand for the five content classes, but it never\
  \ enables identity.\n\n\n Prompt, tool, and policy capture can include source code, file contents, commands, tool results,\
  \ and workspace or user-profile paths. Enable only the classes required for your audit use case and send them to an approved\
  \ collection endpoint.\n\n\n To learn more, see the enterprise managed settings reference and monitor agent usage with OpenTelemetry\
  \ .\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post Client telemetry user attribution and configurable\
  \ capture appeared first on The GitHub Blog ."
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
- at: '2026-10-12T22:38:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-14T19:52:01Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-12-client-telemetry-user-attribution-and-configurable-capture
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-14T19:51:40Z'
  url: https://github.blog/changelog/2026-10-12-client-telemetry-user-attribution-and-configurable-capture
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Enterprise administrators can now use telemetry in managed settings to attribute GitHub Copilot\
  \ activity to a user without collecting their prompts, responses, or tool content.\n\n\n The telemetry.capture.identity\
  \ setting adds three attributes to OpenTelemetry (OTel) data:\n\n\n\n user.name : The authenticated Copilot account name,\
  \ currently the GitHub login.\n process.user.name : The local operating-system account.\n host.name : The local machine\
  \ name.\n\n Identity capture is off by default and remains separate from the existing pseudonymous user identifier. Fine-grained\
  \ capture controls are available in Copilot CLI, the GitHub Copilot app, and VS Code sessions using Agent Host.\n\n\n Administrators\
  \ can also independently control five additional capture classes:\n\n\n\n prompts : User, system, and developer prompts\
  \ and supported input context.\n responses : Assistant responses and supported reasoning content.\n toolArguments : Raw\
  \ tool arguments, commands, tool schemas, and identifiers for tools, MCP servers, plugins, and hooks.\n toolOutput : Tool\
  \ results and execution-error details.\n policyDetail : Raw policy details such as sandbox filesystem paths.\n\n Every capture\
  \ class is off by default. Explicit managed values take precedence over local settings, SDK configuration, and environment\
  \ variables. The existing captureContent setting remains available as a legacy shorthand for the five content classes, but\
  \ it never enables identity.\n\n\n Prompt, tool, and policy capture can include source code, file contents, commands, tool\
  \ results, and workspace or user-profile paths. Enable only the classes required for your audit use case and send them to\
  \ an approved collection endpoint.\n\n\n To learn more, see the enterprise managed settings reference and monitor agent\
  \ usage with OpenTelemetry .\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post Client telemetry user\
  \ attribution and configurable capture appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
