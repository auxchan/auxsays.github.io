---
layout: aux-update
title: GitHub / Copilot Faster C++ code intelligence with whole codebase indexing official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Faster C++ code intelligence with whole codebase
  indexing.
permalink: /updates/github/github/faster-c-code-intelligence-with-whole-codebase-indexing/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-22-faster-c-code-intelligence-with-whole-codebase-indexing
update_download_url: ''
update_version: Faster C++ code intelligence with whole codebase indexing
update_logo_text: GIT
update_published_at: '2026-09-22T22:24:48Z'
update_last_checked: '2026-09-22T23:24:44Z'
source_last_checked: '2026-09-23T07:01:02Z'
official_body_last_checked: '2026-09-23T07:01:02Z'
record_last_updated: '2026-09-22T23:24:44Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Faster C++ code intelligence with whole codebase indexing
update_detail_title: GitHub / Copilot Faster C++ code intelligence with whole codebase indexing
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Faster C++ code intelligence with whole codebase indexing has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Faster C++ code intelligence with whole codebase indexing.
release_summary: "C++ code intelligence in GitHub Copilot CLI is now faster with support for whole codebase indexing.\n\n\n\
  \ C++ repositories can contain millions of lines of code across deeply connected source files and headers. Without a reusable\
  \ index, code-intelligence requests may need to rediscover project information as you navigate, making it slower to find\
  \ a definition, locate references, or understand unfamiliar code.\n\n\n Whole codebase indexing (WCI) creates a persistent\
  \ index of symbols across your C++ project, including files that aren’t currently open. The Microsoft C++ Language Server\
  \ uses your project’s compilation information to resolve types, symbols, includes, and relationships between files. WCI\
  \ makes that symbol information available for reuse instead of rediscovering it for each request.\n\n\n You spend less time\
  \ waiting for definitions, references, implementations, and symbol search results, and more time reviewing, understanding,\
  \ and changing code.\n\n\n Configure indexing\n Whole codebase indexing is enabled by default because its persistent symbol\
  \ index helps the Microsoft C++ Language Server efficiently understand relationships across your entire project. The language\
  \ server loads the index when you first open a C++ project. You can check indexing progress at any time with /lsp logs .\n\
  \n\n Building the index for the first time can take additional time and temporarily increase memory usage, particularly\
  \ for large or complex repositories. After the initial index is complete, it is reused and dynamically updated, so this\
  \ overhead is primarily associated with initial setup.\n\n\n To disable whole codebase indexing, you can temporarily disable\
  \ WCI using the indexing documentation .\n\n\n Restart your Copilot session after changing the setting.\n\n\n Feedback\n\
  \ Help us improve the Microsoft C++ language server for Copilot CLI by filling out our short survey . To report a problem\
  \ or suggest an improvement, open an issue in the GitHub repository.\n\n\n\n The post Faster C++ code intelligence with\
  \ whole codebase indexing appeared first on The GitHub Blog ."
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
- at: '2026-09-22T22:24:48Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-22T23:24:54Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-22-faster-c-code-intelligence-with-whole-codebase-indexing
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-22T23:24:44Z'
  url: https://github.blog/changelog/2026-09-22-faster-c-code-intelligence-with-whole-codebase-indexing
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-23T07:01:02Z'
  url: https://github.blog/changelog/2026-09-22-faster-c-code-intelligence-with-whole-codebase-indexing
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "C++ code intelligence in GitHub Copilot CLI is now faster with support for whole codebase indexing.\n\
  \n\n C++ repositories can contain millions of lines of code across deeply connected source files and headers. Without a\
  \ reusable index, code-intelligence requests may need to rediscover project information as you navigate, making it slower\
  \ to find a definition, locate references, or understand unfamiliar code.\n\n\n Whole codebase indexing (WCI) creates a\
  \ persistent index of symbols across your C++ project, including files that aren’t currently open. The Microsoft C++ Language\
  \ Server uses your project’s compilation information to resolve types, symbols, includes, and relationships between files.\
  \ WCI makes that symbol information available for reuse instead of rediscovering it for each request.\n\n\n You spend less\
  \ time waiting for definitions, references, implementations, and symbol search results, and more time reviewing, understanding,\
  \ and changing code.\n\n\n Configure indexing\n Whole codebase indexing is enabled by default because its persistent symbol\
  \ index helps the Microsoft C++ Language Server efficiently understand relationships across your entire project. The language\
  \ server loads the index when you first open a C++ project. You can check indexing progress at any time with /lsp logs .\n\
  \n\n Building the index for the first time can take additional time and temporarily increase memory usage, particularly\
  \ for large or complex repositories. After the initial index is complete, it is reused and dynamically updated, so this\
  \ overhead is primarily associated with initial setup.\n\n\n To disable whole codebase indexing, you can temporarily disable\
  \ WCI using the indexing documentation .\n\n\n Restart your Copilot session after changing the setting.\n\n\n Feedback\n\
  \ Help us improve the Microsoft C++ language server for Copilot CLI by filling out our short survey . To report a problem\
  \ or suggest an improvement, open an issue in the GitHub repository.\n\n\n\n The post Faster C++ code intelligence with\
  \ whole codebase indexing appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
