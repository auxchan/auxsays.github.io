---
layout: aux-update
title: GitHub / Copilot Push attribution for commits in limited public preview official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Push attribution for commits in limited public
  preview.
permalink: /updates/github/github/push-attribution-for-commits-in-limited-public-preview/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-12-push-attribution-public-preview
update_download_url: ''
update_version: Push attribution for commits in limited public preview
update_logo_text: GIT
update_published_at: '2026-10-12T16:30:11Z'
update_last_checked: '2026-10-12T17:58:56Z'
source_last_checked: '2026-10-13T02:59:17Z'
official_body_last_checked: '2026-10-13T02:59:17Z'
record_last_updated: '2026-10-12T17:58:56Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Push attribution for commits in limited public preview
update_detail_title: GitHub / Copilot Push attribution for commits in limited public preview
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Push attribution for commits in limited public preview has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Push attribution for commits in limited public preview.
release_summary: "GitHub now durably records the authenticated user who pushed each commit and surfaces that pusher identity\
  \ in the UI and API alongside the existing author and committer fields.\n\n\n Commit author and committer fields are just\
  \ strings that the pushing client supplies, so anyone with write access to a repository can set them to any name and email\
  \ they choose. That makes it possible for an attacker who compromises a low-privilege account to forge commits that appear\
  \ to come from a trusted maintainer, evading review policies and confusing audit trails. GitHub already authenticates pushes.\
  \ This release adds durable, per-commit pusher attribution alongside the author and committer metadata.\n\n\n With this\
  \ release:\n\n\n\n Every commit pushed to a repository now has a durable, authenticated pusher identity attached to it,\
  \ independent of whatever the author and committer metadata claims.\n A new repository rule condition, Committer must match\
  \ pusher , blocks pushes where the committer metadata doesn’t match any verified email address of the authenticated pusher.\
  \ This closes a path for commit identity spoofing.\n\n You can use the pusher identity to spot-check suspicious activity\
  \ or speed up security investigations instead of relying on unverified metadata. You can do this because the pusher identity\
  \ is now visible wherever commits are shown instead. To enforce stricter identity requirements on a repository, add the\
  \ new Committer must match pusher rule to a ruleset.\n\n\n Push attribution is available now as a limited public preview\
  \ for GitHub Enterprise customers. If you are interested in joining the preview, please contact your account team and request\
  \ access.\n\n\n Learn more about configuring push rulesets .\n\n\n\n The post Push attribution for commits in limited public\
  \ preview appeared first on The GitHub Blog ."
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
- at: '2026-10-12T16:30:11Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-12T17:59:07Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-12-push-attribution-public-preview
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-12T17:58:56Z'
  url: https://github.blog/changelog/2026-10-12-push-attribution-public-preview
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-13T02:59:17Z'
  url: https://github.blog/changelog/2026-10-12-push-attribution-public-preview
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub now durably records the authenticated user who pushed each commit and surfaces that pusher\
  \ identity in the UI and API alongside the existing author and committer fields.\n\n\n Commit author and committer fields\
  \ are just strings that the pushing client supplies, so anyone with write access to a repository can set them to any name\
  \ and email they choose. That makes it possible for an attacker who compromises a low-privilege account to forge commits\
  \ that appear to come from a trusted maintainer, evading review policies and confusing audit trails. GitHub already authenticates\
  \ pushes. This release adds durable, per-commit pusher attribution alongside the author and committer metadata.\n\n\n With\
  \ this release:\n\n\n\n Every commit pushed to a repository now has a durable, authenticated pusher identity attached to\
  \ it, independent of whatever the author and committer metadata claims.\n A new repository rule condition, Committer must\
  \ match pusher , blocks pushes where the committer metadata doesn’t match any verified email address of the authenticated\
  \ pusher. This closes a path for commit identity spoofing.\n\n You can use the pusher identity to spot-check suspicious\
  \ activity or speed up security investigations instead of relying on unverified metadata. You can do this because the pusher\
  \ identity is now visible wherever commits are shown instead. To enforce stricter identity requirements on a repository,\
  \ add the new Committer must match pusher rule to a ruleset.\n\n\n Push attribution is available now as a limited public\
  \ preview for GitHub Enterprise customers. If you are interested in joining the preview, please contact your account team\
  \ and request access.\n\n\n Learn more about configuring push rulesets .\n\n\n\n The post Push attribution for commits in\
  \ limited public preview appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
