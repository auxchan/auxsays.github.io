---
layout: aux-update
title: 'GitHub / Copilot GitHub Actions: Early September 2026 updates official update breakdown'
description: 'Official GitHub / Copilot update record captured from GitHub for GitHub Actions: Early September 2026 updates.'
permalink: /updates/github/github/github-actions-early-september-2026-updates/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-03-github-actions-early-september-2026-updates
update_download_url: ''
update_version: 'GitHub Actions: Early September 2026 updates'
update_logo_text: GIT
update_published_at: '2026-09-03T20:30:53Z'
update_last_checked: '2026-09-03T21:57:51Z'
source_last_checked: '2026-09-04T07:19:07Z'
official_body_last_checked: '2026-09-04T07:19:07Z'
record_last_updated: '2026-09-03T21:57:51Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot GitHub Actions: Early September 2026 updates'
update_detail_title: 'GitHub / Copilot GitHub Actions: Early September 2026 updates'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot GitHub Actions: Early September 2026 updates has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot GitHub Actions: Early September 2026 updates.'
release_summary: "GitHub Actions now includes three updates that give you clearer visibility and finer-grained control over\
  \ your workflows.\n\n\n New REST API for runner version deprecations\n A new REST API returns when registration and runtime\
  \ support end for a given runner version, so you can plan runner upgrades before a version is deprecated. Call GET /actions/runners/deprecations/{version}\
  \ at the repository, organization, or enterprise level. The response includes runner_version , runtime_deprecates_at , and\
  \ registration_deprecates_at .\n\n\n New vulnerability-alerts permission for GITHUB_TOKEN\n You can now grant workflows\
  \ read-only access to Dependabot alerts with the new vulnerability-alerts permission for GITHUB_TOKEN . This permission\
  \ supports read and none values, which lets you follow least-privilege practices instead of relying on broader scopes. For\
  \ more information, check the permissions key in the workflow syntax .\n\n\n New job context properties for reusable workflows\n\
  \ Reusable workflows can now determine their own source identity at runtime with four new job context properties:\n\n\n\n\
  \ job.workflow_ref : The full ref of the workflow file that defines the current job.\n job.workflow_sha : The commit SHA\
  \ of the workflow file.\n job.workflow_repository : The owner/repo of the workflow file.\n job.workflow_file_path : The\
  \ file path relative to the repository root.\n\n Unlike the existing github.workflow_ref and github.workflow_sha properties,\
  \ these job context values reflect the workflow that defines the current job. For a job defined directly in a workflow,\
  \ job.workflow_ref matches github.workflow_ref ; they diverge only for reusable workflows. These properties are not available\
  \ on GitHub Enterprise Server.\n\n\n To learn more, check the job context documentation .\n\n\n\n The post GitHub Actions:\
  \ Early September 2026 updates appeared first on The GitHub Blog ."
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
- at: '2026-09-03T20:30:53Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-03T21:58:07Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-03-github-actions-early-september-2026-updates
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-03T21:57:51Z'
  url: https://github.blog/changelog/2026-09-03-github-actions-early-september-2026-updates
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-04T07:19:07Z'
  url: https://github.blog/changelog/2026-09-03-github-actions-early-september-2026-updates
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub Actions now includes three updates that give you clearer visibility and finer-grained control\
  \ over your workflows.\n\n\n New REST API for runner version deprecations\n A new REST API returns when registration and\
  \ runtime support end for a given runner version, so you can plan runner upgrades before a version is deprecated. Call GET\
  \ /actions/runners/deprecations/{version} at the repository, organization, or enterprise level. The response includes runner_version\
  \ , runtime_deprecates_at , and registration_deprecates_at .\n\n\n New vulnerability-alerts permission for GITHUB_TOKEN\n\
  \ You can now grant workflows read-only access to Dependabot alerts with the new vulnerability-alerts permission for GITHUB_TOKEN\
  \ . This permission supports read and none values, which lets you follow least-privilege practices instead of relying on\
  \ broader scopes. For more information, check the permissions key in the workflow syntax .\n\n\n New job context properties\
  \ for reusable workflows\n Reusable workflows can now determine their own source identity at runtime with four new job context\
  \ properties:\n\n\n\n job.workflow_ref : The full ref of the workflow file that defines the current job.\n job.workflow_sha\
  \ : The commit SHA of the workflow file.\n job.workflow_repository : The owner/repo of the workflow file.\n job.workflow_file_path\
  \ : The file path relative to the repository root.\n\n Unlike the existing github.workflow_ref and github.workflow_sha properties,\
  \ these job context values reflect the workflow that defines the current job. For a job defined directly in a workflow,\
  \ job.workflow_ref matches github.workflow_ref ; they diverge only for reusable workflows. These properties are not available\
  \ on GitHub Enterprise Server.\n\n\n To learn more, check the job context documentation .\n\n\n\n The post GitHub Actions:\
  \ Early September 2026 updates appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
