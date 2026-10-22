---
layout: aux-update
title: GitHub / Copilot CodeQL 2.27.1 adds C and C++ query and Kotlin 2.4.20 support official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for CodeQL 2.27.1 adds C and C++ query and Kotlin
  2.4.20 support.
permalink: /updates/github/github/codeql-2-27-1-adds-c-and-c-query-and-kotlin-2-4-20-support/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-25-codeql-2-27-1-adds-c-and-c-query-and-kotlin-2-4-20-support
update_download_url: ''
update_version: CodeQL 2.27.1 adds C and C++ query and Kotlin 2.4.20 support
update_logo_text: GIT
update_published_at: '2026-09-25T09:55:23Z'
update_last_checked: '2026-09-25T14:11:16Z'
source_last_checked: '2026-09-25T19:25:21Z'
official_body_last_checked: '2026-09-25T19:25:21Z'
record_last_updated: '2026-09-25T14:11:16Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.27.1 adds C and C++ query and Kotlin 2.4.20 support
update_detail_title: GitHub / Copilot CodeQL 2.27.1 adds C and C++ query and Kotlin 2.4.20 support
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.27.1 adds C and C++ query and Kotlin 2.4.20 support has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.27.1 adds C and C++ query and Kotlin 2.4.20 support.
release_summary: "CodeQL 2.27.1 adds new queries for C/C++ and C#, support for Kotlin 2.4.20, and query-accuracy improvements.\
  \ CodeQL is the static analysis engine behind GitHub code scanning, which helps you find and remediate security issues in\
  \ your code.\n\n\n Language and framework support\n C/C++\n\n\n\n We’ve added taint flow models for boost::asio::ip::basic_resolver::resolve\
  \ , flow summaries for Bloomberg Development Environment’s BloombergLP::bdlbb::Blob segmented byte buffer, and flow summaries\
  \ for the Protocol Buffers google::protobuf::MessageLite C++ API.\n\n Go\n\n\n\n We’ve added or improved data flow models\
  \ for Go 1.27 standard-library APIs, including bytes.CutLast , database/sql.ConvertAssign , database/sql/driver.RowsColumnScanner.ScanColumn\
  \ , net/url.URL.Clone , net/url.Values.Clone , strings.CutLast , and the new encoding/json/jsontext package.\n We’ve expanded\
  \ data flow models for the strings package, including Clone , Cut , CutPrefix , CutSuffix , Fields , FieldsFunc , Join ,\
  \ Builder , Reader , and Replacer APIs.\n\n Java/Kotlin\n\n\n\n CodeQL now supports Kotlin 2.4.20.\n We’ve fixed extraction\
  \ of Foo::class.java arguments when using the Kotlin K2 compiler. This reduces false positives in queries such as java/android/implicit-pendingintents\
  \ .\n\n JavaScript/TypeScript\n\n\n\n CodeQL now recognizes Fastify servers configured through chainable methods such as\
  \ fastify().withTypeProvider() and fastify().setValidatorCompiler(...) . This improves route attribution, which may add\
  \ results for queries such as js/missing-rate-limiting and remove false positives when globally registered plugins protect\
  \ routes.\n\n Rust\n\n\n\n We’ve fixed path resolution for m::{self} paths when m is a trait.\n We’ve added data flow models\
  \ for core::fmt::Write , improving detection of vulnerabilities where tainted data is written to formatted output buffers.\n\
  \ The Rust extractor now uses rust-analyzer version 0.0.347. This updates the Rust library AST with new node types and accessor\
  \ APIs. See the CodeQL 2.27.1 changelog for migration details.\n\n Query changes\n C/C++\n\n\n\n We’ve added the cpp/ambiguous-assignment-of-comparison\
  \ query to detect potentially ambiguous expressions that assign a comparison result to a variable and use the assignment\
  \ as a truth value.\n\n C#\n\n\n\n We’ve added the cs/linq/missed-firstordefault query, which identifies foreach loops that\
  \ can be expressed more clearly with LINQ’s FirstOrDefault method.\n The cs/linq/missed-* queries no longer suggest lambda\
  \ rewrites that capture in , out , or ref parameters, preventing suggestions that wouldn’t compile.\n The cs/web/missing-token-validation\
  \ query now recognizes ASP.NET Core’s AutoValidateAntiforgeryTokenAttribute when you register it as a global MVC filter\
  \ through AddControllersWithViews and related methods. This reduces false positives for protected actions.\n\n GitHub Actions\n\
  \n\n\n The actions/unpinned-tag query no longer reports actions pinned by a structurally valid .github/workflows/actions.lock\
  \ entry for the enclosing workflow.\n The actions/unpinned-tag query no longer reports $/ self-repository references, such\
  \ as uses: $/path/to/action , because they resolve to the same repository at the running commit and are inherently pinned.\n\
  \n Other improvements\n C#\n\n\n\n Private NuGet registries with the Replaces base option enabled in the organization-level\
  \ private registry configuration now replace default NuGet feeds whenever CodeQL downloads dependencies, including when\
  \ a project explicitly configures default feeds.\n\n For full details, see the CodeQL 2.27.1 changelog . GitHub automatically\
  \ deploys every new CodeQL version to users of GitHub code scanning on github.com. GitHub Enterprise Server (GHES) 3.24\
  \ will include the new functionality in CodeQL 2.27.1. If you use an older version of GHES, you can manually upgrade your\
  \ CodeQL version .\n\n\n\n The post CodeQL 2.27.1 adds C and C++ query and Kotlin 2.4.20 support appeared first on The GitHub\
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
- at: '2026-09-25T09:55:23Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-25T14:11:27Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-25-codeql-2-27-1-adds-c-and-c-query-and-kotlin-2-4-20-support
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-25T14:11:16Z'
  url: https://github.blog/changelog/2026-09-25-codeql-2-27-1-adds-c-and-c-query-and-kotlin-2-4-20-support
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-25T19:25:21Z'
  url: https://github.blog/changelog/2026-09-25-codeql-2-27-1-adds-c-and-c-query-and-kotlin-2-4-20-support
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL 2.27.1 adds new queries for C/C++ and C#, support for Kotlin 2.4.20, and query-accuracy\
  \ improvements. CodeQL is the static analysis engine behind GitHub code scanning, which helps you find and remediate security\
  \ issues in your code.\n\n\n Language and framework support\n C/C++\n\n\n\n We’ve added taint flow models for boost::asio::ip::basic_resolver::resolve\
  \ , flow summaries for Bloomberg Development Environment’s BloombergLP::bdlbb::Blob segmented byte buffer, and flow summaries\
  \ for the Protocol Buffers google::protobuf::MessageLite C++ API.\n\n Go\n\n\n\n We’ve added or improved data flow models\
  \ for Go 1.27 standard-library APIs, including bytes.CutLast , database/sql.ConvertAssign , database/sql/driver.RowsColumnScanner.ScanColumn\
  \ , net/url.URL.Clone , net/url.Values.Clone , strings.CutLast , and the new encoding/json/jsontext package.\n We’ve expanded\
  \ data flow models for the strings package, including Clone , Cut , CutPrefix , CutSuffix , Fields , FieldsFunc , Join ,\
  \ Builder , Reader , and Replacer APIs.\n\n Java/Kotlin\n\n\n\n CodeQL now supports Kotlin 2.4.20.\n We’ve fixed extraction\
  \ of Foo::class.java arguments when using the Kotlin K2 compiler. This reduces false positives in queries such as java/android/implicit-pendingintents\
  \ .\n\n JavaScript/TypeScript\n\n\n\n CodeQL now recognizes Fastify servers configured through chainable methods such as\
  \ fastify().withTypeProvider() and fastify().setValidatorCompiler(...) . This improves route attribution, which may add\
  \ results for queries such as js/missing-rate-limiting and remove false positives when globally registered plugins protect\
  \ routes.\n\n Rust\n\n\n\n We’ve fixed path resolution for m::{self} paths when m is a trait.\n We’ve added data flow models\
  \ for core::fmt::Write , improving detection of vulnerabilities where tainted data is written to formatted output buffers.\n\
  \ The Rust extractor now uses rust-analyzer version 0.0.347. This updates the Rust library AST with new node types and accessor\
  \ APIs. See the CodeQL 2.27.1 changelog for migration details.\n\n Query changes\n C/C++\n\n\n\n We’ve added the cpp/ambiguous-assignment-of-comparison\
  \ query to detect potentially ambiguous expressions that assign a comparison result to a variable and use the assignment\
  \ as a truth value.\n\n C#\n\n\n\n We’ve added the cs/linq/missed-firstordefault query, which identifies foreach loops that\
  \ can be expressed more clearly with LINQ’s FirstOrDefault method.\n The cs/linq/missed-* queries no longer suggest lambda\
  \ rewrites that capture in , out , or ref parameters, preventing suggestions that wouldn’t compile.\n The cs/web/missing-token-validation\
  \ query now recognizes ASP.NET Core’s AutoValidateAntiforgeryTokenAttribute when you register it as a global MVC filter\
  \ through AddControllersWithViews and related methods. This reduces false positives for protected actions.\n\n GitHub Actions\n\
  \n\n\n The actions/unpinned-tag query no longer reports actions pinned by a structurally valid .github/workflows/actions.lock\
  \ entry for the enclosing workflow.\n The actions/unpinned-tag query no longer reports $/ self-repository references, such\
  \ as uses: $/path/to/action , because they resolve to the same repository at the running commit and are inherently pinned.\n\
  \n Other improvements\n C#\n\n\n\n Private NuGet registries with the Replaces base option enabled in the organization-level\
  \ private registry configuration now replace default NuGet feeds whenever CodeQL downloads dependencies, including when\
  \ a project explicitly configures default feeds.\n\n For full details, see the CodeQL 2.27.1 changelog . GitHub automatically\
  \ deploys every new CodeQL version to users of GitHub code scanning on github.com. GitHub Enterprise Server (GHES) 3.24\
  \ will include the new functionality in CodeQL 2.27.1. If you use an older version of GHES, you can manually upgrade your\
  \ CodeQL version .\n\n\n\n The post CodeQL 2.27.1 adds C and C++ query and Kotlin 2.4.20 support appeared first on The GitHub\
  \ Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
