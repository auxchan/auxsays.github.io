---
layout: aux-update
title: GitHub / Copilot CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript analysis official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript
  analysis.
permalink: /updates/github/github/codeql-2-27-2-improves-c-go-rust-and-javascript-analysis/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-09-codeql-2-27-2-improves-c-go-rust-and-javascript-analysis
update_download_url: ''
update_version: CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript analysis
update_logo_text: GIT
update_published_at: '2026-10-09T21:32:54Z'
update_last_checked: '2026-10-10T00:58:40Z'
source_last_checked: '2026-10-10T08:25:46Z'
official_body_last_checked: '2026-10-10T08:25:46Z'
record_last_updated: '2026-10-10T00:58:40Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript analysis
update_detail_title: GitHub / Copilot CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript analysis
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript analysis has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript analysis.
release_summary: "CodeQL 2.27.2 is now available, adding a C++ regular-expression parser and analysis improvements across\
  \ several languages. CodeQL is the static analysis engine behind GitHub code scanning, which helps you find and remediate\
  \ security issues in your code. The Default suite runs 498 security queries covering 170 CWEs. The Extended suite adds 131\
  \ queries covering 32 more CWEs.\n\n\n Language and framework support\n C/C++\n\n\n\n CodeQL now parses regular expressions\
  \ that use the ECMAScript grammar in std::regex .\n We’ve added SQL-injection sink models for the Comdb2 C API as well as\
  \ flow summaries for Bloomberg BDE codecs and byte-stream deserializers.\n\n Go\n\n\n\n CodeQL now models the github.com/coder/websocket\
  \ import path, in addition to nhooyr.io/websocket .\n\n Rust\n\n\n\n The Rust extractor now supports the AnyAttr and DocComment\
  \ classes.\n We’ve improved data flow for async blocks used with await as well as added flow summaries for native-tls ,\
  \ async-native-tls , and tokio-native-tls .\n\n JavaScript/TypeScript\n\n\n\n CodeQL now recognizes the Workflow SDK’s \"\
  use workflow\" and \"use step\" directives.\n We’ve improved Hapi route-handler and request-input tracking through custom\
  \ route-registration helpers and higher-order functions.\n\n macOS 27 compatibility\n\n With the release of macOS 27 and\
  \ Xcode 27, Apple stopped shipping multi-architecture x86-64/arm64 binaries. These binaries are required by CodeQL to perform\
  \ traced analysis. For this reason, CodeQL’s autobuild and manual build modes will not be supported for compiled languages\
  \ on macOS 27 with any Xcode version, and on macOS 26 when Xcode 27 is selected. When using these build modes, please use\
  \ at most macOS 26 and Xcode 26. We are also working on improving support for build mode none on macOS to help mitigate\
  \ this limitation.\n\n Query changes\n C#\n\n\n\n The cs/web/missing-x-frame-options query now recognizes ASP.NET Core response\
  \ headers and Content Security Policy frame-ancestors directives as clickjacking protections.\n The cs/web/xss query no\
  \ longer treats Razor tag-helper attribute values written with WriteLiteral as XSS sinks.\n\n GitHub Actions\n\n\n\n You\
  \ can now remove owners from the trusted set used by the actions/unpinned-tag query by adding an entry prefixed with ! ,\
  \ such as !github . This lets you report unpinned tags for first-party owners.\n\n CodeQL CLI\n\n The CLI now reports invalid\
  \ qlpack: and from: values in query suites as clear errors instead of crashing.\n CodeQL now rejects YAML data-extension\
  \ integers outside the signed 32-bit range instead of silently truncating some values.\n Error and warning messages on standard\
  \ error now include ERROR: and WARNING: prefixes. Structured output, including logs and SARIF, remains unchanged.\n codeql\
  \ query compile now accepts --dil-constants with --dump-dil to include optimized constant tuple sets in emitted DIL.\n Commands\
  \ that load data extensions now only warn when none of the patterns in a pack’s dataExtensions list match any files.\n\n\
  \ Go library breaking change\n The Go control-flow graph (CFG) now uses the shared CFG library. It includes additional nodes\
  \ for constructs such as assignments, parameters and results, range statements, and deferred calls, and excludes nodes that\
  \ aren’t reachable from the entry point. This changes CFG nodes, edges, locations, textual representations, and basic-block\
  \ boundaries, so you may need to update queries that rely on the previous representation.\n\n\n The update:\n\n\n\n Removes\
  \ BasicBlocks::Cfg .\n Adds ControlFlow::EntryNode , ControlFlow::ExitNode , and SwitchStmt.getExpr .\n Deprecates IfStmt.getCond\
  \ in favor of IfStmt.getCondition .\n Changes the return types of IfStmt.getThen and LoopStmt.getBody to Stmt .\n Consolidates\
  \ several IR instruction classes.\n\n For full details, see the CodeQL 2.27.2 changelog . GitHub automatically deploys every\
  \ new CodeQL version to users of GitHub code scanning on github.com. A future GitHub Enterprise Server (GHES) release will\
  \ also include the new functionality in CodeQL 2.27.2. If you use an older version of GHES, you can manually upgrade your\
  \ CodeQL version .\n\n\n\n The post CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript analysis appeared first on The\
  \ GitHub Blog ."
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
- at: '2026-10-09T21:32:54Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-10T00:58:56Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-09-codeql-2-27-2-improves-c-go-rust-and-javascript-analysis
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-10T00:58:40Z'
  url: https://github.blog/changelog/2026-10-09-codeql-2-27-2-improves-c-go-rust-and-javascript-analysis
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-10T08:25:46Z'
  url: https://github.blog/changelog/2026-10-09-codeql-2-27-2-improves-c-go-rust-and-javascript-analysis
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL 2.27.2 is now available, adding a C++ regular-expression parser and analysis improvements\
  \ across several languages. CodeQL is the static analysis engine behind GitHub code scanning, which helps you find and remediate\
  \ security issues in your code. The Default suite runs 498 security queries covering 170 CWEs. The Extended suite adds 131\
  \ queries covering 32 more CWEs.\n\n\n Language and framework support\n C/C++\n\n\n\n CodeQL now parses regular expressions\
  \ that use the ECMAScript grammar in std::regex .\n We’ve added SQL-injection sink models for the Comdb2 C API as well as\
  \ flow summaries for Bloomberg BDE codecs and byte-stream deserializers.\n\n Go\n\n\n\n CodeQL now models the github.com/coder/websocket\
  \ import path, in addition to nhooyr.io/websocket .\n\n Rust\n\n\n\n The Rust extractor now supports the AnyAttr and DocComment\
  \ classes.\n We’ve improved data flow for async blocks used with await as well as added flow summaries for native-tls ,\
  \ async-native-tls , and tokio-native-tls .\n\n JavaScript/TypeScript\n\n\n\n CodeQL now recognizes the Workflow SDK’s \"\
  use workflow\" and \"use step\" directives.\n We’ve improved Hapi route-handler and request-input tracking through custom\
  \ route-registration helpers and higher-order functions.\n\n macOS 27 compatibility\n\n With the release of macOS 27 and\
  \ Xcode 27, Apple stopped shipping multi-architecture x86-64/arm64 binaries. These binaries are required by CodeQL to perform\
  \ traced analysis. For this reason, CodeQL’s autobuild and manual build modes will not be supported for compiled languages\
  \ on macOS 27 with any Xcode version, and on macOS 26 when Xcode 27 is selected. When using these build modes, please use\
  \ at most macOS 26 and Xcode 26. We are also working on improving support for build mode none on macOS to help mitigate\
  \ this limitation.\n\n Query changes\n C#\n\n\n\n The cs/web/missing-x-frame-options query now recognizes ASP.NET Core response\
  \ headers and Content Security Policy frame-ancestors directives as clickjacking protections.\n The cs/web/xss query no\
  \ longer treats Razor tag-helper attribute values written with WriteLiteral as XSS sinks.\n\n GitHub Actions\n\n\n\n You\
  \ can now remove owners from the trusted set used by the actions/unpinned-tag query by adding an entry prefixed with ! ,\
  \ such as !github . This lets you report unpinned tags for first-party owners.\n\n CodeQL CLI\n\n The CLI now reports invalid\
  \ qlpack: and from: values in query suites as clear errors instead of crashing.\n CodeQL now rejects YAML data-extension\
  \ integers outside the signed 32-bit range instead of silently truncating some values.\n Error and warning messages on standard\
  \ error now include ERROR: and WARNING: prefixes. Structured output, including logs and SARIF, remains unchanged.\n codeql\
  \ query compile now accepts --dil-constants with --dump-dil to include optimized constant tuple sets in emitted DIL.\n Commands\
  \ that load data extensions now only warn when none of the patterns in a pack’s dataExtensions list match any files.\n\n\
  \ Go library breaking change\n The Go control-flow graph (CFG) now uses the shared CFG library. It includes additional nodes\
  \ for constructs such as assignments, parameters and results, range statements, and deferred calls, and excludes nodes that\
  \ aren’t reachable from the entry point. This changes CFG nodes, edges, locations, textual representations, and basic-block\
  \ boundaries, so you may need to update queries that rely on the previous representation.\n\n\n The update:\n\n\n\n Removes\
  \ BasicBlocks::Cfg .\n Adds ControlFlow::EntryNode , ControlFlow::ExitNode , and SwitchStmt.getExpr .\n Deprecates IfStmt.getCond\
  \ in favor of IfStmt.getCondition .\n Changes the return types of IfStmt.getThen and LoopStmt.getBody to Stmt .\n Consolidates\
  \ several IR instruction classes.\n\n For full details, see the CodeQL 2.27.2 changelog . GitHub automatically deploys every\
  \ new CodeQL version to users of GitHub code scanning on github.com. A future GitHub Enterprise Server (GHES) release will\
  \ also include the new functionality in CodeQL 2.27.2. If you use an older version of GHES, you can manually upgrade your\
  \ CodeQL version .\n\n\n\n The post CodeQL 2.27.2 improves C++, Go, Rust, and JavaScript analysis appeared first on The\
  \ GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
