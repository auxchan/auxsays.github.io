---
layout: aux-update
title: GitHub / Copilot Reference same-repository actions with self-repository syntax official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/reference-same-repository-actions-with-self-repository-syntax/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax
update_download_url: ''
update_version: Reference same-repository actions with self-repository syntax
update_logo_text: GIT
update_published_at: '2026-07-30T17:39:46Z'
update_last_checked: '2026-07-31T06:49:35Z'
source_last_checked: '2026-07-31T06:49:35Z'
official_body_last_checked: '2026-07-31T06:49:35Z'
record_last_updated: '2026-07-31T06:49:35Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Reference same-repository actions with self-repository syntax
update_detail_title: GitHub / Copilot Reference same-repository actions with self-repository syntax
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Reference same-repository actions with self-repository syntax has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Reference same-repository actions with self-repository syntax.
release_summary: "You can now reference an action or reusable workflow that lives in the same repository using the new self-repository\
  \ syntax. A uses: value that starts with $/ resolves to your workflow’s own repository at the exact commit that is running,\
  \ with no checkout required. It works everywhere the workspace-relative ./ syntax works, including workflow steps, composite\
  \ action steps, nested composition, and reusable workflow calls.\n\n\n Before this, referencing an action defined in your\
  \ own repository meant either relying on ./ and a checkout, or hardcoding a version. This was a maintenance burden and quietly\
  \ defeated commit SHA pinning. With self-repository references, sibling actions and workflows automatically match the ref\
  \ you are already running, so your internal references stay consistent even when callers pin to a full-length commit SHA.\
  \ This also makes it possible to adopt the enterprise policy that requires actions to be pinned to a full-length commit\
  \ SHA for workflows that call their own actions.\n\n\n Self-repository references are now the recommended way to compose\
  \ actions and reusable workflows within a repository. They are available on github.com. This feature requires the GitHub\
  \ Actions runner to be on version 2.336.0 or newer.\n\n\n Learn more by checking out our docs about finding and customizing\
  \ actions , or join the discussion within GitHub Community .\n\n\n\n The post Reference same-repository actions with self-repository\
  \ syntax appeared first on The GitHub Blog ."
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
- at: '2026-07-30T17:39:46Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-31T06:49:44Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-31T06:49:35Z'
  url: https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now reference an action or reusable workflow that lives in the same repository using the\
  \ new self-repository syntax. A uses: value that starts with $/ resolves to your workflow’s own repository at the exact\
  \ commit that is running, with no checkout required. It works everywhere the workspace-relative ./ syntax works, including\
  \ workflow steps, composite action steps, nested composition, and reusable workflow calls.\n\n\n Before this, referencing\
  \ an action defined in your own repository meant either relying on ./ and a checkout, or hardcoding a version. This was\
  \ a maintenance burden and quietly defeated commit SHA pinning. With self-repository references, sibling actions and workflows\
  \ automatically match the ref you are already running, so your internal references stay consistent even when callers pin\
  \ to a full-length commit SHA. This also makes it possible to adopt the enterprise policy that requires actions to be pinned\
  \ to a full-length commit SHA for workflows that call their own actions.\n\n\n Self-repository references are now the recommended\
  \ way to compose actions and reusable workflows within a repository. They are available on github.com. This feature requires\
  \ the GitHub Actions runner to be on version 2.336.0 or newer.\n\n\n Learn more by checking out our docs about finding and\
  \ customizing actions , or join the discussion within GitHub Community .\n\n\n\n The post Reference same-repository actions\
  \ with self-repository syntax appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
