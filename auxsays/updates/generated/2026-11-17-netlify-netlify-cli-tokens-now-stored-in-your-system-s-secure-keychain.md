---
layout: aux-update
title: Netlify Netlify CLI tokens now stored in your system’s secure keychain official update breakdown
description: Official Netlify update record captured from Netlify for Netlify CLI tokens now stored in your system’s secure
  keychain.
permalink: /updates/netlify/netlify/netlify-cli-tokens-now-stored-in-your-system-s-secure-keychain/
update_entry: true
company_id: netlify
product_id: netlify
update_brand_id: netlify
update_product: Netlify
update_category: Dev / Web
update_type: official-source
update_source_name: Netlify
update_source_url: https://www.netlify.com/changelog/2026-11-17-netlify-cli-keychain-storage/
update_download_url: ''
update_version: Netlify CLI tokens now stored in your system’s secure keychain
update_logo_text: NET
update_published_at: '2026-11-17T00:00:00Z'
update_last_checked: '2026-11-27T00:11:34Z'
source_last_checked: '2026-11-27T00:11:34Z'
official_body_last_checked: '2026-11-27T00:11:34Z'
record_last_updated: '2026-11-27T00:11:34Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: Netlify Netlify CLI tokens now stored in your system’s secure keychain
update_detail_title: Netlify Netlify CLI tokens now stored in your system’s secure keychain
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: Netlify Netlify CLI tokens now stored in your system’s secure keychain has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: Netlify published Netlify Netlify CLI tokens now stored in your system’s secure keychain.
release_summary: ← All changelog entries November 17, 2026 Netlify CLI tokens now stored in your system’s secure keychain
  cli announcement security Starting in version 27.18.0, Netlify CLI stores authentication tokens encrypted at rest in your
  operating system’s native secure keychain rather than in plain text on disk. This update protects your account credentials
  across macOS, Windows, and supported Linux distributions. Previously.
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
- at: '2026-11-17T00:00:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-27T00:11:49Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: html-changelog
primary_official_source: https://www.netlify.com/changelog/
fallback_official_sources: []
official_patch_notes_capture_status: captured-from-official-html
official_patch_notes_source_url: https://www.netlify.com/changelog/2026-11-17-netlify-cli-keychain-storage/
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: html-changelog
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-27T00:11:34Z'
  url: https://www.netlify.com/changelog/2026-11-17-netlify-cli-keychain-storage/
  status: captured-from-official-html
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "← All changelog entries November 17, 2026 Netlify CLI tokens now stored in your system’s secure\
  \ keychain cli announcement security Starting in version 27.18.0, Netlify CLI stores authentication tokens encrypted at\
  \ rest in your operating system’s native secure keychain rather than in plain text on disk. This update protects your account\
  \ credentials across macOS, Windows, and supported Linux distributions.\n\n\n Previously, Netlify CLI saved login tokens\
  \ in plain text in a local configuration file (such as ~/Library/Preferences/netlify/config.json on macOS). Because these\
  \ tokens grant full access to manage your Netlify account and projects, plain text storage left them exposed to any malicious\
  \ script or local process with disk read access. Storing tokens directly in your device’s secure credential store mitigates\
  \ that risk and limits the blast radius of local machine breaches or prompt injection attacks.\n\n\n How it works\n Netlify\
  \ CLI now integrates directly with platform-native credential managers:\n\n\n\n macOS : Keychain\n Windows : Windows Credential\
  \ Manager\n Linux : Secret Service API (standard on GNOME and KDE, and configurable elsewhere)\n\n When you run netlify\
  \ login , new tokens are automatically saved to the OS keychain. Depending on your system settings, your device may occasionally\
  \ ask for biometric authorization (such as Touch ID or fingerprint) or your password when the CLI accesses your credentials.\n\
  \n\n Migrating your token\n\n\n\n When an existing plain text token is detected during an interactive command, Netlify CLI\
  \ prompts you to migrate to keychain storage. Approving the prompt initiates a login refresh, saves your token securely\
  \ to the keychain, and removes the legacy plain text file entry. If you decline, your choice is remembered so you aren’t\
  \ nagged again. You can also trigger the migration at any time by running netlify login --new .\n\n\n If keychain storage\
  \ is unavailable on your system or writes fail, Netlify CLI automatically falls back to plain text storage. To verify where\
  \ your active token is stored, run netlify status . You can also set NETLIFY_USE_LEGACY_AUTH_STORAGE=1 to disable keychain\
  \ storage if required in your environment.\n\n\n What you need to do\n To update your Netlify CLI to the latest version,\
  \ run:\n\n\n npm install -g netlify-cli@latest\n The next time you run an interactive command requiring authentication,\
  \ press Enter at the prompt to migrate your token to your system’s keychain, or run netlify login --new to migrate immediately.\n\
  \n\n When updating, keep the following in mind:\n\n\n\n Multiple global CLI installs : If you have multiple global installs\
  \ of Netlify CLI across different Node managers (such as nvm , pnpm , or Homebrew), update all of them so an older version\
  \ doesn’t revert your credentials back to plain text storage.\n Local Netlify MCP : If you use the local Netlify Model Context\
  \ Protocol (MCP) server, ensure you have @netlify/mcp version 1.22.1 or later to support keychain-stored credentials.\n\n\
  \ Learn more about managing your credentials in the Netlify CLI documentation or view the changes in the Netlify CLI repository\
  \ .\n\n\n Previous: November 17, 2026 GPT-6.2 Astra and GPT-6.2 Sol now available in AI Gateway and Agent Runners Next:\
  \ November 17, 2026 Connectors for Agent Runners Changelog\n\n Every Netlify release, in your inbox One short email when\
  \ something ships.\n\n\n\n Email address Subscribe\nPrefer a feed? Follow the changelog via RSS ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
