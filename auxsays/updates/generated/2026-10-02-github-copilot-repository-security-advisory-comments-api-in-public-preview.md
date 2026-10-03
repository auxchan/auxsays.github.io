---
layout: aux-update
title: GitHub / Copilot Repository security advisory comments API in public preview official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Repository security advisory comments API in
  public preview.
permalink: /updates/github/github/repository-security-advisory-comments-api-in-public-preview/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-02-repository-security-advisory-comments-api-in-public-preview
update_download_url: ''
update_version: Repository security advisory comments API in public preview
update_logo_text: GIT
update_published_at: '2026-10-02T13:15:25Z'
update_last_checked: '2026-10-03T14:22:37Z'
source_last_checked: '2026-10-03T14:22:37Z'
official_body_last_checked: '2026-10-03T14:22:37Z'
record_last_updated: '2026-10-03T14:22:37Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Repository security advisory comments API in public preview
update_detail_title: GitHub / Copilot Repository security advisory comments API in public preview
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Repository security advisory comments API in public preview has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Repository security advisory comments API in public preview.
release_summary: "You can now read, add, and edit comments on repository security advisories using the REST API, including\
  \ advisories created from private vulnerability reports.\n\n\n Until now, the discussion on an advisory was only reachable\
  \ in the web UI, even though it often holds the most useful triage context on a vulnerability report. With the new endpoints,\
  \ you can:\n\n\n\n List the comments on a repository security advisory, optionally limited to those updated since a given\
  \ time.\n Get a single comment.\n Add a comment.\n Edit a comment.\n\n Repository security advisory responses also now include\
  \ a comments count, and global advisory responses include the count for their linked repository advisory, so you can tell\
  \ which advisories have discussion before you fetch it. These fields count non-confidential comments and help identify advisories\
  \ with comment activity before fetching the comments.\n\n\n This helps you export advisory discussions for audits and migrations,\
  \ automatically add triage notes, and build advisory workflows that work the same way as the ones you already have for issues\
  \ and pull requests.\n\n\n A few things to know:\n\n\n\n Access follows the same rules as the advisory itself. You need\
  \ the repository security advisories scope, and anyone who can’t see an advisory can’t see its comments.\n Access requires\
  \ permission to view the advisory and the appropriate read or write repository security advisories permission or token scope.\
  \ Non-collaborators cannot view internal comments, and confidential comments are not returned by these REST endpoints.\n\
  \ Deleting comments isn’t supported yet through the API.\n\n This is available in public preview for public repositories\
  \ on GitHub Free, GitHub Pro, GitHub Team, and GitHub Enterprise Cloud.\n\n\n Learn more in our REST API docs .\n\n\n\n\
  \ The post Repository security advisory comments API in public preview appeared first on The GitHub Blog ."
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
- at: '2026-10-02T13:15:25Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-03T14:22:47Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-02-repository-security-advisory-comments-api-in-public-preview
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-03T14:22:37Z'
  url: https://github.blog/changelog/2026-10-02-repository-security-advisory-comments-api-in-public-preview
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now read, add, and edit comments on repository security advisories using the REST API,\
  \ including advisories created from private vulnerability reports.\n\n\n Until now, the discussion on an advisory was only\
  \ reachable in the web UI, even though it often holds the most useful triage context on a vulnerability report. With the\
  \ new endpoints, you can:\n\n\n\n List the comments on a repository security advisory, optionally limited to those updated\
  \ since a given time.\n Get a single comment.\n Add a comment.\n Edit a comment.\n\n Repository security advisory responses\
  \ also now include a comments count, and global advisory responses include the count for their linked repository advisory,\
  \ so you can tell which advisories have discussion before you fetch it. These fields count non-confidential comments and\
  \ help identify advisories with comment activity before fetching the comments.\n\n\n This helps you export advisory discussions\
  \ for audits and migrations, automatically add triage notes, and build advisory workflows that work the same way as the\
  \ ones you already have for issues and pull requests.\n\n\n A few things to know:\n\n\n\n Access follows the same rules\
  \ as the advisory itself. You need the repository security advisories scope, and anyone who can’t see an advisory can’t\
  \ see its comments.\n Access requires permission to view the advisory and the appropriate read or write repository security\
  \ advisories permission or token scope. Non-collaborators cannot view internal comments, and confidential comments are not\
  \ returned by these REST endpoints.\n Deleting comments isn’t supported yet through the API.\n\n This is available in public\
  \ preview for public repositories on GitHub Free, GitHub Pro, GitHub Team, and GitHub Enterprise Cloud.\n\n\n Learn more\
  \ in our REST API docs .\n\n\n\n The post Repository security advisory comments API in public preview appeared first on\
  \ The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
