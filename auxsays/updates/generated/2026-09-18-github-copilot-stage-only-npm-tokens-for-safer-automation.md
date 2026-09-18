---
layout: aux-update
title: GitHub / Copilot Stage-only npm tokens for safer automation official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Stage-only npm tokens for safer automation.
permalink: /updates/github/github/stage-only-npm-tokens-for-safer-automation/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-18-stage-only-npm-tokens-for-safer-automation
update_download_url: ''
update_version: Stage-only npm tokens for safer automation
update_logo_text: GIT
update_published_at: '2026-09-18T16:37:50Z'
update_last_checked: '2026-09-18T18:39:47Z'
source_last_checked: '2026-09-18T22:54:09Z'
official_body_last_checked: '2026-09-18T22:54:09Z'
record_last_updated: '2026-09-18T18:39:47Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Stage-only npm tokens for safer automation
update_detail_title: GitHub / Copilot Stage-only npm tokens for safer automation
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Stage-only npm tokens for safer automation has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Stage-only npm tokens for safer automation.
release_summary: "You can now select Read and write (stage only) when creating an npm granular access token. This lets your\
  \ automated workflows stage package versions for review without giving the token permission to publish new versions directly\
  \ to the npm registry.\n\n\n Your workflow uses npm stage publish to submit a version. A package maintainer then reviews\
  \ and approves its release with two-factor authentication (2FA). npm rejects direct npm publish attempts with that token,\
  \ even if you’ve configured it to bypass 2FA for automation.\n\n\n Stage-only tokens retain other package write permissions\
  \ , including moving dist-tags and deprecating versions. Protect them with the same care as any other write token.\n\n\n\
  \ Prepare your automation for the token transition\n This release is opt-in and doesn’t change existing tokens or their\
  \ direct-publish capabilities.\n\n\n As previously announced, npm is targeting January 2027 to remove direct publishing\
  \ through bypass-2FA tokens. If you can’t move to trusted publishing yet, stage-only tokens offer a migration path for token-based\
  \ automation.\n\n\n To get started:\n\n\n\n Create a granular access token with Read and write (stage only) permissions\
  \ for the packages your workflow needs.\n Replace your workflow’s publishing token and use npm stage publish instead of\
  \ npm publish .\n Have a maintainer review and approve staged versions with 2FA.\n\n Staged publishing works with existing\
  \ npm packages. You’ll need publish access to the package, 2FA enabled on your npm account, npm CLI 11.15.0 or later, and\
  \ Node.js 22.14.0 or later.\n\n\n Learn more about staged publishing , and share questions or migration blockers in the\
  \ npm community discussion category .\n\n\n\n The post Stage-only npm tokens for safer automation appeared first on The\
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
- at: '2026-09-18T16:37:50Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-18T18:39:54Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-18-stage-only-npm-tokens-for-safer-automation
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-18T18:39:47Z'
  url: https://github.blog/changelog/2026-09-18-stage-only-npm-tokens-for-safer-automation
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-18T22:54:09Z'
  url: https://github.blog/changelog/2026-09-18-stage-only-npm-tokens-for-safer-automation
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now select Read and write (stage only) when creating an npm granular access token. This\
  \ lets your automated workflows stage package versions for review without giving the token permission to publish new versions\
  \ directly to the npm registry.\n\n\n Your workflow uses npm stage publish to submit a version. A package maintainer then\
  \ reviews and approves its release with two-factor authentication (2FA). npm rejects direct npm publish attempts with that\
  \ token, even if you’ve configured it to bypass 2FA for automation.\n\n\n Stage-only tokens retain other package write permissions\
  \ , including moving dist-tags and deprecating versions. Protect them with the same care as any other write token.\n\n\n\
  \ Prepare your automation for the token transition\n This release is opt-in and doesn’t change existing tokens or their\
  \ direct-publish capabilities.\n\n\n As previously announced, npm is targeting January 2027 to remove direct publishing\
  \ through bypass-2FA tokens. If you can’t move to trusted publishing yet, stage-only tokens offer a migration path for token-based\
  \ automation.\n\n\n To get started:\n\n\n\n Create a granular access token with Read and write (stage only) permissions\
  \ for the packages your workflow needs.\n Replace your workflow’s publishing token and use npm stage publish instead of\
  \ npm publish .\n Have a maintainer review and approve staged versions with 2FA.\n\n Staged publishing works with existing\
  \ npm packages. You’ll need publish access to the package, 2FA enabled on your npm account, npm CLI 11.15.0 or later, and\
  \ Node.js 22.14.0 or later.\n\n\n Learn more about staged publishing , and share questions or migration blockers in the\
  \ npm community discussion category .\n\n\n\n The post Stage-only npm tokens for safer automation appeared first on The\
  \ GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
