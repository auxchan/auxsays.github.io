---
layout: aux-update
title: GitHub / Copilot Separate GitHub Actions path for GitHub Code Quality official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/separate-github-actions-path-for-github-code-quality/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-20-separate-github-actions-path-for-github-code-quality
update_download_url: ''
update_version: Separate GitHub Actions path for GitHub Code Quality
update_logo_text: GIT
update_published_at: '2026-08-20T14:29:27Z'
update_last_checked: '2026-08-21T03:04:45Z'
source_last_checked: '2026-08-21T03:04:45Z'
official_body_last_checked: '2026-08-21T03:04:45Z'
record_last_updated: '2026-08-21T03:04:45Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Separate GitHub Actions path for GitHub Code Quality
update_detail_title: GitHub / Copilot Separate GitHub Actions path for GitHub Code Quality
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Separate GitHub Actions path for GitHub Code Quality has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Separate GitHub Actions path for GitHub Code Quality.
release_summary: "A dedicated workflow path for code quality CodeQL actions workflows is now generally available. Your workflow\
  \ run history and your Actions usage reports now tell GitHub Code Quality runs apart from GitHub code scanning runs. Code\
  \ Quality analysis runs on dynamic/github-code-quality/codeql and shows github-code-quality as the actor, instead of sharing\
  \ the dynamic/github-code-scanning/codeql path and the github-advanced-security actor with code scanning.\n\n\n What you\
  \ need to do\n Code Quality itself doesn’t need reconfiguration, and your enabled repositories keep scanning as they are.\
  \ If you’ve built anything on the old path or actor, you need to update it:\n\n\n\n Change Actions usage and billing reports\
  \ that filter on dynamic/github-code-scanning/codeql so they also account for dynamic/github-code-quality/codeql .\n Update\
  \ scripts, dashboards, or workflow run filters that identify Code Quality runs by the github-advanced-security actor.\n\n\
  \ GitHub Code Quality is available on GitHub Enterprise Cloud and GitHub Team, as well as on GitHub Enterprise Cloud with\
  \ data residency. To learn more, see GitHub Code Quality billing .\n\n\n Join the discussion within GitHub Community .\n\
  \n\n\n The post Separate GitHub Actions path for GitHub Code Quality appeared first on The GitHub Blog ."
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
- at: '2026-08-20T14:29:27Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-21T03:04:58Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-20-separate-github-actions-path-for-github-code-quality
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-21T03:04:45Z'
  url: https://github.blog/changelog/2026-08-20-separate-github-actions-path-for-github-code-quality
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "A dedicated workflow path for code quality CodeQL actions workflows is now generally available.\
  \ Your workflow run history and your Actions usage reports now tell GitHub Code Quality runs apart from GitHub code scanning\
  \ runs. Code Quality analysis runs on dynamic/github-code-quality/codeql and shows github-code-quality as the actor, instead\
  \ of sharing the dynamic/github-code-scanning/codeql path and the github-advanced-security actor with code scanning.\n\n\
  \n What you need to do\n Code Quality itself doesn’t need reconfiguration, and your enabled repositories keep scanning as\
  \ they are. If you’ve built anything on the old path or actor, you need to update it:\n\n\n\n Change Actions usage and billing\
  \ reports that filter on dynamic/github-code-scanning/codeql so they also account for dynamic/github-code-quality/codeql\
  \ .\n Update scripts, dashboards, or workflow run filters that identify Code Quality runs by the github-advanced-security\
  \ actor.\n\n GitHub Code Quality is available on GitHub Enterprise Cloud and GitHub Team, as well as on GitHub Enterprise\
  \ Cloud with data residency. To learn more, see GitHub Code Quality billing .\n\n\n Join the discussion within GitHub Community\
  \ .\n\n\n\n The post Separate GitHub Actions path for GitHub Code Quality appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
