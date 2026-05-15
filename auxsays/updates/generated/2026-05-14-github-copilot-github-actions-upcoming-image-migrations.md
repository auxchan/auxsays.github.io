---
layout: aux-update
title: 'GitHub / Copilot GitHub Actions: Upcoming image migrations official update breakdown'
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/github-actions-upcoming-image-migrations/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-14-github-actions-upcoming-image-migrations
update_download_url: ''
update_version: 'GitHub Actions: Upcoming image migrations'
update_logo_text: GIT
update_published_at: '2026-05-14T18:31:34Z'
update_last_checked: '2026-05-14T20:04:55Z'
source_last_checked: '2026-05-15T04:31:04Z'
official_body_last_checked: '2026-05-15T04:31:04Z'
record_last_updated: '2026-05-14T20:04:55Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot GitHub Actions: Upcoming image migrations'
update_detail_title: 'GitHub / Copilot GitHub Actions: Upcoming image migrations'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot GitHub Actions: Upcoming image migrations has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot GitHub Actions: Upcoming image migrations.'
release_summary: "There are two upcoming image migrations customers should be aware of, and GitHub is transitioning to owning\
  \ the Arm64 images for hosted runners.\n\n\n Arm64 runner images now maintained by GitHub\n GitHub now owns and maintains\
  \ the Arm64 runner images for GitHub Actions hosted runners. These images were previously maintained by Arm Limited, LLC\
  \ and are now fully managed by GitHub. No action is required from users as part of this transition.\n\n\n What’s changing\n\
  \n Windows 11 Arm ( windows-11-arm ) images have already transitioned to GitHub-managed builds and pipelines.\n Ubuntu 24.04\
  \ ( ubuntu-24.04-arm ) and Ubuntu 22.04 ( ubuntu-22.04-arm ) images are being migrated to GitHub’s internal pipelines. During\
  \ the transition, these images won’t receive updates, and no new release notes will appear in the actions/runner-images\
  \ repository for them.\n The actions/partner-runner-images repository will be archived after the transition is complete.\
  \ All open issues and future support will move to actions/runner-images .\n\n What’s not changing\n\n Image functionality\
  \ and compatibility remain exactly the same.\n No packages are being added or removed as part of this transition.\n No breaking\
  \ changes will be introduced during the migration period.\n\n If you encounter a critical issue with the Ubuntu Arm64 images\
  \ during the transition, such as a CVE or vulnerability, open an issue in the actions/runner-images repository.\n\n\n Windows\
  \ 2025 Visual Studio 2026 image migration\n The windows-latest and windows-2025 labels in GitHub Actions will be migrated\
  \ to use Visual Studio 2026 by default. This change will be rolled out over a week beginning June 8, 2026 and will complete\
  \ by June 15, 2026.\n\n\n If you want to test the new image, update the runs-on: target in your YAML workflow file to the\
  \ new label windows-2025-vs2026 .\n\n\n Note: This label is meant for testing only. After the migration, this label will\
  \ point to the windows-2025 image.\n\n\n If you want to remain on VS 2022, update the runs-on: target in your YAML workflow\
  \ file to windows-2022 .\n\n\n For more information, or if you have questions, head to the runner-images repository .\n\n\
  \n macos-latest migration begins June 15\n The macos-latest image label migration will begin June 15 and take 30 days to\
  \ complete. The macos-latest image label will point to the macOS 26 image instead of macOS 15. During the migration, users\
  \ should expect to see their workflows begin running on the macOS 26 image.\n\n\n To continue using macOS 15, you can target\
  \ the macos-15 label directly.\n\n\n For questions, or more information, head to the runner-images repository .\n\n\n\n\
  \ The post GitHub Actions: Upcoming image migrations appeared first on The GitHub Blog ."
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
- at: '2026-05-14T18:31:34Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-14T20:04:56Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-14-github-actions-upcoming-image-migrations
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-14T20:04:55Z'
  url: https://github.blog/changelog/2026-05-14-github-actions-upcoming-image-migrations
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-05-15T04:31:04Z'
  url: https://github.blog/changelog/2026-05-14-github-actions-upcoming-image-migrations
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "There are two upcoming image migrations customers should be aware of, and GitHub is transitioning\
  \ to owning the Arm64 images for hosted runners.\n\n\n Arm64 runner images now maintained by GitHub\n GitHub now owns and\
  \ maintains the Arm64 runner images for GitHub Actions hosted runners. These images were previously maintained by Arm Limited,\
  \ LLC and are now fully managed by GitHub. No action is required from users as part of this transition.\n\n\n What’s changing\n\
  \n Windows 11 Arm ( windows-11-arm ) images have already transitioned to GitHub-managed builds and pipelines.\n Ubuntu 24.04\
  \ ( ubuntu-24.04-arm ) and Ubuntu 22.04 ( ubuntu-22.04-arm ) images are being migrated to GitHub’s internal pipelines. During\
  \ the transition, these images won’t receive updates, and no new release notes will appear in the actions/runner-images\
  \ repository for them.\n The actions/partner-runner-images repository will be archived after the transition is complete.\
  \ All open issues and future support will move to actions/runner-images .\n\n What’s not changing\n\n Image functionality\
  \ and compatibility remain exactly the same.\n No packages are being added or removed as part of this transition.\n No breaking\
  \ changes will be introduced during the migration period.\n\n If you encounter a critical issue with the Ubuntu Arm64 images\
  \ during the transition, such as a CVE or vulnerability, open an issue in the actions/runner-images repository.\n\n\n Windows\
  \ 2025 Visual Studio 2026 image migration\n The windows-latest and windows-2025 labels in GitHub Actions will be migrated\
  \ to use Visual Studio 2026 by default. This change will be rolled out over a week beginning June 8, 2026 and will complete\
  \ by June 15, 2026.\n\n\n If you want to test the new image, update the runs-on: target in your YAML workflow file to the\
  \ new label windows-2025-vs2026 .\n\n\n Note: This label is meant for testing only. After the migration, this label will\
  \ point to the windows-2025 image.\n\n\n If you want to remain on VS 2022, update the runs-on: target in your YAML workflow\
  \ file to windows-2022 .\n\n\n For more information, or if you have questions, head to the runner-images repository .\n\n\
  \n macos-latest migration begins June 15\n The macos-latest image label migration will begin June 15 and take 30 days to\
  \ complete. The macos-latest image label will point to the macOS 26 image instead of macOS 15. During the migration, users\
  \ should expect to see their workflows begin running on the macOS 26 image.\n\n\n To continue using macOS 15, you can target\
  \ the macos-15 label directly.\n\n\n For questions, or more information, head to the runner-images repository .\n\n\n\n\
  \ The post GitHub Actions: Upcoming image migrations appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
