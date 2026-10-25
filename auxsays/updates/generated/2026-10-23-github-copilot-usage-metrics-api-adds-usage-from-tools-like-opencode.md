---
layout: aux-update
title: GitHub / Copilot Usage metrics API adds usage from tools like OpenCode official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Usage metrics API adds usage from tools like
  OpenCode.
permalink: /updates/github/github/usage-metrics-api-adds-usage-from-tools-like-opencode/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-23-usage-metrics-api-adds-usage-from-tools-like-opencode
update_download_url: ''
update_version: Usage metrics API adds usage from tools like OpenCode
update_logo_text: GIT
update_published_at: '2026-10-23T23:42:03Z'
update_last_checked: '2026-10-24T00:07:24Z'
source_last_checked: '2026-10-25T14:14:31Z'
official_body_last_checked: '2026-10-25T14:14:31Z'
record_last_updated: '2026-10-24T00:07:24Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Usage metrics API adds usage from tools like OpenCode
update_detail_title: GitHub / Copilot Usage metrics API adds usage from tools like OpenCode
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Usage metrics API adds usage from tools like OpenCode has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Usage metrics API adds usage from tools like OpenCode.
release_summary: "The Copilot usage metrics API now reports model usage from more of the tools your developers use with Copilot,\
  \ including tools like OpenCode that weren’t previously captured in your reports. A new totals_by_client array is available\
  \ in the enterprise, organization, enterprise-user, and organization-user 1-day and 28-day reports.\n\n\n What’s new\n Each\
  \ totals_by_client entry represents one client and includes:\n\n\n\n client : The tool that sent the requests, such as opencode\
  \ , claude_code , codex , zed , copilot_cli , github_app , cloud_agent , code_review , vscode , or jetbrains . Unrecognized\
  \ clients are grouped under other .\n request_count : The number of successful model requests from the client.\n session_count\
  \ : The number of distinct sessions from the client.\n token_usage : Prompt tokens, output tokens, and average tokens per\
  \ request.\n totals_by_model : The same request and token metrics broken down by model, with a model_selection_mode that\
  \ shows whether the model was requested directly ( user_selected ), chosen by auto ( auto ), or chosen by the product (\
  \ product_selected ). Selection modes that aren’t reported individually yet appear as other , and values that can’t be normalized\
  \ appear as unknown .\n\n Why this matters\n More developers now use Copilot as the model provider behind tools outside\
  \ the IDE. Because those tools often don’t send editor telemetry, their usage was missing from totals_by_ide and hard to\
  \ account for. Counting requests on the server closes that gap, so you can see which tools drive Copilot usage, compare\
  \ request and token volume across them, and base tool support and governance decisions on real usage.\n\n\n This is different\
  \ from agent app activity , which counts jobs started by agent apps such as Claude and Codex on GitHub. totals_by_client\
  \ measures model traffic, meaning requests and tokens, from any tool that uses Copilot.\n\n\n Important notes\n\n Scope:\
  \ Enterprise, organization, enterprise-user, and organization-user reports, in both 1-day and 28-day versions. In the aggregated\
  \ 28-day reports, totals_by_client appears in each day_totals entry.\n Access: Available to enterprise owners and billing\
  \ managers, organization owners, and anyone with a custom organization or enterprise role that grants the View Copilot Metrics\
  \ permission. The Copilot usage metrics policy must be enabled.\n Copilot code review and Copilot cloud agent: Requests\
  \ from these clients report product_selected because the product chooses the model. Copilot code review models are reported\
  \ as unknown .\n Request counts: request_count counts model calls, not prompts. One prompt can trigger several model calls,\
  \ so don’t compare this field directly with prompt or interaction counts.\n Client identification: Clients are identified\
  \ by the integration ID they send with each request. Treat client as a best-effort grouping, not a verified identity.\n\
  \ Backward compatibility: This change is additive. Existing fields are unchanged, and totals_by_client is an empty array\
  \ when there is no usage to report.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post\
  \ Usage metrics API adds usage from tools like OpenCode appeared first on The GitHub Blog ."
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
- at: '2026-10-23T23:42:03Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-24T00:07:31Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-23-usage-metrics-api-adds-usage-from-tools-like-opencode
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-24T13:45:04Z'
  url: https://github.blog/changelog/2026-10-23-usage-metrics-api-adds-usage-from-tools-like-opencode
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-24T18:44:02Z'
  url: https://github.blog/changelog/2026-10-23-usage-metrics-api-adds-usage-from-tools-like-opencode
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-24T23:38:49Z'
  url: https://github.blog/changelog/2026-10-23-usage-metrics-api-adds-usage-from-tools-like-opencode
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-25T07:30:31Z'
  url: https://github.blog/changelog/2026-10-23-usage-metrics-api-adds-usage-from-tools-like-opencode
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-25T14:14:31Z'
  url: https://github.blog/changelog/2026-10-23-usage-metrics-api-adds-usage-from-tools-like-opencode
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The Copilot usage metrics API now reports model usage from more of the tools your developers use\
  \ with Copilot, including tools like OpenCode that weren’t previously captured in your reports. A new totals_by_client array\
  \ is available in the enterprise, organization, enterprise-user, and organization-user 1-day and 28-day reports.\n\n\n What’s\
  \ new\n Each totals_by_client entry represents one client and includes:\n\n\n\n client : The tool that sent the requests,\
  \ such as opencode , claude_code , codex , zed , copilot_cli , github_app , cloud_agent , code_review , vscode , or jetbrains\
  \ . Unrecognized clients are grouped under other .\n request_count : The number of successful model requests from the client.\n\
  \ session_count : The number of distinct sessions from the client.\n token_usage : Prompt tokens, output tokens, and average\
  \ tokens per request.\n totals_by_model : The same request and token metrics broken down by model, with a model_selection_mode\
  \ that shows whether the model was requested directly ( user_selected ), chosen by auto ( auto ), or chosen by the product\
  \ ( product_selected ). Selection modes that aren’t reported individually yet appear as other , and values that can’t be\
  \ normalized appear as unknown .\n\n Why this matters\n More developers now use Copilot as the model provider behind tools\
  \ outside the IDE. Because those tools often don’t send editor telemetry, their usage was missing from totals_by_ide and\
  \ hard to account for. Counting requests on the server closes that gap, so you can see which tools drive Copilot usage,\
  \ compare request and token volume across them, and base tool support and governance decisions on real usage.\n\n\n This\
  \ is different from agent app activity , which counts jobs started by agent apps such as Claude and Codex on GitHub. totals_by_client\
  \ measures model traffic, meaning requests and tokens, from any tool that uses Copilot.\n\n\n Important notes\n\n Scope:\
  \ Enterprise, organization, enterprise-user, and organization-user reports, in both 1-day and 28-day versions. In the aggregated\
  \ 28-day reports, totals_by_client appears in each day_totals entry.\n Access: Available to enterprise owners and billing\
  \ managers, organization owners, and anyone with a custom organization or enterprise role that grants the View Copilot Metrics\
  \ permission. The Copilot usage metrics policy must be enabled.\n Copilot code review and Copilot cloud agent: Requests\
  \ from these clients report product_selected because the product chooses the model. Copilot code review models are reported\
  \ as unknown .\n Request counts: request_count counts model calls, not prompts. One prompt can trigger several model calls,\
  \ so don’t compare this field directly with prompt or interaction counts.\n Client identification: Clients are identified\
  \ by the integration ID they send with each request. Treat client as a best-effort grouping, not a verified identity.\n\
  \ Backward compatibility: This change is additive. Existing fields are unchanged, and totals_by_client is an empty array\
  \ when there is no usage to report.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\n\n The post\
  \ Usage metrics API adds usage from tools like OpenCode appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
