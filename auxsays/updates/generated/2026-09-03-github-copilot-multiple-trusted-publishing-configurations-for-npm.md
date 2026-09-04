---
layout: aux-update
title: GitHub / Copilot Multiple trusted publishing configurations for npm official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Multiple trusted publishing configurations for
  npm.
permalink: /updates/github/github/multiple-trusted-publishing-configurations-for-npm/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-03-multiple-trusted-publishing-configurations-for-npm
update_download_url: ''
update_version: Multiple trusted publishing configurations for npm
update_logo_text: GIT
update_published_at: '2026-09-03T20:34:34Z'
update_last_checked: '2026-09-03T21:57:51Z'
source_last_checked: '2026-09-04T13:20:04Z'
official_body_last_checked: '2026-09-04T13:20:04Z'
record_last_updated: '2026-09-03T21:57:51Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Multiple trusted publishing configurations for npm
update_detail_title: GitHub / Copilot Multiple trusted publishing configurations for npm
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Multiple trusted publishing configurations for npm has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Multiple trusted publishing configurations for npm.
release_summary: "We’re continuing to make trusted publishing smoother for npm publishers, guided by maintainers feedback.\
  \ Three updates to npm publishing are now generally available:\n\n\n\n Multiple trusted publishing configurations per package\n\
  \ Staged packages can only be approved after malware scanning is complete\n Maintainers can see their staged history in\
  \ the package versions tab\n\n A package can now have more than one trusted publishing (OIDC) configuration. Maintainers\
  \ are no longer limited to one configuration per package to separate workflows with stable, prerelease, or staging versions.\
  \ Before this, maintainers had to depend on workflow workarounds or keep a long-lived token around for the paths OIDC couldn’t\
  \ cover.\n\n\n Each configuration is independent and additive, with its own repository, workflow, and environment criteria.\
  \ You can add, list, and remove them from your package’s settings page. A publish or stage is authorized if the incoming\
  \ OIDC token matches any one configuration. Configurations never restrict one another, and evaluation order is not guaranteed,\
  \ so don’t build logic that depends on which configuration matches.\n\n\n Every trusted publishing configuration can stage\
  \ a package by default. Direct publishing is opt-in per configuration. We recommend keeping your configurations to staging\
  \ only. Staged publishing adds a human approval step before a version becomes available, so a compromised workflow can’t\
  \ push straight to the registry.\n\n\n Since we introduced publish-time malware scanning, packages are scanned before they\
  \ become available. In the staged publishing queue, the approval button is now disabled while a package is still being scanned\
  \ and becomes available once the scan completes. The page refreshes status every minute.\n\n\n The versions tab on npmjs.com\
  \ now shows to respective maintainers a detailed history for each version, including whether it was approved, rejected,\
  \ or still staged.\n\n\n Follow along and ask questions in the community discussion .\n\n\n\n The post Multiple trusted\
  \ publishing configurations for npm appeared first on The GitHub Blog ."
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
- at: '2026-09-03T20:34:34Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-03T21:57:59Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-03-multiple-trusted-publishing-configurations-for-npm
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-03T21:57:51Z'
  url: https://github.blog/changelog/2026-09-03-multiple-trusted-publishing-configurations-for-npm
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-04T07:19:07Z'
  url: https://github.blog/changelog/2026-09-03-multiple-trusted-publishing-configurations-for-npm
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-04T13:20:04Z'
  url: https://github.blog/changelog/2026-09-03-multiple-trusted-publishing-configurations-for-npm
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "We’re continuing to make trusted publishing smoother for npm publishers, guided by maintainers\
  \ feedback. Three updates to npm publishing are now generally available:\n\n\n\n Multiple trusted publishing configurations\
  \ per package\n Staged packages can only be approved after malware scanning is complete\n Maintainers can see their staged\
  \ history in the package versions tab\n\n A package can now have more than one trusted publishing (OIDC) configuration.\
  \ Maintainers are no longer limited to one configuration per package to separate workflows with stable, prerelease, or staging\
  \ versions. Before this, maintainers had to depend on workflow workarounds or keep a long-lived token around for the paths\
  \ OIDC couldn’t cover.\n\n\n Each configuration is independent and additive, with its own repository, workflow, and environment\
  \ criteria. You can add, list, and remove them from your package’s settings page. A publish or stage is authorized if the\
  \ incoming OIDC token matches any one configuration. Configurations never restrict one another, and evaluation order is\
  \ not guaranteed, so don’t build logic that depends on which configuration matches.\n\n\n Every trusted publishing configuration\
  \ can stage a package by default. Direct publishing is opt-in per configuration. We recommend keeping your configurations\
  \ to staging only. Staged publishing adds a human approval step before a version becomes available, so a compromised workflow\
  \ can’t push straight to the registry.\n\n\n Since we introduced publish-time malware scanning, packages are scanned before\
  \ they become available. In the staged publishing queue, the approval button is now disabled while a package is still being\
  \ scanned and becomes available once the scan completes. The page refreshes status every minute.\n\n\n The versions tab\
  \ on npmjs.com now shows to respective maintainers a detailed history for each version, including whether it was approved,\
  \ rejected, or still staged.\n\n\n Follow along and ask questions in the community discussion .\n\n\n\n The post Multiple\
  \ trusted publishing configurations for npm appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
