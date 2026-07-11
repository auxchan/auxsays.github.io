---
layout: aux-update
title: GitHub / Copilot CodeQL 2.26.0 adds Kotlin 2.4.0 support and AI prompt injection detection official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/codeql-2-26-0-adds-kotlin-2-4-0-support-and-ai-prompt-injection-detection/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-10-codeql-2-26-0-adds-kotlin-2-4-0-support-and-ai-prompt-injection-detection
update_download_url: ''
update_version: CodeQL 2.26.0 adds Kotlin 2.4.0 support and AI prompt injection detection
update_logo_text: GIT
update_published_at: '2026-07-10T20:40:56Z'
update_last_checked: '2026-07-11T08:16:22Z'
source_last_checked: '2026-07-11T08:16:22Z'
official_body_last_checked: '2026-07-11T08:16:22Z'
record_last_updated: '2026-07-11T08:16:22Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.26.0 adds Kotlin 2.4.0 support and AI prompt injection detection
update_detail_title: GitHub / Copilot CodeQL 2.26.0 adds Kotlin 2.4.0 support and AI prompt injection detection
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.26.0 adds Kotlin 2.4.0 support and AI prompt injection detection has an official
  AUXSAYS record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.26.0 adds Kotlin 2.4.0 support and AI prompt injection detection.
release_summary: "CodeQL is the static analysis engine behind GitHub code scanning , which finds and remediates security issues\
  \ in your code. We’ve recently released CodeQL 2.26.0 , which adds support for Kotlin 2.4.0, introduces a JavaScript and\
  \ TypeScript query for system prompt injection, and improves analysis accuracy across multiple languages.\n\n\n Language\
  \ and framework support\n Kotlin : CodeQL now supports Kotlin versions up to 2.4.0.\n\n\n C# : We’ve added Razor Page handler\
  \ method parameters, such as parameters for OnGet , OnPost , and OnPostAsync , as remote flow sources. Security queries\
  \ such as cs/sql-injection can now detect vulnerabilities involving these parameters in PageModel subclasses.\n\n\n Go :\
  \ We’ve added models for the log/slog package introduced in Go 1.21. The go/log-injection and go/clear-text-logging queries\
  \ can now detect issues in code that uses slog package functions and slog.Logger methods.\n\n\n JavaScript/TypeScript :\
  \ We’ve added prompt injection sinks for additional OpenAI, Anthropic, and Google GenAI SDK APIs, including Sora prompts,\
  \ OpenAI Realtime session instructions, Anthropic legacy completion prompts, and Google GenAI cached content and system\
  \ instructions.\n\n\n Query changes\n JavaScript/TypeScript\n\n\n\n We’ve added the js/system-prompt-injection query to\
  \ detect when untrusted, user-provided values flow into an AI model’s system prompt, allowing an attacker to manipulate\
  \ the model’s behavior.\n We’ve added the experimental javascript/ssrf-ipv6-transition-incomplete-guard query to detect\
  \ server-side request forgery (SSRF) guards that reject private IPv4 ranges but can be bypassed with IPv6 transition address\
  \ formats.\n\n Go\n\n\n\n The go/unhandled-writable-file-close query now produces fewer false positives. It no longer flags\
  \ a deferred call to Close when every execution path first handles a call to Sync on the same file handle.\n\n Python\n\n\
  \n\n The py/modification-of-locals query no longer flags modifications to a locals() dictionary after it has passed out\
  \ of the scope where it was created, reducing false positives.\n\n Swift\n\n\n\n We’ve improved CryptoKit modeling for the\
  \ swift/weak-sensitive-data-hashing and swift/weak-password-hashing queries. These queries may now detect additional results.\n\
  \n GitHub Actions\n\n\n\n We’ve updated the actions/pr-on-self-hosted-runner query to recognize the latest standard runner\
  \ labels, reducing false positives.\n We’ve corrected the name, description, and alert message for actions/untrusted-checkout/medium\
  \ to clarify that it applies to a nonprivileged context.\n\n For a full list of changes, please refer to the complete changelog\
  \ for version 2.26.0 . Every new version of CodeQL is automatically deployed to users of GitHub code scanning on github.com.\
  \ The new functionality in CodeQL 2.26.0 will also be included in a future GitHub Enterprise Server (GHES) release. If you\
  \ use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.26.0 adds Kotlin\
  \ 2.4.0 support and AI prompt injection detection appeared first on The GitHub Blog ."
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
- at: '2026-07-10T20:40:56Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-11T08:16:24Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-10-codeql-2-26-0-adds-kotlin-2-4-0-support-and-ai-prompt-injection-detection
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-11T08:16:22Z'
  url: https://github.blog/changelog/2026-07-10-codeql-2-26-0-adds-kotlin-2-4-0-support-and-ai-prompt-injection-detection
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL is the static analysis engine behind GitHub code scanning , which finds and remediates\
  \ security issues in your code. We’ve recently released CodeQL 2.26.0 , which adds support for Kotlin 2.4.0, introduces\
  \ a JavaScript and TypeScript query for system prompt injection, and improves analysis accuracy across multiple languages.\n\
  \n\n Language and framework support\n Kotlin : CodeQL now supports Kotlin versions up to 2.4.0.\n\n\n C# : We’ve added Razor\
  \ Page handler method parameters, such as parameters for OnGet , OnPost , and OnPostAsync , as remote flow sources. Security\
  \ queries such as cs/sql-injection can now detect vulnerabilities involving these parameters in PageModel subclasses.\n\n\
  \n Go : We’ve added models for the log/slog package introduced in Go 1.21. The go/log-injection and go/clear-text-logging\
  \ queries can now detect issues in code that uses slog package functions and slog.Logger methods.\n\n\n JavaScript/TypeScript\
  \ : We’ve added prompt injection sinks for additional OpenAI, Anthropic, and Google GenAI SDK APIs, including Sora prompts,\
  \ OpenAI Realtime session instructions, Anthropic legacy completion prompts, and Google GenAI cached content and system\
  \ instructions.\n\n\n Query changes\n JavaScript/TypeScript\n\n\n\n We’ve added the js/system-prompt-injection query to\
  \ detect when untrusted, user-provided values flow into an AI model’s system prompt, allowing an attacker to manipulate\
  \ the model’s behavior.\n We’ve added the experimental javascript/ssrf-ipv6-transition-incomplete-guard query to detect\
  \ server-side request forgery (SSRF) guards that reject private IPv4 ranges but can be bypassed with IPv6 transition address\
  \ formats.\n\n Go\n\n\n\n The go/unhandled-writable-file-close query now produces fewer false positives. It no longer flags\
  \ a deferred call to Close when every execution path first handles a call to Sync on the same file handle.\n\n Python\n\n\
  \n\n The py/modification-of-locals query no longer flags modifications to a locals() dictionary after it has passed out\
  \ of the scope where it was created, reducing false positives.\n\n Swift\n\n\n\n We’ve improved CryptoKit modeling for the\
  \ swift/weak-sensitive-data-hashing and swift/weak-password-hashing queries. These queries may now detect additional results.\n\
  \n GitHub Actions\n\n\n\n We’ve updated the actions/pr-on-self-hosted-runner query to recognize the latest standard runner\
  \ labels, reducing false positives.\n We’ve corrected the name, description, and alert message for actions/untrusted-checkout/medium\
  \ to clarify that it applies to a nonprivileged context.\n\n For a full list of changes, please refer to the complete changelog\
  \ for version 2.26.0 . Every new version of CodeQL is automatically deployed to users of GitHub code scanning on github.com.\
  \ The new functionality in CodeQL 2.26.0 will also be included in a future GitHub Enterprise Server (GHES) release. If you\
  \ use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.26.0 adds Kotlin\
  \ 2.4.0 support and AI prompt injection detection appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
