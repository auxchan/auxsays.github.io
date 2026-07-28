---
layout: aux-update
title: GitHub / Copilot Enterprise managed settings in the GitHub Copilot app and Copilot cloud agent official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/enterprise-managed-settings-in-the-github-copilot-app-and-copilot-cloud-agent/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-27-enterprise-managed-settings-now-apply-to-the-github-copilot-app
update_download_url: ''
update_version: Enterprise managed settings in the GitHub Copilot app and Copilot cloud agent
update_logo_text: GIT
update_published_at: '2026-07-27T17:00:35Z'
update_last_checked: '2026-07-28T09:08:26Z'
source_last_checked: '2026-07-28T09:08:26Z'
official_body_last_checked: '2026-07-28T09:08:26Z'
record_last_updated: '2026-07-28T09:08:26Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Enterprise managed settings in the GitHub Copilot app and Copilot cloud agent
update_detail_title: GitHub / Copilot Enterprise managed settings in the GitHub Copilot app and Copilot cloud agent
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Enterprise managed settings in the GitHub Copilot app and Copilot cloud agent has an official
  AUXSAYS record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Enterprise managed settings in the GitHub Copilot app and Copilot cloud
  agent.
release_summary: "You can now govern the GitHub Copilot app and Copilot cloud agent with enterprise managed settings, the\
  \ same centrally managed policies you use to control Copilot across your enterprise. With a managed-settings.json file,\
  \ enterprise owners define one set of guardrails, such as which plugins and marketplaces developers can use and whether\
  \ they can bypass approval prompts. Copilot clients automatically enforce these settings for everyone on your enterprise’s\
  \ Copilot plan.\n\n\n As your developers adopt Copilot across more surfaces, you’re accountable for applying the same governance\
  \ everywhere they work. Any client that sits outside your policy is a gap, a place where someone could install a plugin\
  \ you haven’t vetted or run a command you’d normally gate. Your governance is only as strong as its least-covered surface.\n\
  \n\n The Copilot app and cloud agent now join Copilot CLI and VS Code as supported clients for enterprise managed settings,\
  \ so your guardrails follow your developers into the app and cloud agent tasks. You define your policy once, and it’s enforced\
  \ consistently wherever your teams build. That’s the cross-client consistency and high-trust teams need to adopt Copilot\
  \ with confidence.\n\n\n Bring every client under the same guardrails\n The Copilot app reads the same managed-settings.json\
  \ you already use for your other clients. You can govern things like:\n\n\n\n Which plugins are available.\n Which plugin\
  \ marketplaces developers can install from.\n Whether developers can bypass approval prompts before Copilot runs commands,\
  \ accesses files, or fetches URLs.\n Setting auto model selection as the default for new conversations.\n\n The Copilot\
  \ cloud agent reads the applicable managed settings, including those for plugins and marketplace controls. It only uses\
  \ the plugins and marketplaces you’ve approved. Bypass-prompt controls only apply to the interactive clients (i.e., the\
  \ app, Copilot CLI, and VS Code).\n\n\n For each supported key, your managed value takes precedence over anything a developer\
  \ sets locally. See the full list of options in the enterprise managed settings reference .\n\n\n If you already deploy\
  \ managed-settings.json for Copilot CLI and VS Code, there’s nothing new to set up. The Copilot app automatically picks\
  \ up your existing configuration the next time a developer signs in or restarts the app, and the cloud agent observes changes\
  \ on the next task assignment.\n\n\n Getting started\n If you’re setting up enterprise managed settings for the first time,\
  \ the default approach is server-managed deployment:\n\n\n\n Create and configure a .github-private repository in your enterprise.\
  \ For more information, see our guide .\n In that repository, create or update copilot/managed-settings.json .\n Add your\
  \ enterprise policy keys and values in JSON, then commit and push to the default branch.\n\n Supported clients apply updated\
  \ settings within about an hour, immediately after a developer restarts the client, or when a developer signs back in. You\
  \ can also deploy through MDM or a distributed file.\n\n\n To learn more, see configuring enterprise managed settings .\n\
  \n\n Join the discussion within GitHub Community .\n\n\n\n The post Enterprise managed settings in the GitHub Copilot app\
  \ and Copilot cloud agent appeared first on The GitHub Blog ."
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
- at: '2026-07-27T17:00:35Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-28T09:08:30Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-27-enterprise-managed-settings-now-apply-to-the-github-copilot-app
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-28T09:08:26Z'
  url: https://github.blog/changelog/2026-07-27-enterprise-managed-settings-now-apply-to-the-github-copilot-app
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now govern the GitHub Copilot app and Copilot cloud agent with enterprise managed settings,\
  \ the same centrally managed policies you use to control Copilot across your enterprise. With a managed-settings.json file,\
  \ enterprise owners define one set of guardrails, such as which plugins and marketplaces developers can use and whether\
  \ they can bypass approval prompts. Copilot clients automatically enforce these settings for everyone on your enterprise’s\
  \ Copilot plan.\n\n\n As your developers adopt Copilot across more surfaces, you’re accountable for applying the same governance\
  \ everywhere they work. Any client that sits outside your policy is a gap, a place where someone could install a plugin\
  \ you haven’t vetted or run a command you’d normally gate. Your governance is only as strong as its least-covered surface.\n\
  \n\n The Copilot app and cloud agent now join Copilot CLI and VS Code as supported clients for enterprise managed settings,\
  \ so your guardrails follow your developers into the app and cloud agent tasks. You define your policy once, and it’s enforced\
  \ consistently wherever your teams build. That’s the cross-client consistency and high-trust teams need to adopt Copilot\
  \ with confidence.\n\n\n Bring every client under the same guardrails\n The Copilot app reads the same managed-settings.json\
  \ you already use for your other clients. You can govern things like:\n\n\n\n Which plugins are available.\n Which plugin\
  \ marketplaces developers can install from.\n Whether developers can bypass approval prompts before Copilot runs commands,\
  \ accesses files, or fetches URLs.\n Setting auto model selection as the default for new conversations.\n\n The Copilot\
  \ cloud agent reads the applicable managed settings, including those for plugins and marketplace controls. It only uses\
  \ the plugins and marketplaces you’ve approved. Bypass-prompt controls only apply to the interactive clients (i.e., the\
  \ app, Copilot CLI, and VS Code).\n\n\n For each supported key, your managed value takes precedence over anything a developer\
  \ sets locally. See the full list of options in the enterprise managed settings reference .\n\n\n If you already deploy\
  \ managed-settings.json for Copilot CLI and VS Code, there’s nothing new to set up. The Copilot app automatically picks\
  \ up your existing configuration the next time a developer signs in or restarts the app, and the cloud agent observes changes\
  \ on the next task assignment.\n\n\n Getting started\n If you’re setting up enterprise managed settings for the first time,\
  \ the default approach is server-managed deployment:\n\n\n\n Create and configure a .github-private repository in your enterprise.\
  \ For more information, see our guide .\n In that repository, create or update copilot/managed-settings.json .\n Add your\
  \ enterprise policy keys and values in JSON, then commit and push to the default branch.\n\n Supported clients apply updated\
  \ settings within about an hour, immediately after a developer restarts the client, or when a developer signs back in. You\
  \ can also deploy through MDM or a distributed file.\n\n\n To learn more, see configuring enterprise managed settings .\n\
  \n\n Join the discussion within GitHub Community .\n\n\n\n The post Enterprise managed settings in the GitHub Copilot app\
  \ and Copilot cloud agent appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
