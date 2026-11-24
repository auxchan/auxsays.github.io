---
layout: aux-update
title: GitHub / Copilot Usage reports will include a user ID column starting December 1 official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Usage reports will include a user ID column
  starting December 1.
permalink: /updates/github/github/usage-reports-will-include-a-user-id-column-starting-december-1/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-23-usage-reports-will-include-a-user-id-column-starting-december-1
update_download_url: ''
update_version: Usage reports will include a user ID column starting December 1
update_logo_text: GIT
update_published_at: '2026-11-23T10:29:36Z'
update_last_checked: '2026-11-24T12:51:38Z'
source_last_checked: '2026-11-24T12:51:38Z'
official_body_last_checked: '2026-11-24T12:51:38Z'
record_last_updated: '2026-11-24T12:51:38Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Usage reports will include a user ID column starting December 1
update_detail_title: GitHub / Copilot Usage reports will include a user ID column starting December 1
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Usage reports will include a user ID column starting December 1 has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Usage reports will include a user ID column starting December 1.
release_summary: "Starting December 1, 2026, usage reports that include a username column will also include a user_id column\
  \ next to it. Every column after username will move one position to the right.\n\n\n This change applies to the detailed\
  \ usage report, the AI usage report, and the premium request usage report, including exports you create with the GitHub\
  \ REST API. The summarized usage report won’t change.\n\n\n These changes apply to all GitHub Enterprise Cloud account types\
  \ and standalone organizations on GitHub Team.\n\n\n What you need to do\n If your scripts or tools read these reports by\
  \ column position, update them to read columns by header name before December 1.\n\n\n What’s changing\n The user_id column\
  \ contains the ID of the account that generated the usage, including bot accounts. It’s empty for usage that isn’t tied\
  \ to an account. With this column, you can:\n\n\n\n Identify usage from deleted accounts, which currently have an empty\
  \ username .\n Follow a user’s usage after they change their username.\n Match report rows to events in your audit log.\n\
  \n Usage from different deleted accounts will also appear on separate rows instead of combined in one row with an empty\
  \ username . We’ll calculate amounts the same way, but because we round each row separately, totals you add up from the\
  \ report may differ slightly in the last decimal places.\n\n\n To learn more, see Usage report fields .\n\n\n\n The post\
  \ Usage reports will include a user ID column starting December 1 appeared first on The GitHub Blog ."
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
- at: '2026-11-23T10:29:36Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-24T12:52:04Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-23-usage-reports-will-include-a-user-id-column-starting-december-1
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-24T12:51:38Z'
  url: https://github.blog/changelog/2026-11-23-usage-reports-will-include-a-user-id-column-starting-december-1
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Starting December 1, 2026, usage reports that include a username column will also include a user_id\
  \ column next to it. Every column after username will move one position to the right.\n\n\n This change applies to the detailed\
  \ usage report, the AI usage report, and the premium request usage report, including exports you create with the GitHub\
  \ REST API. The summarized usage report won’t change.\n\n\n These changes apply to all GitHub Enterprise Cloud account types\
  \ and standalone organizations on GitHub Team.\n\n\n What you need to do\n If your scripts or tools read these reports by\
  \ column position, update them to read columns by header name before December 1.\n\n\n What’s changing\n The user_id column\
  \ contains the ID of the account that generated the usage, including bot accounts. It’s empty for usage that isn’t tied\
  \ to an account. With this column, you can:\n\n\n\n Identify usage from deleted accounts, which currently have an empty\
  \ username .\n Follow a user’s usage after they change their username.\n Match report rows to events in your audit log.\n\
  \n Usage from different deleted accounts will also appear on separate rows instead of combined in one row with an empty\
  \ username . We’ll calculate amounts the same way, but because we round each row separately, totals you add up from the\
  \ report may differ slightly in the last decimal places.\n\n\n To learn more, see Usage report fields .\n\n\n\n The post\
  \ Usage reports will include a user ID column starting December 1 appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
