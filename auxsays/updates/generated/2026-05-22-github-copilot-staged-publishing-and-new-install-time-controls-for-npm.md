---
layout: aux-update
title: GitHub / Copilot Staged publishing and new install-time controls for npm official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/staged-publishing-and-new-install-time-controls-for-npm/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-22-staged-publishing-and-new-install-time-controls-for-npm
update_download_url: ''
update_version: Staged publishing and new install-time controls for npm
update_logo_text: GIT
update_published_at: '2026-05-22T18:27:12Z'
update_last_checked: '2026-05-22T20:14:04Z'
source_last_checked: '2026-05-24T19:43:20Z'
official_body_last_checked: '2026-05-24T19:43:20Z'
record_last_updated: '2026-05-22T20:14:04Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Staged publishing and new install-time controls for npm
update_detail_title: GitHub / Copilot Staged publishing and new install-time controls for npm
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Staged publishing and new install-time controls for npm has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Staged publishing and new install-time controls for npm.
release_summary: "Today we’re shipping two updates focused on supply-chain security for npm:\n\n\n\n Staged publishing is\
  \ generally available.\n New --allow-* install source flags ( --allow-file , --allow-remote , --allow-directory ) complement\
  \ the existing --allow-git flag.\n\n Both are available in npm CLI 11.15.0 or newer.\n\n\n\n Staged publishing is generally\
  \ available\n Staged publishing is now generally available on npm. Instead of a direct publish that immediately makes a\
  \ package version available to consumers, the prebuilt tarball is uploaded to a stage queue where a maintainer must explicitly\
  \ approve it before it becomes installable. The queue is visible both on npmjs.com and in the npm CLI.\n\n\n Staged publishing\
  \ reinforces proof of presence on every publish, including those that originate from non-interactive CI/CD workflows and\
  \ those using trusted publishing with OIDC. A human maintainer with a 2FA challenge is required to approve a staged package\
  \ before it is released to the registry.\n\n\n Staged publishing is live today, and so are the docs.\n\n\n\n Overview and\
  \ getting started\n CLI reference and permissions\n Trusted publishers (updated)\n\n Requirements\n\n npm CLI 11.15.0 or\
  \ newer is required to use npm stage .\n Update CI/CD workflows to use npm stage publish instead of npm publish where you\
  \ want staged behavior.\n\n Recommended setup\n We recommend pairing staged publishing with trusted publishing (OIDC) .\
  \ A trusted publishing configuration can be limited to stage-only , which means npm publish from that workflow will be rejected\
  \ and only npm stage publish is accepted. Your CI workflows continue to run non-interactively, and a maintainer later approves\
  \ the staged version from the website or the CLI.\n\n\n You can also run npm stage publish locally, but the highest-value\
  \ setup is CI publishing to the stage queue and a maintainer approving from a trusted device.\n\n\n If you already manage\
  \ trusted publishing configurations in bulk, released Feb 2026 , you can use it to migrate your packages to staged publishing.\
  \ Remember to update your CI workflows to the new CLI version and to use npm stage publish .\n\n\n New install source flags\n\
  \ In npm 11.10.0 we introduced --allow-git to give you control over whether npm install can resolve dependencies from Git\
  \ sources. Starting in npm 11.15.0 , we are adding three more flags so you can apply the same explicit-allowlist approach\
  \ to every nonregistry install source:\n\n\n\n --allow-file : Controls installs from local file paths and local tarballs.\n\
  \ --allow-remote : Controls installs from remote URLs, including https tarballs.\n --allow-directory : Controls installs\
  \ from local directories.\n --allow-git (existing): Controls installs from any Git source, including github: , gitlab: ,\
  \ git+ URLs, and bare owner/repo shorthands.\n\n Each flag accepts all (the current default) or none , and can also be set\
  \ in .npmrc or package.json config.\n\n\n Learn more by checking out our docs:\n\n\n\n npm install reference (the --allow-file\
  \ , --allow-remote , --allow-git variants are on the same page)\n Config reference\n\n As a reminder from the Feb 2026 announcement,\
  \ --allow-git will change its default from all to none in the next major version of the CLI ( v12 ). The new --allow-file\
  \ , --allow-remote , and --allow-directory flags are additions in 11.15.0—you can opt into stricter behavior today by setting\
  \ them to none .\n\n\n\n Join the discussion\n We’d like to hear how you’re rolling this out. Share feedback and questions\
  \ in the GitHub Community discussion .\n\n\n\n The post Staged publishing and new install-time controls for npm appeared\
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
- at: '2026-05-22T18:27:12Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-22T20:14:05Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-22-staged-publishing-and-new-install-time-controls-for-npm
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-23T19:40:54Z'
  url: https://github.blog/changelog/2026-05-22-staged-publishing-and-new-install-time-controls-for-npm
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-24T04:42:21Z'
  url: https://github.blog/changelog/2026-05-22-staged-publishing-and-new-install-time-controls-for-npm
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-24T08:46:02Z'
  url: https://github.blog/changelog/2026-05-22-staged-publishing-and-new-install-time-controls-for-npm
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-24T14:04:20Z'
  url: https://github.blog/changelog/2026-05-22-staged-publishing-and-new-install-time-controls-for-npm
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-24T19:43:20Z'
  url: https://github.blog/changelog/2026-05-22-staged-publishing-and-new-install-time-controls-for-npm
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Today we’re shipping two updates focused on supply-chain security for npm:\n\n\n\n Staged publishing\
  \ is generally available.\n New --allow-* install source flags ( --allow-file , --allow-remote , --allow-directory ) complement\
  \ the existing --allow-git flag.\n\n Both are available in npm CLI 11.15.0 or newer.\n\n\n\n Staged publishing is generally\
  \ available\n Staged publishing is now generally available on npm. Instead of a direct publish that immediately makes a\
  \ package version available to consumers, the prebuilt tarball is uploaded to a stage queue where a maintainer must explicitly\
  \ approve it before it becomes installable. The queue is visible both on npmjs.com and in the npm CLI.\n\n\n Staged publishing\
  \ reinforces proof of presence on every publish, including those that originate from non-interactive CI/CD workflows and\
  \ those using trusted publishing with OIDC. A human maintainer with a 2FA challenge is required to approve a staged package\
  \ before it is released to the registry.\n\n\n Staged publishing is live today, and so are the docs.\n\n\n\n Overview and\
  \ getting started\n CLI reference and permissions\n Trusted publishers (updated)\n\n Requirements\n\n npm CLI 11.15.0 or\
  \ newer is required to use npm stage .\n Update CI/CD workflows to use npm stage publish instead of npm publish where you\
  \ want staged behavior.\n\n Recommended setup\n We recommend pairing staged publishing with trusted publishing (OIDC) .\
  \ A trusted publishing configuration can be limited to stage-only , which means npm publish from that workflow will be rejected\
  \ and only npm stage publish is accepted. Your CI workflows continue to run non-interactively, and a maintainer later approves\
  \ the staged version from the website or the CLI.\n\n\n You can also run npm stage publish locally, but the highest-value\
  \ setup is CI publishing to the stage queue and a maintainer approving from a trusted device.\n\n\n If you already manage\
  \ trusted publishing configurations in bulk, released Feb 2026 , you can use it to migrate your packages to staged publishing.\
  \ Remember to update your CI workflows to the new CLI version and to use npm stage publish .\n\n\n New install source flags\n\
  \ In npm 11.10.0 we introduced --allow-git to give you control over whether npm install can resolve dependencies from Git\
  \ sources. Starting in npm 11.15.0 , we are adding three more flags so you can apply the same explicit-allowlist approach\
  \ to every nonregistry install source:\n\n\n\n --allow-file : Controls installs from local file paths and local tarballs.\n\
  \ --allow-remote : Controls installs from remote URLs, including https tarballs.\n --allow-directory : Controls installs\
  \ from local directories.\n --allow-git (existing): Controls installs from any Git source, including github: , gitlab: ,\
  \ git+ URLs, and bare owner/repo shorthands.\n\n Each flag accepts all (the current default) or none , and can also be set\
  \ in .npmrc or package.json config.\n\n\n Learn more by checking out our docs:\n\n\n\n npm install reference (the --allow-file\
  \ , --allow-remote , --allow-git variants are on the same page)\n Config reference\n\n As a reminder from the Feb 2026 announcement,\
  \ --allow-git will change its default from all to none in the next major version of the CLI ( v12 ). The new --allow-file\
  \ , --allow-remote , and --allow-directory flags are additions in 11.15.0—you can opt into stricter behavior today by setting\
  \ them to none .\n\n\n\n Join the discussion\n We’d like to hear how you’re rolling this out. Share feedback and questions\
  \ in the GitHub Community discussion .\n\n\n\n The post Staged publishing and new install-time controls for npm appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
