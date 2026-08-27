---
layout: aux-update
title: GitHub / Copilot Global model policy generally available official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Global model policy generally available.
permalink: /updates/github/github/global-model-policy-generally-available/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-26-global-model-policy-generally-available
update_download_url: ''
update_version: Global model policy generally available
update_logo_text: GIT
update_published_at: '2026-08-26T22:08:38Z'
update_last_checked: '2026-08-27T11:00:51Z'
source_last_checked: '2026-08-27T23:27:08Z'
official_body_last_checked: '2026-08-27T23:27:08Z'
record_last_updated: '2026-08-27T11:00:51Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Global model policy generally available
update_detail_title: GitHub / Copilot Global model policy generally available
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Global model policy generally available has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Global model policy generally available.
release_summary: "In July, we announced a default model policy for generally available GitHub Copilot models on Copilot Business\
  \ and Copilot Enterprise plans. Starting today, we’re gradually rolling out enforcement of the policy through September\
  \ 1, so it will take effect at different times for different enterprises. Previously unconfigured and new generally available\
  \ models will inherit the global policy state. Administrators can make durable decisions for individual models at their\
  \ discretion. Open-weight models and any models that require data retention are disabled by default.\n\n\n What’s changing\n\
  \ Once the policy takes effect for your organization or enterprise:\n\n\n\n Models you haven’t previously configured will\
  \ change their state to “Delegate to default policy”, and they’ll begin following your policy setting. If your policy is\
  \ enabled — which is the default — those models will become available to your users.\n “Delegate to default policy” is a\
  \ live, dynamic state that always tracks your policy. You can change the policy at any time, and all applicable models follow\
  \ that state change.\n We always preserve explicit choices. If you’ve deliberately enabled or disabled a specific model,\
  \ we do not change that setting.\n We exclude open-weight models (e.g., DeepSeek and Kimi K2) and models not covered by\
  \ GitHub’s data retention agreement (e.g., Fable 5) from default enablement, regardless of your policy.\n\n After the rollout,\
  \ each model in your settings shows one of four states:\n\n\n\n Enabled: You’ve explicitly turned the model on.\n Disabled:\
  \ You’ve explicitly turned the model off.\n Delegate to enterprise teams/apps or organizations: The model follows a setting\
  \ inherited from your enterprise team or organization.\n Delegate to default policy: The model follows your default enablement\
  \ policy.\n\n To learn more, see default model availability .\n\n\n What’s next\n We are looking for your feedback in the\
  \ community discussion below. We’re evaluating making the global model policy state an explicit decision and removing the\
  \ “Delegate to default policy” state. This would help ensure that every policy reflects an explicit, intentional choice\
  \ rather than an inferred one.\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post Global model policy\
  \ generally available appeared first on The GitHub Blog ."
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
- at: '2026-08-26T22:08:38Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-27T11:00:59Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-26-global-model-policy-generally-available
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-27T11:00:51Z'
  url: https://github.blog/changelog/2026-08-26-global-model-policy-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-27T23:27:08Z'
  url: https://github.blog/changelog/2026-08-26-global-model-policy-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "In July, we announced a default model policy for generally available GitHub Copilot models on\
  \ Copilot Business and Copilot Enterprise plans. Starting today, we’re gradually rolling out enforcement of the policy through\
  \ September 1, so it will take effect at different times for different enterprises. Previously unconfigured and new generally\
  \ available models will inherit the global policy state. Administrators can make durable decisions for individual models\
  \ at their discretion. Open-weight models and any models that require data retention are disabled by default.\n\n\n What’s\
  \ changing\n Once the policy takes effect for your organization or enterprise:\n\n\n\n Models you haven’t previously configured\
  \ will change their state to “Delegate to default policy”, and they’ll begin following your policy setting. If your policy\
  \ is enabled — which is the default — those models will become available to your users.\n “Delegate to default policy” is\
  \ a live, dynamic state that always tracks your policy. You can change the policy at any time, and all applicable models\
  \ follow that state change.\n We always preserve explicit choices. If you’ve deliberately enabled or disabled a specific\
  \ model, we do not change that setting.\n We exclude open-weight models (e.g., DeepSeek and Kimi K2) and models not covered\
  \ by GitHub’s data retention agreement (e.g., Fable 5) from default enablement, regardless of your policy.\n\n After the\
  \ rollout, each model in your settings shows one of four states:\n\n\n\n Enabled: You’ve explicitly turned the model on.\n\
  \ Disabled: You’ve explicitly turned the model off.\n Delegate to enterprise teams/apps or organizations: The model follows\
  \ a setting inherited from your enterprise team or organization.\n Delegate to default policy: The model follows your default\
  \ enablement policy.\n\n To learn more, see default model availability .\n\n\n What’s next\n We are looking for your feedback\
  \ in the community discussion below. We’re evaluating making the global model policy state an explicit decision and removing\
  \ the “Delegate to default policy” state. This would help ensure that every policy reflects an explicit, intentional choice\
  \ rather than an inferred one.\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post Global model policy\
  \ generally available appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
