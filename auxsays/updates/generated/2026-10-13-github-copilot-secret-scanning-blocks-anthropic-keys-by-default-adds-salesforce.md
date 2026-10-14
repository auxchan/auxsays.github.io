---
layout: aux-update
title: GitHub / Copilot Secret scanning blocks Anthropic keys by default, adds Salesforce official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Secret scanning blocks Anthropic keys by default,
  adds Salesforce.
permalink: /updates/github/github/secret-scanning-blocks-anthropic-keys-by-default-adds-salesforce/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-13-secret-scanning-blocks-anthropic-keys-by-default-adds-salesforce
update_download_url: ''
update_version: Secret scanning blocks Anthropic keys by default, adds Salesforce
update_logo_text: GIT
update_published_at: '2026-10-13T16:12:36Z'
update_last_checked: '2026-10-14T07:24:48Z'
source_last_checked: '2026-10-14T07:24:48Z'
official_body_last_checked: '2026-10-14T07:24:48Z'
record_last_updated: '2026-10-14T07:24:48Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Secret scanning blocks Anthropic keys by default, adds Salesforce
update_detail_title: GitHub / Copilot Secret scanning blocks Anthropic keys by default, adds Salesforce
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Secret scanning blocks Anthropic keys by default, adds Salesforce has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Secret scanning blocks Anthropic keys by default, adds Salesforce.
release_summary: "Secret scanning now detects new secret types from Salesforce, Anthropic, and Cloudsmith, with the new Anthropic\
  \ secret types blocked with push protection by default.\n\n\n New secret scanning partner\n Salesforce is now a secret scanning\
  \ partner.\n\n\n When a provider’s secret is found in a public repository, GitHub forwards it to the relevant partner so\
  \ they can revoke or rotate the credential before it can be abused.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Salesforce\n\
  \ salesforce_marketing_cloud_api_oauth2_token\n\n\n\n Detectors added\n Secret scanning now automatically detects the following\
  \ new secret types in your repositories.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Anthropic\n anthropic_service_api_key\n\
  \n\n Anthropic\n anthropic_user_api_key\n\n\n Cloudsmith\n cloudsmith_api_key\n\n\n\n Partner secrets are automatically\
  \ reported to the secret issuer when found in public repositories through the secret scanning partnership program . User\
  \ secrets generate secret scanning alerts when found in public or private repositories.\n\n\n Push protection defaults expanded\n\
  \ The following detectors are now included in push protection by default. Repositories with secret scanning enabled, including\
  \ free public repositories, will have commits containing these secrets automatically blocked.\n\n\n\n\n\n Provider\n Secret\
  \ type\n\n\n\n\n Anthropic\n anthropic_service_api_key\n\n\n Anthropic\n anthropic_user_api_key\n\n\n\n Learn more\n Learn\
  \ more about secret scanning and see the full list of supported secrets in our documentation. Let us know what you think\
  \ in the community discussion .\n\n\n\n The post Secret scanning blocks Anthropic keys by default, adds Salesforce appeared\
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
- at: '2026-10-13T16:12:36Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-14T07:25:09Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-13-secret-scanning-blocks-anthropic-keys-by-default-adds-salesforce
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-14T07:24:48Z'
  url: https://github.blog/changelog/2026-10-13-secret-scanning-blocks-anthropic-keys-by-default-adds-salesforce
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Secret scanning now detects new secret types from Salesforce, Anthropic, and Cloudsmith, with\
  \ the new Anthropic secret types blocked with push protection by default.\n\n\n New secret scanning partner\n Salesforce\
  \ is now a secret scanning partner.\n\n\n When a provider’s secret is found in a public repository, GitHub forwards it to\
  \ the relevant partner so they can revoke or rotate the credential before it can be abused.\n\n\n\n\n\n Provider\n Secret\
  \ type\n\n\n\n\n Salesforce\n salesforce_marketing_cloud_api_oauth2_token\n\n\n\n Detectors added\n Secret scanning now\
  \ automatically detects the following new secret types in your repositories.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n\
  \ Anthropic\n anthropic_service_api_key\n\n\n Anthropic\n anthropic_user_api_key\n\n\n Cloudsmith\n cloudsmith_api_key\n\
  \n\n\n Partner secrets are automatically reported to the secret issuer when found in public repositories through the secret\
  \ scanning partnership program . User secrets generate secret scanning alerts when found in public or private repositories.\n\
  \n\n Push protection defaults expanded\n The following detectors are now included in push protection by default. Repositories\
  \ with secret scanning enabled, including free public repositories, will have commits containing these secrets automatically\
  \ blocked.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Anthropic\n anthropic_service_api_key\n\n\n Anthropic\n anthropic_user_api_key\n\
  \n\n\n Learn more\n Learn more about secret scanning and see the full list of supported secrets in our documentation. Let\
  \ us know what you think in the community discussion .\n\n\n\n The post Secret scanning blocks Anthropic keys by default,\
  \ adds Salesforce appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
