---
layout: aux-update
title: GitHub / Copilot GitHub Actions workflow lockfiles in public preview official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for GitHub Actions workflow lockfiles in public
  preview.
permalink: /updates/github/github/github-actions-workflow-lockfiles-in-public-preview/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-14-github-actions-workflow-lockfiles-in-public-preview
update_download_url: ''
update_version: GitHub Actions workflow lockfiles in public preview
update_logo_text: GIT
update_published_at: '2026-10-14T13:49:15Z'
update_last_checked: '2026-10-14T14:31:10Z'
source_last_checked: '2026-10-14T19:51:40Z'
official_body_last_checked: '2026-10-14T19:51:40Z'
record_last_updated: '2026-10-14T19:51:40Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub Actions workflow lockfiles in public preview
update_detail_title: GitHub / Copilot GitHub Actions workflow lockfiles in public preview
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub Actions workflow lockfiles in public preview has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub Actions workflow lockfiles in public preview.
release_summary: "GitHub Actions workflow dependency lockfiles are now in public preview for GitHub Enterprise Cloud and GitHub\
  \ Enterprise Cloud with data residency. Tags and branches can move after you review a workflow, so a later run might execute\
  \ different code. Lockfiles let you keep those references in your workflow while running the exact commits you locked.\n\
  \n\n If an action is compromised, a moved tag or branch can introduce malicious code into your workflow without a change\
  \ to your repository. Lockfiles help protect against unexpected dependency changes by keeping workflow runs tied to the\
  \ commits you locked. Locking does not determine whether the dependency itself is safe, so review dependencies before locking\
  \ them.\n\n\n Install the gh actions-lock extension for the GitHub CLI to create and maintain your workflow lockfile. With\
  \ the extension, you can:\n\n\n\n Pin your dependencies: Generate .github/workflows/actions.lock with reviewable commits\
  \ for actions and their transitive dependencies, as well as reusable workflow dependencies.\n Adopt locking gradually: Onboard\
  \ workflows individually. Once onboarded, a workflow must have lockfile entries for its dependencies, and GitHub Actions\
  \ runs the recorded commits.\n Keep workflow runs consistent: GitHub Actions requires each dependency of an onboarded workflow\
  \ to be in the lockfile and uses its recorded commit, even if a tag or branch moves.\n Check for stale lockfiles: Verify\
  \ that the lockfile is up to date without modifying files, including in a CI check.\n\n The Require lockfile policy is also\
  \ available in public preview. Enterprise, organization, and repository administrators can require workflows to use lockfiles\
  \ across their enterprise, organization, or repository.\n\n\n Keep locked dependencies up to date with Dependabot\n Dependabot\
  \ helps you keep your GitHub Actions dependencies up to date. When it opens a version update for an action in a workflow\
  \ that is already onboarded, it also regenerates the matching lockfile entry in the same pull request, keeping the updated\
  \ workflow reference and its locked commit in sync without additional configuration. Read more about Dependabot updates\
  \ for actions .\n\n\n Get started\n To get started, install the extension from the public gh-actions-lock repository , then\
  \ review and commit the generated lockfile and workflow changes.\n\n\n For more details and links to setup instructions,\
  \ see workflow dependency lockfiles in GitHub Docs.\n\n\n Share feedback in the existing community discussion or open an\
  \ issue in the gh-actions-lock repository .\n\n\n Thank you to the community members who helped shape this preview through\
  \ testing and feedback, with special thanks to Andrew Nesbitt, François Proulx, Jesse Houwing, and William Woodruff for\
  \ their close collaboration and iteration on this solution over the past year.\n\n\n\n The post GitHub Actions workflow\
  \ lockfiles in public preview appeared first on The GitHub Blog ."
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
- at: '2026-10-14T13:49:15Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-14T14:31:19Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-14-github-actions-workflow-lockfiles-in-public-preview
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-14T14:31:10Z'
  url: https://github.blog/changelog/2026-10-14-github-actions-workflow-lockfiles-in-public-preview
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-14T19:51:40Z'
  url: https://github.blog/changelog/2026-10-14-github-actions-workflow-lockfiles-in-public-preview
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub Actions workflow dependency lockfiles are now in public preview for GitHub Enterprise Cloud,\
  \ GitHub Enterprise Cloud with data residency, Team, and Free plans. Tags and branches can move after you review a workflow,\
  \ so a later run might execute different code. Lockfiles let you keep those references in your workflow while running the\
  \ exact commits you locked.\n\n\n Editor’s note (October 14th, 2026): Updated which plans have access to this public preview.\n\
  \n\n If an action is compromised, a moved tag or branch can introduce malicious code into your workflow without a change\
  \ to your repository. Lockfiles help protect against unexpected dependency changes by keeping workflow runs tied to the\
  \ commits you locked. Locking does not determine whether the dependency itself is safe, so review dependencies before locking\
  \ them.\n\n\n Install the gh actions-lock extension for the GitHub CLI to create and maintain your workflow lockfile. With\
  \ the extension, you can:\n\n\n\n Pin your dependencies: Generate .github/workflows/actions.lock with reviewable commits\
  \ for actions and their transitive dependencies, as well as reusable workflow dependencies.\n Adopt locking gradually: Onboard\
  \ workflows individually. Once onboarded, a workflow must have lockfile entries for its dependencies, and GitHub Actions\
  \ runs the recorded commits.\n Keep workflow runs consistent: GitHub Actions requires each dependency of an onboarded workflow\
  \ to be in the lockfile and uses its recorded commit, even if a tag or branch moves.\n Check for stale lockfiles: Verify\
  \ that the lockfile is up to date without modifying files, including in a CI check.\n\n The Require lockfile policy is also\
  \ available in public preview. Enterprise, organization, and repository administrators can require workflows to use lockfiles\
  \ across their enterprise, organization, or repository.\n\n\n Keep locked dependencies up to date with Dependabot\n Dependabot\
  \ helps you keep your GitHub Actions dependencies up to date. When it opens a version update for an action in a workflow\
  \ that is already onboarded, it also regenerates the matching lockfile entry in the same pull request, keeping the updated\
  \ workflow reference and its locked commit in sync without additional configuration. Read more about Dependabot updates\
  \ for actions .\n\n\n Get started\n To get started, install the extension from the public gh-actions-lock repository , then\
  \ review and commit the generated lockfile and workflow changes.\n\n\n For more details and links to setup instructions,\
  \ see workflow dependency lockfiles in GitHub Docs.\n\n\n Share feedback in the existing community discussion or open an\
  \ issue in the gh-actions-lock repository .\n\n\n Thank you to the community members who helped shape this preview through\
  \ testing and feedback, with special thanks to Andrew Nesbitt, François Proulx, Jesse Houwing, and William Woodruff for\
  \ their close collaboration and iteration on this solution over the past year.\n\n\n\n The post GitHub Actions workflow\
  \ lockfiles in public preview appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
