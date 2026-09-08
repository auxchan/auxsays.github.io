---
layout: aux-update
title: GitHub / Copilot Automatic Dependabot access to GitHub-hosted registries official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Automatic Dependabot access to GitHub-hosted
  registries.
permalink: /updates/github/github/automatic-dependabot-access-to-github-hosted-registries/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-08-automatic-dependabot-access-to-github-hosted-registries
update_download_url: ''
update_version: Automatic Dependabot access to GitHub-hosted registries
update_logo_text: GIT
update_published_at: '2026-09-08T16:46:05Z'
update_last_checked: '2026-09-08T19:01:43Z'
source_last_checked: '2026-09-08T19:01:43Z'
official_body_last_checked: '2026-09-08T19:01:43Z'
record_last_updated: '2026-09-08T19:01:43Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Automatic Dependabot access to GitHub-hosted registries
update_detail_title: GitHub / Copilot Automatic Dependabot access to GitHub-hosted registries
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Automatic Dependabot access to GitHub-hosted registries has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Automatic Dependabot access to GitHub-hosted registries.
release_summary: "Dependabot can now read from private GitHub Packages registries without a personal access token. If a package\
  \ has granted your repository access through “Manage Actions access” in the package settings, Dependabot reuses that grant.\n\
  \n\n What’s new\n Dependabot’s GITHUB_TOKEN can now request packages: read , and Dependabot jobs send that token when pulling\
  \ from *.pkg.github.com and ghcr.io . Any package that has granted your repository access through “Manage Actions access”\
  \ will accept it, the same as a regular GitHub Actions workflow.\n\n\n This is available for every GitHub Packages ecosystem\
  \ that Dependabot supports.\n\n\n How to enable it\n For each package Dependabot needs to read:\n\n\n\n Open the package’s\
  \ settings page (under your organization’s or personal account’s Packages tab).\n Under “Manage Actions access”, add the\
  \ repository that runs Dependabot with Read access.\n\n You don’t need to change dependabot.yml , and you can remove any\
  \ PAT-based registry entries you added for these packages.\n\n\n Learn more\n\n Ensuring workflow access to your package\n\
  \ Configuring access to private registries for Dependabot\n\n Editor’s note\n Shortly after the initial release on June\
  \ 23, 2026, we temporarily rolled back this feature after identifying a conflict that caused some npm update jobs to resolve\
  \ public packages through GitHub Packages. We have re-enabled the feature with automatic GitHub Packages credentials used\
  \ only as fallback authentication, so explicit registry credentials and normal registry routing continue to take precedence.\n\
  \n\n\n The post Automatic Dependabot access to GitHub-hosted registries appeared first on The GitHub Blog ."
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
- at: '2026-09-08T16:46:05Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-08T19:01:52Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-08-automatic-dependabot-access-to-github-hosted-registries
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-08T19:01:43Z'
  url: https://github.blog/changelog/2026-09-08-automatic-dependabot-access-to-github-hosted-registries
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Dependabot can now read from private GitHub Packages registries without a personal access token.\
  \ If a package has granted your repository access through “Manage Actions access” in the package settings, Dependabot reuses\
  \ that grant.\n\n\n What’s new\n Dependabot’s GITHUB_TOKEN can now request packages: read , and Dependabot jobs send that\
  \ token when pulling from *.pkg.github.com and ghcr.io . Any package that has granted your repository access through “Manage\
  \ Actions access” will accept it, the same as a regular GitHub Actions workflow.\n\n\n This is available for every GitHub\
  \ Packages ecosystem that Dependabot supports.\n\n\n How to enable it\n For each package Dependabot needs to read:\n\n\n\
  \n Open the package’s settings page (under your organization’s or personal account’s Packages tab).\n Under “Manage Actions\
  \ access”, add the repository that runs Dependabot with Read access.\n\n You don’t need to change dependabot.yml , and you\
  \ can remove any PAT-based registry entries you added for these packages.\n\n\n Learn more\n\n Ensuring workflow access\
  \ to your package\n Configuring access to private registries for Dependabot\n\n Editor’s note\n Shortly after the initial\
  \ release on June 23, 2026, we temporarily rolled back this feature after identifying a conflict that caused some npm update\
  \ jobs to resolve public packages through GitHub Packages. We have re-enabled the feature with automatic GitHub Packages\
  \ credentials used only as fallback authentication, so explicit registry credentials and normal registry routing continue\
  \ to take precedence.\n\n\n\n The post Automatic Dependabot access to GitHub-hosted registries appeared first on The GitHub\
  \ Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
