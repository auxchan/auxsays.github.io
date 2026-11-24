---
layout: aux-update
title: GitHub / Copilot GitHub Enterprise Server 3.23 release candidate official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for GitHub Enterprise Server 3.23 release candidate.
permalink: /updates/github/github/github-enterprise-server-3-23-release-candidate/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-20-github-enterprise-server-3-23-release-candidate
update_download_url: ''
update_version: GitHub Enterprise Server 3.23 release candidate
update_logo_text: GIT
update_published_at: '2026-11-20T20:41:26Z'
update_last_checked: '2026-11-20T23:13:30Z'
source_last_checked: '2026-11-24T03:01:46Z'
official_body_last_checked: '2026-11-24T03:01:46Z'
record_last_updated: '2026-11-20T23:13:30Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub Enterprise Server 3.23 release candidate
update_detail_title: GitHub / Copilot GitHub Enterprise Server 3.23 release candidate
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub Enterprise Server 3.23 release candidate has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub Enterprise Server 3.23 release candidate.
release_summary: "GitHub Enterprise Server (GHES) 3.23 is now available and introduces new capabilities across the platform.\
  \ Here are a few highlights in the 3.23 release:\n\n\n\n When working in GitHub Projects, you can create more precise project\
  \ views by combining filters with logical OR , explicit AND , and parentheses for grouping. For example, (status:Done OR\
  \ status:Todo) is:issue shows issues with either status.\n\n\n If your enterprise uses GitHub Secret Protection, you can\
  \ detect unstructured secrets entirely within your network using AI secret detection on GHES, including in air-gapped environments.\
  \ A self-contained, fine-tuned model runs on the appliance’s CPU without a GPU, hosted LLM, or outbound connection. This\
  \ feature is in public preview and subject to change.\n\n\n\n\n As a developer, you can identify known malicious packages\
  \ in PyPI, Maven, RubyGems, NuGet, Go, Rust, and Composer through the GitHub Advisory Database, in addition to npm. The\
  \ database automatically ingests malware advisories from OpenSSF’s malicious-packages repository to expand coverage across\
  \ these ecosystems.\n\n\n\n\n By default, Dependabot waits until a package version has been available on its registry for\
  \ at least three days before opening a version update pull request. This cooldown gives maintainers and the community more\
  \ time to detect and report compromised or buggy releases before users merge updates.\n\n\n\n\n As an OAuth app developer,\
  \ you can limit token lifetimes by using access tokens that expire after eight hours and refresh tokens to obtain new access\
  \ tokens. Token expiration is opt-in for existing OAuth apps and the default for newly created apps. You can request expiring\
  \ tokens with scope=offline_access during authorization for testing and gradual rollout, or require expiration in your app\
  \ registration. Before requiring expiration, you must update all clients to request, store, and use refresh tokens to avoid\
  \ breaking sign-in for clients that do not support them. This feature is in public preview and subject to change.\n\n\n\n\
  \n In your GHES cluster, you can now move the Redis primary from a node that also runs other services, such as MySQL, to\
  \ a dedicated node. Redis then uses the dedicated node’s resources and data volume rather than sharing them with those services.\
  \ This procedure does not attach a new disk to an existing node or use an external Redis service.\n\n\n\n\n Release candidates\
  \ let you try the latest features early and share feedback before general availability. To learn more, see About upgrades\
  \ to new releases and the GHES 3.23 release notes . To get started, download the GHES 3.23 release candidate .\n\n\n If\
  \ you have feedback or questions about the release candidate, contact GitHub Support .\n\n\n\n The post GitHub Enterprise\
  \ Server 3.23 release candidate appeared first on The GitHub Blog ."
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
- at: '2026-11-20T20:41:26Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-20T23:13:58Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-20-github-enterprise-server-3-23-release-candidate
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-21T22:22:38Z'
  url: https://github.blog/changelog/2026-11-20-github-enterprise-server-3-23-release-candidate
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-22T09:44:36Z'
  url: https://github.blog/changelog/2026-11-20-github-enterprise-server-3-23-release-candidate
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-22T22:32:43Z'
  url: https://github.blog/changelog/2026-11-20-github-enterprise-server-3-23-release-candidate
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-23T11:03:18Z'
  url: https://github.blog/changelog/2026-11-20-github-enterprise-server-3-23-release-candidate
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-24T03:01:46Z'
  url: https://github.blog/changelog/2026-11-20-github-enterprise-server-3-23-release-candidate
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub Enterprise Server (GHES) 3.23 is now available and introduces new capabilities across the\
  \ platform. Here are a few highlights in the 3.23 release:\n\n\n\n When working in GitHub Projects, you can create more\
  \ precise project views by combining filters with logical OR , explicit AND , and parentheses for grouping. For example,\
  \ (status:Done OR status:Todo) is:issue shows issues with either status.\n\n\n If your enterprise uses GitHub Secret Protection,\
  \ you can detect unstructured secrets entirely within your network using AI secret detection on GHES, including in air-gapped\
  \ environments. A self-contained, fine-tuned model runs on the appliance’s CPU without a GPU, hosted LLM, or outbound connection.\
  \ This feature is in public preview and subject to change.\n\n\n\n\n As a developer, you can identify known malicious packages\
  \ in PyPI, Maven, RubyGems, NuGet, Go, Rust, and Composer through the GitHub Advisory Database, in addition to npm. The\
  \ database automatically ingests malware advisories from OpenSSF’s malicious-packages repository to expand coverage across\
  \ these ecosystems.\n\n\n\n\n By default, Dependabot waits until a package version has been available on its registry for\
  \ at least three days before opening a version update pull request. This cooldown gives maintainers and the community more\
  \ time to detect and report compromised or buggy releases before users merge updates.\n\n\n\n\n As an OAuth app developer,\
  \ you can limit token lifetimes by using access tokens that expire after eight hours and refresh tokens to obtain new access\
  \ tokens. Token expiration is opt-in for existing OAuth apps and the default for newly created apps. You can request expiring\
  \ tokens with scope=offline_access during authorization for testing and gradual rollout, or require expiration in your app\
  \ registration. Before requiring expiration, you must update all clients to request, store, and use refresh tokens to avoid\
  \ breaking sign-in for clients that do not support them. This feature is in public preview and subject to change.\n\n\n\n\
  \n In your GHES cluster, you can now move the Redis primary from a node that also runs other services, such as MySQL, to\
  \ a dedicated node. Redis then uses the dedicated node’s resources and data volume rather than sharing them with those services.\
  \ This procedure does not attach a new disk to an existing node or use an external Redis service.\n\n\n\n\n Release candidates\
  \ let you try the latest features early and share feedback before general availability. To learn more, see About upgrades\
  \ to new releases and the GHES 3.23 release notes . To get started, download the GHES 3.23 release candidate .\n\n\n If\
  \ you have feedback or questions about the release candidate, contact GitHub Support .\n\n\n\n The post GitHub Enterprise\
  \ Server 3.23 release candidate appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
