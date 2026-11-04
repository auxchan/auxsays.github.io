---
layout: aux-update
title: GitHub / Copilot BYOK and enterprise custom models in the Copilot usage API official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for BYOK and enterprise custom models in the Copilot
  usage API.
permalink: /updates/github/github/byok-and-enterprise-custom-models-in-the-copilot-usage-api/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-03-byok-and-enterprise-custom-models-in-the-copilot-usage-api
update_download_url: ''
update_version: BYOK and enterprise custom models in the Copilot usage API
update_logo_text: GIT
update_published_at: '2026-11-04T00:32:19Z'
update_last_checked: '2026-11-04T02:10:55Z'
source_last_checked: '2026-11-04T08:56:28Z'
official_body_last_checked: '2026-11-04T08:56:28Z'
record_last_updated: '2026-11-04T02:10:55Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot BYOK and enterprise custom models in the Copilot usage API
update_detail_title: GitHub / Copilot BYOK and enterprise custom models in the Copilot usage API
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot BYOK and enterprise custom models in the Copilot usage API has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot BYOK and enterprise custom models in the Copilot usage API.
release_summary: "The Copilot usage metrics API now shows bring your own key (BYOK) usage across GitHub Copilot, so you can\
  \ separate it from Copilot-hosted model usage. Reports cover two kinds of BYOK:\n\n\n\n Local BYOK is configured by developers\
  \ in their client. Requests go from Copilot CLI or the GitHub Copilot app directly to the developer’s provider key or local\
  \ model. Find it in used_local_byok , totals_by_local_byok , and active local BYOK user counts.\n Enterprise custom models\
  \ are configured by admins in GitHub settings, and requests route through GitHub to your provider. Find them with is_custom_enterprise_model\
  \ in totals_by_client .\n\n Both appear in enterprise and organization reports, at the user and aggregate level, in 1-day\
  \ and 28-day reports.\n\n\n Local BYOK\n Local BYOK covers a developer’s own provider key and local models served by tools\
  \ such as Ollama, Foundry Local, LM Studio, and llama-server.\n\n\n\n used_local_byok : Whether a user made at least one\
  \ local BYOK request in Copilot CLI or the Copilot app that day. Appears in user-level reports.\n totals_by_local_byok :\
  \ Session, request, prompt, and token counts, broken out by byok_kind ( local_managed , local_user , local_auto , or remote_user\
  \ ) and surface ( copilot_cli or copilot_app ). Appears in user-level and aggregate reports.\n daily_active_local_byok_users\
  \ , weekly_active_local_byok_users , and monthly_active_local_byok_users : Distinct users with local BYOK activity for the\
  \ day, calendar week, and calendar month. Appears in aggregate reports.\n\n Enterprise custom models\n\n Added is_custom_enterprise_model\
  \ , a boolean on each totals_by_client[].totals_by_model[] entry. Its value is true when the request used a custom model\
  \ configured for your enterprise or organization. GitHub observes these requests server-side, so the field covers every\
  \ client, including IDEs.\n A model used both as a Copilot-hosted model and as a custom model appears as two entries, so\
  \ the counts stay separate.\n Custom model entries include real request and token counts.\n\n Why this matters\n BYOK usage\
  \ used to blend into Copilot-hosted totals, because local and custom models often share names with Copilot models. Now you\
  \ can:\n\n\n\n Govern BYOK: See who sends requests to their own provider keys, local models, or enterprise custom models,\
  \ and check that against your BYOK policy.\n Understand spend: Separate Copilot-hosted usage from usage billed by your own\
  \ provider or run on free local models, so cost per user reflects what Copilot actually serves.\n See across all tools:\
  \ Get one view of AI usage in your enterprise, whichever model or provider your developers choose.\n Compare efficiency:\
  \ Group users by BYOK or custom model usage and compare them against the Copilot usage metrics you already track.\n\n Important\
  \ notes\n\n No change to existing totals: BYOK usage is already counted. Local BYOK is a subset of totals_by_cli and totals_by_copilot_app\
  \ , and custom model usage is already in totals_by_client . Existing totals are unchanged.\n Lower bound for local BYOK:\
  \ Local BYOK fields rely on client telemetry, so they undercount when telemetry is disabled. Token counts can also undercount\
  \ because some local providers don’t report token usage. Enterprise custom model counts are observed server-side and don’t\
  \ have this limitation.\n Model names: Custom model names use the existing model name normalization, so unrecognized names\
  \ appear as unknown . Local BYOK usage isn’t broken out by model name.\n No backfill: Report days before this release don’t\
  \ include is_custom_enterprise_model .\n Access: Available to enterprise owners, enterprise billing managers, organization\
  \ owners, and anyone with a custom organization or enterprise role that grants the View Copilot Metrics permission. The\
  \ Copilot usage metrics policy must be enabled.\n\n Visit the Copilot usage metrics API documentation to get started.\n\n\
  \n\n The post BYOK and enterprise custom models in the Copilot usage API appeared first on The GitHub Blog ."
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
- at: '2026-11-04T00:32:19Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-04T02:11:01Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-03-byok-and-enterprise-custom-models-in-the-copilot-usage-api
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-04T02:10:55Z'
  url: https://github.blog/changelog/2026-11-03-byok-and-enterprise-custom-models-in-the-copilot-usage-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-04T08:56:28Z'
  url: https://github.blog/changelog/2026-11-03-byok-and-enterprise-custom-models-in-the-copilot-usage-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The Copilot usage metrics API now shows bring your own key (BYOK) usage across GitHub Copilot,\
  \ so you can separate it from Copilot-hosted model usage. Reports cover two kinds of BYOK:\n\n\n\n Local BYOK is configured\
  \ by developers in their client. Requests go from Copilot CLI or the GitHub Copilot app directly to the developer’s provider\
  \ key or local model. Find it in used_local_byok , totals_by_local_byok , and active local BYOK user counts.\n Enterprise\
  \ custom models are configured by admins in GitHub settings, and requests route through GitHub to your provider. Find them\
  \ with is_custom_enterprise_model in totals_by_client .\n\n Both appear in enterprise and organization reports, at the user\
  \ and aggregate level, in 1-day and 28-day reports.\n\n\n Local BYOK\n Local BYOK covers a developer’s own provider key\
  \ and local models served by tools such as Ollama, Foundry Local, LM Studio, and llama-server.\n\n\n\n used_local_byok :\
  \ Whether a user made at least one local BYOK request in Copilot CLI or the Copilot app that day. Appears in user-level\
  \ reports.\n totals_by_local_byok : Session, request, prompt, and token counts, broken out by byok_kind ( local_managed\
  \ , local_user , local_auto , or remote_user ) and surface ( copilot_cli or copilot_app ). Appears in user-level and aggregate\
  \ reports.\n daily_active_local_byok_users , weekly_active_local_byok_users , and monthly_active_local_byok_users : Distinct\
  \ users with local BYOK activity for the day, calendar week, and calendar month. Appears in aggregate reports.\n\n Enterprise\
  \ custom models\n\n Added is_custom_enterprise_model , a boolean on each totals_by_client[].totals_by_model[] entry. Its\
  \ value is true when the request used a custom model configured for your enterprise or organization. GitHub observes these\
  \ requests server-side, so the field covers every client, including IDEs.\n A model used both as a Copilot-hosted model\
  \ and as a custom model appears as two entries, so the counts stay separate.\n Custom model entries include real request\
  \ and token counts.\n\n Why this matters\n BYOK usage used to blend into Copilot-hosted totals, because local and custom\
  \ models often share names with Copilot models. Now you can:\n\n\n\n Govern BYOK: See who sends requests to their own provider\
  \ keys, local models, or enterprise custom models, and check that against your BYOK policy.\n Understand spend: Separate\
  \ Copilot-hosted usage from usage billed by your own provider or run on free local models, so cost per user reflects what\
  \ Copilot actually serves.\n See across all tools: Get one view of AI usage in your enterprise, whichever model or provider\
  \ your developers choose.\n Compare efficiency: Group users by BYOK or custom model usage and compare them against the Copilot\
  \ usage metrics you already track.\n\n Important notes\n\n No change to existing totals: BYOK usage is already counted.\
  \ Local BYOK is a subset of totals_by_cli and totals_by_copilot_app , and custom model usage is already in totals_by_client\
  \ . Existing totals are unchanged.\n Lower bound for local BYOK: Local BYOK fields rely on client telemetry, so they undercount\
  \ when telemetry is disabled. Token counts can also undercount because some local providers don’t report token usage. Enterprise\
  \ custom model counts are observed server-side and don’t have this limitation.\n Model names: Custom model names use the\
  \ existing model name normalization, so unrecognized names appear as unknown . Local BYOK usage isn’t broken out by model\
  \ name.\n No backfill: Report days before this release don’t include is_custom_enterprise_model .\n Access: Available to\
  \ enterprise owners, enterprise billing managers, organization owners, and anyone with a custom organization or enterprise\
  \ role that grants the View Copilot Metrics permission. The Copilot usage metrics policy must be enabled.\n\n Visit the\
  \ Copilot usage metrics API documentation to get started.\n\n\n\n The post BYOK and enterprise custom models in the Copilot\
  \ usage API appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
