---
layout: aux-update
title: GitHub / Copilot CodeQL 2.27.0 adds support for Linux ARM64 official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for CodeQL 2.27.0 adds support for Linux ARM64.
permalink: /updates/github/github/codeql-2-27-0-adds-support-for-linux-arm64/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-09-codeql-2-27-0-adds-support-for-linux-arm64
update_download_url: ''
update_version: CodeQL 2.27.0 adds support for Linux ARM64
update_logo_text: GIT
update_published_at: '2026-09-09T21:45:06Z'
update_last_checked: '2026-09-10T00:02:42Z'
source_last_checked: '2026-09-10T06:50:27Z'
official_body_last_checked: '2026-09-10T06:50:27Z'
record_last_updated: '2026-09-10T00:02:42Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.27.0 adds support for Linux ARM64
update_detail_title: GitHub / Copilot CodeQL 2.27.0 adds support for Linux ARM64
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.27.0 adds support for Linux ARM64 has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.27.0 adds support for Linux ARM64.
release_summary: "CodeQL 2.27.0 is now available on Linux ARM64, adds a new Rust security query, expanded framework coverage\
  \ for Java/Kotlin and C#, and analysis accuracy improvements across multiple languages. CodeQL is the static analysis engine\
  \ behind GitHub code scanning, which helps you find and remediate security issues in your code.\n\n\n Language and framework\
  \ support\n CodeQL CLI\n\n\n\n You can now run CodeQL natively on Linux arm64. Download the CodeQL CLI and CodeQL bundle\
  \ from the linux-arm64 per-platform release assets .\n GitHub code scanning default setup can now use your organization’s\
  \ private registry configurations to authenticate with container registries or the GitHub API when fetching custom queries\
  \ or packs. This lets you use custom content from private Git sources and Docker registries.\n\n C#\n\n\n\n We’ve improved\
  \ ASP.NET Core MVC controller and action discovery to more closely match runtime behavior. This improves coverage for application\
  \ parts, endpoint mappings, inherited actions, as well as controller and action exclusions.\n We’ve added taint tracking\
  \ support for OData action parameter binding. This improves detection coverage for vulnerabilities involving values extracted\
  \ from ODataActionParameters and entities tracked by Delta .\n In build-mode: none , CodeQL now always attempts to restore\
  \ projects and solutions using available NuGet feeds. CodeQL also reports explicitly configured feeds that aren’t reachable,\
  \ making it easier to identify dependencies that may be missing from analysis.\n\n Java/Kotlin\n\n\n\n We’ve added modeling\
  \ for the Micronaut framework, including HTTP controllers, WebSocket endpoints, configuration injection, data access, security\
  \ annotations, and HTTP client sinks.\n\n Query changes\n C/C++\n\n\n\n We’ve added PostgreSQL libpq query-execution and\
  \ prepared-statement functions as SQL injection sinks. Queries such as cpp/sql-injection can now identify vulnerabilities\
  \ involving PQexec , PQexecParams , PQprepare , PQsendQuery , PQsendQueryParams , and PQsendPrepare .\n\n GitHub Actions\n\
  \n\n\n We’ve improved how CodeQL evaluates checks of author-association fields from event payloads. CodeQL now treats these\
  \ checks as protection only when the event payload provides the relevant field. This may produce additional alerts for workflows\
  \ that rely on ineffective checks.\n\n Rust\n\n\n\n We’ve added the rust/command-line-injection query to detect uncontrolled\
  \ command lines.\n We’ve updated the rust/hard-coded-cryptographic-value query to reduce duplicate results with very similar\
  \ source locations.\n The rust/unused-variable query no longer reports variables in functions that contain the standard\
  \ todo!() or unimplemented!() macros.\n\n Upcoming Deprecations\n\n\n\n Language support for Java 9 and 10 has been deprecated\
  \ and will be removed in January 2027. Java 7 and 8 will continue to be supported.\n The generic multi-platform codeql.zip\
  \ CLI distribution will be removed in a future release. Download the per-platform .zip for your platform instead. The CLI\
  \ now emits a warning when it is run from an all-platforms distribution; set CODEQL_ALLOW_ALL_PLATFORMS_DIST=true to suppress\
  \ it.\n\n For full details, see the CodeQL 2.27.0 changelog . GitHub automatically deploys every new CodeQL version to users\
  \ of GitHub code scanning on github.com. A future GitHub Enterprise Server (GHES) release will also include the new functionality\
  \ in CodeQL 2.27.0. If you use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n The post\
  \ CodeQL 2.27.0 adds support for Linux ARM64 appeared first on The GitHub Blog ."
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
- at: '2026-09-09T21:45:06Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-10T00:02:51Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-09-codeql-2-27-0-adds-support-for-linux-arm64
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-10T00:02:42Z'
  url: https://github.blog/changelog/2026-09-09-codeql-2-27-0-adds-support-for-linux-arm64
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-10T04:10:59Z'
  url: https://github.blog/changelog/2026-09-09-codeql-2-27-0-adds-support-for-linux-arm64
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-10T06:50:27Z'
  url: https://github.blog/changelog/2026-09-09-codeql-2-27-0-adds-support-for-linux-arm64
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL 2.27.0 is now available on Linux ARM64, adds a new Rust security query, expanded framework\
  \ coverage for Java/Kotlin and C#, and analysis accuracy improvements across multiple languages. CodeQL is the static analysis\
  \ engine behind GitHub code scanning, which helps you find and remediate security issues in your code.\n\n\n Language and\
  \ framework support\n CodeQL CLI\n\n\n\n You can now run CodeQL natively on Linux arm64. Download the CodeQL CLI and CodeQL\
  \ bundle from the linux-arm64 per-platform release assets .\n GitHub code scanning default setup can now use your organization’s\
  \ private registry configurations to authenticate with container registries or the GitHub API when fetching custom queries\
  \ or packs. This lets you use custom content from private Git sources and Docker registries.\n\n C#\n\n\n\n We’ve improved\
  \ ASP.NET Core MVC controller and action discovery to more closely match runtime behavior. This improves coverage for application\
  \ parts, endpoint mappings, inherited actions, as well as controller and action exclusions.\n We’ve added taint tracking\
  \ support for OData action parameter binding. This improves detection coverage for vulnerabilities involving values extracted\
  \ from ODataActionParameters and entities tracked by Delta .\n In build-mode: none , CodeQL now always attempts to restore\
  \ projects and solutions using available NuGet feeds. CodeQL also reports explicitly configured feeds that aren’t reachable,\
  \ making it easier to identify dependencies that may be missing from analysis.\n\n Java/Kotlin\n\n\n\n We’ve added modeling\
  \ for the Micronaut framework, including HTTP controllers, WebSocket endpoints, configuration injection, data access, security\
  \ annotations, and HTTP client sinks.\n\n Query changes\n C/C++\n\n\n\n We’ve added PostgreSQL libpq query-execution and\
  \ prepared-statement functions as SQL injection sinks. Queries such as cpp/sql-injection can now identify vulnerabilities\
  \ involving PQexec , PQexecParams , PQprepare , PQsendQuery , PQsendQueryParams , and PQsendPrepare .\n\n GitHub Actions\n\
  \n\n\n We’ve improved how CodeQL evaluates checks of author-association fields from event payloads. CodeQL now treats these\
  \ checks as protection only when the event payload provides the relevant field. This may produce additional alerts for workflows\
  \ that rely on ineffective checks.\n\n Rust\n\n\n\n We’ve added the rust/command-line-injection query to detect uncontrolled\
  \ command lines.\n We’ve updated the rust/hard-coded-cryptographic-value query to reduce duplicate results with very similar\
  \ source locations.\n The rust/unused-variable query no longer reports variables in functions that contain the standard\
  \ todo!() or unimplemented!() macros.\n\n Upcoming Deprecations\n\n\n\n Language support for Java 9 and 10 has been deprecated\
  \ and will be removed in January 2027. Java 7 and 8 will continue to be supported.\n The generic multi-platform codeql.zip\
  \ CLI distribution will be removed in a future release. Download the per-platform .zip for your platform instead. The CLI\
  \ now emits a warning when it is run from an all-platforms distribution; set CODEQL_ALLOW_ALL_PLATFORMS_DIST=true to suppress\
  \ it.\n\n For full details, see the CodeQL 2.27.0 changelog . GitHub automatically deploys every new CodeQL version to users\
  \ of GitHub code scanning on github.com. A future GitHub Enterprise Server (GHES) release will also include the new functionality\
  \ in CodeQL 2.27.0. If you use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n The post\
  \ CodeQL 2.27.0 adds support for Linux ARM64 appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
