---
layout: aux-update
title: GitHub / Copilot CodeQL 2.25.6 adds Swift 6.3.2 support and improves C# coverage official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/codeql-2-25-6-adds-swift-6-3-2-support-and-improves-c-coverage/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-05-codeql-2-25-6-adds-swift-6-3-2-support-and-improves-c-coverage
update_download_url: ''
update_version: CodeQL 2.25.6 adds Swift 6.3.2 support and improves C# coverage
update_logo_text: GIT
update_published_at: '2026-06-05T21:30:57Z'
update_last_checked: '2026-06-06T04:30:45Z'
source_last_checked: '2026-06-06T08:47:52Z'
official_body_last_checked: '2026-06-06T08:47:52Z'
record_last_updated: '2026-06-06T04:30:45Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.25.6 adds Swift 6.3.2 support and improves C# coverage
update_detail_title: GitHub / Copilot CodeQL 2.25.6 adds Swift 6.3.2 support and improves C# coverage
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.25.6 adds Swift 6.3.2 support and improves C# coverage has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.25.6 adds Swift 6.3.2 support and improves C# coverage.
release_summary: "CodeQL is the static analysis engine behind GitHub code scanning , which finds and remediates security issues\
  \ in your code. We’ve recently released CodeQL 2.25.6 , which adds Swift 6.3.2 support, completes full coverage for C# 14\
  \ and .NET 10, and improves sensitive data detection across multiple languages.\n\n\n Language and framework support\n Swift\n\
  \n\n\n CodeQL now supports analysis of apps built with Swift 6.3.2.\n\n C#\n\n\n\n We’ve completed full support for C# 14\
  \ and .NET 10. The extractor now supports all new language features, and the data flow library now includes generated models\
  \ for the .NET 10 runtime.\n\n Java/Kotlin\n\n\n\n We’ve added source and sink models for org.apache.avro .\n\n C/C++\n\n\
  \n\n We’ve added flow source models for scanf_s and related functions.\n\n Query changes\n GitHub Actions\n\n\n\n We’ve\
  \ adjusted actions/untrusted-checkout/critical so alerts now appear at the checkout point, aligning it with related untrusted\
  \ resource queries. Note that this change will cause alerts that were previously closed from this query to reopen.\n The\
  \ actions/unpinned-tag query now recognizes 64-character SHA-256 commit hashes as properly pinned references in addition\
  \ to 40-character SHA-1 hashes, which may reduce false positives.\n The analysis now recognizes more Bash regex checks that\
  \ restrict values to alphanumeric characters, including patterns that check for SHA-1 or SHA-256 hashes, which may reduce\
  \ false positives where command output is validated before use.\n\n JavaScript/TypeScript, Python, Swift, and Rust\n\n\n\
  \n We’ve improved the sensitive data heuristics used to identify code handling passwords and private data, allowing CodeQL\
  \ to detect more variations of established patterns. Queries such as js/clear-text-logging , py/clear-text-logging-sensitive-data\
  \ , swift/cleartext-logging , and rust/cleartext-logging may now find more correct results and fewer false positives.\n\n\
  \ For a full list of changes, please refer to the complete changelog for version 2.25.6 . Every new version of CodeQL is\
  \ automatically deployed to users of GitHub code scanning on github.com. The new functionality in CodeQL 2.25.6 will also\
  \ be included in a future GitHub Enterprise Server (GHES) release. If you use an older version of GHES, you can manually\
  \ upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.25.6 adds Swift 6.3.2 support and improves C# coverage appeared\
  \ first on The GitHub Blog ."
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
- at: '2026-06-05T21:30:57Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-06T04:30:48Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-05-codeql-2-25-6-adds-swift-6-3-2-support-and-improves-c-coverage
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-06T04:30:45Z'
  url: https://github.blog/changelog/2026-06-05-codeql-2-25-6-adds-swift-6-3-2-support-and-improves-c-coverage
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-06-06T08:47:52Z'
  url: https://github.blog/changelog/2026-06-05-codeql-2-25-6-adds-swift-6-3-2-support-and-improves-c-coverage
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL is the static analysis engine behind GitHub code scanning , which finds and remediates\
  \ security issues in your code. We’ve recently released CodeQL 2.25.6 , which adds Swift 6.3.2 support, completes full coverage\
  \ for C# 14 and .NET 10, and improves sensitive data detection across multiple languages.\n\n\n Language and framework support\n\
  \ Swift\n\n\n\n CodeQL now supports analysis of apps built with Swift 6.3.2.\n\n C#\n\n\n\n We’ve completed full support\
  \ for C# 14 and .NET 10. The extractor now supports all new language features, and the data flow library now includes generated\
  \ models for the .NET 10 runtime.\n\n Java/Kotlin\n\n\n\n We’ve added source and sink models for org.apache.avro .\n\n C/C++\n\
  \n\n\n We’ve added flow source models for scanf_s and related functions.\n\n Query changes\n GitHub Actions\n\n\n\n We’ve\
  \ adjusted actions/untrusted-checkout/critical so alerts now appear at the checkout point, aligning it with related untrusted\
  \ resource queries. Note that this change will cause alerts that were previously closed from this query to reopen.\n The\
  \ actions/unpinned-tag query now recognizes 64-character SHA-256 commit hashes as properly pinned references in addition\
  \ to 40-character SHA-1 hashes, which may reduce false positives.\n The analysis now recognizes more Bash regex checks that\
  \ restrict values to alphanumeric characters, including patterns that check for SHA-1 or SHA-256 hashes, which may reduce\
  \ false positives where command output is validated before use.\n\n JavaScript/TypeScript, Python, Swift, and Rust\n\n\n\
  \n We’ve improved the sensitive data heuristics used to identify code handling passwords and private data, allowing CodeQL\
  \ to detect more variations of established patterns. Queries such as js/clear-text-logging , py/clear-text-logging-sensitive-data\
  \ , swift/cleartext-logging , and rust/cleartext-logging may now find more correct results and fewer false positives.\n\n\
  \ For a full list of changes, please refer to the complete changelog for version 2.25.6 . Every new version of CodeQL is\
  \ automatically deployed to users of GitHub code scanning on github.com. The new functionality in CodeQL 2.25.6 will also\
  \ be included in a future GitHub Enterprise Server (GHES) release. If you use an older version of GHES, you can manually\
  \ upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.25.6 adds Swift 6.3.2 support and improves C# coverage appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
