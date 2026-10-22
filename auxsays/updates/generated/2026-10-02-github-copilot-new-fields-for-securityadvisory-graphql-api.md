---
layout: aux-update
title: GitHub / Copilot New fields for SecurityAdvisory GraphQL API official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for New fields for SecurityAdvisory GraphQL API.
permalink: /updates/github/github/new-fields-for-securityadvisory-graphql-api/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-02-new-fields-for-securityadvisory-graphql-api
update_download_url: ''
update_version: New fields for SecurityAdvisory GraphQL API
update_logo_text: GIT
update_published_at: '2026-10-02T13:18:00Z'
update_last_checked: '2026-10-03T07:46:49Z'
source_last_checked: '2026-10-03T07:46:49Z'
official_body_last_checked: '2026-10-03T07:46:49Z'
record_last_updated: '2026-10-03T07:46:49Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot New fields for SecurityAdvisory GraphQL API
update_detail_title: GitHub / Copilot New fields for SecurityAdvisory GraphQL API
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot New fields for SecurityAdvisory GraphQL API has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot New fields for SecurityAdvisory GraphQL API.
release_summary: "You can now read more of the GitHub Advisory Database directly from the GraphQL API without falling back\
  \ to the REST API.\n\n\n The SecurityAdvisory object gained five new fields:\n\n\n\n cveId : The advisory’s CVE identifier.\n\
  \ sourceCodeLocation : A link to the affected source code relevant to the advisory.\n githubReviewedAt : When GitHub reviewed\
  \ the advisory.\n nvdPublishedAt : When the National Vulnerability Database (NVD) published its record.\n repositoryAdvisoryUrl\
  \ : A link to the linked repository security advisory when there is one.\n\n The securityAdvisories query also gained two\
  \ new filters, severities and isWithdrawn , so you can narrow results on the server instead of downloading everything and\
  \ filtering it yourself. They work alongside the filters you already use, such as classification, identifier, EPSS, and\
  \ published or updated since.\n\n\n This means fewer round trips, one authentication path, and one rate limit budget for\
  \ integrations that read advisory data. It also makes it easier to build things like severity-based triage feeds, withdrawn\
  \ advisory audits, and tracking of how quickly advisories move from NVD publication to GitHub review.\n\n\n These changes\
  \ are additive and read-only, so your existing queries keep working.\n\n\n Learn more in the GraphQL API documentation and\
  \ share your feedback .\n\n\n\n The post New fields for SecurityAdvisory GraphQL API appeared first on The GitHub Blog ."
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
- at: '2026-10-02T13:18:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-03T07:47:04Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-02-new-fields-for-securityadvisory-graphql-api
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-03T07:46:49Z'
  url: https://github.blog/changelog/2026-10-02-new-fields-for-securityadvisory-graphql-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now read more of the GitHub Advisory Database directly from the GraphQL API without falling\
  \ back to the REST API.\n\n\n The SecurityAdvisory object gained five new fields:\n\n\n\n cveId : The advisory’s CVE identifier.\n\
  \ sourceCodeLocation : A link to the affected source code relevant to the advisory.\n githubReviewedAt : When GitHub reviewed\
  \ the advisory.\n nvdPublishedAt : When the National Vulnerability Database (NVD) published its record.\n repositoryAdvisoryUrl\
  \ : A link to the linked repository security advisory when there is one.\n\n The securityAdvisories query also gained two\
  \ new filters, severities and isWithdrawn , so you can narrow results on the server instead of downloading everything and\
  \ filtering it yourself. They work alongside the filters you already use, such as classification, identifier, EPSS, and\
  \ published or updated since.\n\n\n This means fewer round trips, one authentication path, and one rate limit budget for\
  \ integrations that read advisory data. It also makes it easier to build things like severity-based triage feeds, withdrawn\
  \ advisory audits, and tracking of how quickly advisories move from NVD publication to GitHub review.\n\n\n These changes\
  \ are additive and read-only, so your existing queries keep working.\n\n\n Learn more in the GraphQL API documentation and\
  \ share your feedback .\n\n\n\n The post New fields for SecurityAdvisory GraphQL API appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
