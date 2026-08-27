---
layout: aux-update
title: GitHub / Copilot Actions retention will cover checks, workflow runs, and statuses official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Actions retention will cover checks, workflow
  runs, and statuses.
permalink: /updates/github/github/actions-retention-will-cover-checks-workflow-runs-and-statuses/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-27-actions-retention-will-cover-checks-workflow-runs-and-statuses
update_download_url: ''
update_version: Actions retention will cover checks, workflow runs, and statuses
update_logo_text: GIT
update_published_at: '2026-08-27T21:50:39Z'
update_last_checked: '2026-08-27T23:27:08Z'
source_last_checked: '2026-08-27T23:27:08Z'
official_body_last_checked: '2026-08-27T23:27:08Z'
record_last_updated: '2026-08-27T23:27:08Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Actions retention will cover checks, workflow runs, and statuses
update_detail_title: GitHub / Copilot Actions retention will cover checks, workflow runs, and statuses
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Actions retention will cover checks, workflow runs, and statuses has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Actions retention will cover checks, workflow runs, and statuses.
release_summary: "Starting October 1, 2026, checks, workflow runs, and statuses will be governed by the same Actions retention\
  \ setting that already controls how long artifacts and logs are kept, with a default of 90 days. Until now, checks, workflow\
  \ runs, and statuses were retained for 400+ days regardless of your retention configuration. After this change, they will\
  \ automatically be cleaned up once they pass the artifact and log retention period configured for your repository, organization,\
  \ or enterprise.\n\n\n This change reduces the amount of stale data stored across GitHub Actions, helping keep checks, workflow\
  \ runs, and statuses fast and reliable for everyone.\n\n\n What’s changing\n\n Checks, workflow runs, and statuses will\
  \ follow your Actions retention setting. They will be cleaned up once they exceed your configured artifact and log retention\
  \ period , instead of sticking around for 400+ days.\n The retention setting now has a broader scope. The setting label\
  \ in the UI will be updated to read “Check, workflow run, status, artifact and log retention” to reflect that it now governs\
  \ all five.\n Retention caps still apply. A repository can raise its retention only up to the cap configured at the organization\
  \ and enterprise level. For public repositories, the maximum retention for checks, workflow runs, and statuses is 90 days,\
  \ matching the existing limit for artifacts and logs.\n The change is not retroactive. Adjusting your retention setting\
  \ will not restore data that was previously evicted due to a retention policy. This matches how artifact and log retention\
  \ behaves today.\n\n Billing and storage implications\n Artifacts and logs count toward your billable GitHub Actions storage\
  \ . Because this change cleans up data once it passes your retention period, repositories that previously kept artifacts\
  \ and logs around longer than their configured setting may see a reduction in billable Actions storage usage.\n\n\n Keep\
  \ this in mind when you review your retention setting:\n\n\n\n Lowering your retention period removes artifacts and logs\
  \ sooner, which can reduce your Actions storage costs.\n Raising your retention period keeps artifacts and logs available\
  \ longer, which may increase your billable Actions storage. Checks, workflow run, and statuses metadata are not billed for\
  \ storage, but the artifacts and logs associated with them are.\n\n What you need to do\n For most repositories, no action\
  \ is required. Starting on October 1, checks, workflow runs, and statuses will be cleaned up according to the retention\
  \ setting you already have configured.\n\n\n To prepare:\n\n\n\n Review your Actions retention setting for your repository,\
  \ organization, or enterprise before October 1, 2026. Confirm it reflects how long you need checks, workflow runs, and statuses\
  \ to remain available.\n Increase the retention period if you need a longer window , up to the maximum allowed by your organization\
  \ and enterprise caps (90 days for public repositories). Note that a longer retention period keeps artifacts and logs longer\
  \ and may increase your billable Actions storage.\n Export or archive anything you need to keep beyond your configured retention\
  \ period, since older checks, workflow runs, and statuses will be automatically removed once this change takes effect.\n\
  \n\n The post Actions retention will cover checks, workflow runs, and statuses appeared first on The GitHub Blog ."
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
- at: '2026-08-27T21:50:39Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-27T23:27:21Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-27-actions-retention-will-cover-checks-workflow-runs-and-statuses
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-27T23:27:08Z'
  url: https://github.blog/changelog/2026-08-27-actions-retention-will-cover-checks-workflow-runs-and-statuses
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Starting October 1, 2026, checks, workflow runs, and statuses will be governed by the same Actions\
  \ retention setting that already controls how long artifacts and logs are kept, with a default of 90 days. Until now, checks,\
  \ workflow runs, and statuses were retained for 400+ days regardless of your retention configuration. After this change,\
  \ they will automatically be cleaned up once they pass the artifact and log retention period configured for your repository,\
  \ organization, or enterprise.\n\n\n This change reduces the amount of stale data stored across GitHub Actions, helping\
  \ keep checks, workflow runs, and statuses fast and reliable for everyone.\n\n\n What’s changing\n\n Checks, workflow runs,\
  \ and statuses will follow your Actions retention setting. They will be cleaned up once they exceed your configured artifact\
  \ and log retention period , instead of sticking around for 400+ days.\n The retention setting now has a broader scope.\
  \ The setting label in the UI will be updated to read “Check, workflow run, status, artifact and log retention” to reflect\
  \ that it now governs all five.\n Retention caps still apply. A repository can raise its retention only up to the cap configured\
  \ at the organization and enterprise level. For public repositories, the maximum retention for checks, workflow runs, and\
  \ statuses is 90 days, matching the existing limit for artifacts and logs.\n The change is not retroactive. Adjusting your\
  \ retention setting will not restore data that was previously evicted due to a retention policy. This matches how artifact\
  \ and log retention behaves today.\n\n Billing and storage implications\n Artifacts and logs count toward your billable\
  \ GitHub Actions storage . Because this change cleans up data once it passes your retention period, repositories that previously\
  \ kept artifacts and logs around longer than their configured setting may see a reduction in billable Actions storage usage.\n\
  \n\n Keep this in mind when you review your retention setting:\n\n\n\n Lowering your retention period removes artifacts\
  \ and logs sooner, which can reduce your Actions storage costs.\n Raising your retention period keeps artifacts and logs\
  \ available longer, which may increase your billable Actions storage. Checks, workflow run, and statuses metadata are not\
  \ billed for storage, but the artifacts and logs associated with them are.\n\n What you need to do\n For most repositories,\
  \ no action is required. Starting on October 1, checks, workflow runs, and statuses will be cleaned up according to the\
  \ retention setting you already have configured.\n\n\n To prepare:\n\n\n\n Review your Actions retention setting for your\
  \ repository, organization, or enterprise before October 1, 2026. Confirm it reflects how long you need checks, workflow\
  \ runs, and statuses to remain available.\n Increase the retention period if you need a longer window , up to the maximum\
  \ allowed by your organization and enterprise caps (90 days for public repositories). Note that a longer retention period\
  \ keeps artifacts and logs longer and may increase your billable Actions storage.\n Export or archive anything you need\
  \ to keep beyond your configured retention period, since older checks, workflow runs, and statuses will be automatically\
  \ removed once this change takes effect.\n\n\n The post Actions retention will cover checks, workflow runs, and statuses\
  \ appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
