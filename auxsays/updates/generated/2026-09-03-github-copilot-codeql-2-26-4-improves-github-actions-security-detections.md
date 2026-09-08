---
layout: aux-update
title: GitHub / Copilot CodeQL 2.26.4 improves GitHub actions security detections official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for CodeQL 2.26.4 improves GitHub actions security
  detections.
permalink: /updates/github/github/codeql-2-26-4-improves-github-actions-security-detections/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-03-codeql-2-26-4-improves-github-actions-security-detections
update_download_url: ''
update_version: CodeQL 2.26.4 improves GitHub actions security detections
update_logo_text: GIT
update_published_at: '2026-09-03T14:04:59Z'
update_last_checked: '2026-09-03T18:14:11Z'
source_last_checked: '2026-09-03T21:57:51Z'
official_body_last_checked: '2026-09-03T21:57:51Z'
record_last_updated: '2026-09-03T18:14:11Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.26.4 improves GitHub actions security detections
update_detail_title: GitHub / Copilot CodeQL 2.26.4 improves GitHub actions security detections
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.26.4 improves GitHub actions security detections has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.26.4 improves GitHub actions security detections.
release_summary: "CodeQL is the static analysis engine behind GitHub code scanning, which finds and remediates security issues\
  \ in your code. We’ve recently released CodeQL 2.26.4 , which adds support for Go 1.27, improves alert locations for Rust\
  \ data flow queries, and includes accuracy improvements across C#, Java/Kotlin, and GitHub Actions.\n\n\n Language and framework\
  \ support\n Go\n\n\n\n CodeQL now supports Go 1.27.\n\n Rust\n\n\n\n Alert locations for data flow queries are now more\
  \ precise and are based on the actual source and sink nodes. Some alerts will change location, so they’ll appear as new\
  \ alerts while the previous alerts close.\n\n Java/Kotlin\n\n\n\n We’ve added SQL injection sink models for Spring R2DBC\
  \ DatabaseClient and the R2DBC SPI.\n Taint now propagates through calls to String.valueOf(Object) when the argument is\
  \ a CharSequence (e.g., a String or a StringBuilder ).\n\n JavaScript/TypeScript\n\n\n\n We’ve added support for regular\
  \ expressions using the d flag and for the React Native Worklets 'worklet' directive.\n\n Python\n\n\n\n We’ve added taint\
  \ flow through list.extend and list.insert , matching the existing taint flow through list.append .\n\n Query changes\n\
  \ C#\n\n\n\n The cs/web/missing-token-validation query now recognizes enabled ASP.NET Core RequireAntiforgeryToken attributes\
  \ when antiforgery middleware is used.\n The cs/virtual-call-in-constructor query no longer reports uses of virtual members\
  \ in nameof expressions, since they aren’t calls.\n The cs/useless-cast-to-self and cs/simplifiable-boolean-expression queries\
  \ produce fewer false positives in build-mode: none databases.\n\n GitHub Actions\n\n\n\n Checks on actor fields read from\
  \ the event payload (e.g., github.event.pull_request.user.login ) now only count as protection for events that actually\
  \ populate that field. This may produce more alerts for queries that use the ControlCheck class.\n The actions/unpinned-tag\
  \ query now detects mutable references to reusable workflows.\n You can now specify EnvironmentCheck through a models-as-data\
  \ model. Queries using ControlCheck may find more results when an environment is no longer a sufficient sanitizer.\n\n For\
  \ a full list of changes, please refer to the complete changelog for version 2.26.4 . Every new version of CodeQL is automatically\
  \ deployed to users of GitHub code scanning on github.com. The new functionality in CodeQL 2.26.4 will also be included\
  \ in a future GitHub Enterprise Server (GHES) release. If you use an older version of GHES, you can manually upgrade your\
  \ CodeQL version .\n\n\n\n The post CodeQL 2.26.4 improves GitHub actions security detections appeared first on The GitHub\
  \ Blog ."
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
- at: '2026-09-03T14:04:59Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-03T18:14:22Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-03-codeql-2-26-4-improves-github-actions-security-detections
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-03T18:14:11Z'
  url: https://github.blog/changelog/2026-09-03-codeql-2-26-4-improves-github-actions-security-detections
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-03T21:57:51Z'
  url: https://github.blog/changelog/2026-09-03-codeql-2-26-4-improves-github-actions-security-detections
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL is the static analysis engine behind GitHub code scanning, which finds and remediates security\
  \ issues in your code. We’ve recently released CodeQL 2.26.4 , which adds support for Go 1.27, improves alert locations\
  \ for Rust data flow queries, and includes accuracy improvements across C#, Java/Kotlin, and GitHub Actions.\n\n\n Language\
  \ and framework support\n Go\n\n\n\n CodeQL now supports Go 1.27.\n\n Rust\n\n\n\n Alert locations for data flow queries\
  \ are now more precise and are based on the actual source and sink nodes. Some alerts will change location, so they’ll appear\
  \ as new alerts while the previous alerts close.\n\n Java/Kotlin\n\n\n\n We’ve added SQL injection sink models for Spring\
  \ R2DBC DatabaseClient and the R2DBC SPI.\n Taint now propagates through calls to String.valueOf(Object) when the argument\
  \ is a CharSequence (e.g., a String or a StringBuilder ).\n\n JavaScript/TypeScript\n\n\n\n We’ve added support for regular\
  \ expressions using the d flag and for the React Native Worklets 'worklet' directive.\n\n Python\n\n\n\n We’ve added taint\
  \ flow through list.extend and list.insert , matching the existing taint flow through list.append .\n\n Query changes\n\
  \ C#\n\n\n\n The cs/web/missing-token-validation query now recognizes enabled ASP.NET Core RequireAntiforgeryToken attributes\
  \ when antiforgery middleware is used.\n The cs/virtual-call-in-constructor query no longer reports uses of virtual members\
  \ in nameof expressions, since they aren’t calls.\n The cs/useless-cast-to-self and cs/simplifiable-boolean-expression queries\
  \ produce fewer false positives in build-mode: none databases.\n\n GitHub Actions\n\n\n\n Checks on actor fields read from\
  \ the event payload (e.g., github.event.pull_request.user.login ) now only count as protection for events that actually\
  \ populate that field. This may produce more alerts for queries that use the ControlCheck class.\n The actions/unpinned-tag\
  \ query now detects mutable references to reusable workflows.\n You can now specify EnvironmentCheck through a models-as-data\
  \ model. Queries using ControlCheck may find more results when an environment is no longer a sufficient sanitizer.\n\n For\
  \ a full list of changes, please refer to the complete changelog for version 2.26.4 . Every new version of CodeQL is automatically\
  \ deployed to users of GitHub code scanning on github.com. The new functionality in CodeQL 2.26.4 will also be included\
  \ in a future GitHub Enterprise Server (GHES) release. If you use an older version of GHES, you can manually upgrade your\
  \ CodeQL version .\n\n\n\n The post CodeQL 2.26.4 improves GitHub actions security detections appeared first on The GitHub\
  \ Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
