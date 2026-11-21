---
layout: aux-update
title: GitHub / Copilot Secret scanning upgrades detectors, adds SpaceX as partner official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Secret scanning upgrades detectors, adds SpaceX
  as partner.
permalink: /updates/github/github/secret-scanning-upgrades-detectors-adds-spacex-as-partner/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-05-secret-scanning-upgrades-detectors-adds-spacex-as-partner
update_download_url: ''
update_version: Secret scanning upgrades detectors, adds SpaceX as partner
update_logo_text: GIT
update_published_at: '2026-11-05T15:48:50Z'
update_last_checked: '2026-11-05T22:27:22Z'
source_last_checked: '2026-11-06T09:21:50Z'
official_body_last_checked: '2026-11-06T09:21:50Z'
record_last_updated: '2026-11-05T22:27:22Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Secret scanning upgrades detectors, adds SpaceX as partner
update_detail_title: GitHub / Copilot Secret scanning upgrades detectors, adds SpaceX as partner
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Secret scanning upgrades detectors, adds SpaceX as partner has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Secret scanning upgrades detectors, adds SpaceX as partner.
release_summary: "This update expands secret scanning’s detection coverage:\n\n\n\n New partner: SpaceX is now a secret scanning\
  \ partner.\n New detector: GitHub now detects starlink_public_api_v2_secret .\n Upgraded detectors: Alibaba, AWS, Google,\
  \ OpenVSX, Pydantic Services, and Tencent detectors include additional false-positive filtering.\n\n New secret scanning\
  \ partners\n The following provider joined the secret scanning partnership program. When one of their secrets is found in\
  \ a public repository, GitHub forwards it to the partner so they can revoke or rotate the credential before it can be abused.\n\
  \n\n\n\n\n Provider\n Secret type\n\n\n\n\n SpaceX\n starlink_public_api_v2_secret\n\n\n\n Detectors added\n Secret scanning\
  \ now automatically detects the following new secret type in your repositories.\n\n\n\n\n\n Provider\n Secret type\n\n\n\
  \n\n SpaceX\n starlink_public_api_v2_secret\n\n\n\n Partner secrets are automatically reported to the secret issuer when\
  \ found in public repositories through the secret scanning partnership program . User secrets generate secret scanning alerts\
  \ when found in public or private repositories.\n\n\n False positives reduced\n The following detector improvements reduce\
  \ false-positive matches for supported secrets.\n\n\n\n\n\n Provider\n Secret type\n Improvement\n\n\n\n\n Alibaba\n alibaba_cloud_access_key_id\n\
  \ Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\n\n AWS\n aws_access_key_id\n\
  \ Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\n\n AWS\n aws_session_token\n\
  \ Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\n\n AWS\n aws_temporary_access_key_id\n\
  \ Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\n\n Google\n google_cloud_storage_access_key_secret\n\
  \ Suppress unpaired matches when dictionary filtering removes all qualifying companion key identifiers.\n\n\n Google\n google_cloud_storage_service_account_access_key_id\n\
  \ Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\n\n Google\n google_cloud_storage_user_access_key_id\n\
  \ Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\n\n OpenVSX\n openvsx_access_token\n\
  \ Tighten context matching for legacy tokens to avoid treating unrelated UUIDs as credentials.\n\n\n Pydantic Services Inc.\n\
  \ logfire_token\n Match the documented token length and character set to exclude placeholder values and public browser tokens.\n\
  \n\n Tencent\n tencent_cloud_secret_id\n Require both letters and digits after the token prefix to exclude alphabetic identifiers\
  \ such as function names.\n\n\n\n Learn more\n Learn more about secret scanning and see the full list of supported secrets\
  \ in our documentation. Let us know what you think in the community discussion .\n\n\n\n The post Secret scanning upgrades\
  \ detectors, adds SpaceX as partner appeared first on The GitHub Blog ."
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
- at: '2026-11-05T15:48:50Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-05T22:27:34Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-05-secret-scanning-upgrades-detectors-adds-spacex-as-partner
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-05T22:27:22Z'
  url: https://github.blog/changelog/2026-11-05-secret-scanning-upgrades-detectors-adds-spacex-as-partner
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-06T09:21:50Z'
  url: https://github.blog/changelog/2026-11-05-secret-scanning-upgrades-detectors-adds-spacex-as-partner
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "This update expands secret scanning’s detection coverage:\n\n\n\n New partner: SpaceX is now a\
  \ secret scanning partner.\n New detector: GitHub now detects starlink_public_api_v2_secret .\n Upgraded detectors: Alibaba,\
  \ AWS, Google, OpenVSX, Pydantic Services, and Tencent detectors include additional false-positive filtering.\n\n New secret\
  \ scanning partners\n The following provider joined the secret scanning partnership program. When one of their secrets is\
  \ found in a public repository, GitHub forwards it to the partner so they can revoke or rotate the credential before it\
  \ can be abused.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n SpaceX\n starlink_public_api_v2_secret\n\n\n\n Detectors added\n\
  \ Secret scanning now automatically detects the following new secret type in your repositories.\n\n\n\n\n\n Provider\n Secret\
  \ type\n\n\n\n\n SpaceX\n starlink_public_api_v2_secret\n\n\n\n Partner secrets are automatically reported to the secret\
  \ issuer when found in public repositories through the secret scanning partnership program . User secrets generate secret\
  \ scanning alerts when found in public or private repositories.\n\n\n False positives reduced\n The following detector improvements\
  \ reduce false-positive matches for supported secrets.\n\n\n\n\n\n Provider\n Secret type\n Improvement\n\n\n\n\n Alibaba\n\
  \ alibaba_cloud_access_key_id\n Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\
  \n\n AWS\n aws_access_key_id\n Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\
  \n\n AWS\n aws_session_token\n Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\
  \n\n AWS\n aws_temporary_access_key_id\n Suppress unpaired matches when dictionary filtering removes all qualifying companion\
  \ secrets.\n\n\n Google\n google_cloud_storage_access_key_secret\n Suppress unpaired matches when dictionary filtering removes\
  \ all qualifying companion key identifiers.\n\n\n Google\n google_cloud_storage_service_account_access_key_id\n Suppress\
  \ unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\n\n Google\n google_cloud_storage_user_access_key_id\n\
  \ Suppress unpaired matches when dictionary filtering removes all qualifying companion secrets.\n\n\n OpenVSX\n openvsx_access_token\n\
  \ Tighten context matching for legacy tokens to avoid treating unrelated UUIDs as credentials.\n\n\n Pydantic Services Inc.\n\
  \ logfire_token\n Match the documented token length and character set to exclude placeholder values and public browser tokens.\n\
  \n\n Tencent\n tencent_cloud_secret_id\n Require both letters and digits after the token prefix to exclude alphabetic identifiers\
  \ such as function names.\n\n\n\n Learn more\n Learn more about secret scanning and see the full list of supported secrets\
  \ in our documentation. Let us know what you think in the community discussion .\n\n\n\n The post Secret scanning upgrades\
  \ detectors, adds SpaceX as partner appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
