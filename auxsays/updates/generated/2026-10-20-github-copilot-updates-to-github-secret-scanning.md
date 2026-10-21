---
layout: aux-update
title: GitHub / Copilot Updates to GitHub secret scanning official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Updates to GitHub secret scanning.
permalink: /updates/github/github/updates-to-github-secret-scanning/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-20-updates-to-github-secret-scanning
update_download_url: ''
update_version: Updates to GitHub secret scanning
update_logo_text: GIT
update_published_at: '2026-10-20T18:03:55Z'
update_last_checked: '2026-10-20T19:34:17Z'
source_last_checked: '2026-10-21T14:29:24Z'
official_body_last_checked: '2026-10-21T14:29:24Z'
record_last_updated: '2026-10-20T19:34:17Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Updates to GitHub secret scanning
update_detail_title: GitHub / Copilot Updates to GitHub secret scanning
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Updates to GitHub secret scanning has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Updates to GitHub secret scanning.
release_summary: "This update covers improvements and bug fixes for GitHub secret scanning.\n\n\n Update to audit log events\n\
  \ On November 12, 2026 , the business field in affected secret_scanning_alert.* and secret_scanning_push_protection.bypass\
  \ audit log events will change from the enterprise display name to the enterprise slug .\n\n\n To avoid disruption to any\
  \ automated workflows, you should update integrations that filter by display name before rollout to accept both formats\
  \ or use business_id instead. The business field remains a string. Event names and numeric business_id values are unchanged.\n\
  \n\n Recent improvements and bug fixes\n\n Custom pattern alerts: Existing open alerts stay open when a rescan finds that\
  \ they still match an edited custom pattern, rather than being closed and reopened.\n Base64-encoded GitHub tokens: In private\
  \ and internal repositories on github.com with secret scanning enabled, the existing revocation action (public preview)\
  \ now supports encoded personal access tokens (classic), fine-grained personal access tokens, OAuth access tokens, and GitHub\
  \ App user access tokens. GitHub automatically decodes the value.\n Dismissal-request webhooks: Payloads now include exemption_request.number\
  \ , the repository-scoped request number also available in the REST API. Use the repository and request number together\
  \ to correlate requests across integrations.\n Accessibility: The Request pending status on an alert is now keyboard-focusable\
  \ without activating an action. The revocation flow announces progress to screen readers and moves focus to its completion\
  \ panel when that panel appears.\n Bypass-request metadata: Fixed empty secret-type and location details in bypass-request\
  \ API responses and webhook payloads for command-line pushes when another repository rule ran after secret scanning.\n Delegated\
  \ bypass: Fixed push failures caused by existing organization-role entries in reviewer lists, and 500 errors when setting\
  \ valid reviewer configurations for organization-owned repositories through the REST API.\n Custom pattern API: Requests\
  \ rejected by the scanning service for invalid arguments now return 422 instead of 500 , so your integration can distinguish\
  \ these input errors from server failures.\n\n Learn more\n Learn more about enterprise audit log events and the secret\
  \ scanning REST API . Share your feedback in GitHub Community .\n\n\n\n The post Updates to GitHub secret scanning appeared\
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
- at: '2026-10-20T18:03:55Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-20T19:34:34Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-20-updates-to-github-secret-scanning
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-20T19:34:17Z'
  url: https://github.blog/changelog/2026-10-20-updates-to-github-secret-scanning
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-21T00:20:53Z'
  url: https://github.blog/changelog/2026-10-20-updates-to-github-secret-scanning
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-21T07:26:28Z'
  url: https://github.blog/changelog/2026-10-20-updates-to-github-secret-scanning
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-21T14:29:24Z'
  url: https://github.blog/changelog/2026-10-20-updates-to-github-secret-scanning
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "This update covers improvements and bug fixes for GitHub secret scanning.\n\n\n Update to audit\
  \ log events\n On November 12, 2026 , the business field in affected secret_scanning_alert.* and secret_scanning_push_protection.bypass\
  \ audit log events will change from the enterprise display name to the enterprise slug .\n\n\n To avoid disruption to any\
  \ automated workflows, you should update integrations that filter by display name before rollout to accept both formats\
  \ or use business_id instead. The business field remains a string. Event names and numeric business_id values are unchanged.\n\
  \n\n Recent improvements and bug fixes\n\n Custom pattern alerts: Existing open alerts stay open when a rescan finds that\
  \ they still match an edited custom pattern, rather than being closed and reopened.\n Base64-encoded GitHub tokens: In private\
  \ and internal repositories on github.com with secret scanning enabled, the existing revocation action (public preview)\
  \ now supports encoded personal access tokens (classic), fine-grained personal access tokens, OAuth access tokens, and GitHub\
  \ App user access tokens. GitHub automatically decodes the value.\n Dismissal-request webhooks: Payloads now include exemption_request.number\
  \ , the repository-scoped request number also available in the REST API. Use the repository and request number together\
  \ to correlate requests across integrations.\n Accessibility: The Request pending status on an alert is now keyboard-focusable\
  \ without activating an action. The revocation flow announces progress to screen readers and moves focus to its completion\
  \ panel when that panel appears.\n Bypass-request metadata: Fixed empty secret-type and location details in bypass-request\
  \ API responses and webhook payloads for command-line pushes when another repository rule ran after secret scanning.\n Delegated\
  \ bypass: Fixed push failures caused by existing organization-role entries in reviewer lists, and 500 errors when setting\
  \ valid reviewer configurations for organization-owned repositories through the REST API.\n Custom pattern API: Requests\
  \ rejected by the scanning service for invalid arguments now return 422 instead of 500 , so your integration can distinguish\
  \ these input errors from server failures.\n\n Learn more\n Learn more about enterprise audit log events and the secret\
  \ scanning REST API . Share your feedback in GitHub Community .\n\n\n\n The post Updates to GitHub secret scanning appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
