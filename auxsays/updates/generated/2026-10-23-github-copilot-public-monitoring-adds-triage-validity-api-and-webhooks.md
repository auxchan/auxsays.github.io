---
layout: aux-update
title: GitHub / Copilot Public monitoring adds triage, validity, API, and webhooks official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Public monitoring adds triage, validity, API,
  and webhooks.
permalink: /updates/github/github/public-monitoring-adds-triage-validity-api-and-webhooks/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-23-public-monitoring-adds-triage-validity-api-and-webhooks
update_download_url: ''
update_version: Public monitoring adds triage, validity, API, and webhooks
update_logo_text: GIT
update_published_at: '2026-10-23T17:17:58Z'
update_last_checked: '2026-10-24T07:21:14Z'
source_last_checked: '2026-10-24T07:21:14Z'
official_body_last_checked: '2026-10-24T07:21:14Z'
record_last_updated: '2026-10-24T07:21:14Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Public monitoring adds triage, validity, API, and webhooks
update_detail_title: GitHub / Copilot Public monitoring adds triage, validity, API, and webhooks
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Public monitoring adds triage, validity, API, and webhooks has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Public monitoring adds triage, validity, API, and webhooks.
release_summary: "Public monitoring now includes alert management capabilities like automatic validity checks to help you\
  \ triage and remediate leaked secrets at scale.\n\n\n\n Alert management with dismissals, timelines, and filtering\n Always-on\
  \ validity checks for supported secret types\n REST API and webhook support for public monitoring alerts\n\n Alert management\n\
  \ Enterprises with public monitoring can now triage findings directly from the enterprise security dashboard:\n\n\n\n Dismiss\
  \ and reopen alerts: Close alerts as Dismissed or Fixed , provide an optional comment explaining the decision, or reopen\
  \ closed alerts if circumstances change.\n Activity timeline: Review an audit trail of all actions and state changes taken\
  \ on an alert.\n Filter and sort: Filter the alert list by repository, committer, secret type, attribution method (membership\
  \ or verified domain), and state (i.e., open or closed ) to focus on the exposures that matter most.\n\n Closing an alert\
  \ updates its state for your enterprise. It does not revoke the exposed credential or remove it from the public repository.\n\
  \n\n Always-on validity checks\n Public monitoring now automatically checks token validity on an ongoing basis for supported\
  \ providers. Alerts display whether a credential is Active , Inactive , or Unknown , allowing security teams to quickly\
  \ prioritize response for live tokens.\n\n\n REST API and webhook integration\n Bring public monitoring findings into your\
  \ custom incident response pipelines:\n\n\n\n REST API: Enterprise admins and enterprise security managers can query attributed\
  \ findings programmatically using GET /enterprises/{enterprise}/secret-scanning/public-monitoring-alerts . This returns\
  \ alert metadata, secret type, attribution, and exposed locations.\n Enterprise webhooks: Subscribe to the secret_scanning_public_monitoring_alert\
  \ webhook event at the enterprise level to receive real-time notifications whenever a newly detected leak is attributed\
  \ to your organization.\n\n Eligibility and billing\n Public monitoring remains available in public preview for GitHub Enterprise\
  \ Cloud customers, including GitHub Enterprise Cloud with data residency. Enterprise admins and enterprise security managers\
  \ can enable the feature and manage alert settings from the enterprise security dashboard.\n\n\n Public monitoring is included\
  \ with your GitHub Advanced Security or GitHub Secret Protection license at no additional cost.\n\n\n Learn more\n Learn\
  \ more about public monitoring and join the discussion in the GitHub Community .\n\n\n\n The post Public monitoring adds\
  \ triage, validity, API, and webhooks appeared first on The GitHub Blog ."
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
- at: '2026-10-23T17:17:58Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-24T07:21:38Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-23-public-monitoring-adds-triage-validity-api-and-webhooks
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-24T07:21:14Z'
  url: https://github.blog/changelog/2026-10-23-public-monitoring-adds-triage-validity-api-and-webhooks
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Public monitoring now includes alert management capabilities like automatic validity checks to\
  \ help you triage and remediate leaked secrets at scale.\n\n\n\n Alert management with dismissals, timelines, and filtering\n\
  \ Always-on validity checks for supported secret types\n REST API and webhook support for public monitoring alerts\n\n Alert\
  \ management\n Enterprises with public monitoring can now triage findings directly from the enterprise security dashboard:\n\
  \n\n\n Dismiss and reopen alerts: Close alerts as Dismissed or Fixed , provide an optional comment explaining the decision,\
  \ or reopen closed alerts if circumstances change.\n Activity timeline: Review an audit trail of all actions and state changes\
  \ taken on an alert.\n Filter and sort: Filter the alert list by repository, committer, secret type, attribution method\
  \ (membership or verified domain), and state (i.e., open or closed ) to focus on the exposures that matter most.\n\n Closing\
  \ an alert updates its state for your enterprise. It does not revoke the exposed credential or remove it from the public\
  \ repository.\n\n\n Always-on validity checks\n Public monitoring now automatically checks token validity on an ongoing\
  \ basis for supported providers. Alerts display whether a credential is Active , Inactive , or Unknown , allowing security\
  \ teams to quickly prioritize response for live tokens.\n\n\n REST API and webhook integration\n Bring public monitoring\
  \ findings into your custom incident response pipelines:\n\n\n\n REST API: Enterprise admins and enterprise security managers\
  \ can query attributed findings programmatically using GET /enterprises/{enterprise}/secret-scanning/public-monitoring-alerts\
  \ . This returns alert metadata, secret type, attribution, and exposed locations.\n Enterprise webhooks: Subscribe to the\
  \ secret_scanning_public_monitoring_alert webhook event at the enterprise level to receive real-time notifications whenever\
  \ a newly detected leak is attributed to your organization.\n\n Eligibility and billing\n Public monitoring remains available\
  \ in public preview for GitHub Enterprise Cloud customers, including GitHub Enterprise Cloud with data residency. Enterprise\
  \ admins and enterprise security managers can enable the feature and manage alert settings from the enterprise security\
  \ dashboard.\n\n\n Public monitoring is included with your GitHub Advanced Security or GitHub Secret Protection license\
  \ at no additional cost.\n\n\n Learn more\n Learn more about public monitoring and join the discussion in the GitHub Community\
  \ .\n\n\n\n The post Public monitoring adds triage, validity, API, and webhooks appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
