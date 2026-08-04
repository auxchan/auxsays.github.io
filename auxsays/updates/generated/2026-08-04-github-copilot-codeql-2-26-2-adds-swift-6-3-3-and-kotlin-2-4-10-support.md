---
layout: aux-update
title: GitHub / Copilot CodeQL 2.26.2 adds Swift 6.3.3 and Kotlin 2.4.10 support official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/codeql-2-26-2-adds-swift-6-3-3-and-kotlin-2-4-10-support/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-04-codeql-2-26-2-adds-swift-6-3-3-and-kotlin-2-4-10-support
update_download_url: ''
update_version: CodeQL 2.26.2 adds Swift 6.3.3 and Kotlin 2.4.10 support
update_logo_text: GIT
update_published_at: '2026-08-04T10:57:39Z'
update_last_checked: '2026-08-04T18:04:57Z'
source_last_checked: '2026-08-04T18:04:57Z'
official_body_last_checked: '2026-08-04T18:04:57Z'
record_last_updated: '2026-08-04T18:04:57Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.26.2 adds Swift 6.3.3 and Kotlin 2.4.10 support
update_detail_title: GitHub / Copilot CodeQL 2.26.2 adds Swift 6.3.3 and Kotlin 2.4.10 support
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.26.2 adds Swift 6.3.3 and Kotlin 2.4.10 support has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.26.2 adds Swift 6.3.3 and Kotlin 2.4.10 support.
release_summary: "CodeQL is the static analysis engine behind GitHub code scanning, which finds and remediates security issues\
  \ in your code. We’ve recently released CodeQL 2.26.2, which adds support for Swift 6.3.3 and Kotlin 2.4.10, and improves\
  \ the accuracy of path injection, URL redirection, and GitHub Actions queries.\n\n\n Language and framework support\n Swift:\
  \ CodeQL now supports analysis of apps built with Swift 6.3.3.\n\n\n Java/Kotlin: CodeQL now supports Kotlin versions up\
  \ to 2.4.10.\n\n\n Query changes\n C#\n\n\n\n System.Web.HttpRequest.RawUrl is no longer a sanitizer for cs/web/unvalidated-url-redirection\
  \ , since it contains the unnormalized request line. This may lead to more results.\n We’ve removed the cs/useless-assignment-to-local\
  \ query from the code-quality suite. It remains in the code-quality-extended suite.\n\n Go\n\n\n\n path/filepath.Rel is\
  \ no longer a sanitizer for go/path-injection and go/zipslip , which may lead to more results.\n\n Java/Kotlin\n\n\n\n java.io.File.getName()\
  \ is no longer a complete sanitizer for java/path-injection , since it doesn’t remove a .. path component. This may lead\
  \ to more results.\n\n C/C++\n\n\n\n We’ve updated the cpp/new-free-mismatch query to use the external/cwe/cwe-762 tag instead\
  \ of external/cwe/cwe-401 , which better matches the query’s behavior.\n\n GitHub Actions\n\n\n\n We’ve changed the EnvironmentCheck\
  \ logic so it only protects against non-TOCTOU scenarios, which surfaces more results in the untrusted checkout queries.\n\
  \n Breaking change\n\n CodeQL no longer parses [[ -style links in alert messages. This undocumented legacy feature let query\
  \ authors embed links inline in select clause message strings. Use $@ placeholder pairs instead.\n\n For a full list of\
  \ changes, please refer to the complete changelog for version 2.26.2 . Every new version of CodeQL is automatically deployed\
  \ to users of GitHub code scanning on github.com. The new functionality in CodeQL 2.26.2 will also be included in a future\
  \ GitHub Enterprise Server (GHES) release. If you use an older version of GHES, you can manually upgrade your CodeQL version\
  \ .\n\n\n\n The post CodeQL 2.26.2 adds Swift 6.3.3 and Kotlin 2.4.10 support appeared first on The GitHub Blog ."
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
- at: '2026-08-04T10:57:39Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-04T18:05:07Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-04-codeql-2-26-2-adds-swift-6-3-3-and-kotlin-2-4-10-support
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-04T18:04:57Z'
  url: https://github.blog/changelog/2026-08-04-codeql-2-26-2-adds-swift-6-3-3-and-kotlin-2-4-10-support
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL is the static analysis engine behind GitHub code scanning, which finds and remediates security\
  \ issues in your code. We’ve recently released CodeQL 2.26.2, which adds support for Swift 6.3.3 and Kotlin 2.4.10, and\
  \ improves the accuracy of path injection, URL redirection, and GitHub Actions queries.\n\n\n Language and framework support\n\
  \ Swift: CodeQL now supports analysis of apps built with Swift 6.3.3.\n\n\n Java/Kotlin: CodeQL now supports Kotlin versions\
  \ up to 2.4.10.\n\n\n Query changes\n C#\n\n\n\n System.Web.HttpRequest.RawUrl is no longer a sanitizer for cs/web/unvalidated-url-redirection\
  \ , since it contains the unnormalized request line. This may lead to more results.\n We’ve removed the cs/useless-assignment-to-local\
  \ query from the code-quality suite. It remains in the code-quality-extended suite.\n\n Go\n\n\n\n path/filepath.Rel is\
  \ no longer a sanitizer for go/path-injection and go/zipslip , which may lead to more results.\n\n Java/Kotlin\n\n\n\n java.io.File.getName()\
  \ is no longer a complete sanitizer for java/path-injection , since it doesn’t remove a .. path component. This may lead\
  \ to more results.\n\n C/C++\n\n\n\n We’ve updated the cpp/new-free-mismatch query to use the external/cwe/cwe-762 tag instead\
  \ of external/cwe/cwe-401 , which better matches the query’s behavior.\n\n GitHub Actions\n\n\n\n We’ve changed the EnvironmentCheck\
  \ logic so it only protects against non-TOCTOU scenarios, which surfaces more results in the untrusted checkout queries.\n\
  \n Breaking change\n\n CodeQL no longer parses [[ -style links in alert messages. This undocumented legacy feature let query\
  \ authors embed links inline in select clause message strings. Use $@ placeholder pairs instead.\n\n For a full list of\
  \ changes, please refer to the complete changelog for version 2.26.2 . Every new version of CodeQL is automatically deployed\
  \ to users of GitHub code scanning on github.com. The new functionality in CodeQL 2.26.2 will also be included in a future\
  \ GitHub Enterprise Server (GHES) release. If you use an older version of GHES, you can manually upgrade your CodeQL version\
  \ .\n\n\n\n The post CodeQL 2.26.2 adds Swift 6.3.3 and Kotlin 2.4.10 support appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
