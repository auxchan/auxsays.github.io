---
layout: aux-update
title: GitHub / Copilot Control GitHub Actions cache access with cache-mode official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Control GitHub Actions cache access with cache-mode.
permalink: /updates/github/github/control-github-actions-cache-access-with-cache-mode/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-10-control-github-actions-cache-access-with-cache-mode
update_download_url: ''
update_version: Control GitHub Actions cache access with cache-mode
update_logo_text: GIT
update_published_at: '2026-09-10T17:26:59Z'
update_last_checked: '2026-09-10T18:48:26Z'
source_last_checked: '2026-09-10T23:13:08Z'
official_body_last_checked: '2026-09-10T23:13:08Z'
record_last_updated: '2026-09-10T18:48:26Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Control GitHub Actions cache access with cache-mode
update_detail_title: GitHub / Copilot Control GitHub Actions cache access with cache-mode
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Control GitHub Actions cache access with cache-mode has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Control GitHub Actions cache access with cache-mode.
release_summary: "You can now use cache-mode to apply least-privilege access to the GitHub Actions cache at the workflow or\
  \ job level. By granting each workflow or job only the cache access it needs, you can prevent unnecessary restores or saves\
  \ and help protect trusted workflows from cache poisoning. This capability is now generally available on all plans.\n\n\n\
  \ Choose the access each workflow or job needs:\n\n\n\n read allows cache restores but prevents cache saves. This is the\
  \ default for low-trust events such as pull_request_target .\n write allows cache restores and saves. This is the default\
  \ for trusted events such as push .\n write-only allows cache saves but prevents cache restores.\n none prevents all cache\
  \ access.\n\n Job-level settings override workflow-level settings. The selected mode is enforced by the cache service and\
  \ carries through reusable workflows, where a called workflow cannot receive more cache access than its caller granted.\n\
  \n\n An explicitly declared cache-mode also overrides the read-only cache default for low-trust events such as pull_request_target\
  \ . Declaring write or write-only for these events can increase the risk of cache poisoning, so GitHub Actions adds a warning\
  \ annotation when the declared mode grants write access. Workflows that do not set cache-mode continue to use the existing\
  \ secure defaults.\n\n\n Cache mode is generally available on github.com for all GitHub plans. For configuration details,\
  \ see the cache-mode workflow syntax documentation .\n\n\n Join the discussion within GitHub Community\n\n\n\n The post\
  \ Control GitHub Actions cache access with cache-mode appeared first on The GitHub Blog ."
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
- at: '2026-09-10T17:26:59Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-10T18:48:35Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-10-control-github-actions-cache-access-with-cache-mode
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-10T18:48:26Z'
  url: https://github.blog/changelog/2026-09-10-control-github-actions-cache-access-with-cache-mode
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-10T19:46:46Z'
  url: https://github.blog/changelog/2026-09-10-control-github-actions-cache-access-with-cache-mode
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-10T23:13:08Z'
  url: https://github.blog/changelog/2026-09-10-control-github-actions-cache-access-with-cache-mode
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now use cache-mode to apply least-privilege access to the GitHub Actions cache at the\
  \ workflow or job level. By granting each workflow or job only the cache access it needs, you can prevent unnecessary restores\
  \ or saves and help protect trusted workflows from cache poisoning. This capability is now generally available on all plans.\n\
  \n\n Choose the access each workflow or job needs:\n\n\n\n read allows cache restores but prevents cache saves. This is\
  \ the default for low-trust events such as pull_request_target .\n write allows cache restores and saves. This is the default\
  \ for trusted events such as push .\n write-only allows cache saves but prevents cache restores.\n none prevents all cache\
  \ access.\n\n Job-level settings override workflow-level settings. The selected mode is enforced by the cache service and\
  \ carries through reusable workflows, where a called workflow cannot receive more cache access than its caller granted.\n\
  \n\n An explicitly declared cache-mode also overrides the read-only cache default for low-trust events such as pull_request_target\
  \ . Declaring write or write-only for these events can increase the risk of cache poisoning, so GitHub Actions adds a warning\
  \ annotation when the declared mode grants write access. Workflows that do not set cache-mode continue to use the existing\
  \ secure defaults.\n\n\n Cache mode is generally available on github.com for all GitHub plans. For configuration details,\
  \ see the cache-mode workflow syntax documentation .\n\n\n Join the discussion within GitHub Community\n\n\n\n The post\
  \ Control GitHub Actions cache access with cache-mode appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
