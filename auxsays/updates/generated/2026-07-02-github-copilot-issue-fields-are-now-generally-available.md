---
layout: aux-update
title: GitHub / Copilot Issue fields are now generally available official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/issue-fields-are-now-generally-available/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-02-issue-fields-are-now-generally-available
update_download_url: ''
update_version: Issue fields are now generally available
update_logo_text: GIT
update_published_at: '2026-07-02T08:17:17Z'
update_last_checked: '2026-07-02T09:35:55Z'
source_last_checked: '2026-07-02T09:35:55Z'
official_body_last_checked: '2026-07-02T09:35:55Z'
record_last_updated: '2026-07-02T09:35:55Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Issue fields are now generally available
update_detail_title: GitHub / Copilot Issue fields are now generally available
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Issue fields are now generally available has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Issue fields are now generally available.
release_summary: "Issue fields are now generally available for all GitHub organizations on Free, Team, Enterprise, and GitHub\
  \ Enterprise Cloud with data residency plans and will ship in GitHub Enterprise Server 3.23. Issue fields bring structured,\
  \ typed metadata to issues, making it easy to track priority, effort, dates, and custom values consistently across your\
  \ organization.\n\n\n\n\n\n Since public preview in May , more than 40,000 organizations have adopted issue fields to add\
  \ structured metadata that’s searchable, reportable, and consistent across every repository.\n\n\n What’s new since public\
  \ preview:\n\n\n\n Issue fields on the issues list : Field values now appear directly on the repository issues list, so\
  \ you can scan priority, effort, and other metadata at a glance without opening each issue.\n Public project support : Issue\
  \ fields now work in public projects, with visibility controls so organizations can decide which fields are visible to nonmembers.\
  \ Logged-out users can also see public fields.\n MCP integration : Issue fields are now accessible through GitHub’s MCP\
  \ server , enabling AI tools like Copilot to read and set field values when creating or updating issues.\n Internationalization\
  \ : Field names now support non-English characters, matching parity with issue types.\n Bug fixes and reliability : Fixed\
  \ issues with field updates not reflecting in issue timestamps, project view sorting not updating when field option order\
  \ changes, fields not appearing correctly in exclusion autocomplete, and single-select options not displaying in the right\
  \ order with colors.\n\n Every organization automatically gets four default fields ( Priority , Effort , Start date , and\
  \ Target date ) that work out of the box. Organization admins can customize fields, add new ones, and configure which fields\
  \ appear on each issue type from Settings > Planning > Issue fields .\n\n\n To learn more, see the issue fields documentation\
  \ . Share feedback in the community discussion .\n\n\n Also in this release\n Edit history for issues and pull requests\
  \ is now limited to 100 entries\n GitHub now enforces a limit of 100 stored edits per content item for issues, issue comments,\
  \ pull requests, and pull request review comments. When a new edit pushes the count beyond 100, the oldest intermediate\
  \ edits are automatically removed while preserving the original content and the most recent 99 changes.\n\n\n This limit\
  \ aligns stored data with actual usage, where over 97% of API consumers never paginate beyond the first page. The original\
  \ content and most recent 99 edits are always preserved. The GraphQL userContentEdits connection and REST API continue to\
  \ work as before. This applies to all plans and will ship in GitHub Enterprise Server 3.23.\n\n\n\n The post Issue fields\
  \ are now generally available appeared first on The GitHub Blog ."
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
- at: '2026-07-02T08:17:17Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-02T09:35:58Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-02-issue-fields-are-now-generally-available
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-02T09:35:55Z'
  url: https://github.blog/changelog/2026-07-02-issue-fields-are-now-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Issue fields are now generally available for all GitHub organizations on Free, Team, Enterprise,\
  \ and GitHub Enterprise Cloud with data residency plans and will ship in GitHub Enterprise Server 3.23. Issue fields bring\
  \ structured, typed metadata to issues, making it easy to track priority, effort, dates, and custom values consistently\
  \ across your organization.\n\n\n\n\n\n Since public preview in May , more than 40,000 organizations have adopted issue\
  \ fields to add structured metadata that’s searchable, reportable, and consistent across every repository.\n\n\n What’s\
  \ new since public preview:\n\n\n\n Issue fields on the issues list : Field values now appear directly on the repository\
  \ issues list, so you can scan priority, effort, and other metadata at a glance without opening each issue.\n Public project\
  \ support : Issue fields now work in public projects, with visibility controls so organizations can decide which fields\
  \ are visible to nonmembers. Logged-out users can also see public fields.\n MCP integration : Issue fields are now accessible\
  \ through GitHub’s MCP server , enabling AI tools like Copilot to read and set field values when creating or updating issues.\n\
  \ Internationalization : Field names now support non-English characters, matching parity with issue types.\n Bug fixes and\
  \ reliability : Fixed issues with field updates not reflecting in issue timestamps, project view sorting not updating when\
  \ field option order changes, fields not appearing correctly in exclusion autocomplete, and single-select options not displaying\
  \ in the right order with colors.\n\n Every organization automatically gets four default fields ( Priority , Effort , Start\
  \ date , and Target date ) that work out of the box. Organization admins can customize fields, add new ones, and configure\
  \ which fields appear on each issue type from Settings > Planning > Issue fields .\n\n\n To learn more, see the issue fields\
  \ documentation . Share feedback in the community discussion .\n\n\n Also in this release\n Edit history for issues and\
  \ pull requests is now limited to 100 entries\n GitHub now enforces a limit of 100 stored edits per content item for issues,\
  \ issue comments, pull requests, and pull request review comments. When a new edit pushes the count beyond 100, the oldest\
  \ intermediate edits are automatically removed while preserving the original content and the most recent 99 changes.\n\n\
  \n This limit aligns stored data with actual usage, where over 97% of API consumers never paginate beyond the first page.\
  \ The original content and most recent 99 edits are always preserved. The GraphQL userContentEdits connection and REST API\
  \ continue to work as before. This applies to all plans and will ship in GitHub Enterprise Server 3.23.\n\n\n\n The post\
  \ Issue fields are now generally available appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
