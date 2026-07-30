---
layout: aux-update
title: GitHub / Copilot CodeQL 2.26.1 improves analysis accuracy and framework coverage official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/codeql-2-26-1-improves-analysis-accuracy-and-framework-coverage/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-29-codeql-2-26-1-improves-analysis-accuracy-and-framework-coverage
update_download_url: ''
update_version: CodeQL 2.26.1 improves analysis accuracy and framework coverage
update_logo_text: GIT
update_published_at: '2026-07-29T09:45:11Z'
update_last_checked: '2026-07-29T14:34:41Z'
source_last_checked: '2026-07-30T03:47:44Z'
official_body_last_checked: '2026-07-30T03:47:44Z'
record_last_updated: '2026-07-29T14:34:41Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.26.1 improves analysis accuracy and framework coverage
update_detail_title: GitHub / Copilot CodeQL 2.26.1 improves analysis accuracy and framework coverage
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.26.1 improves analysis accuracy and framework coverage has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.26.1 improves analysis accuracy and framework coverage.
release_summary: "CodeQL is the static analysis engine behind GitHub code scanning , which finds and remediates security issues\
  \ in your code. We’ve recently released CodeQL 2.26.1 , which improves framework coverage for Go, Java/Kotlin, and JavaScript/TypeScript,\
  \ and reduces false positives in Rust analysis.\n\n\n Language and framework support\n C/C++\n\n\n\n Models-as-data flow\
  \ summaries now use fully qualified field names, such as MyNamespace::MyStruct::myField . Unqualified field names remain\
  \ supported but will be removed in 12 months.\n\n Go\n\n\n\n We’ve improved modeling for the log/slog package, including\
  \ slog.Logger methods, With , WithGroup , Attr , and Value . This expands coverage for applications using structured logging.\n\
  \n Java/Kotlin\n\n\n\n We’ve added source, sink, and flow summary models for org.apache.poi .\n\n JavaScript/TypeScript\n\
  \n\n\n We’ve added support for Angular’s @HostListener('window:message', ...) and @HostListener('document:message', ...)\
  \ decorators. CodeQL now recognizes the decorated method’s event parameter as a client-side remote flow source.\n\n Query\
  \ changes\n Go\n\n\n\n The improved log/slog modeling expands coverage for the go/log-injection and go/clear-text-logging\
  \ queries.\n\n Java/Kotlin\n\n\n\n The java/path-injection query now recognizes input validated with @javax.validation.constraints.Pattern\
  \ as sanitized, reducing false positives.\n The java/ssrf query now treats the first argument of Spring WebFlux’s WebClient.UriSpec.uri\
  \ method as a request forgery sink, which may produce additional valid alerts.\n\n JavaScript/TypeScript\n\n\n\n The js/missing-origin-check\
  \ query now analyzes Angular message event handlers declared with @HostListener .\n\n Rust\n\n\n\n The rust/hard-coded-cryptographic-value\
  \ query now treats arithmetic, bitwise, and string append operations as barriers. This reduces false positives when code\
  \ combines hard-coded constants with nonconstant data, such as when incrementing a nonce or appending variable data to a\
  \ constant prefix.\n\n For a full list of changes, please refer to the complete changelog for version 2.26.1 . Every new\
  \ version of CodeQL is automatically deployed to users of GitHub code scanning on github.com. The new functionality in CodeQL\
  \ 2.26.1 will also be included in a future GitHub Enterprise Server (GHES) release. If you use an older version of GHES,\
  \ you can manually upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.26.1 improves analysis accuracy and framework\
  \ coverage appeared first on The GitHub Blog ."
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
- at: '2026-07-29T09:45:11Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-29T14:34:44Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-29-codeql-2-26-1-improves-analysis-accuracy-and-framework-coverage
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-29T14:34:41Z'
  url: https://github.blog/changelog/2026-07-29-codeql-2-26-1-improves-analysis-accuracy-and-framework-coverage
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-30T03:47:44Z'
  url: https://github.blog/changelog/2026-07-29-codeql-2-26-1-improves-analysis-accuracy-and-framework-coverage
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL is the static analysis engine behind GitHub code scanning , which finds and remediates\
  \ security issues in your code. We’ve recently released CodeQL 2.26.1 , which improves framework coverage for Go, Java/Kotlin,\
  \ and JavaScript/TypeScript, and reduces false positives in Rust analysis.\n\n\n Language and framework support\n C/C++\n\
  \n\n\n Models-as-data flow summaries now use fully qualified field names, such as MyNamespace::MyStruct::myField . Unqualified\
  \ field names remain supported but will be removed in 12 months.\n\n Go\n\n\n\n We’ve improved modeling for the log/slog\
  \ package, including slog.Logger methods, With , WithGroup , Attr , and Value . This expands coverage for applications using\
  \ structured logging.\n\n Java/Kotlin\n\n\n\n We’ve added source, sink, and flow summary models for org.apache.poi .\n\n\
  \ JavaScript/TypeScript\n\n\n\n We’ve added support for Angular’s @HostListener('window:message', ...) and @HostListener('document:message',\
  \ ...) decorators. CodeQL now recognizes the decorated method’s event parameter as a client-side remote flow source.\n\n\
  \ Query changes\n Go\n\n\n\n The improved log/slog modeling expands coverage for the go/log-injection and go/clear-text-logging\
  \ queries.\n\n Java/Kotlin\n\n\n\n The java/path-injection query now recognizes input validated with @javax.validation.constraints.Pattern\
  \ as sanitized, reducing false positives.\n The java/ssrf query now treats the first argument of Spring WebFlux’s WebClient.UriSpec.uri\
  \ method as a request forgery sink, which may produce additional valid alerts.\n\n JavaScript/TypeScript\n\n\n\n The js/missing-origin-check\
  \ query now analyzes Angular message event handlers declared with @HostListener .\n\n Rust\n\n\n\n The rust/hard-coded-cryptographic-value\
  \ query now treats arithmetic, bitwise, and string append operations as barriers. This reduces false positives when code\
  \ combines hard-coded constants with nonconstant data, such as when incrementing a nonce or appending variable data to a\
  \ constant prefix.\n\n For a full list of changes, please refer to the complete changelog for version 2.26.1 . Every new\
  \ version of CodeQL is automatically deployed to users of GitHub code scanning on github.com. The new functionality in CodeQL\
  \ 2.26.1 will also be included in a future GitHub Enterprise Server (GHES) release. If you use an older version of GHES,\
  \ you can manually upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.26.1 improves analysis accuracy and framework\
  \ coverage appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
