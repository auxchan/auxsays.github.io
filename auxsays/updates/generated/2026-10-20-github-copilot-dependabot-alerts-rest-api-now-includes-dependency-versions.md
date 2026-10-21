---
layout: aux-update
title: GitHub / Copilot Dependabot alerts REST API now includes dependency versions official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Dependabot alerts REST API now includes dependency
  versions.
permalink: /updates/github/github/dependabot-alerts-rest-api-now-includes-dependency-versions/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-20-dependabot-alerts-rest-api-now-includes-dependency-versions
update_download_url: ''
update_version: Dependabot alerts REST API now includes dependency versions
update_logo_text: GIT
update_published_at: '2026-10-20T17:13:40Z'
update_last_checked: '2026-10-21T00:20:53Z'
source_last_checked: '2026-10-21T00:20:53Z'
official_body_last_checked: '2026-10-21T00:20:53Z'
record_last_updated: '2026-10-21T00:20:53Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Dependabot alerts REST API now includes dependency versions
update_detail_title: GitHub / Copilot Dependabot alerts REST API now includes dependency versions
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Dependabot alerts REST API now includes dependency versions has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Dependabot alerts REST API now includes dependency versions.
release_summary: "You can now get the version of a vulnerable dependency directly from Dependabot alert responses in the REST\
  \ API. Each alert’s dependency object includes a new version_requirement field with the version or version constraint that\
  \ Dependabot last recorded for the alert.\n\n\n Alert responses already included the advisory’s vulnerable version range,\
  \ but not the version in your repository. If you sync alerts to other security tools, you no longer need to parse lockfiles\
  \ or make a separate GraphQL request for vulnerableRequirements to get that version.\n\n\n The value depends on how Dependabot\
  \ detected the dependency:\n\n\n\n Lockfiles: The resolved version.\n Manifests without a lockfile: The version or version\
  \ constraint declared in the manifest.\n Dependency submission API: The resolved version submitted by your build tooling.\n\
  \n The field is null when no value is available. If an alert covers more than one vulnerable version of a dependency, the\
  \ field holds one recorded value and may not represent all of them. Long version constraints may also be truncated.\n\n\n\
  \ You’ll find version_requirement in responses for individual alerts, in repository, organization, and enterprise alert\
  \ lists, and in dependabot_alert webhook payloads.\n\n\n This field is available now on github.com and GitHub Enterprise\
  \ Cloud with data residency, and will be included in GitHub Enterprise Server 3.24.\n\n\n Learn more about the REST API\
  \ endpoints for Dependabot alerts and the dependabot_alert webhook event .\n\n\n\n The post Dependabot alerts REST API now\
  \ includes dependency versions appeared first on The GitHub Blog ."
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
- at: '2026-10-20T17:13:40Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-21T00:20:59Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-20-dependabot-alerts-rest-api-now-includes-dependency-versions
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-21T00:20:53Z'
  url: https://github.blog/changelog/2026-10-20-dependabot-alerts-rest-api-now-includes-dependency-versions
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now get the version of a vulnerable dependency directly from Dependabot alert responses\
  \ in the REST API. Each alert’s dependency object includes a new version_requirement field with the version or version constraint\
  \ that Dependabot last recorded for the alert.\n\n\n Alert responses already included the advisory’s vulnerable version\
  \ range, but not the version in your repository. If you sync alerts to other security tools, you no longer need to parse\
  \ lockfiles or make a separate GraphQL request for vulnerableRequirements to get that version.\n\n\n The value depends on\
  \ how Dependabot detected the dependency:\n\n\n\n Lockfiles: The resolved version.\n Manifests without a lockfile: The version\
  \ or version constraint declared in the manifest.\n Dependency submission API: The resolved version submitted by your build\
  \ tooling.\n\n The field is null when no value is available. If an alert covers more than one vulnerable version of a dependency,\
  \ the field holds one recorded value and may not represent all of them. Long version constraints may also be truncated.\n\
  \n\n You’ll find version_requirement in responses for individual alerts, in repository, organization, and enterprise alert\
  \ lists, and in dependabot_alert webhook payloads.\n\n\n This field is available now on github.com and GitHub Enterprise\
  \ Cloud with data residency, and will be included in GitHub Enterprise Server 3.24.\n\n\n Learn more about the REST API\
  \ endpoints for Dependabot alerts and the dependabot_alert webhook event .\n\n\n\n The post Dependabot alerts REST API now\
  \ includes dependency versions appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
