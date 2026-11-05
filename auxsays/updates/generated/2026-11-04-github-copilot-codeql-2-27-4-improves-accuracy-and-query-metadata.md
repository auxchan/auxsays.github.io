---
layout: aux-update
title: GitHub / Copilot CodeQL 2.27.4 improves accuracy and query metadata official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for CodeQL 2.27.4 improves accuracy and query metadata.
permalink: /updates/github/github/codeql-2-27-4-improves-accuracy-and-query-metadata/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-04-codeql-2-27-4-improves-accuracy-and-query-metadata
update_download_url: ''
update_version: CodeQL 2.27.4 improves accuracy and query metadata
update_logo_text: GIT
update_published_at: '2026-11-04T20:04:52Z'
update_last_checked: '2026-11-05T02:21:12Z'
source_last_checked: '2026-11-05T09:03:00Z'
official_body_last_checked: '2026-11-05T09:03:00Z'
record_last_updated: '2026-11-05T02:21:12Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.27.4 improves accuracy and query metadata
update_detail_title: GitHub / Copilot CodeQL 2.27.4 improves accuracy and query metadata
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.27.4 improves accuracy and query metadata has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.27.4 improves accuracy and query metadata.
release_summary: "CodeQL is the static analysis engine behind GitHub code scanning, which finds and remediates security issues\
  \ in your code. We’ve recently released CodeQL 2.27.4 with query accuracy improvements across several languages, stronger\
  \ security checks when you bundle or publish a pack, and corrections to query metadata.\n\n\n Query changes\n Java/Kotlin\n\
  \n\n\n The java/log-injection query now recognizes additional sanitizers and sanitizer guards from the JDK, Apache Commons\
  \ Lang and Text, Guava, OWASP Java Encoder, and Spring Framework.\n Path-injection queries now recognize additional substring\
  \ guards and string replacement and removal operations from Apache Commons Lang and Guava.\n\n Rust\n\n\n\n We have reduced\
  \ false positives in the rust/uncontrolled-allocation-size , rust/log-injection , and rust/cleartext-logging queries.\n\n\
  \ C/C++\n\n\n\n The cpp/suspicious-pointer-scaling query no longer reports intentional pointer arithmetic on std::byte*\
  \ buffers.\n The cpp/unused-local-variable and cpp/unused-static-variable queries no longer report variables marked with\
  \ [[maybe_unused]] .\n\n CWE metadata changes\n\n\n CodeQL no longer applies the CWE-730 tag to the following queries:\n\
  \n\n\n C# : cs/redos and cs/regex-injection .\n Java/Kotlin : java/redos , java/polynomial-redos , and java/regex-injection\
  \ .\n JavaScript/TypeScript : js/redos , js/polynomial-redos , js/regex-injection , js/regex-injection-more-sources , js/server-crash\
  \ , and js/loop-bound-injection .\n Python : py/redos , py/polynomial-redos , and py/regex-injection .\n Ruby : rb/redos\
  \ , rb/polynomial-redos , and rb/regexp-injection .\n Swift : swift/redos and swift/regex-injection .\n\n This was initially\
  \ reported in CodeQL issue #22318 ; thank you to @wiggin15 for the feedback.\n\n\n CodeQL CLI\n\n The CLI now writes Java\
  \ virtual machine warnings and initialization errors to standard error, so they won’t interfere with JSON or other machine-readable\
  \ output.\n When you bundle or publish a pack, the CLI checks whether each file remains inside the pack root after resolving\
  \ symbolic links. It omits files that resolve outside the root and displays a warning.\n\n For full details, see the CodeQL\
  \ 2.27.4 changelog . GitHub automatically deploys every new CodeQL version to users of GitHub code scanning on github.com.\
  \ The new functionality in CodeQL 2.27.4 will also be included in the GitHub Enterprise Server (GHES) 3.24 release. If you\
  \ use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.27.4 improves accuracy\
  \ and query metadata appeared first on The GitHub Blog ."
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
- at: '2026-11-04T20:04:52Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-05T02:21:25Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-04-codeql-2-27-4-improves-accuracy-and-query-metadata
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-05T02:21:12Z'
  url: https://github.blog/changelog/2026-11-04-codeql-2-27-4-improves-accuracy-and-query-metadata
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-05T09:03:00Z'
  url: https://github.blog/changelog/2026-11-04-codeql-2-27-4-improves-accuracy-and-query-metadata
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL is the static analysis engine behind GitHub code scanning, which finds and remediates security\
  \ issues in your code. We’ve recently released CodeQL 2.27.4 with query accuracy improvements across several languages,\
  \ stronger security checks when you bundle or publish a pack, and corrections to query metadata.\n\n\n Query changes\n Java/Kotlin\n\
  \n\n\n The java/log-injection query now recognizes additional sanitizers and sanitizer guards from the JDK, Apache Commons\
  \ Lang and Text, Guava, OWASP Java Encoder, and Spring Framework.\n Path-injection queries now recognize additional substring\
  \ guards and string replacement and removal operations from Apache Commons Lang and Guava.\n\n Rust\n\n\n\n We have reduced\
  \ false positives in the rust/uncontrolled-allocation-size , rust/log-injection , and rust/cleartext-logging queries.\n\n\
  \ C/C++\n\n\n\n The cpp/suspicious-pointer-scaling query no longer reports intentional pointer arithmetic on std::byte*\
  \ buffers.\n The cpp/unused-local-variable and cpp/unused-static-variable queries no longer report variables marked with\
  \ [[maybe_unused]] .\n\n CWE metadata changes\n\n\n CodeQL no longer applies the CWE-730 tag to the following queries:\n\
  \n\n\n C# : cs/redos and cs/regex-injection .\n Java/Kotlin : java/redos , java/polynomial-redos , and java/regex-injection\
  \ .\n JavaScript/TypeScript : js/redos , js/polynomial-redos , js/regex-injection , js/regex-injection-more-sources , js/server-crash\
  \ , and js/loop-bound-injection .\n Python : py/redos , py/polynomial-redos , and py/regex-injection .\n Ruby : rb/redos\
  \ , rb/polynomial-redos , and rb/regexp-injection .\n Swift : swift/redos and swift/regex-injection .\n\n This was initially\
  \ reported in CodeQL issue #22318 ; thank you to @wiggin15 for the feedback.\n\n\n CodeQL CLI\n\n The CLI now writes Java\
  \ virtual machine warnings and initialization errors to standard error, so they won’t interfere with JSON or other machine-readable\
  \ output.\n When you bundle or publish a pack, the CLI checks whether each file remains inside the pack root after resolving\
  \ symbolic links. It omits files that resolve outside the root and displays a warning.\n\n For full details, see the CodeQL\
  \ 2.27.4 changelog . GitHub automatically deploys every new CodeQL version to users of GitHub code scanning on github.com.\
  \ The new functionality in CodeQL 2.27.4 will also be included in the GitHub Enterprise Server (GHES) 3.24 release. If you\
  \ use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.27.4 improves accuracy\
  \ and query metadata appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
