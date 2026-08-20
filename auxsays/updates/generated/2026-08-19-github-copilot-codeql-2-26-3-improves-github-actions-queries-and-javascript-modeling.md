---
layout: aux-update
title: GitHub / Copilot CodeQL 2.26.3 improves GitHub Actions queries and JavaScript modeling official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/codeql-2-26-3-improves-github-actions-queries-and-javascript-modeling/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-19-codeql-2-26-3-improves-github-actions-queries-and-javascript-modeling
update_download_url: ''
update_version: CodeQL 2.26.3 improves GitHub Actions queries and JavaScript modeling
update_logo_text: GIT
update_published_at: '2026-08-19T21:09:30Z'
update_last_checked: '2026-08-20T03:01:37Z'
source_last_checked: '2026-08-20T14:22:36Z'
official_body_last_checked: '2026-08-20T14:22:36Z'
record_last_updated: '2026-08-20T03:01:37Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.26.3 improves GitHub Actions queries and JavaScript modeling
update_detail_title: GitHub / Copilot CodeQL 2.26.3 improves GitHub Actions queries and JavaScript modeling
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.26.3 improves GitHub Actions queries and JavaScript modeling has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.26.3 improves GitHub Actions queries and JavaScript modeling.
release_summary: "CodeQL 2.26.3 adds JavaScript, TypeScript, and Vue source modeling and improves the accuracy of several\
  \ GitHub Actions queries. CodeQL is the static analysis engine behind GitHub code scanning , which helps you find and remediate\
  \ security issues in your code.\n\n\n Language and framework support\n GitHub Actions\n\n\n\n Analysis now recognizes untrusted\
  \ data in github.event.merge_group for workflows triggered by the merge_group event.\n Breaking change: We’ve removed the\
  \ codeql.actions.security.SelfHostedQuery module because runner labels don’t reliably distinguish self-hosted runners from\
  \ managed runners. You’ll need to update any custom queries that rely on this module.\n\n JavaScript/TypeScript\n\n\n\n\
  \ Custom models can now reference specific files using a package name in the form file:<path> . This lets you define sources\
  \ and sinks based on a file’s public exports.\n We’ve added flow models for Vue’s ref , shallowRef , toRef , reactive ,\
  \ and computed Composition API helpers.\n CodeQL now recognizes Vue Router’s useRoute() Composition API as a client-side\
  \ remote flow source, including its query , params , path , fullPath , and hash members.\n CodeQL now treats declared inputs\
  \ properties in Sails Action2 controller files as remote flow sources. This may improve results for queries such as js/path-injection\
  \ .\n Queries using the response threat model now track promise-wrapped client response data into promise fulfillment values.\
  \ This may improve results for queries such as js/xss .\n\n C/C++\n\n\n\n We’ve added flow source models for RegQueryValue\
  \ and related functions from the winreg.h Windows header.\n\n Ruby\n\n\n\n We’ve removed library input to vendored gems\
  \ from the set of taint sources, reducing false positives for several queries when you use vendoring.\n\n Query changes\n\
  \ GitHub Actions\n\n\n\n We’ve improved the accuracy of the actions/output-clobbering/high query so it no longer reports\
  \ simple jq path filters when their output remains JSON-encoded. We also implemented a fix for a performance issue in this\
  \ query caused by unescaped regular expression input.\n The actions/cache-poisoning/poisonable-step and actions/untrusted-checkout/critical\
  \ queries now start paths at the expressions that control untrusted checkouts, making alerts easier to follow.\n GitHub\
  \ Actions queries now correctly classify the schedule event when determining whether a workflow can be externally triggered.\n\
  \ The actions/envvar-injection/critical query now requires the untrusted source and privileged context to originate from\
  \ the same trigger event. It also no longer treats pull request head labels as injection-capable because they can’t contain\
  \ newlines.\n The actions/cache-poisoning/code-injection , actions/cache-poisoning/direct-cache , and actions/cache-poisoning/poisonable-step\
  \ queries now account for read-only cache access on low-trust triggers running in the default branch scope. They retain\
  \ results only for triggers that GitHub allows to write to that cache scope.\n We’ve clarified the name and alert message\
  \ of the actions/cache-poisoning/code-injection query.\n\n JavaScript/TypeScript\n\n\n\n The js/missing-rate-limiting query\
  \ now recognizes the @fastify/rate-limit package as a rate limiter.\n\n For all changes, see the complete CodeQL 2.26.3\
  \ changelog .\n\n\n GitHub automatically deploys each new CodeQL version to users of GitHub code scanning on GitHub.com.\
  \ A future GitHub Enterprise Server (GHES) release will include this functionality. If you use an older GHES version, you\
  \ can manually upgrade CodeQL .\n\n\n\n The post CodeQL 2.26.3 improves GitHub Actions queries and JavaScript modeling appeared\
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
- at: '2026-08-19T21:09:30Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-20T03:01:41Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-19-codeql-2-26-3-improves-github-actions-queries-and-javascript-modeling
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-20T03:01:37Z'
  url: https://github.blog/changelog/2026-08-19-codeql-2-26-3-improves-github-actions-queries-and-javascript-modeling
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-20T08:17:25Z'
  url: https://github.blog/changelog/2026-08-19-codeql-2-26-3-improves-github-actions-queries-and-javascript-modeling
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-20T14:22:36Z'
  url: https://github.blog/changelog/2026-08-19-codeql-2-26-3-improves-github-actions-queries-and-javascript-modeling
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL 2.26.3 adds JavaScript, TypeScript, and Vue source modeling and improves the accuracy of\
  \ several GitHub Actions queries. CodeQL is the static analysis engine behind GitHub code scanning , which helps you find\
  \ and remediate security issues in your code.\n\n\n Language and framework support\n GitHub Actions\n\n\n\n Analysis now\
  \ recognizes untrusted data in github.event.merge_group for workflows triggered by the merge_group event.\n Breaking change:\
  \ We’ve removed the codeql.actions.security.SelfHostedQuery module because runner labels don’t reliably distinguish self-hosted\
  \ runners from managed runners. You’ll need to update any custom queries that rely on this module.\n\n JavaScript/TypeScript\n\
  \n\n\n Custom models can now reference specific files using a package name in the form file:<path> . This lets you define\
  \ sources and sinks based on a file’s public exports.\n We’ve added flow models for Vue’s ref , shallowRef , toRef , reactive\
  \ , and computed Composition API helpers.\n CodeQL now recognizes Vue Router’s useRoute() Composition API as a client-side\
  \ remote flow source, including its query , params , path , fullPath , and hash members.\n CodeQL now treats declared inputs\
  \ properties in Sails Action2 controller files as remote flow sources. This may improve results for queries such as js/path-injection\
  \ .\n Queries using the response threat model now track promise-wrapped client response data into promise fulfillment values.\
  \ This may improve results for queries such as js/xss .\n\n C/C++\n\n\n\n We’ve added flow source models for RegQueryValue\
  \ and related functions from the winreg.h Windows header.\n\n Ruby\n\n\n\n We’ve removed library input to vendored gems\
  \ from the set of taint sources, reducing false positives for several queries when you use vendoring.\n\n Query changes\n\
  \ GitHub Actions\n\n\n\n We’ve improved the accuracy of the actions/output-clobbering/high query so it no longer reports\
  \ simple jq path filters when their output remains JSON-encoded. We also implemented a fix for a performance issue in this\
  \ query caused by unescaped regular expression input.\n The actions/cache-poisoning/poisonable-step and actions/untrusted-checkout/critical\
  \ queries now start paths at the expressions that control untrusted checkouts, making alerts easier to follow.\n GitHub\
  \ Actions queries now correctly classify the schedule event when determining whether a workflow can be externally triggered.\n\
  \ The actions/envvar-injection/critical query now requires the untrusted source and privileged context to originate from\
  \ the same trigger event. It also no longer treats pull request head labels as injection-capable because they can’t contain\
  \ newlines.\n The actions/cache-poisoning/code-injection , actions/cache-poisoning/direct-cache , and actions/cache-poisoning/poisonable-step\
  \ queries now account for read-only cache access on low-trust triggers running in the default branch scope. They retain\
  \ results only for triggers that GitHub allows to write to that cache scope.\n We’ve clarified the name and alert message\
  \ of the actions/cache-poisoning/code-injection query.\n\n JavaScript/TypeScript\n\n\n\n The js/missing-rate-limiting query\
  \ now recognizes the @fastify/rate-limit package as a rate limiter.\n\n For all changes, see the complete CodeQL 2.26.3\
  \ changelog .\n\n\n GitHub automatically deploys each new CodeQL version to users of GitHub code scanning on GitHub.com.\
  \ A future GitHub Enterprise Server (GHES) release will include this functionality. If you use an older GHES version, you\
  \ can manually upgrade CodeQL .\n\n\n\n The post CodeQL 2.26.3 improves GitHub Actions queries and JavaScript modeling appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
