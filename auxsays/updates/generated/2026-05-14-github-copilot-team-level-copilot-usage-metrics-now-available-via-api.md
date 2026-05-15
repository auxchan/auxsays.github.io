---
layout: aux-update
title: GitHub / Copilot Team-level Copilot usage metrics now available via API official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/team-level-copilot-usage-metrics-now-available-via-api/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-14-team-level-copilot-usage-metrics-now-available-via-api
update_download_url: ''
update_version: Team-level Copilot usage metrics now available via API
update_logo_text: GIT
update_published_at: '2026-05-14T23:06:25Z'
update_last_checked: '2026-05-15T04:31:04Z'
source_last_checked: '2026-05-15T14:38:59Z'
official_body_last_checked: '2026-05-15T14:38:59Z'
record_last_updated: '2026-05-15T04:31:04Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Team-level Copilot usage metrics now available via API
update_detail_title: GitHub / Copilot Team-level Copilot usage metrics now available via API
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Team-level Copilot usage metrics now available via API has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Team-level Copilot usage metrics now available via API.
release_summary: "The Copilot usage metrics API now exposes a new user-teams report that maps each Copilot-licensed user to\
  \ the teams they belong to. By joining the user-teams report with the existing per-user usage report, enterprise administrators\
  \ and organization owners can produce team-level Copilot usage metrics for any team in their organization or enterprise.\
  \ This includes elements such as active users, completions, chats, as well as breakdowns by language, IDE, feature, and\
  \ model.\n\n\n How it works\n Two new endpoints return signed download URLs to NDJSON reports:\n\n\n\n GET /enterprises/{enterprise}/copilot/metrics/reports/user-teams-1-day\n\
  \ GET /orgs/{org}/copilot/metrics/reports/user-teams-1-day\n\n Each row in the user-teams report represents a team membership\
  \ for a given day, including the team’s enterprise or organization id, team slug, and the user’s ID and login. To produce\
  \ team-level metrics, join the user-teams report to the per-user usage report on user_id and day , then aggregate.\n\n\n\
  \ This release also introduces step-by-step guidance in the docs covering the join, day-level aggregation, and a rolling-window\
  \ pattern for multi-day reporting.\n\n\n Who can use this feature\n These metrics are available through the REST API to\
  \ enterprise administrators, organization owners, billing managers, and people with an enterprise custom role with the View\
  \ Enterprise Copilot Metrics permission.\n\n\n Key benefits\n\n Slice metrics by team : Pivot Copilot adoption, active users,\
  \ and code generation activity from org/enterprise totals down to any organization or enterprise team without building external\
  \ team attribution.\n Identify champions and gaps : See which teams are driving adoption and which need enablement, so you\
  \ can target campaigns and rollout investments.\n Full feature coverage : Team-level breakdowns are available across IDE\
  \ completions, chat, Copilot CLI, code review, and Copilot cloud agent activity. They can be cut by language, IDE, feature,\
  \ or model.\n\n Important notes\n\n User-teams reports are available through the REST API only. There is no dashboard surface\
  \ for team-level metrics in this release.\n Teams with fewer than five Copilot-seated users are excluded from the user-teams\
  \ report, though their members’ individual activity remains visible in the per-user usage report.\n Users who belong to\
  \ multiple teams will have their activity counted in each team’s aggregate, so team totals cannot be summed to reproduce\
  \ an organization or enterprise total.\n For step-by-step guidance, including the join recipe and rolling-window aggregation,\
  \ see Team-level Copilot usage metrics .\n\n Join the discussion within GitHub Community .\n\n\n\n The post Team-level Copilot\
  \ usage metrics now available via API appeared first on The GitHub Blog ."
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
- at: '2026-05-14T23:06:25Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-15T04:31:05Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-14-team-level-copilot-usage-metrics-now-available-via-api
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-15T04:31:04Z'
  url: https://github.blog/changelog/2026-05-14-team-level-copilot-usage-metrics-now-available-via-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-15T09:25:57Z'
  url: https://github.blog/changelog/2026-05-14-team-level-copilot-usage-metrics-now-available-via-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-15T14:38:59Z'
  url: https://github.blog/changelog/2026-05-14-team-level-copilot-usage-metrics-now-available-via-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The Copilot usage metrics API now exposes a new user-teams report that maps each Copilot-licensed\
  \ user to the teams they belong to. By joining the user-teams report with the existing per-user usage report, enterprise\
  \ administrators and organization owners can produce team-level Copilot usage metrics for any team in their organization\
  \ or enterprise. This includes elements such as active users, completions, chats, as well as breakdowns by language, IDE,\
  \ feature, and model.\n\n\n How it works\n Two new endpoints return signed download URLs to NDJSON reports:\n\n\n\n GET\
  \ /enterprises/{enterprise}/copilot/metrics/reports/user-teams-1-day\n GET /orgs/{org}/copilot/metrics/reports/user-teams-1-day\n\
  \n Each row in the user-teams report represents a team membership for a given day, including the team’s enterprise or organization\
  \ id, team slug, and the user’s ID and login. To produce team-level metrics, join the user-teams report to the per-user\
  \ usage report on user_id and day , then aggregate.\n\n\n This release also introduces step-by-step guidance in the docs\
  \ covering the join, day-level aggregation, and a rolling-window pattern for multi-day reporting.\n\n\n Who can use this\
  \ feature\n These metrics are available through the REST API to enterprise administrators, organization owners, billing\
  \ managers, and people with an enterprise custom role with the View Enterprise Copilot Metrics permission.\n\n\n Key benefits\n\
  \n Slice metrics by team : Pivot Copilot adoption, active users, and code generation activity from org/enterprise totals\
  \ down to any organization or enterprise team without building external team attribution.\n Identify champions and gaps\
  \ : See which teams are driving adoption and which need enablement, so you can target campaigns and rollout investments.\n\
  \ Full feature coverage : Team-level breakdowns are available across IDE completions, chat, Copilot CLI, code review, and\
  \ Copilot cloud agent activity. They can be cut by language, IDE, feature, or model.\n\n Important notes\n\n User-teams\
  \ reports are available through the REST API only. There is no dashboard surface for team-level metrics in this release.\n\
  \ Teams with fewer than five Copilot-seated users are excluded from the user-teams report, though their members’ individual\
  \ activity remains visible in the per-user usage report.\n Users who belong to multiple teams will have their activity counted\
  \ in each team’s aggregate, so team totals cannot be summed to reproduce an organization or enterprise total.\n For step-by-step\
  \ guidance, including the join recipe and rolling-window aggregation, see Team-level Copilot usage metrics .\n\n Join the\
  \ discussion within GitHub Community .\n\n\n\n The post Team-level Copilot usage metrics now available via API appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
