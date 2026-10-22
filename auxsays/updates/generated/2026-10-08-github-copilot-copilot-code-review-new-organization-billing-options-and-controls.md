---
layout: aux-update
title: 'GitHub / Copilot Copilot code review: New organization billing options and controls official update breakdown'
description: 'Official GitHub / Copilot update record captured from GitHub for Copilot code review: New organization billing
  options and controls.'
permalink: /updates/github/github/copilot-code-review-new-organization-billing-options-and-controls/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-08-copilot-code-review-new-organization-billing-options-and-controls
update_download_url: ''
update_version: 'Copilot code review: New organization billing options and controls'
update_logo_text: GIT
update_published_at: '2026-10-08T19:43:05Z'
update_last_checked: '2026-10-10T08:25:46Z'
source_last_checked: '2026-10-10T08:25:46Z'
official_body_last_checked: '2026-10-10T08:25:46Z'
record_last_updated: '2026-10-10T08:25:46Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot Copilot code review: New organization billing options and controls'
update_detail_title: 'GitHub / Copilot Copilot code review: New organization billing options and controls'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot Copilot code review: New organization billing options and controls has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot Copilot code review: New organization billing options and controls.'
release_summary: "This release adds new billing and license controls for Copilot code review admins:\n\n\n\n Billing: Organization\
  \ owners can bill Copilot code reviews from members with a Copilot license to the organization’s cost center instead of\
  \ using up those members’ Copilot quotas.\n Review request controls: Organization owners and repository admins can control\
  \ whether people with external licenses can request a review.\n\n \U0001F4B3 Choose how members with a Copilot license are\
  \ billed\n By default, Copilot code review bills requests associated with members who have a Copilot license to that member’s\
  \ own Copilot entitlement. Organization owners can now choose to bill the organization that owns the repository instead\
  \ in order to avoid consuming or exhausting member quotas.\n\n\n The Choose how members with a Copilot license are billed\
  \ setting has two options:\n\n\n\n Member (default): Bills the member’s own Copilot entitlement. If the member’s quota is\
  \ exhausted, the code review fails.\n Organization : Bills the organization that owns the repository. This requires AI Credits\
  \ paid usage to be enabled for the organization, and you can optionally set a budget.\n\n You can find the setting in your\
  \ organization settings, under Copilot -> Policies .\n\n\n \U0001F512 Control who can request a review\n By default, anyone\
  \ with a paid Copilot license can use it to request a review from Copilot in the repositories they have access to. Organization\
  \ owners and repository admins can now, if desired, turn on the Only allow Copilot code review to be triggered by authorized\
  \ users setting to require that review requests come from people with a Copilot license provided by your organization or\
  \ enterprise. When it’s on, people can’t use a Copilot license from outside your organization or enterprise (e.g., a personal\
  \ license) to request a review. If you turn it on at the organization level, repository admins can’t turn it off.\n\n\n\
  \ For details on how the setting applies to personal repositories, automatic reviews, and API requests, see Reviews requested\
  \ with an external Copilot license .\n\n\n\n The post Copilot code review: New organization billing options and controls\
  \ appeared first on The GitHub Blog ."
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
- at: '2026-10-08T19:43:05Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-10T08:25:55Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-08-copilot-code-review-new-organization-billing-options-and-controls
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-10T08:25:46Z'
  url: https://github.blog/changelog/2026-10-08-copilot-code-review-new-organization-billing-options-and-controls
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "This release adds new billing and license controls for Copilot code review admins:\n\n\n\n Billing:\
  \ Organization owners can bill Copilot code reviews from members with a Copilot license to the organization’s cost center\
  \ instead of using up those members’ Copilot quotas.\n Review request controls: Organization owners and repository admins\
  \ can control whether people with external licenses can request a review.\n\n \U0001F4B3 Choose how members with a Copilot\
  \ license are billed\n By default, Copilot code review bills requests associated with members who have a Copilot license\
  \ to that member’s own Copilot entitlement. Organization owners can now choose to bill the organization that owns the repository\
  \ instead in order to avoid consuming or exhausting member quotas.\n\n\n The Choose how members with a Copilot license are\
  \ billed setting has two options:\n\n\n\n Member (default): Bills the member’s own Copilot entitlement. If the member’s\
  \ quota is exhausted, the code review fails.\n Organization : Bills the organization that owns the repository. This requires\
  \ AI Credits paid usage to be enabled for the organization, and you can optionally set a budget.\n\n You can find the setting\
  \ in your organization settings, under Copilot -> Policies .\n\n\n \U0001F512 Control who can request a review\n By default,\
  \ anyone with a paid Copilot license can use it to request a review from Copilot in the repositories they have access to.\
  \ Organization owners and repository admins can now, if desired, turn on the Only allow Copilot code review to be triggered\
  \ by authorized users setting to require that review requests come from people with a Copilot license provided by your organization\
  \ or enterprise. When it’s on, people can’t use a Copilot license from outside your organization or enterprise (e.g., a\
  \ personal license) to request a review. If you turn it on at the organization level, repository admins can’t turn it off.\n\
  \n\n For details on how the setting applies to personal repositories, automatic reviews, and API requests, see Reviews requested\
  \ with an external Copilot license .\n\n\n\n The post Copilot code review: New organization billing options and controls\
  \ appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
