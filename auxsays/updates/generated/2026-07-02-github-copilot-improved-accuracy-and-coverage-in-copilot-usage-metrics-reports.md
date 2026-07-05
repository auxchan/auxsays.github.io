---
layout: aux-update
title: GitHub / Copilot Improved accuracy and coverage in Copilot usage metrics reports official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/improved-accuracy-and-coverage-in-copilot-usage-metrics-reports/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-02-improved-accuracy-and-coverage-in-copilot-usage-metrics-reports
update_download_url: ''
update_version: Improved accuracy and coverage in Copilot usage metrics reports
update_logo_text: GIT
update_published_at: '2026-07-02T23:19:06Z'
update_last_checked: '2026-07-03T04:12:12Z'
source_last_checked: '2026-07-05T09:24:12Z'
official_body_last_checked: '2026-07-05T09:24:12Z'
record_last_updated: '2026-07-03T04:12:12Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Improved accuracy and coverage in Copilot usage metrics reports
update_detail_title: GitHub / Copilot Improved accuracy and coverage in Copilot usage metrics reports
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Improved accuracy and coverage in Copilot usage metrics reports has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Improved accuracy and coverage in Copilot usage metrics reports.
release_summary: "We’ve made three improvements to the Copilot usage metrics API that make its reports more complete and accurate:\
  \ GitHub Copilot CLI now reports suggested lines of code, users seen only through server-side telemetry now have their IDE\
  \ identified, and AI credit consumption is now attributed more completely.\n\n\n What’s new\n\n GitHub Copilot CLI now reports\
  \ suggested lines of code. CLI activity now contributes to the loc_suggested_to_add_sum and loc_suggested_to_delete_sum\
  \ fields, which previously always reported 0 for the CLI. Code generation counts are also more accurate on newer CLI versions,\
  \ where suggested and accepted edits are de-duplicated so the same edit isn’t counted twice.\n IDE identified for more users.\
  \ Users who were previously visible only through server-side telemetry now have their IDE and plugin versions surfaced in\
  \ totals_by_ide , so totals_by_ide reflects more of your Copilot users.\n AI credits attributed more accurately. We fixed\
  \ two issues that caused some users to show 0.0 AI credits despite real usage. First, AI credit consumption not associated\
  \ with an organization was being dropped. It’s now attributed to the correct organization or enterprise. Second, users seen\
  \ only through server-side telemetry were not being matched to their billing data. Their consumption is now included. Thanks\
  \ to these updates, ai_credits_used totals more completely reflect actual consumption.\n\n Why this matters\n\n More complete\
  \ coverage: Surfacing CLI suggested lines of code and identifying IDEs for server-side-only users means fewer blind spots\
  \ in who is using Copilot and how.\n More trustworthy consumption data: Correcting AI credit attribution means ai_credits_used\
  \ totals more accurately reflect what your users actually consumed.\n Consistent analysis across surfaces: As Copilot usage\
  \ spans the IDE, CLI, and server-side surfaces, these updates keep the reports aligned with real activity.\n\n Important\
  \ notes\n\n These metrics are available to enterprise administrators and organization owners who have access to Copilot\
  \ usage metrics through the REST API.\n Copilot CLI reports suggested lines of code from CLI version 1.0.57 onward. Code\
  \ generation de-duplication applies from version 1.0.64 onward. Between 1.0.57 and 1.0.64 , code generation activity may\
  \ be slightly undercounted for the CLI.\n AI credit totals for previously-missed usage will increase as a result of these\
  \ attribution fixes—values that were already reported are unchanged.\n\n Visit the Copilot usage metrics API documentation\
  \ to learn more.\n\n\n\n The post Improved accuracy and coverage in Copilot usage metrics reports appeared first on The\
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
- at: '2026-07-02T23:19:06Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-03T04:12:14Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-02-improved-accuracy-and-coverage-in-copilot-usage-metrics-reports
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-03T04:12:12Z'
  url: https://github.blog/changelog/2026-07-02-improved-accuracy-and-coverage-in-copilot-usage-metrics-reports
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-03T09:37:32Z'
  url: https://github.blog/changelog/2026-07-02-improved-accuracy-and-coverage-in-copilot-usage-metrics-reports
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-03T19:53:01Z'
  url: https://github.blog/changelog/2026-07-02-improved-accuracy-and-coverage-in-copilot-usage-metrics-reports
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-04T09:02:24Z'
  url: https://github.blog/changelog/2026-07-02-improved-accuracy-and-coverage-in-copilot-usage-metrics-reports
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-07-05T09:24:12Z'
  url: https://github.blog/changelog/2026-07-02-improved-accuracy-and-coverage-in-copilot-usage-metrics-reports
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "We’ve made three improvements to the Copilot usage metrics API that make its reports more complete\
  \ and accurate: GitHub Copilot CLI now reports suggested lines of code, users seen only through server-side telemetry now\
  \ have their IDE identified, and AI credit consumption is now attributed more completely.\n\n\n What’s new\n\n GitHub Copilot\
  \ CLI now reports suggested lines of code. CLI activity now contributes to the loc_suggested_to_add_sum and loc_suggested_to_delete_sum\
  \ fields, which previously always reported 0 for the CLI. Code generation counts are also more accurate on newer CLI versions,\
  \ where suggested and accepted edits are de-duplicated so the same edit isn’t counted twice.\n IDE identified for more users.\
  \ Users who were previously visible only through server-side telemetry now have their IDE and plugin versions surfaced in\
  \ totals_by_ide , so totals_by_ide reflects more of your Copilot users.\n AI credits attributed more accurately. We fixed\
  \ two issues that caused some users to show 0.0 AI credits despite real usage. First, AI credit consumption not associated\
  \ with an organization was being dropped. It’s now attributed to the correct organization or enterprise. Second, users seen\
  \ only through server-side telemetry were not being matched to their billing data. Their consumption is now included. Thanks\
  \ to these updates, ai_credits_used totals more completely reflect actual consumption.\n\n Why this matters\n\n More complete\
  \ coverage: Surfacing CLI suggested lines of code and identifying IDEs for server-side-only users means fewer blind spots\
  \ in who is using Copilot and how.\n More trustworthy consumption data: Correcting AI credit attribution means ai_credits_used\
  \ totals more accurately reflect what your users actually consumed.\n Consistent analysis across surfaces: As Copilot usage\
  \ spans the IDE, CLI, and server-side surfaces, these updates keep the reports aligned with real activity.\n\n Important\
  \ notes\n\n These metrics are available to enterprise administrators and organization owners who have access to Copilot\
  \ usage metrics through the REST API.\n Copilot CLI reports suggested lines of code from CLI version 1.0.57 onward. Code\
  \ generation de-duplication applies from version 1.0.64 onward. Between 1.0.57 and 1.0.64 , code generation activity may\
  \ be slightly undercounted for the CLI.\n AI credit totals for previously-missed usage will increase as a result of these\
  \ attribution fixes—values that were already reported are unchanged.\n\n Visit the Copilot usage metrics API documentation\
  \ to learn more.\n\n\n\n The post Improved accuracy and coverage in Copilot usage metrics reports appeared first on The\
  \ GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
