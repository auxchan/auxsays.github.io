---
layout: aux-update
title: GitHub / Copilot Safer pull_request_target defaults for GitHub Actions checkout official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/safer-pull-request-target-defaults-for-github-actions-checkout/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-18-safer-pull_request_target-defaults-for-github-actions-checkout
update_download_url: ''
update_version: Safer pull_request_target defaults for GitHub Actions checkout
update_logo_text: GIT
update_published_at: '2026-06-18T14:06:55Z'
update_last_checked: '2026-06-18T15:55:12Z'
source_last_checked: '2026-06-18T15:55:12Z'
official_body_last_checked: '2026-06-18T15:55:12Z'
record_last_updated: '2026-06-18T15:55:12Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Safer pull_request_target defaults for GitHub Actions checkout
update_detail_title: GitHub / Copilot Safer pull_request_target defaults for GitHub Actions checkout
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Safer pull_request_target defaults for GitHub Actions checkout has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Safer pull_request_target defaults for GitHub Actions checkout.
release_summary: "The pull_request_target event is one of the most commonly misused triggers in GitHub Actions, leading to\
  \ vulnerabilities in workflows. Workflows triggered by pull_request_target run with the base repository’s GITHUB_TOKEN ,\
  \ secrets, and default-branch cache access. Checking out the head of an unreviewed pull request from a fork inside one of\
  \ these workflows typically lets attacker-controlled code execute with the workflow’s full privileges. This pattern is known\
  \ as a “pwn request,” and it has been the root cause of multiple supply-chain incidents across the ecosystem. For more information,\
  \ see our blog posts about helping to prevent these requests .\n\n\n Starting today, actions/checkout v7 is generally available\
  \ and refuses common pwn request patterns by default.\n\n\n On July 16, 2026, we’ll backport the enforcement to all currently\
  \ supported major versions. Workflows pinned to a floating major tag (e.g., actions/checkout@v4 ) will automatically pick\
  \ up the change. Workflows pinned to a specific SHA, minor, or patch version aren’t affected by the backport and will need\
  \ to upgrade using Dependabot or through established upgrade processes.\n\n\n Same-repository pull requests aren’t affected,\
  \ and the pull_request event is unchanged.\n\n\n What’s changing\n actions/checkout v7 refuses to fetch fork pull request\
  \ code in pull_request_target and workflow_run workflows (the latter only when workflow_run.event is a pull_request* event).\
  \ It refuses when the pull request is from a fork and any of the following apply:\n\n\n\n repository: resolves to the fork\
  \ pull request’s repository.\n ref: matches refs/pull//head or refs/pull//merge .\n ref: resolves to a fork pull request’s\
  \ head or merge commit SHA.\n\n This change is focused on preventing the most common form of pwn requests in the Actions\
  \ ecosystem. actions/checkout will now fail for usage in pull_request_target events from forks with insecure inputs such\
  \ as:\n\n\n\n ref: refs/pull/${{ github.event.pull_request.number }}/merge\n ref: ${{ github.event.pull_request.head.sha\
  \ }}\n repository: ${{ github.event.pull_request.head.repo.full_name }}\n\n What’s not changing or covered\n Pwn requests\
  \ can be introduced in other ways outside of the scope of this change. For example, a run block uses git or the gh CLI to\
  \ pull a HEAD ref or other untrusted source that is subsequently executed. Additionally, pwn requests triggered in other\
  \ event types besides pull_request_target (such as issue_comment ) will not be blocked by this change. Further hardening\
  \ of additional events may be explored in future releases.\n\n\n This change only blocks checkouts of the fork pull request\
  \ head and merge commits. It does not block checkouts of other untrusted repositories. For example, setting repository:\
  \ to an unrelated third-party repository is not blocked. Checking out and executing any untrusted code in a privileged event\
  \ remains a pwn request risk that should be reviewed.\n\n\n Opting out of this protection\n Some workflows need to check\
  \ out fork pull request code with elevated trust, and this is why pull_request_target was created in the first place. For\
  \ example, generating coverage reports that require a private artifact registry or producing and running authenticated checks\
  \ against the changes introduced from the pull request. We’re keeping an opt-out available so these workflows can continue\
  \ to function, but you should treat opting out as a deliberate security decision.\n\n\n Before you opt out, read our guidance\
  \ for securely using pull_request_target . After confirming the event is needed and safely used in your workflow, you can\
  \ opt out of this protection by adding the allow-unsafe-pr-checkout input on the actions/checkout step. The flag is intentionally\
  \ named to be easy to spot in code review and static analysis.\n\n\n Read more and give your feedback\n For more details,\
  \ see the actions/checkout repository , the GitHub Actions documentation on pull_request_target , and the security hardening\
  \ guidance for GitHub Actions .\n\n\n\n The post Safer pull_request_target defaults for GitHub Actions checkout appeared\
  \ first on The GitHub Blog ."
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
- at: '2026-06-18T14:06:55Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-18T15:55:13Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-18-safer-pull_request_target-defaults-for-github-actions-checkout
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-18T15:55:12Z'
  url: https://github.blog/changelog/2026-06-18-safer-pull_request_target-defaults-for-github-actions-checkout
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The pull_request_target event is one of the most commonly misused triggers in GitHub Actions,\
  \ leading to vulnerabilities in workflows. Workflows triggered by pull_request_target run with the base repository’s GITHUB_TOKEN\
  \ , secrets, and default-branch cache access. Checking out the head of an unreviewed pull request from a fork inside one\
  \ of these workflows typically lets attacker-controlled code execute with the workflow’s full privileges. This pattern is\
  \ known as a “pwn request,” and it has been the root cause of multiple supply-chain incidents across the ecosystem. For\
  \ more information, see our blog posts about helping to prevent these requests .\n\n\n Starting today, actions/checkout\
  \ v7 is generally available and refuses common pwn request patterns by default.\n\n\n On July 16, 2026, we’ll backport the\
  \ enforcement to all currently supported major versions. Workflows pinned to a floating major tag (e.g., actions/checkout@v4\
  \ ) will automatically pick up the change. Workflows pinned to a specific SHA, minor, or patch version aren’t affected by\
  \ the backport and will need to upgrade using Dependabot or through established upgrade processes.\n\n\n Same-repository\
  \ pull requests aren’t affected, and the pull_request event is unchanged.\n\n\n What’s changing\n actions/checkout v7 refuses\
  \ to fetch fork pull request code in pull_request_target and workflow_run workflows (the latter only when workflow_run.event\
  \ is a pull_request* event). It refuses when the pull request is from a fork and any of the following apply:\n\n\n\n repository:\
  \ resolves to the fork pull request’s repository.\n ref: matches refs/pull//head or refs/pull//merge .\n ref: resolves to\
  \ a fork pull request’s head or merge commit SHA.\n\n This change is focused on preventing the most common form of pwn requests\
  \ in the Actions ecosystem. actions/checkout will now fail for usage in pull_request_target events from forks with insecure\
  \ inputs such as:\n\n\n\n ref: refs/pull/${{ github.event.pull_request.number }}/merge\n ref: ${{ github.event.pull_request.head.sha\
  \ }}\n repository: ${{ github.event.pull_request.head.repo.full_name }}\n\n What’s not changing or covered\n Pwn requests\
  \ can be introduced in other ways outside of the scope of this change. For example, a run block uses git or the gh CLI to\
  \ pull a HEAD ref or other untrusted source that is subsequently executed. Additionally, pwn requests triggered in other\
  \ event types besides pull_request_target (such as issue_comment ) will not be blocked by this change. Further hardening\
  \ of additional events may be explored in future releases.\n\n\n This change only blocks checkouts of the fork pull request\
  \ head and merge commits. It does not block checkouts of other untrusted repositories. For example, setting repository:\
  \ to an unrelated third-party repository is not blocked. Checking out and executing any untrusted code in a privileged event\
  \ remains a pwn request risk that should be reviewed.\n\n\n Opting out of this protection\n Some workflows need to check\
  \ out fork pull request code with elevated trust, and this is why pull_request_target was created in the first place. For\
  \ example, generating coverage reports that require a private artifact registry or producing and running authenticated checks\
  \ against the changes introduced from the pull request. We’re keeping an opt-out available so these workflows can continue\
  \ to function, but you should treat opting out as a deliberate security decision.\n\n\n Before you opt out, read our guidance\
  \ for securely using pull_request_target . After confirming the event is needed and safely used in your workflow, you can\
  \ opt out of this protection by adding the allow-unsafe-pr-checkout input on the actions/checkout step. The flag is intentionally\
  \ named to be easy to spot in code review and static analysis.\n\n\n Read more and give your feedback\n For more details,\
  \ see the actions/checkout repository , the GitHub Actions documentation on pull_request_target , and the security hardening\
  \ guidance for GitHub Actions .\n\n\n\n The post Safer pull_request_target defaults for GitHub Actions checkout appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
