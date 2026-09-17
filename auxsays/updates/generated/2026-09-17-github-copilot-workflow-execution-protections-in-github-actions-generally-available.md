---
layout: aux-update
title: GitHub / Copilot Workflow execution protections in GitHub Actions generally available official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Workflow execution protections in GitHub Actions
  generally available.
permalink: /updates/github/github/workflow-execution-protections-in-github-actions-generally-available/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-17-workflow-execution-protections-in-github-actions-generally-available
update_download_url: ''
update_version: Workflow execution protections in GitHub Actions generally available
update_logo_text: GIT
update_published_at: '2026-09-17T15:45:26Z'
update_last_checked: '2026-09-17T19:17:40Z'
source_last_checked: '2026-09-17T19:17:40Z'
official_body_last_checked: '2026-09-17T19:17:40Z'
record_last_updated: '2026-09-17T19:17:40Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Workflow execution protections in GitHub Actions generally available
update_detail_title: GitHub / Copilot Workflow execution protections in GitHub Actions generally available
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Workflow execution protections in GitHub Actions generally available has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Workflow execution protections in GitHub Actions generally available.
release_summary: "Workflow execution protections for GitHub Actions, previously in public preview, are now generally available\
  \ for GitHub Enterprise, organizations, and repositories.\n\n\n Execution protections let you define an allowlist that controls\
  \ who can trigger an Actions workflow and what events can start it. Actor rules cover the who, event rules cover the what,\
  \ and actions evaluate both before a run.\n\n\n What’s new\n Alongside the actor and event rules you’ve used in public preview,\
  \ general availability adds:\n\n\n\n Workflow file targeting: Scope execution protection rules to specific workflow files\
  \ rather than an entire repository, so a single repository can apply different policies to different workflows. For example,\
  \ restrict deploy.yml to a designated team while leaving CI workflows open to all contributors.\n Insights: See how actions\
  \ evaluate and enforce your rules across your enterprise, organization, and repositories. This enables you to audit policy\
  \ impact and tune rules both before and after you enforce them.\n REST API: Manage execution protections programmatically\
  \ at the enterprise, organization, and repository level. Create, read, update, and delete rules — including workflow path\
  \ conditions — so you can manage Actions policy as code, keep rules consistent across hundreds of repositories, and wire\
  \ enforcement into your existing governance tooling instead of clicking through settings.\n\n Evaluate mode also carries\
  \ over from the preview, so you can run rules in shadow mode and see which workflow runs would be blocked before you enforce\
  \ them.\n\n\n New secure defaults\n Vulnerabilities in pull_request_target workflows, such as Pwn Requests , are one of\
  \ the most commonly exploited vulnerabilities in action workflows. pull_request_target runs with access to your secrets\
  \ in the context of the base repository, so if code is executed from a fork, that untrusted code could poison your pipeline\
  \ and exfiltrate secrets. We’re rolling out a default protection rule to limit the execution of pull_request_target events.\n\
  \n\n For public repositories that do not already have an applicable event policy, GitHub is introducing a default rule that\
  \ disables pull_request_target . This default does not apply to private or internal repositories. It initially runs in evaluate\
  \ mode, so you can see which workflow runs would be affected before enforcement begins.\n\n\n On November 2, 2026, we’ll\
  \ automatically enforce the default rule for affected repositories that were using the default pull_request_target policy\
  \ before general availability.\n\n\n To prepare for the roll out of this rule, you can view the results of the evaluate\
  \ rule using Insights and see which workflow runs will fail once enforcement begins.\n\n\n From there you have two options:\
  \ leave the rule in place to block pull_request_target , or explicitly allow pull_request_target in an applicable Actions\
  \ event policy if your workflows still depend on the trigger. Specific workflows can be allow-listed using the new workflow\
  \ file targeting.\n\n\n To get started, see About Actions policies , Control workflow execution , and the Actions policies\
  \ REST API reference .\n\n\n\n The post Workflow execution protections in GitHub Actions generally available appeared first\
  \ on The GitHub Blog ."
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
- at: '2026-09-17T15:45:26Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-17T19:18:00Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-17-workflow-execution-protections-in-github-actions-generally-available
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-17T19:17:40Z'
  url: https://github.blog/changelog/2026-09-17-workflow-execution-protections-in-github-actions-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Workflow execution protections for GitHub Actions, previously in public preview, are now generally\
  \ available for GitHub Enterprise, organizations, and repositories.\n\n\n Execution protections let you define an allowlist\
  \ that controls who can trigger an Actions workflow and what events can start it. Actor rules cover the who, event rules\
  \ cover the what, and actions evaluate both before a run.\n\n\n What’s new\n Alongside the actor and event rules you’ve\
  \ used in public preview, general availability adds:\n\n\n\n Workflow file targeting: Scope execution protection rules to\
  \ specific workflow files rather than an entire repository, so a single repository can apply different policies to different\
  \ workflows. For example, restrict deploy.yml to a designated team while leaving CI workflows open to all contributors.\n\
  \ Insights: See how actions evaluate and enforce your rules across your enterprise, organization, and repositories. This\
  \ enables you to audit policy impact and tune rules both before and after you enforce them.\n REST API: Manage execution\
  \ protections programmatically at the enterprise, organization, and repository level. Create, read, update, and delete rules\
  \ — including workflow path conditions — so you can manage Actions policy as code, keep rules consistent across hundreds\
  \ of repositories, and wire enforcement into your existing governance tooling instead of clicking through settings.\n\n\
  \ Evaluate mode also carries over from the preview, so you can run rules in shadow mode and see which workflow runs would\
  \ be blocked before you enforce them.\n\n\n New secure defaults\n Vulnerabilities in pull_request_target workflows, such\
  \ as Pwn Requests , are one of the most commonly exploited vulnerabilities in action workflows. pull_request_target runs\
  \ with access to your secrets in the context of the base repository, so if code is executed from a fork, that untrusted\
  \ code could poison your pipeline and exfiltrate secrets. We’re rolling out a default protection rule to limit the execution\
  \ of pull_request_target events.\n\n\n For public repositories that do not already have an applicable event policy, GitHub\
  \ is introducing a default rule that disables pull_request_target . This default does not apply to private or internal repositories.\
  \ It initially runs in evaluate mode, so you can see which workflow runs would be affected before enforcement begins.\n\n\
  \n On November 2, 2026, we’ll automatically enforce the default rule for affected repositories that were using the default\
  \ pull_request_target policy before general availability.\n\n\n To prepare for the roll out of this rule, you can view the\
  \ results of the evaluate rule using Insights and see which workflow runs will fail once enforcement begins.\n\n\n From\
  \ there you have two options: leave the rule in place to block pull_request_target , or explicitly allow pull_request_target\
  \ in an applicable Actions event policy if your workflows still depend on the trigger. Specific workflows can be allow-listed\
  \ using the new workflow file targeting.\n\n\n To get started, see About Actions policies , Control workflow execution ,\
  \ and the Actions policies REST API reference .\n\n\n\n The post Workflow execution protections in GitHub Actions generally\
  \ available appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
