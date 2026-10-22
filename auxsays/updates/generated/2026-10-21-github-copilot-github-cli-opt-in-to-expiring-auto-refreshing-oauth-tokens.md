---
layout: aux-update
title: 'GitHub / Copilot GitHub CLI: Opt in to expiring, auto-refreshing OAuth tokens official update breakdown'
description: 'Official GitHub / Copilot update record captured from GitHub for GitHub CLI: Opt in to expiring, auto-refreshing
  OAuth tokens.'
permalink: /updates/github/github/github-cli-opt-in-to-expiring-auto-refreshing-oauth-tokens/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-21-github-cli-opt-in-to-expiring-auto-refreshing-oauth-tokens
update_download_url: ''
update_version: 'GitHub CLI: Opt in to expiring, auto-refreshing OAuth tokens'
update_logo_text: GIT
update_published_at: '2026-10-21T16:43:23Z'
update_last_checked: '2026-10-21T19:42:19Z'
source_last_checked: '2026-10-22T00:27:37Z'
official_body_last_checked: '2026-10-22T00:27:37Z'
record_last_updated: '2026-10-21T19:42:19Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot GitHub CLI: Opt in to expiring, auto-refreshing OAuth tokens'
update_detail_title: 'GitHub / Copilot GitHub CLI: Opt in to expiring, auto-refreshing OAuth tokens'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot GitHub CLI: Opt in to expiring, auto-refreshing OAuth tokens has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot GitHub CLI: Opt in to expiring, auto-refreshing OAuth tokens.'
release_summary: "You can now use expiring, automatically refreshing OAuth credentials in GitHub CLI as part of a public preview.\
  \ When you opt in, gh stores an expiring access token alongside a rotating refresh token and automatically refreshes the\
  \ token whenever it is needed. You stay authenticated without reauthenticating, and a leaked access token becomes unusable\
  \ within hours instead of lasting indefinitely.\n\n\n Opting in at login\n Starting with v2.103.0, pass the new --expiring\
  \ flag when you log in with gh auth login --expiring . To opt in for every sign-in without passing the flag each time, run\
  \ gh config set expiring_credentials enabled . From then on, there is nothing new to run day to day: gh refreshes the credential\
  \ for you in the background. To check the state of an expiring credential, including when the current access token expires,\
  \ run gh auth status .\n\n\n Using expiring tokens with git\n If you authenticate to git over HTTPS and want to use expiring\
  \ tokens, we strongly recommend configuring gh as your git credential helper by running gh auth setup-git . This lets gh\
  \ serve and refresh the credential for git, so your expiring token is correctly handled.\n\n\n We also strongly recommend\
  \ upgrading to git 2.46 or newer, which lets gh mark expiring credentials so they are not cached past their lifetime. On\
  \ older git versions, gh still works but prints a one-time recommendation to upgrade.\n\n\n Good to know\n\n It’s opt-in\
  \ and backward compatible. If you don’t opt in through the flag or configuration setting, nothing changes. Existing sign-ins\
  \ and manually supplied tokens keep working exactly as before.\n You get whatever the server issues. --expiring requests\
  \ refreshable credentials. If a server does not support them, gh falls back cleanly to a normal nonexpiring token.\n It\
  \ will become the default over time. Expiring credentials are opt-in today. In a future release, we plan to make them the\
  \ default for new sign-ins.\n\n Things to watch out for\n Expiring access tokens are short-lived, so anything that captures\
  \ a token once and reuses it later can break. Scripts and extensions that run gh auth token and store the result, or copy\
  \ the token into another tool, will eventually be left holding an expired token.\n\n\n If you consume the token outside\
  \ of gh , read it fresh each time with gh auth token . This refreshes it when needed rather than caching the value. If a\
  \ workflow depends on a token that stays valid for a long time, hold off on opting in for that workflow. When gh is configured\
  \ as your git credential helper, it refreshes the credential for you, so git operations over HTTPS keep working.\n\n\n Who\
  \ can use it\n Expiring tokens are available on github.com and ghe.com today. GitHub Enterprise Server issues them starting\
  \ with GHES 3.23. On earlier versions, opting in falls back to today’s nonexpiring behavior.\n\n\n For more on authenticating\
  \ with GitHub CLI, including expiring tokens, see Authenticating with GitHub CLI .\n\n\n Install or upgrade to GitHub CLI\
  \ v2.103.0 today to get started.\n\n\n Have feedback or found an issue? Open an issue in the cli/cli repository .\n\n\n\n\
  \ The post GitHub CLI: Opt in to expiring, auto-refreshing OAuth tokens appeared first on The GitHub Blog ."
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
- at: '2026-10-21T16:43:23Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-21T19:42:28Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-21-github-cli-opt-in-to-expiring-auto-refreshing-oauth-tokens
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-21T19:42:19Z'
  url: https://github.blog/changelog/2026-10-21-github-cli-opt-in-to-expiring-auto-refreshing-oauth-tokens
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-22T00:27:37Z'
  url: https://github.blog/changelog/2026-10-21-github-cli-opt-in-to-expiring-auto-refreshing-oauth-tokens
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now use expiring, automatically refreshing OAuth credentials in GitHub CLI as part of\
  \ a public preview. When you opt in, gh stores an expiring access token alongside a rotating refresh token and automatically\
  \ refreshes the token whenever it is needed. You stay authenticated without reauthenticating, and a leaked access token\
  \ becomes unusable within hours instead of lasting indefinitely.\n\n\n Opting in at login\n Starting with v2.103.0, pass\
  \ the new --expiring flag when you log in with gh auth login --expiring . To opt in for every sign-in without passing the\
  \ flag each time, run gh config set expiring_credentials enabled . From then on, there is nothing new to run day to day:\
  \ gh refreshes the credential for you in the background. To check the state of an expiring credential, including when the\
  \ current access token expires, run gh auth status .\n\n\n Using expiring tokens with git\n If you authenticate to git over\
  \ HTTPS and want to use expiring tokens, we strongly recommend configuring gh as your git credential helper by running gh\
  \ auth setup-git . This lets gh serve and refresh the credential for git, so your expiring token is correctly handled.\n\
  \n\n We also strongly recommend upgrading to git 2.46 or newer, which lets gh mark expiring credentials so they are not\
  \ cached past their lifetime. On older git versions, gh still works but prints a one-time recommendation to upgrade.\n\n\
  \n Good to know\n\n It’s opt-in and backward compatible. If you don’t opt in through the flag or configuration setting,\
  \ nothing changes. Existing sign-ins and manually supplied tokens keep working exactly as before.\n You get whatever the\
  \ server issues. --expiring requests refreshable credentials. If a server does not support them, gh falls back cleanly to\
  \ a normal nonexpiring token.\n It will become the default over time. Expiring credentials are opt-in today. In a future\
  \ release, we plan to make them the default for new sign-ins.\n\n Things to watch out for\n Expiring access tokens are short-lived,\
  \ so anything that captures a token once and reuses it later can break. Scripts and extensions that run gh auth token and\
  \ store the result, or copy the token into another tool, will eventually be left holding an expired token.\n\n\n If you\
  \ consume the token outside of gh , read it fresh each time with gh auth token . This refreshes it when needed rather than\
  \ caching the value. If a workflow depends on a token that stays valid for a long time, hold off on opting in for that workflow.\
  \ When gh is configured as your git credential helper, it refreshes the credential for you, so git operations over HTTPS\
  \ keep working.\n\n\n Who can use it\n Expiring tokens are available on github.com and ghe.com today. GitHub Enterprise\
  \ Server issues them starting with GHES 3.23. On earlier versions, opting in falls back to today’s nonexpiring behavior.\n\
  \n\n For more on authenticating with GitHub CLI, including expiring tokens, see Authenticating with GitHub CLI .\n\n\n Install\
  \ or upgrade to GitHub CLI v2.103.0 today to get started.\n\n\n Have feedback or found an issue? Open an issue in the cli/cli\
  \ repository .\n\n\n\n The post GitHub CLI: Opt in to expiring, auto-refreshing OAuth tokens appeared first on The GitHub\
  \ Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
