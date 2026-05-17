---
layout: aux-update
title: 'GitHub / Copilot GitHub App installation tokens: Per-request override header official update breakdown'
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/github-app-installation-tokens-per-request-override-header/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-15-github-app-installation-tokens-per-request-override-header
update_download_url: ''
update_version: 'GitHub App installation tokens: Per-request override header'
update_logo_text: GIT
update_published_at: '2026-05-16T00:07:40Z'
update_last_checked: '2026-05-16T04:05:55Z'
source_last_checked: '2026-05-17T08:34:31Z'
official_body_last_checked: '2026-05-17T08:34:31Z'
record_last_updated: '2026-05-16T04:05:55Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot GitHub App installation tokens: Per-request override header'
update_detail_title: 'GitHub / Copilot GitHub App installation tokens: Per-request override header'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot GitHub App installation tokens: Per-request override header has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot GitHub App installation tokens: Per-request override header.'
release_summary: "As announced in April 2026 , GitHub is rolling out a new token format for GitHub App installation tokens.\
  \ To help you validate your apps and workflows before the rollout reaches you, we’re providing a temporary request header\
  \ that lets you force either token format on demand.\n\n\n What is the header?\n Setting X-GitHub-Stateless-S2S-Token on\
  \ a POST /app/installations/:installation_id/access_tokens request overrides the server-side rollout decision for that single\
  \ request.\n\n\n\n\n\n Header value\n Effect\n\n\n\n\n enabled\n Returns a stateless (JWT-format) token, regardless of where\
  \ you are in the rollout.\n\n\n disabled\n Returns a stateful (classic opaque) token, even if your integration is already\
  \ included in the rollout.\n\n\n (absent)\n Normal rollout behavior (i.e., no override).\n\n\n\n Any other value ( true\
  \ , false , 1 , 0 , etc.) is silently ignored and given the standard rollout behavior.\n\n\n The header is supported on\
  \ the POST /app/installations/:installation_id/access_tokens REST API.\n\n\n How to use it\n Before the rollout reaches\
  \ your app, test proactively\n Use enabled to request a stateless token on demand and validate that your application handles\
  \ it correctly.\n\n\n When creating an installation access token, send the X-GitHub-Stateless-S2S-Token: enabled request\
  \ header to force the new token format in the response. For full endpoint details and request examples, see the REST API\
  \ documentation for creating an installation access token for an app .\n\n\n A stateless token is a ghs_ -prefixed JWT .\
  \ It is longer (~520 characters) and contains two dots . In contrast, a stateful token is a short opaque string with no\
  \ dots .\n\n\n Things to check in your app:\n\n\n\n No hardcoded token length assumptions\n Any regex used to validate an\
  \ installation token is updated to handle additional underscores and the presencce of a JWT. Our recommended regex to match\
  \ both new and current format tokens is ghs_[A-Za-z0-9\\._]{36,} .\n Database columns for token storage and header settings\
  \ accept at least 520 characters\n Any token introspection or validation code treats ghs_ tokens as opaque strings\n\n During\
  \ the rollout, temporarily opt out if you need more time\n If the rollout reaches your app before you’re ready, you can\
  \ set the header with disabled to continue receiving stateful tokens while you update your application.\n\n\n Verifying\
  \ the token type\n You can verify the token type by checking the number of dots after the ghs_ prefix: a stateless JWT-format\
  \ token has two dots, while a stateful opaque token has no dots.\n\n\n Scope\n\n The header is temporary. At a future deprecation\
  \ point, to be announced separately in the coming weeks, it will no longer be respected. At that point, all eligible apps\
  \ will unconditionally receive stateless tokens. Remove the header from your production code once you have validated both\
  \ token formats.\n Existing app installation tokens continue to work until they expire.\n This change applies to GitHub\
  \ Enterprise Cloud and Data Residency environments. GitHub Enterprise Server isn’t impacted by this change.\n Upcoming rollouts\
  \ will apply the new token format only to GitHub App installation server-to-server tokens, including Actions GITHUB_TOKEN.\n\
  \ We’ll share more details in the coming weeks on planned format changes for user-to-server tokens used in Copilot code\
  \ review flows.\n\n How to prepare\n\n Test with enabled : Call the endpoint with the opt-in header and verify your app\
  \ accepts the new token format end-to-end.\n Test with disabled : Confirm your app also works with the classic opaque format,\
  \ so it degrades gracefully if stateless tokens are ever temporarily unavailable.\n Remove the header: Once both paths are\
  \ validated, remove the header. GitHub’s rollout will then automatically manage the token format.\n\n Reach out to GitHub\
  \ Support if you see this change affecting your app workflows and need to temporarily opt-out of the change. Join the discussion\
  \ within GitHub Community .\n\n\n\n The post GitHub App installation tokens: Per-request override header appeared first\
  \ on The GitHub Blog ."
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
- at: '2026-05-16T00:07:40Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-16T04:05:56Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-15-github-app-installation-tokens-per-request-override-header
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-16T08:21:01Z'
  url: https://github.blog/changelog/2026-05-15-github-app-installation-tokens-per-request-override-header
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-16T14:02:20Z'
  url: https://github.blog/changelog/2026-05-15-github-app-installation-tokens-per-request-override-header
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-16T19:36:26Z'
  url: https://github.blog/changelog/2026-05-15-github-app-installation-tokens-per-request-override-header
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-17T04:35:14Z'
  url: https://github.blog/changelog/2026-05-15-github-app-installation-tokens-per-request-override-header
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-17T08:34:31Z'
  url: https://github.blog/changelog/2026-05-15-github-app-installation-tokens-per-request-override-header
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "As announced in April 2026 , GitHub is rolling out a new token format for GitHub App installation\
  \ tokens. To help you validate your apps and workflows before the rollout reaches you, we’re providing a temporary request\
  \ header that lets you force either token format on demand.\n\n\n What is the header?\n Setting X-GitHub-Stateless-S2S-Token\
  \ on a POST /app/installations/:installation_id/access_tokens request overrides the server-side rollout decision for that\
  \ single request.\n\n\n\n\n\n Header value\n Effect\n\n\n\n\n enabled\n Returns a stateless (JWT-format) token, regardless\
  \ of where you are in the rollout.\n\n\n disabled\n Returns a stateful (classic opaque) token, even if your integration\
  \ is already included in the rollout.\n\n\n (absent)\n Normal rollout behavior (i.e., no override).\n\n\n\n Any other value\
  \ ( true , false , 1 , 0 , etc.) is silently ignored and given the standard rollout behavior.\n\n\n The header is supported\
  \ on the POST /app/installations/:installation_id/access_tokens REST API.\n\n\n How to use it\n Before the rollout reaches\
  \ your app, test proactively\n Use enabled to request a stateless token on demand and validate that your application handles\
  \ it correctly.\n\n\n When creating an installation access token, send the X-GitHub-Stateless-S2S-Token: enabled request\
  \ header to force the new token format in the response. For full endpoint details and request examples, see the REST API\
  \ documentation for creating an installation access token for an app .\n\n\n A stateless token is a ghs_ -prefixed JWT .\
  \ It is longer (~520 characters) and contains two dots . In contrast, a stateful token is a short opaque string with no\
  \ dots .\n\n\n Things to check in your app:\n\n\n\n No hardcoded token length assumptions\n Any regex used to validate an\
  \ installation token is updated to handle additional underscores and the presencce of a JWT. Our recommended regex to match\
  \ both new and current format tokens is ghs_[A-Za-z0-9\\._]{36,} .\n Database columns for token storage and header settings\
  \ accept at least 520 characters\n Any token introspection or validation code treats ghs_ tokens as opaque strings\n\n During\
  \ the rollout, temporarily opt out if you need more time\n If the rollout reaches your app before you’re ready, you can\
  \ set the header with disabled to continue receiving stateful tokens while you update your application.\n\n\n Verifying\
  \ the token type\n You can verify the token type by checking the number of dots after the ghs_ prefix: a stateless JWT-format\
  \ token has two dots, while a stateful opaque token has no dots.\n\n\n Scope\n\n The header is temporary. At a future deprecation\
  \ point, to be announced separately in the coming weeks, it will no longer be respected. At that point, all eligible apps\
  \ will unconditionally receive stateless tokens. Remove the header from your production code once you have validated both\
  \ token formats.\n Existing app installation tokens continue to work until they expire.\n This change applies to GitHub\
  \ Enterprise Cloud and Data Residency environments. GitHub Enterprise Server isn’t impacted by this change.\n Upcoming rollouts\
  \ will apply the new token format only to GitHub App installation server-to-server tokens, including Actions GITHUB_TOKEN.\n\
  \ We’ll share more details in the coming weeks on planned format changes for user-to-server tokens used in Copilot code\
  \ review flows.\n\n How to prepare\n\n Test with enabled : Call the endpoint with the opt-in header and verify your app\
  \ accepts the new token format end-to-end.\n Test with disabled : Confirm your app also works with the classic opaque format,\
  \ so it degrades gracefully if stateless tokens are ever temporarily unavailable.\n Remove the header: Once both paths are\
  \ validated, remove the header. GitHub’s rollout will then automatically manage the token format.\n\n Reach out to GitHub\
  \ Support if you see this change affecting your app workflows and need to temporarily opt-out of the change. Join the discussion\
  \ within GitHub Community .\n\n\n\n The post GitHub App installation tokens: Per-request override header appeared first\
  \ on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
