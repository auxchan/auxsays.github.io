---
layout: aux-update
title: GitHub / Copilot Code coverage uploads now flag invalid report formats official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Code coverage uploads now flag invalid report
  formats.
permalink: /updates/github/github/code-coverage-uploads-now-flag-invalid-report-formats/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-23-code-coverage-uploads-now-flag-invalid-report-formats
update_download_url: ''
update_version: Code coverage uploads now flag invalid report formats
update_logo_text: GIT
update_published_at: '2026-11-23T15:28:36Z'
update_last_checked: '2026-11-24T12:51:38Z'
source_last_checked: '2026-11-24T12:51:38Z'
official_body_last_checked: '2026-11-24T12:51:38Z'
record_last_updated: '2026-11-24T12:51:38Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Code coverage uploads now flag invalid report formats
update_detail_title: GitHub / Copilot Code coverage uploads now flag invalid report formats
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Code coverage uploads now flag invalid report formats has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Code coverage uploads now flag invalid report formats.
release_summary: "The GitHub Code Quality upload-code-coverage action now checks that your coverage report is in Cobertura\
  \ XML format. If it isn’t in a supported format, the upload step fails and the Actions log shows this error:\n\n\n\n This\
  \ file is not a Cobertura XML report. Upload a Cobertura XML report.\n\n\n\n Previously, these uploads appeared to succeed,\
  \ but no coverage showed up on your pull requests. Now you’ll find out about the problem in the workflow run, with a clear\
  \ next step.\n\n\n If your workflow begins failing with this error, configure your test framework to output Cobertura XML,\
  \ or convert your report to Cobertura XML before the upload step.\n\n\n We’ve also made processing more forgiving for valid\
  \ Cobertura reports. We no longer reject a report because of minor structural issues, and we skip individual lines that\
  \ don’t have a usable line number or hit count instead of discarding the whole report.\n\n\n To use code coverage, you need\
  \ GitHub Code Quality enabled for your repository. This change is available now on GitHub Enterprise Cloud and GitHub Team,\
  \ including GitHub Enterprise Cloud with data residency. It isn’t available on GitHub Enterprise Server. Learn more about\
  \ setting up code coverage for your repository on GitHub Enterprise Cloud .\n\n\n\n The post Code coverage uploads now flag\
  \ invalid report formats appeared first on The GitHub Blog ."
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
- at: '2026-11-23T15:28:36Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-24T12:51:51Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-23-code-coverage-uploads-now-flag-invalid-report-formats
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-24T12:51:38Z'
  url: https://github.blog/changelog/2026-11-23-code-coverage-uploads-now-flag-invalid-report-formats
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The GitHub Code Quality upload-code-coverage action now checks that your coverage report is in\
  \ Cobertura XML format. If it isn’t in a supported format, the upload step fails and the Actions log shows this error:\n\
  \n\n\n This file is not a Cobertura XML report. Upload a Cobertura XML report.\n\n\n\n Previously, these uploads appeared\
  \ to succeed, but no coverage showed up on your pull requests. Now you’ll find out about the problem in the workflow run,\
  \ with a clear next step.\n\n\n If your workflow begins failing with this error, configure your test framework to output\
  \ Cobertura XML, or convert your report to Cobertura XML before the upload step.\n\n\n We’ve also made processing more forgiving\
  \ for valid Cobertura reports. We no longer reject a report because of minor structural issues, and we skip individual lines\
  \ that don’t have a usable line number or hit count instead of discarding the whole report.\n\n\n To use code coverage,\
  \ you need GitHub Code Quality enabled for your repository. This change is available now on GitHub Enterprise Cloud and\
  \ GitHub Team, including GitHub Enterprise Cloud with data residency. It isn’t available on GitHub Enterprise Server. Learn\
  \ more about setting up code coverage for your repository on GitHub Enterprise Cloud .\n\n\n\n The post Code coverage uploads\
  \ now flag invalid report formats appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
