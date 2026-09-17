---
layout: aux-update
title: GitHub / Copilot Automate SSO authorization for classic PATs and SSH keys official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Automate SSO authorization for classic PATs
  and SSH keys.
permalink: /updates/github/github/automate-sso-authorization-for-classic-pats-and-ssh-keys/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-16-automate-sso-authorization-for-classic-pats-and-ssh-keys
update_download_url: ''
update_version: Automate SSO authorization for classic PATs and SSH keys
update_logo_text: GIT
update_published_at: '2026-09-16T20:20:16Z'
update_last_checked: '2026-09-16T23:31:27Z'
source_last_checked: '2026-09-17T19:17:40Z'
official_body_last_checked: '2026-09-17T19:17:40Z'
record_last_updated: '2026-09-16T23:31:27Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Automate SSO authorization for classic PATs and SSH keys
update_detail_title: GitHub / Copilot Automate SSO authorization for classic PATs and SSH keys
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Automate SSO authorization for classic PATs and SSH keys has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Automate SSO authorization for classic PATs and SSH keys.
release_summary: "Enterprise admins can now automate SSO authorization for existing classic personal access tokens (PATs)\
  \ and SSH keys for organizations in GitHub Enterprise Cloud, replacing manual per-organization authorization by your developers.\n\
  \n\n If your enterprise has multiple SSO-protected organizations, manually authorizing credentials one organization at a\
  \ time creates friction and overhead, leading to the use of long-lived tokens to avoid rotation.\n\n\n With this release,\
  \ enterprise admins can opt-in to a new enterprise setting to allow credential delegation through enterprise-installed GitHub\
  \ Apps with the enterprise_credentials:write permission. These GitHub Apps can then call the new API to bulk-authorize a\
  \ classic PAT or an SSH key for up to 50 organizations in a single request.\n\n\n The API:\n\n\n\n Identifies the credential\
  \ by its non-secret token ID or SSH key fingerprint, so no credential secrets are passed to the GitHub App.\n Confirms that\
  \ each target organization belongs to the enterprise, the credential owner belongs to each organization, and the enterprise\
  \ uses enterprise-level SSO. It does this before granting authorization.\n Safely skips organizations where an active authorization\
  \ already exists.\n\n If your enterprise manages SSO authorization for service accounts or automation credentials across\
  \ many organizations, you can have your GitHub App call this API whenever a token is rotated or a set of new organizations\
  \ are added. You can do this instead of authorizing each organization by hand. This is available now for GitHub Enterprise\
  \ Cloud accounts.\n\n\n Learn more about REST API endpoints for enterprise credential authorizations and installing a GitHub\
  \ App on your enterprise .\n\n\n\n The post Automate SSO authorization for classic PATs and SSH keys appeared first on The\
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
- at: '2026-09-16T20:20:16Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-16T23:31:36Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-16-automate-sso-authorization-for-classic-pats-and-ssh-keys
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-16T23:31:27Z'
  url: https://github.blog/changelog/2026-09-16-automate-sso-authorization-for-classic-pats-and-ssh-keys
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-17T01:52:34Z'
  url: https://github.blog/changelog/2026-09-16-automate-sso-authorization-for-classic-pats-and-ssh-keys
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-17T07:07:26Z'
  url: https://github.blog/changelog/2026-09-16-automate-sso-authorization-for-classic-pats-and-ssh-keys
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-17T13:58:22Z'
  url: https://github.blog/changelog/2026-09-16-automate-sso-authorization-for-classic-pats-and-ssh-keys
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-17T19:17:40Z'
  url: https://github.blog/changelog/2026-09-16-automate-sso-authorization-for-classic-pats-and-ssh-keys
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Enterprise admins can now automate SSO authorization for existing classic personal access tokens\
  \ (PATs) and SSH keys for organizations in GitHub Enterprise Cloud, replacing manual per-organization authorization by your\
  \ developers.\n\n\n If your enterprise has multiple SSO-protected organizations, manually authorizing credentials one organization\
  \ at a time creates friction and overhead, leading to the use of long-lived tokens to avoid rotation.\n\n\n With this release,\
  \ enterprise admins can opt-in to a new enterprise setting to allow credential delegation through enterprise-installed GitHub\
  \ Apps with the enterprise_credentials:write permission. These GitHub Apps can then call the new API to bulk-authorize a\
  \ classic PAT or an SSH key for up to 50 organizations in a single request.\n\n\n The API:\n\n\n\n Identifies the credential\
  \ by its non-secret token ID or SSH key fingerprint, so no credential secrets are passed to the GitHub App.\n Confirms that\
  \ each target organization belongs to the enterprise, the credential owner belongs to each organization, and the enterprise\
  \ uses enterprise-level SSO. It does this before granting authorization.\n Safely skips organizations where an active authorization\
  \ already exists.\n\n If your enterprise manages SSO authorization for service accounts or automation credentials across\
  \ many organizations, you can have your GitHub App call this API whenever a token is rotated or a set of new organizations\
  \ are added. You can do this instead of authorizing each organization by hand. This is available now for GitHub Enterprise\
  \ Cloud accounts.\n\n\n Learn more about REST API endpoints for enterprise credential authorizations and installing a GitHub\
  \ App on your enterprise .\n\n\n\n The post Automate SSO authorization for classic PATs and SSH keys appeared first on The\
  \ GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
