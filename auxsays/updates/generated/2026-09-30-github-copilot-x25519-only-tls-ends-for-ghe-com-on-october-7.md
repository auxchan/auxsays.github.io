---
layout: aux-update
title: GitHub / Copilot X25519-only TLS ends for GHE.com on October 7 official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for X25519-only TLS ends for GHE.com on October
  7.
permalink: /updates/github/github/x25519-only-tls-ends-for-ghe-com-on-october-7/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-30-x25519-only-tls-ends-for-ghe-com-on-september-15
update_download_url: ''
update_version: X25519-only TLS ends for GHE.com on October 7
update_logo_text: GIT
update_published_at: '2026-09-30T13:30:24Z'
update_last_checked: '2026-10-01T06:58:18Z'
source_last_checked: '2026-10-01T06:58:18Z'
official_body_last_checked: '2026-10-01T06:58:18Z'
record_last_updated: '2026-10-01T06:58:18Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot X25519-only TLS ends for GHE.com on October 7
update_detail_title: GitHub / Copilot X25519-only TLS ends for GHE.com on October 7
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot X25519-only TLS ends for GHE.com on October 7 has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot X25519-only TLS ends for GHE.com on October 7.
release_summary: "Beginning October 7, 2026, GitHub Enterprise Cloud with data residency will no longer accept TLS connections\
  \ from clients that offer only X25519 for key agreement.\n\n\n Most customers don’t need to take action. The affected endpoints\
  \ will continue to support the FIPS-approved P-256 ( secp256r1 ) and P-384 ( secp384r1 ) groups. Current browsers, operating\
  \ systems, GitHub CLI releases, and commonly used TLS libraries already support P-256.\n\n\n You may be affected if an application,\
  \ proxy, security appliance, or TLS library is explicitly configured to offer only X25519. Before October 7, 2026, you should:\n\
  \n\n\n Update your operating system, runtime, GitHub CLI, proxy, and TLS libraries to supported versions.\n Remove any X25519-only\
  \ configuration.\n Ensure P-256 ( secp256r1 ) is enabled. You may also enable P-384 ( secp384r1 ).\n\n After October 7,\
  \ X25519-only clients will be unable to establish HTTPS connections. This change applies only to GitHub Enterprise Cloud\
  \ with data residency. SSH connectivity is not affected.\n\n\n If you need help validating your TLS configuration, contact\
  \ GitHub Support .\n\n\n\n The post X25519-only TLS ends for GHE.com on October 7 appeared first on The GitHub Blog ."
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
- at: '2026-09-30T13:30:24Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-01T06:58:39Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-30-x25519-only-tls-ends-for-ghe-com-on-september-15
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-01T06:58:18Z'
  url: https://github.blog/changelog/2026-09-30-x25519-only-tls-ends-for-ghe-com-on-september-15
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Beginning October 7, 2026, GitHub Enterprise Cloud with data residency will no longer accept TLS\
  \ connections from clients that offer only X25519 for key agreement.\n\n\n Most customers don’t need to take action. The\
  \ affected endpoints will continue to support the FIPS-approved P-256 ( secp256r1 ) and P-384 ( secp384r1 ) groups. Current\
  \ browsers, operating systems, GitHub CLI releases, and commonly used TLS libraries already support P-256.\n\n\n You may\
  \ be affected if an application, proxy, security appliance, or TLS library is explicitly configured to offer only X25519.\
  \ Before October 7, 2026, you should:\n\n\n\n Update your operating system, runtime, GitHub CLI, proxy, and TLS libraries\
  \ to supported versions.\n Remove any X25519-only configuration.\n Ensure P-256 ( secp256r1 ) is enabled. You may also enable\
  \ P-384 ( secp384r1 ).\n\n After October 7, X25519-only clients will be unable to establish HTTPS connections. This change\
  \ applies only to GitHub Enterprise Cloud with data residency. SSH connectivity is not affected.\n\n\n If you need help\
  \ validating your TLS configuration, contact GitHub Support .\n\n\n\n The post X25519-only TLS ends for GHE.com on October\
  \ 7 appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
