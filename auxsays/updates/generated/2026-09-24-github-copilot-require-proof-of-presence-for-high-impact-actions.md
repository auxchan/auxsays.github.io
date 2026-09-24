---
layout: aux-update
title: GitHub / Copilot Require proof of presence for high-impact actions official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Require proof of presence for high-impact actions.
permalink: /updates/github/github/require-proof-of-presence-for-high-impact-actions/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-24-require-proof-of-presence-for-high-impact-actions
update_download_url: ''
update_version: Require proof of presence for high-impact actions
update_logo_text: GIT
update_published_at: '2026-09-24T20:28:33Z'
update_last_checked: '2026-09-24T23:36:23Z'
source_last_checked: '2026-09-24T23:36:23Z'
official_body_last_checked: '2026-09-24T23:36:23Z'
record_last_updated: '2026-09-24T23:36:23Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Require proof of presence for high-impact actions
update_detail_title: GitHub / Copilot Require proof of presence for high-impact actions
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Require proof of presence for high-impact actions has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Require proof of presence for high-impact actions.
release_summary: "You can now require an interactive re-authentication or a multi-factor challenge before members take high-impact\
  \ actions on GitHub Enterprise Cloud accounts. Proof of presence is an expansion of GitHub’s sudo mode for enterprises,\
  \ enforcing a higher security bar when it’s needed. This public preview is only scoped to managed user (EMU) enterprises\
  \ on github.com and GHEC-DR that use Microsoft Entra ID as their SSO identity provider (IdP), via SAML or OIDC.\n\n\n Stolen\
  \ session cookies and long-lived authentication tokens have shown up in several recent supply chain attacks. Proof of presence\
  \ confirms that a real, authorized person is acting at the moment the high-impact action happens, not just that a valid\
  \ session or token was used. We validate this by sending the user back to their IdP to check, allowing you to set custom\
  \ IdP policies to govern the actions taken on GitHub. This improves security posture by blocking the use of compromised\
  \ or hijacked credentials or agents going an extra step without your knowledge. It also helps regulated customers meet compliance\
  \ requirements for fresh authentication before sensitive operations from frameworks like FDA Part 11.\n\n\n With proof of\
  \ presence enabled:\n\n\n\n When an enterprise member attempts a high-impact action (e.g., creating a token, editing webhooks,\
  \ changing organization security settings, viewing recovery codes) GitHub redirects them to their IdP to satisfy a specific\
  \ authentication policy. This might mean performing multi-factor authentication, checking for device compliance, or just\
  \ signing in again to prove freshness.\n GitHub only allows the action to proceed if the user comes back from the IdP with\
  \ proof they satisfied the required policy.\n\n Proof of presence uses the same session model as sudo mode. After a successful\
  \ challenge, the user can continue performing high-impact actions in that browser session for two hours without performing\
  \ another proof of presence check.\n\n\n If your enterprise uses Entra ID for SSO, you can configure proof of presence to\
  \ add this extra layer of verification through one of these requirements:\n\n\n\n Re-authentication : The member authenticates\
  \ again with your IdP. Depending on your IdP policy, a password may satisfy this.\n MFA : The member authenticates again\
  \ and satisfies an additional multi-factor challenge (e.g., authenticator app, biometric) as configured in your IdP.\n\n\
  \ Support for proof of presence before pull request merges is coming soon.\n\n\n Learn more about how to configure proof\
  \ of presence and sudo mode , or join the conversation in GitHub Community .\n\n\n\n The post Require proof of presence\
  \ for high-impact actions appeared first on The GitHub Blog ."
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
- at: '2026-09-24T20:28:33Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-24T23:36:33Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-24-require-proof-of-presence-for-high-impact-actions
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-24T23:36:23Z'
  url: https://github.blog/changelog/2026-09-24-require-proof-of-presence-for-high-impact-actions
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now require an interactive re-authentication or a multi-factor challenge before members\
  \ take high-impact actions on GitHub Enterprise Cloud accounts. Proof of presence is an expansion of GitHub’s sudo mode\
  \ for enterprises, enforcing a higher security bar when it’s needed. This public preview is only scoped to managed user\
  \ (EMU) enterprises on github.com and GHEC-DR that use Microsoft Entra ID as their SSO identity provider (IdP), via SAML\
  \ or OIDC.\n\n\n Stolen session cookies and long-lived authentication tokens have shown up in several recent supply chain\
  \ attacks. Proof of presence confirms that a real, authorized person is acting at the moment the high-impact action happens,\
  \ not just that a valid session or token was used. We validate this by sending the user back to their IdP to check, allowing\
  \ you to set custom IdP policies to govern the actions taken on GitHub. This improves security posture by blocking the use\
  \ of compromised or hijacked credentials or agents going an extra step without your knowledge. It also helps regulated customers\
  \ meet compliance requirements for fresh authentication before sensitive operations from frameworks like FDA Part 11.\n\n\
  \n With proof of presence enabled:\n\n\n\n When an enterprise member attempts a high-impact action (e.g., creating a token,\
  \ editing webhooks, changing organization security settings, viewing recovery codes) GitHub redirects them to their IdP\
  \ to satisfy a specific authentication policy. This might mean performing multi-factor authentication, checking for device\
  \ compliance, or just signing in again to prove freshness.\n GitHub only allows the action to proceed if the user comes\
  \ back from the IdP with proof they satisfied the required policy.\n\n Proof of presence uses the same session model as\
  \ sudo mode. After a successful challenge, the user can continue performing high-impact actions in that browser session\
  \ for two hours without performing another proof of presence check.\n\n\n If your enterprise uses Entra ID for SSO, you\
  \ can configure proof of presence to add this extra layer of verification through one of these requirements:\n\n\n\n Re-authentication\
  \ : The member authenticates again with your IdP. Depending on your IdP policy, a password may satisfy this.\n MFA : The\
  \ member authenticates again and satisfies an additional multi-factor challenge (e.g., authenticator app, biometric) as\
  \ configured in your IdP.\n\n Support for proof of presence before pull request merges is coming soon.\n\n\n Learn more\
  \ about how to configure proof of presence and sudo mode , or join the conversation in GitHub Community .\n\n\n\n The post\
  \ Require proof of presence for high-impact actions appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
