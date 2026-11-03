---
layout: aux-update
title: GitHub / Copilot pull_request_target blocked by default December 2 official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for pull_request_target blocked by default December
  2.
permalink: /updates/github/github/pull-request-target-blocked-by-default-december-2/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2
update_download_url: ''
update_version: pull_request_target blocked by default December 2
update_logo_text: GIT
update_published_at: '2026-11-02T15:14:46Z'
update_last_checked: '2026-11-02T18:47:58Z'
source_last_checked: '2026-11-03T17:12:24Z'
official_body_last_checked: '2026-11-03T17:12:24Z'
record_last_updated: '2026-11-02T18:47:58Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot pull_request_target blocked by default December 2
update_detail_title: GitHub / Copilot pull_request_target blocked by default December 2
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot pull_request_target blocked by default December 2 has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot pull_request_target blocked by default December 2.
release_summary: "Starting December 2, 2026, GitHub Actions will block pull_request_target events by default in all public\
  \ repositories, unless an applicable Actions event policy explicitly allows them. Enforcement was previously scheduled for\
  \ November 2, 2026.\n\n\n GitHub introduced this default rule through workflow execution protections. The rule initially\
  \ runs in evaluate mode, so you can see which workflow runs it would block before enforcement begins.\n\n\n Private and\
  \ internal repositories aren’t affected.\n\n\n Why we’re making this change\n pull_request_target runs in the context of\
  \ the base repository and can access its secrets. If a workflow executes untrusted code from a fork, that code could compromise\
  \ your pipeline or steal secrets. The default rule helps reduce this risk while letting you explicitly allow workflows that\
  \ depend on the trigger.\n\n\n Brownout schedule\n Before permanent enforcement begins on December 2, 2026, we’ll temporarily\
  \ enforce the default protection during two scheduled brownouts. These windows will help you identify affected workflows\
  \ and update your policies before enforcement becomes permanent.\n\n\n\n\n\n Date\n Time (UTC)\n\n\n\n\n November 9, 2026\n\
  \ 16:00–18:00\n\n\n November 16, 2026\n 16:00–18:00\n\n\n\n During each window, pull_request_target workflow attempts blocked\
  \ by the default rule in affected public repositories will create failed runs with an error annotation; the workflows won’t\
  \ execute. After each window, the default rule will return to evaluate mode, allowing workflows to run with warnings. Private\
  \ and internal repositories aren’t affected.\n\n\n Prepare your workflows\n Before the first brownout on November 9, use\
  \ Insights to see which workflow runs the rule would block. From there, you have two options:\n\n\n\n Keep the default rule\
  \ in place to block pull_request_target .\n Explicitly allow pull_request_target in an applicable Actions event policy if\
  \ your workflows depend on it. Use workflow file targeting to allow specific workflows.\n\n See how to control workflow\
  \ execution to configure your policies.\n\n\n This change applies to public repositories on GitHub Free, GitHub Team, and\
  \ GitHub Enterprise Cloud, not GitHub Enterprise Server.\n\n\n\n The post pull_request_target blocked by default December\
  \ 2 appeared first on The GitHub Blog ."
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
- at: '2026-11-02T15:14:46Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-02T18:48:20Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-02T18:47:58Z'
  url: https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-03T03:58:54Z'
  url: https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-03T17:12:24Z'
  url: https://github.blog/changelog/2026-11-02-pull_request_target-blocked-by-default-december-2
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Starting December 2, 2026, GitHub Actions will block pull_request_target events by default in\
  \ all public repositories, unless an applicable Actions event policy explicitly allows them. Enforcement was previously\
  \ scheduled for November 2, 2026.\n\n\n GitHub introduced this default rule through workflow execution protections. The\
  \ rule initially runs in evaluate mode, so you can see which workflow runs it would block before enforcement begins.\n\n\
  \n Private and internal repositories aren’t affected.\n\n\n Why we’re making this change\n pull_request_target runs in the\
  \ context of the base repository and can access its secrets. If a workflow executes untrusted code from a fork, that code\
  \ could compromise your pipeline or steal secrets. The default rule helps reduce this risk while letting you explicitly\
  \ allow workflows that depend on the trigger.\n\n\n Brownout schedule\n Before permanent enforcement begins on December\
  \ 2, 2026, we’ll temporarily enforce the default protection during two scheduled brownouts. These windows will help you\
  \ identify affected workflows and update your policies before enforcement becomes permanent.\n\n\n\n\n\n Date\n Time (UTC)\n\
  \n\n\n\n November 9, 2026\n 16:00–18:00\n\n\n November 16, 2026\n 16:00–18:00\n\n\n\n During each window, pull_request_target\
  \ workflow attempts blocked by the default rule in affected public repositories will create failed runs with an error annotation;\
  \ the workflows won’t execute. After each window, the default rule will return to evaluate mode, allowing workflows to run\
  \ with warnings. Private and internal repositories aren’t affected.\n\n\n Prepare your workflows\n Before the first brownout\
  \ on November 9, use Insights to see which workflow runs the rule would block. From there, you have two options:\n\n\n\n\
  \ Keep the default rule in place to block pull_request_target .\n Explicitly allow pull_request_target in an applicable\
  \ Actions event policy if your workflows depend on it. Use workflow file targeting to allow specific workflows.\n\n See\
  \ how to control workflow execution to configure your policies.\n\n\n This change applies to public repositories on GitHub\
  \ Free, GitHub Team, and GitHub Enterprise Cloud, not GitHub Enterprise Server.\n\n\n\n The post pull_request_target blocked\
  \ by default December 2 appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
