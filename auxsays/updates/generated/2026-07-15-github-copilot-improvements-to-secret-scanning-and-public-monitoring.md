---
layout: aux-update
title: GitHub / Copilot Improvements to secret scanning and public monitoring official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/improvements-to-secret-scanning-and-public-monitoring/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-15-improvements-to-secret-scanning-and-public-monitoring
update_download_url: ''
update_version: Improvements to secret scanning and public monitoring
update_logo_text: GIT
update_published_at: '2026-07-15T22:38:16Z'
update_last_checked: '2026-07-16T08:36:32Z'
source_last_checked: '2026-07-16T08:36:32Z'
official_body_last_checked: '2026-07-16T08:36:32Z'
record_last_updated: '2026-07-16T08:36:32Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Improvements to secret scanning and public monitoring
update_detail_title: GitHub / Copilot Improvements to secret scanning and public monitoring
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Improvements to secret scanning and public monitoring has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Improvements to secret scanning and public monitoring.
release_summary: "This week, we’re rolling out several improvements to secret scanning and public monitoring:\n\n\n\n Resend\
  \ is now a GitHub secret scanning partner.\n Secret scanning now detects new secret types from APIclub and Resend.\n Secret\
  \ scanning now blocks VolcEngine secrets with push protection by default.\n The secret_scanning_alert webhook now includes\
  \ a secret_category field (i.e., default or generic ) so you can distinguish between specific and generic types.\n The public\
  \ monitoring alert list now surfaces insight cards at the top of the page, including a breakdown of associated leaks by\
  \ attribution, your enterprise member count, and your verified domains.\n\n GitHub secret scanning partnership program\n\
  \ GitHub secret scanning protects users by searching repositories for known types of secrets such as tokens and private\
  \ keys. By identifying and flagging these secrets, our scans help prevent data leaks and fraud.\n\n\n We have partnered\
  \ with Resend to scan for their tokens to help secure the development community. GitHub will forward any exposed secrets\
  \ found in public repositories to Resend, who will take appropriate action, including revoking the secret or notifying respect\
  \ admins.\n\n\n Learn more about the secret scanning partnership program . If you are a secret issuer interested in partnering\
  \ with us, you can get started by opening a ticket with GitHub support .\n\n\n Detectors added\n Secret scanning now automatically\
  \ detects the following new secret types in your repositories.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n APIclub\n apiclub_api_key\n\
  \n\n Resend\n resend_api_key\n\n\n\n Partner secrets are automatically reported to the secret issuer when found in public\
  \ repositories through the secret scanning partnership program . User secrets generate secret scanning alerts when found\
  \ in public or private repositories.\n\n\n Push protection defaults expanded\n The following detector is now included in\
  \ push protection by default. Repositories with secret scanning enabled, including free public repositories, will automatically\
  \ block commits containing this secret.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n VolcEngine\n volcengine_ark_api_key\n\
  \n\n\n Distinguish secret categories in the webhook payload\n The secret_scanning_alert webhook payload now includes a secret_category\
  \ field, so you can tell default and generic detections apart without maintaining your own mapping of secret types:\n\n\n\
  \n default : provider patterns plus your custom patterns.\n generic : generic patterns and AI-detected secrets.\n\n This\
  \ mirrors the Default and Generic results views in secret scanning, making it easier to filter, route, and report on alerts\
  \ in your own integrations and automation.\n\n\n New insights on the public monitoring alert list\n The public monitoring\
  \ alert list now shows insight cards at the top of the page, giving your security team at-a-glance context before digging\
  \ into individual alerts:\n\n\n\n Associated leaks by attribution : A breakdown of alert counts by how each leak was attributed\
  \ to your enterprise: member activity (a commit authored by an enterprise member) and verified domain (a committer email\
  \ on one of your verified domains).\n Enterprise members : The total number of members in your enterprise, matching the\
  \ count of members in your enterprise People tab.\n Verified domains : The verified domains associated with your enterprise,\
  \ including both enterprise-owned and organization-owned domains.\n\n Together, these cards help you gauge the scope of\
  \ exposure and understand how leaks are reaching your enterprise, all without leaving the alert list.\n\n\n\n\n\n\n\n Learn\
  \ more\n Learn more about secret scanning , public monitoring , and the full list of supported secrets in our documentation.\
  \ Let us know what you think in the community discussion .\n\n\n\n The post Improvements to secret scanning and public monitoring\
  \ appeared first on The GitHub Blog ."
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
- at: '2026-07-15T22:38:16Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-16T08:36:35Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-15-improvements-to-secret-scanning-and-public-monitoring
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-16T08:36:32Z'
  url: https://github.blog/changelog/2026-07-15-improvements-to-secret-scanning-and-public-monitoring
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "This week, we’re rolling out several improvements to secret scanning and public monitoring:\n\n\
  \n\n Resend is now a GitHub secret scanning partner.\n Secret scanning now detects new secret types from APIclub and Resend.\n\
  \ Secret scanning now blocks VolcEngine secrets with push protection by default.\n The secret_scanning_alert webhook now\
  \ includes a secret_category field (i.e., default or generic ) so you can distinguish between specific and generic types.\n\
  \ The public monitoring alert list now surfaces insight cards at the top of the page, including a breakdown of associated\
  \ leaks by attribution, your enterprise member count, and your verified domains.\n\n GitHub secret scanning partnership\
  \ program\n GitHub secret scanning protects users by searching repositories for known types of secrets such as tokens and\
  \ private keys. By identifying and flagging these secrets, our scans help prevent data leaks and fraud.\n\n\n We have partnered\
  \ with Resend to scan for their tokens to help secure the development community. GitHub will forward any exposed secrets\
  \ found in public repositories to Resend, who will take appropriate action, including revoking the secret or notifying respect\
  \ admins.\n\n\n Learn more about the secret scanning partnership program . If you are a secret issuer interested in partnering\
  \ with us, you can get started by opening a ticket with GitHub support .\n\n\n Detectors added\n Secret scanning now automatically\
  \ detects the following new secret types in your repositories.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n APIclub\n apiclub_api_key\n\
  \n\n Resend\n resend_api_key\n\n\n\n Partner secrets are automatically reported to the secret issuer when found in public\
  \ repositories through the secret scanning partnership program . User secrets generate secret scanning alerts when found\
  \ in public or private repositories.\n\n\n Push protection defaults expanded\n The following detector is now included in\
  \ push protection by default. Repositories with secret scanning enabled, including free public repositories, will automatically\
  \ block commits containing this secret.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n VolcEngine\n volcengine_ark_api_key\n\
  \n\n\n Distinguish secret categories in the webhook payload\n The secret_scanning_alert webhook payload now includes a secret_category\
  \ field, so you can tell default and generic detections apart without maintaining your own mapping of secret types:\n\n\n\
  \n default : provider patterns plus your custom patterns.\n generic : generic patterns and AI-detected secrets.\n\n This\
  \ mirrors the Default and Generic results views in secret scanning, making it easier to filter, route, and report on alerts\
  \ in your own integrations and automation.\n\n\n New insights on the public monitoring alert list\n The public monitoring\
  \ alert list now shows insight cards at the top of the page, giving your security team at-a-glance context before digging\
  \ into individual alerts:\n\n\n\n Associated leaks by attribution : A breakdown of alert counts by how each leak was attributed\
  \ to your enterprise: member activity (a commit authored by an enterprise member) and verified domain (a committer email\
  \ on one of your verified domains).\n Enterprise members : The total number of members in your enterprise, matching the\
  \ count of members in your enterprise People tab.\n Verified domains : The verified domains associated with your enterprise,\
  \ including both enterprise-owned and organization-owned domains.\n\n Together, these cards help you gauge the scope of\
  \ exposure and understand how leaks are reaching your enterprise, all without leaving the alert list.\n\n\n\n\n\n\n\n Learn\
  \ more\n Learn more about secret scanning , public monitoring , and the full list of supported secrets in our documentation.\
  \ Let us know what you think in the community discussion .\n\n\n\n The post Improvements to secret scanning and public monitoring\
  \ appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
