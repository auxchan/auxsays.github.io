---
layout: aux-update
title: GitHub / Copilot CodeQL 2.27.3 adds Python 3.15 features and JSON data extensions official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for CodeQL 2.27.3 adds Python 3.15 features and
  JSON data extensions.
permalink: /updates/github/github/codeql-2-27-3-adds-python-3-15-features-and-json-data-extensions/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-03-codeql-2-27-3-adds-python-3-15-features-and-json-data-extensions
update_download_url: ''
update_version: CodeQL 2.27.3 adds Python 3.15 features and JSON data extensions
update_logo_text: GIT
update_published_at: '2026-11-03T14:56:03Z'
update_last_checked: '2026-11-04T08:56:28Z'
source_last_checked: '2026-11-04T08:56:28Z'
official_body_last_checked: '2026-11-04T08:56:28Z'
record_last_updated: '2026-11-04T08:56:28Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.27.3 adds Python 3.15 features and JSON data extensions
update_detail_title: GitHub / Copilot CodeQL 2.27.3 adds Python 3.15 features and JSON data extensions
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.27.3 adds Python 3.15 features and JSON data extensions has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.27.3 adds Python 3.15 features and JSON data extensions.
release_summary: "CodeQL is the static analysis engine behind GitHub code scanning, which finds and remediates security issues\
  \ in your code. We’ve recently released CodeQL 2.27.3 . It supports new Python 3.15 language features, adds JSON syntax\
  \ for data extensions, adds C23 bit-precise integers, and includes accuracy improvements across languages.\n\n\n Language\
  \ and framework support\n CodeQL CLI\n\n\n\n Data extension files now support JSON syntax, using the same structure as YAML\
  \ data extensions. Java-style comments ( // ... and /* ... */ ) also work. CodeQL parses files with the .json extension\
  \ as JSON and continues to parse all other files as YAML.\n We’ve added an opt-in ai threat model for LLM-generated data.\
  \ It doesn’t include any built-in source models, so you can define your own sources with data extensions.\n\n Python\n\n\
  \n\n The Python extractor now supports Python 3.15 syntax, including unary plus in match literal patterns and Unicode 17\
  \ identifiers.\n We’ve added support for the new frozendict and sentinel builtins introduced in Python 3.15, including data\
  \ flow modeling for frozendict construction.\n\n C/C++\n\n\n\n We’ve added support for C23 bit-precise integers ( _BitInt(N)\
  \ ).\n We’ve added flow summaries for the BlazingMQ BloombergLP::bmqa::Message and MessageProperties classes and their iterators.\n\
  \n C#\n\n\n\n We’ve added support for data flow through positional patterns in is expressions and switch cases.\n When you\
  \ configure private registries, CodeQL now passes the required proxy and certificate environment variables to the NuGet\
  \ CLI.\n\n Ruby\n\n\n\n CodeQL now treats Grape::API request sub-accessors as remote flow sources. These include body.read\
  \ , body.string , params , GET , POST , cookies , env , query_string , and path_info .\n\n Query changes\n C/C++\n\n\n\n\
  \ The cpp/resource-not-released-in-destructor query now recognizes resources released through local aliases, reducing false\
  \ positives.\n\n C#\n\n\n\n The cs/simplifiable-boolean-expression query now produces fewer false positives when type information\
  \ is incomplete.\n\n Java/Kotlin\n\n\n\n The java/ssrf and java/unvalidated-url-redirection queries now recognize case-insensitive\
  \ comparisons of URI.getHost() with fixed allowlist entries. They also recognize these checks when code stores the host\
  \ in a local variable, which reduces false positives.\n\n Python\n\n\n\n The py/xxe , py/xml-bomb , and py/nosql-injection\
  \ queries now respect your configured threat model when selecting untrusted data sources. By default, they still use remote\
  \ flow sources. These queries now also include sources you model with data extensions.\n\n Breaking changes\n\n GitHub Actions:\
  \ The GitHub Actions control flow graph (CFG) now uses the shared CFG library. If your custom queries rely on specific CFG\
  \ nodes, edges, or basic block boundaries, you may need to update them. We’ve removed the legacy Completion classes, so\
  \ use CFG edge labels such as DirectSuccessor , BooleanSuccessor , and ReturnSuccessor instead.\n\n For a full list of changes,\
  \ please refer to the complete changelog for version 2.27.3 . Every new version of CodeQL is automatically deployed to users\
  \ of GitHub code scanning on github.com. The new functionality in CodeQL 2.27.3 will also be included in GitHub Enterprise\
  \ Server (GHES) 3.24 release. If you use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n\
  \ The post CodeQL 2.27.3 adds Python 3.15 features and JSON data extensions appeared first on The GitHub Blog ."
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
- at: '2026-11-03T14:56:03Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-04T08:56:41Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-03-codeql-2-27-3-adds-python-3-15-features-and-json-data-extensions
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-04T08:56:28Z'
  url: https://github.blog/changelog/2026-11-03-codeql-2-27-3-adds-python-3-15-features-and-json-data-extensions
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL is the static analysis engine behind GitHub code scanning, which finds and remediates security\
  \ issues in your code. We’ve recently released CodeQL 2.27.3 . It supports new Python 3.15 language features, adds JSON\
  \ syntax for data extensions, adds C23 bit-precise integers, and includes accuracy improvements across languages.\n\n\n\
  \ Language and framework support\n CodeQL CLI\n\n\n\n Data extension files now support JSON syntax, using the same structure\
  \ as YAML data extensions. Java-style comments ( // ... and /* ... */ ) also work. CodeQL parses files with the .json extension\
  \ as JSON and continues to parse all other files as YAML.\n We’ve added an opt-in ai threat model for LLM-generated data.\
  \ It doesn’t include any built-in source models, so you can define your own sources with data extensions.\n\n Python\n\n\
  \n\n The Python extractor now supports Python 3.15 syntax, including unary plus in match literal patterns and Unicode 17\
  \ identifiers.\n We’ve added support for the new frozendict and sentinel builtins introduced in Python 3.15, including data\
  \ flow modeling for frozendict construction.\n\n C/C++\n\n\n\n We’ve added support for C23 bit-precise integers ( _BitInt(N)\
  \ ).\n We’ve added flow summaries for the BlazingMQ BloombergLP::bmqa::Message and MessageProperties classes and their iterators.\n\
  \n C#\n\n\n\n We’ve added support for data flow through positional patterns in is expressions and switch cases.\n When you\
  \ configure private registries, CodeQL now passes the required proxy and certificate environment variables to the NuGet\
  \ CLI.\n\n Ruby\n\n\n\n CodeQL now treats Grape::API request sub-accessors as remote flow sources. These include body.read\
  \ , body.string , params , GET , POST , cookies , env , query_string , and path_info .\n\n Query changes\n C/C++\n\n\n\n\
  \ The cpp/resource-not-released-in-destructor query now recognizes resources released through local aliases, reducing false\
  \ positives.\n\n C#\n\n\n\n The cs/simplifiable-boolean-expression query now produces fewer false positives when type information\
  \ is incomplete.\n\n Java/Kotlin\n\n\n\n The java/ssrf and java/unvalidated-url-redirection queries now recognize case-insensitive\
  \ comparisons of URI.getHost() with fixed allowlist entries. They also recognize these checks when code stores the host\
  \ in a local variable, which reduces false positives.\n\n Python\n\n\n\n The py/xxe , py/xml-bomb , and py/nosql-injection\
  \ queries now respect your configured threat model when selecting untrusted data sources. By default, they still use remote\
  \ flow sources. These queries now also include sources you model with data extensions.\n\n Breaking changes\n\n GitHub Actions:\
  \ The GitHub Actions control flow graph (CFG) now uses the shared CFG library. If your custom queries rely on specific CFG\
  \ nodes, edges, or basic block boundaries, you may need to update them. We’ve removed the legacy Completion classes, so\
  \ use CFG edge labels such as DirectSuccessor , BooleanSuccessor , and ReturnSuccessor instead.\n\n For a full list of changes,\
  \ please refer to the complete changelog for version 2.27.3 . Every new version of CodeQL is automatically deployed to users\
  \ of GitHub code scanning on github.com. The new functionality in CodeQL 2.27.3 will also be included in GitHub Enterprise\
  \ Server (GHES) 3.24 release. If you use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n\
  \ The post CodeQL 2.27.3 adds Python 3.15 features and JSON data extensions appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
