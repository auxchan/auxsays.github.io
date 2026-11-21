---
layout: aux-update
title: GitHub / Copilot Wait for pull request events with GitHub CLI official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Wait for pull request events with GitHub CLI.
permalink: /updates/github/github/wait-for-pull-request-events-with-github-cli/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-18-wait-for-pull-request-events-with-github-cli
update_download_url: ''
update_version: Wait for pull request events with GitHub CLI
update_logo_text: GIT
update_published_at: '2026-11-19T00:00:13Z'
update_last_checked: '2026-11-19T10:06:11Z'
source_last_checked: '2026-11-19T23:18:32Z'
official_body_last_checked: '2026-11-19T23:18:32Z'
record_last_updated: '2026-11-19T10:06:11Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Wait for pull request events with GitHub CLI
update_detail_title: GitHub / Copilot Wait for pull request events with GitHub CLI
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Wait for pull request events with GitHub CLI has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Wait for pull request events with GitHub CLI.
release_summary: "GitHub CLI now supports GitHub Event Streams . With gh v2.105.0 , you and your agents can wait for a pull\
  \ request to change with a single command instead of polling it in a loop.\n\n\n Run gh event listen with a pull request\
  \ URL and the events you care about, such as a submitted review. It creates the subscription, opens the stream and prints\
  \ each event as a line of JSON.\n\n\n\n By default, it exits after the first event, so it slots into scripts and agent loops.\n\
  \ Use --count to wait for several events, --follow to keep listening, and --timeout to stop waiting.\n Use --jq or --template\
  \ to pull out just the fields you need.\n\n You can wait for submitted reviews, pull request state and head changes, merge\
  \ conflicts and completed check suites. To manage subscriptions directly, use gh event subscription create , list , view\
  \ , and delete .\n\n\n Agents discover the new commands on their own: gh pr create , gh pr view , gh run view , gh run watch\
  \ , and gh api now suggest gh event listen instead of polling.\n\n\n Availability\n The gh event commands are in preview\
  \ and may change. They require access to Event Streams, which is in preview on GitHub.com. To get access, sign up for the\
  \ Event Streams waitlist .\n\n\n To get started, upgrade to gh v2.105.0 or later. For details, see the gh event manual and\
  \ the Event Streams documentation , or run gh event --help .\n\n\n Share your feedback in the GitHub Community discussion\
  \ .\n\n\n\n The post Wait for pull request events with GitHub CLI appeared first on The GitHub Blog ."
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
- at: '2026-11-19T00:00:13Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-19T10:06:23Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-18-wait-for-pull-request-events-with-github-cli
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-19T10:06:11Z'
  url: https://github.blog/changelog/2026-11-18-wait-for-pull-request-events-with-github-cli
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-19T23:18:32Z'
  url: https://github.blog/changelog/2026-11-18-wait-for-pull-request-events-with-github-cli
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub CLI now supports GitHub Event Streams . With gh v2.105.0 , you and your agents can wait\
  \ for a pull request to change with a single command instead of polling it in a loop.\n\n\n Run gh event listen with a pull\
  \ request URL and the events you care about, such as a submitted review. It creates the subscription, opens the stream and\
  \ prints each event as a line of JSON.\n\n\n\n By default, it exits after the first event, so it slots into scripts and\
  \ agent loops.\n Use --count to wait for several events, --follow to keep listening, and --timeout to stop waiting.\n Use\
  \ --jq or --template to pull out just the fields you need.\n\n You can wait for submitted reviews, pull request state and\
  \ head changes, merge conflicts and completed check suites. To manage subscriptions directly, use gh event subscription\
  \ create , list , view , and delete .\n\n\n Agents discover the new commands on their own: gh pr create , gh pr view , gh\
  \ run view , gh run watch , and gh api now suggest gh event listen instead of polling.\n\n\n Availability\n The gh event\
  \ commands are in preview and may change. They require access to Event Streams, which is in preview on GitHub.com. To get\
  \ access, sign up for the Event Streams waitlist .\n\n\n To get started, upgrade to gh v2.105.0 or later. For details, see\
  \ the gh event manual and the Event Streams documentation , or run gh event --help .\n\n\n Share your feedback in the GitHub\
  \ Community discussion .\n\n\n\n The post Wait for pull request events with GitHub CLI appeared first on The GitHub Blog\
  \ ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
