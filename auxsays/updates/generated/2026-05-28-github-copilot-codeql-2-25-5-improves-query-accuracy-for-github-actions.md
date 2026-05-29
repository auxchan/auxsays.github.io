---
layout: aux-update
title: GitHub / Copilot CodeQL 2.25.5 improves query accuracy for GitHub Actions official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/codeql-2-25-5-improves-query-accuracy-for-github-actions/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-28-codeql-2-25-5-improves-query-accuracy-for-github-actions
update_download_url: ''
update_version: CodeQL 2.25.5 improves query accuracy for GitHub Actions
update_logo_text: GIT
update_published_at: '2026-05-28T21:09:44Z'
update_last_checked: '2026-05-29T04:46:35Z'
source_last_checked: '2026-05-29T16:10:24Z'
official_body_last_checked: '2026-05-29T16:10:24Z'
record_last_updated: '2026-05-29T04:46:35Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot CodeQL 2.25.5 improves query accuracy for GitHub Actions
update_detail_title: GitHub / Copilot CodeQL 2.25.5 improves query accuracy for GitHub Actions
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot CodeQL 2.25.5 improves query accuracy for GitHub Actions has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot CodeQL 2.25.5 improves query accuracy for GitHub Actions.
release_summary: "CodeQL is the static analysis engine behind GitHub code scanning , which finds and remediates security issues\
  \ in your code. We’ve recently released CodeQL 2.25.5 , which includes accuracy improvements across C/C++, Java/Kotlin,\
  \ and GitHub Actions queries.\n\n\n Language and framework support\n Java/Kotlin\n\n\n\n We’ve introduced a new sink kind,\
  \ path-injection[read] , for Models-as-Data rows that only read from a path (such as ClassLoader.getResource , FileInputStream\
  \ , and FileReader ). This helps queries distinguish read-only path sinks from more dangerous ones.\n\n GitHub Actions\n\
  \n\n\n We’ve extended the poisonable_steps modeling to detect additional sinks, including scripts executed via Python modules\
  \ and go run in directories.\n\n Query changes\n C/C++\n\n\n\n The cpp/cleartext-transmission query no longer raises an\
  \ alert on calls to fscanf (and variants) when the call reads from an input that isn’t a socket, reducing false positives.\n\
  \n Java/Kotlin\n\n\n\n The java/zipslip query no longer reports archive entry names that flow only to read-only path sinks\
  \ such as ClassLoader.getResource , FileInputStream , and FileReader , reducing false positives.\n\n GitHub Actions\n\n\n\
  \n The actions/unpinned-tag query now analyzes composite action metadata ( action.yml and action.yaml files) in addition\
  \ to workflow files, providing more comprehensive detection.\n We’ve fixed the help file descriptions for the actions/untrusted-checkout/critical\
  \ , actions/untrusted-checkout/high , and actions/untrusted-checkout/medium queries.\n We’ve renamed actions/untrusted-checkout/high\
  \ to more clearly describe which parts of the scenario run in a privileged context.\n\n For a full list of changes, please\
  \ refer to the complete changelog for version 2.25.5 . Every new version of CodeQL is automatically deployed to users of\
  \ GitHub code scanning on github.com. The new functionality in CodeQL 2.25.5 will also be included in GitHub Enterprise\
  \ Server (GHES) release 3.22. If you use an older version of GHES, you can manually upgrade your CodeQL version .\n\n\n\n\
  \ The post CodeQL 2.25.5 improves query accuracy for GitHub Actions appeared first on The GitHub Blog ."
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
- at: '2026-05-28T21:09:44Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-29T04:46:37Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-28-codeql-2-25-5-improves-query-accuracy-for-github-actions
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-29T04:46:35Z'
  url: https://github.blog/changelog/2026-05-28-codeql-2-25-5-improves-query-accuracy-for-github-actions
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-29T10:15:56Z'
  url: https://github.blog/changelog/2026-05-28-codeql-2-25-5-improves-query-accuracy-for-github-actions
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-29T16:10:24Z'
  url: https://github.blog/changelog/2026-05-28-codeql-2-25-5-improves-query-accuracy-for-github-actions
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "CodeQL is the static analysis engine behind GitHub code scanning , which finds and remediates\
  \ security issues in your code. We’ve recently released CodeQL 2.25.5 , which includes accuracy improvements across C/C++,\
  \ Java/Kotlin, and GitHub Actions queries.\n\n\n Language and framework support\n Java/Kotlin\n\n\n\n We’ve introduced a\
  \ new sink kind, path-injection[read] , for Models-as-Data rows that only read from a path (such as ClassLoader.getResource\
  \ , FileInputStream , and FileReader ). This helps queries distinguish read-only path sinks from more dangerous ones.\n\n\
  \ GitHub Actions\n\n\n\n We’ve extended the poisonable_steps modeling to detect additional sinks, including scripts executed\
  \ via Python modules and go run in directories.\n\n Query changes\n C/C++\n\n\n\n The cpp/cleartext-transmission query no\
  \ longer raises an alert on calls to fscanf (and variants) when the call reads from an input that isn’t a socket, reducing\
  \ false positives.\n\n Java/Kotlin\n\n\n\n The java/zipslip query no longer reports archive entry names that flow only to\
  \ read-only path sinks such as ClassLoader.getResource , FileInputStream , and FileReader , reducing false positives.\n\n\
  \ GitHub Actions\n\n\n\n The actions/unpinned-tag query now analyzes composite action metadata ( action.yml and action.yaml\
  \ files) in addition to workflow files, providing more comprehensive detection.\n We’ve fixed the help file descriptions\
  \ for the actions/untrusted-checkout/critical , actions/untrusted-checkout/high , and actions/untrusted-checkout/medium\
  \ queries.\n We’ve renamed actions/untrusted-checkout/high to more clearly describe which parts of the scenario run in a\
  \ privileged context.\n\n For a full list of changes, please refer to the complete changelog for version 2.25.5 . Every\
  \ new version of CodeQL is automatically deployed to users of GitHub code scanning on github.com. The new functionality\
  \ in CodeQL 2.25.5 will also be included in GitHub Enterprise Server (GHES) release 3.22. If you use an older version of\
  \ GHES, you can manually upgrade your CodeQL version .\n\n\n\n The post CodeQL 2.25.5 improves query accuracy for GitHub\
  \ Actions appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
