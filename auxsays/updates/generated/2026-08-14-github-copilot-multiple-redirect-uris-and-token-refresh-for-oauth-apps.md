---
layout: aux-update
title: GitHub / Copilot Multiple redirect URIs and token refresh for OAuth apps official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/multiple-redirect-uris-and-token-refresh-for-oauth-apps/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-14-multiple-redirect-uris-and-token-refresh-for-oauth-apps
update_download_url: ''
update_version: Multiple redirect URIs and token refresh for OAuth apps
update_logo_text: GIT
update_published_at: '2026-08-14T22:43:44Z'
update_last_checked: '2026-08-15T02:58:20Z'
source_last_checked: '2026-08-16T14:10:22Z'
official_body_last_checked: '2026-08-16T14:10:22Z'
record_last_updated: '2026-08-15T02:58:20Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Multiple redirect URIs and token refresh for OAuth apps
update_detail_title: GitHub / Copilot Multiple redirect URIs and token refresh for OAuth apps
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Multiple redirect URIs and token refresh for OAuth apps has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Multiple redirect URIs and token refresh for OAuth apps.
release_summary: "We’ve released multiple updates to the OAuth app and GitHub App platforms to support more secure app development:\n\
  \n\n\n OAuth apps can opt in to expiring access tokens and refresh tokens.\n OAuth apps can have multiple redirect URIs.\n\
  \ Both GitHub Apps and OAuth apps can enable wildcard matching for redirect URIs if needed.\n\n Rotating tokens for OAuth\
  \ apps\n OAuth apps can now request a short-lived token during the user authentication flow. If an app opts in, they get\
  \ an access token that lives for eight hours and a refresh token that’s valid for six months. When the access token expires,\
  \ the app uses the refresh token to get a new token pair.\n\n\n Developers can add refresh token support to their app in\
  \ two ways:\n\n\n\n Include the offline_access scope in their authentication request, which triggers the short-lived token\
  \ pattern. This is how developers should test and roll out this change in their app.\n Set their app registration to always\
  \ use short-lived tokens. This can be used to force old clients to update and ensure that all clients are getting short-lived\
  \ tokens.\n\n Short-lived tokens are enabled by default for all new applications. If your authentication SDK doesn’t support\
  \ the refresh token flow, you can disable this while updating the SDK.\n\n\n\n\n\n For more details on how to use expiring\
  \ tokens with an OAuth app, see the “Authorizing OAuth apps” documentation.\n\n\n Multiple redirect URI support for OAuth\
  \ apps\n OAuth apps can now register up to 10 redirect URIs (called “callback URIs” on GitHub), making it easier to support\
  \ multiple environments, domains, or deployment configurations without creating separate apps.\n\n\n Developers will find\
  \ a new Add redirect URI button in their application settings, which can be used to add additional URLs to match against.\n\
  \n\n\n\n\n Wildcard matching for redirect URIs\n OAuth apps and GitHub Apps can now enable wildcard matching for each redirect\
  \ URI configured. This can allow redirects to multiple related sites (e.g., tenanted subdomains of your app) without registering\
  \ a redirect URI per tenant.\n\n\n When enabled, wildcard matching allows an authorization code (and user) to be sent from\
  \ GitHub to any URL that matches a subdomain or additional path off of the redirect URI.\n\n\n Wildcard matching can be\
  \ abused if the site being redirected to does not have strong control over its routes (e.g., if it hosts user content).\
  \ Review your app architecture before enabling this.\n\n\n\n Apps with only one redirect URI have wildcard matching enabled.\
  \ This is a legacy behavior of GitHub that is now visible and controllable. Please review your apps and disable wildcard\
  \ matching if you do not need it. This applies to all OAuth apps and any GitHub App that had a single redirect URI registered.\n\
  \n\n\n\n\n\n These improvements will all be included in GitHub Enterprise Server 3.23.\n\n\n For more information about\
  \ creating and managing your app’s redirects safely, see user authorization callback URLs for GitHub Apps and creating an\
  \ OAuth app .\n\n\n Join the discussion in the GitHub Community .\n\n\n\n The post Multiple redirect URIs and token refresh\
  \ for OAuth apps appeared first on The GitHub Blog ."
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
- at: '2026-08-14T22:43:44Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-15T02:58:26Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-14-multiple-redirect-uris-and-token-refresh-for-oauth-apps
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-15T14:09:30Z'
  url: https://github.blog/changelog/2026-08-14-multiple-redirect-uris-and-token-refresh-for-oauth-apps
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-15T19:59:07Z'
  url: https://github.blog/changelog/2026-08-14-multiple-redirect-uris-and-token-refresh-for-oauth-apps
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-16T03:09:05Z'
  url: https://github.blog/changelog/2026-08-14-multiple-redirect-uris-and-token-refresh-for-oauth-apps
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-16T08:10:01Z'
  url: https://github.blog/changelog/2026-08-14-multiple-redirect-uris-and-token-refresh-for-oauth-apps
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-16T14:10:22Z'
  url: https://github.blog/changelog/2026-08-14-multiple-redirect-uris-and-token-refresh-for-oauth-apps
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "We’ve released multiple updates to the OAuth app and GitHub App platforms to support more secure\
  \ app development:\n\n\n\n OAuth apps can opt in to expiring access tokens and refresh tokens.\n OAuth apps can have multiple\
  \ redirect URIs.\n Both GitHub Apps and OAuth apps can enable wildcard matching for redirect URIs if needed.\n\n Rotating\
  \ tokens for OAuth apps\n OAuth apps can now request a short-lived token during the user authentication flow. If an app\
  \ opts in, they get an access token that lives for eight hours and a refresh token that’s valid for six months. When the\
  \ access token expires, the app uses the refresh token to get a new token pair.\n\n\n Developers can add refresh token support\
  \ to their app in two ways:\n\n\n\n Include the offline_access scope in their authentication request, which triggers the\
  \ short-lived token pattern. This is how developers should test and roll out this change in their app.\n Set their app registration\
  \ to always use short-lived tokens. This can be used to force old clients to update and ensure that all clients are getting\
  \ short-lived tokens.\n\n Short-lived tokens are enabled by default for all new applications. If your authentication SDK\
  \ doesn’t support the refresh token flow, you can disable this while updating the SDK.\n\n\n\n\n\n For more details on how\
  \ to use expiring tokens with an OAuth app, see the “Authorizing OAuth apps” documentation.\n\n\n Multiple redirect URI\
  \ support for OAuth apps\n OAuth apps can now register up to 10 redirect URIs (called “callback URIs” on GitHub), making\
  \ it easier to support multiple environments, domains, or deployment configurations without creating separate apps.\n\n\n\
  \ Developers will find a new Add redirect URI button in their application settings, which can be used to add additional\
  \ URLs to match against.\n\n\n\n\n\n Wildcard matching for redirect URIs\n OAuth apps and GitHub Apps can now enable wildcard\
  \ matching for each redirect URI configured. This can allow redirects to multiple related sites (e.g., tenanted subdomains\
  \ of your app) without registering a redirect URI per tenant.\n\n\n When enabled, wildcard matching allows an authorization\
  \ code (and user) to be sent from GitHub to any URL that matches a subdomain or additional path off of the redirect URI.\n\
  \n\n Wildcard matching can be abused if the site being redirected to does not have strong control over its routes (e.g.,\
  \ if it hosts user content). Review your app architecture before enabling this.\n\n\n\n Apps with only one redirect URI\
  \ have wildcard matching enabled. This is a legacy behavior of GitHub that is now visible and controllable. Please review\
  \ your apps and disable wildcard matching if you do not need it. This applies to all OAuth apps and any GitHub App that\
  \ had a single redirect URI registered.\n\n\n\n\n\n\n These improvements will all be included in GitHub Enterprise Server\
  \ 3.23.\n\n\n For more information about creating and managing your app’s redirects safely, see user authorization callback\
  \ URLs for GitHub Apps and creating an OAuth app .\n\n\n Join the discussion in the GitHub Community .\n\n\n\n The post\
  \ Multiple redirect URIs and token refresh for OAuth apps appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
