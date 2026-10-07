---
layout: aux-update
title: GitHub / Copilot Stacked pull requests generally available official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Stacked pull requests generally available.
permalink: /updates/github/github/stacked-pull-requests-generally-available/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available
update_download_url: ''
update_version: Stacked pull requests generally available
update_logo_text: GIT
update_published_at: '2026-10-06T20:16:41Z'
update_last_checked: '2026-10-07T01:07:55Z'
source_last_checked: '2026-10-07T13:09:48Z'
official_body_last_checked: '2026-10-07T13:09:48Z'
record_last_updated: '2026-10-07T01:07:55Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Stacked pull requests generally available
update_detail_title: GitHub / Copilot Stacked pull requests generally available
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Stacked pull requests generally available has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Stacked pull requests generally available.
release_summary: "GitHub stacked pull requests are now generally available. Break large changes into smaller, focused pull\
  \ requests that you can review independently and merge together.\n\n\n Since the feature went into public preview , repositories\
  \ using stacks have seen a 9% increase in merged code compared to peers. Over two-thirds of the top 1% of repos now use\
  \ stacked pull requests and have seen a 5% improvement in time-to-merge.\n\n\n With this general availability release, we’re\
  \ introducing several improvements to make stacks easier to create, review, and merge. Thank you to everyone who provided\
  \ feedback and input during the preview period.\n\n\n More flexible merging and rebasing\n\n Approvals stay in place for\
  \ unchanged code. When an otherwise unchanged stack is updated after its base branch, such as main , moves ahead, Rebase\
  \ stack now preserves approvals, even in repositories that dismiss stale approvals.\n Rebased commits stay signed. GitHub\
  \ creates signed replacement commits during Rebase stack , preserving original authorship. Automatic rebases after partial\
  \ merges also sign replacement commits when branch rules require signatures or any original commit was signed.\n Bypass\
  \ permissions apply to stacks. Users with permission to bypass repository rules can now use those permissions to merge the\
  \ lowest unmerged pull request in a stack.\n More consistent stack merging. A stack now enters and lands through the merge\
  \ queue as a single merge group. When using the merge commit method, GitHub now creates one merge commit per pull request\
  \ instead of one for the entire merged group.\n Branching stacks retarget automatically. When a stack’s base branch is deleted,\
  \ GitHub automatically retargets the stack instead of closing its bottom pull request. This supports workflows where one\
  \ stack branches off another.\n Auto-merge for stacks rolling out over the next few weeks. Stacked pull requests can be\
  \ set to merge automatically once the repository’s merge requirements are met. Select a group of pull requests and they\
  \ will all merge together once all the pull requests are ready to merge.\n\n “It took one merge with GitHub’s Stacked PRs\
  \ for me to conclude that it’s amazing.”\n\n Charlie Marsh, Founder of Astral, OpenAI\n\n\n Stack navigation and automation\n\
  \n Stack context stays visible. Stack information is now always visible in the pull request page’s persistent header. View\
  \ details about the stack that a pull request belongs to from the pull requests list view.\n Keyboard shortcuts. Use Shift\
  \ + J and Shift + K shortcuts to navigate between pull requests in a stack.\n Stack membership lifecycle. View events in\
  \ the timeline for when a pull request was added or removed from a stack. The pull_request webhook now includes a stacked\
  \ action when a pull request joins a stack.\n CLI and agent workflows support more ways to work. The gh stack extension\
  \ for GitHub CLI now supports Git worktrees and includes several improvements to speed up initialization, checkout, and\
  \ navigation.\n\n “Seeing every branch in the stack right in the GitHub PR UI, checking each one’s status, and navigating\
  \ between them makes managing and reviewing many dependent PRs far easier. For a team reviewing each other’s work, that’s\
  \ been a meaningful improvement in how we collaborate.”\n\n David Mostoller, software engineer, Comcast\n\n\n Get started\n\
  \ Stacked pull requests are available on all github.com plans and will be included in an upcoming GitHub Enterprise Server\
  \ release.\n\n\n Check out the stacked pull requests documentation to learn more about the feature and how to get started.\n\
  \n\n\n The post Stacked pull requests generally available appeared first on The GitHub Blog ."
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
- at: '2026-10-06T20:16:41Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-07T01:08:06Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-07T01:07:55Z'
  url: https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-07T08:47:47Z'
  url: https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-07T13:09:48Z'
  url: https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub stacked pull requests are now generally available. Break large changes into smaller, focused\
  \ pull requests that you can review independently and merge together.\n\n\n Since the feature went into public preview ,\
  \ repositories using stacks have seen a 9% increase in merged code compared to peers. Over two-thirds of the top 1% of repos\
  \ now use stacked pull requests and have seen a 5% improvement in time-to-merge.\n\n\n With this general availability release,\
  \ we’re introducing several improvements to make stacks easier to create, review, and merge. Thank you to everyone who provided\
  \ feedback and input during the preview period.\n\n\n More flexible merging and rebasing\n\n Approvals stay in place for\
  \ unchanged code. When an otherwise unchanged stack is updated after its base branch, such as main , moves ahead, Rebase\
  \ stack now preserves approvals, even in repositories that dismiss stale approvals.\n Rebased commits stay signed. GitHub\
  \ creates signed replacement commits during Rebase stack , preserving original authorship. Automatic rebases after partial\
  \ merges also sign replacement commits when branch rules require signatures or any original commit was signed.\n Bypass\
  \ permissions apply to stacks. Users with permission to bypass repository rules can now use those permissions to merge the\
  \ lowest unmerged pull request in a stack.\n More consistent stack merging. A stack now enters and lands through the merge\
  \ queue as a single merge group. When using the merge commit method, GitHub now creates one merge commit per pull request\
  \ instead of one for the entire merged group.\n Branching stacks retarget automatically. When a stack’s base branch is deleted,\
  \ GitHub automatically retargets the stack instead of closing its bottom pull request. This supports workflows where one\
  \ stack branches off another.\n Auto-merge for stacks rolling out over the next few weeks. Stacked pull requests can be\
  \ set to merge automatically once the repository’s merge requirements are met. Select a group of pull requests and they\
  \ will all merge together once all the pull requests are ready to merge.\n\n “It took one merge with GitHub’s Stacked PRs\
  \ for me to conclude that it’s amazing.”\n\n Charlie Marsh, Founder of Astral, OpenAI\n\n\n Stack navigation and automation\n\
  \n Stack context stays visible. Stack information is now always visible in the pull request page’s persistent header. View\
  \ details about the stack that a pull request belongs to from the pull requests list view.\n Keyboard shortcuts. Use Shift\
  \ + J and Shift + K shortcuts to navigate between pull requests in a stack.\n Stack membership lifecycle. View events in\
  \ the timeline for when a pull request was added or removed from a stack. The pull_request webhook now includes a stacked\
  \ action when a pull request joins a stack.\n CLI and agent workflows support more ways to work. The gh stack extension\
  \ for GitHub CLI now supports Git worktrees and includes several improvements to speed up initialization, checkout, and\
  \ navigation.\n\n “Seeing every branch in the stack right in the GitHub PR UI, checking each one’s status, and navigating\
  \ between them makes managing and reviewing many dependent PRs far easier. For a team reviewing each other’s work, that’s\
  \ been a meaningful improvement in how we collaborate.”\n\n David Mostoller, software engineer, Comcast\n\n\n Get started\n\
  \ Stacked pull requests are available on all github.com plans and will be included in an upcoming GitHub Enterprise Server\
  \ release.\n\n\n Check out the stacked pull requests documentation to learn more about the feature and how to get started.\n\
  \n\n\n The post Stacked pull requests generally available appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
