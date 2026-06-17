---
layout: aux-update
title: GitHub / Copilot Secret scanning updates – June 2026 official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/secret-scanning-updates-june-2026/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-17-secret-scanning-updates-june-2026
update_download_url: ''
update_version: Secret scanning updates – June 2026
update_logo_text: GIT
update_published_at: '2026-06-17T19:23:42Z'
update_last_checked: '2026-06-17T20:31:57Z'
source_last_checked: '2026-06-17T20:31:57Z'
official_body_last_checked: '2026-06-17T20:31:57Z'
record_last_updated: '2026-06-17T20:31:57Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Secret scanning updates – June 2026
update_detail_title: GitHub / Copilot Secret scanning updates – June 2026
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Secret scanning updates – June 2026 has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Secret scanning updates – June 2026.
release_summary: "Since our last pattern update , we’ve expanded secret scanning’s detection coverage with new partners, more\
  \ patterns blocked by push protection by default, additional validity checks, and richer metadata for leaked secrets.\n\n\
  \n Detectors added\n Secret scanning now automatically detects the following new secret types in your repositories. This\
  \ release adds two new partners (Cloudsmith and Meraki), significantly expands GitLab token coverage, and adds detectors\
  \ for Elastic, Slack, Supabase, DataDog, and VolcEngine.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Cloudsmith\n cloudsmith_api_key\n\
  \n\n Datadog\n datadog_pat\n\n\n Datadog\n datadog_sat\n\n\n Elastic\n elastic_stack_api_key\n\n\n GitLab\n gitlab_ci_build_token\n\
  \n\n GitLab\n gitlab_deploy_token\n\n\n GitLab\n gitlab_feature_flag_client_token\n\n\n GitLab\n gitlab_feed_token_v2\n\n\
  \n GitLab\n gitlab_incoming_email_token\n\n\n GitLab\n gitlab_kubernetes_agent_token\n\n\n GitLab\n gitlab_oauth_app_secret\n\
  \n\n GitLab\n gitlab_pipeline_trigger_token\n\n\n GitLab\n gitlab_runner_auth_token\n\n\n GitLab\n gitlab_runner_registration_token\n\
  \n\n GitLab\n gitlab_scim_oauth_token\n\n\n Meraki\n meraki_api_key\n\n\n Slack\n slack_workflow_trigger_url\n\n\n Supabase\n\
  \ supabase_oauth_access_token\n\n\n Supabase\n supabase_scoped_personal_access_token\n\n\n VolcEngine\n volcengine_ark_api_key\n\
  \n\n\n Partner secrets are automatically reported to the secret issuer when found in public repositories through the secret\
  \ scanning partnership program .\n\n\n User secrets generate secret scanning alerts when found in public or private repositories.\n\
  \n\n Push protection defaults expanded\n The following detectors are now included in push protection by default. Repositories\
  \ with secret scanning enabled, including free public repositories, will have commits containing these secrets automatically\
  \ blocked.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Cloudflare\n cloudflare_account_api_token\n\n\n Cloudflare\n cloudflare_global_user_api_key\n\
  \n\n Cloudflare\n cloudflare_user_api_token\n\n\n Cockroach Labs\n ccdb_api_key\n\n\n Flutterwave\n flutterwave_test_api_secret_key\n\
  \n\n Hack Club\n hackclub_ai_api_key\n\n\n OpenRouter\n openrouter_api_key\n\n\n PostHog\n posthog_oauth_refresh_token\n\
  \n\n Supabase\n supabase_personal_access_token\n\n\n\n Patterns that are not yet enabled by default remain configurable\
  \ in your push protection settings.\n\n\n Validity checks added\n These patterns now support validity checks, so alerts\
  \ tell you whether a leaked credential is still active and help you prioritize remediation.\n\n\n\n\n\n Provider\n Secret\
  \ type\n\n\n\n\n Alibaba\n alibaba_cloud_access_key_id\n\n\n Alibaba\n alibaba_cloud_access_key_secret\n\n\n Azure\n azure_ai_services_key\n\
  \n\n Azure\n azure_anomaly_detector_ee_key\n\n\n Azure\n azure_anomaly_detector_key\n\n\n Azure\n azure_cognitive_services_key\n\
  \n\n Azure\n azure_content_moderator_key\n\n\n Azure\n azure_cosmosdb_key_identifiable\n\n\n Azure\n azure_custom_vision_prediction_key\n\
  \n\n Azure\n azure_custom_vision_training_key\n\n\n Azure\n azure_event_hub_key_identifiable\n\n\n Azure\n azure_function_key\n\
  \n\n Azure\n azure_relay_key_identifiable\n\n\n Azure\n azure_service_bus_identifiable\n\n\n Azure\n azure_storage_account_key\n\
  \n\n Azure\n azure_text_translation_key\n\n\n Coveo\n coveo_access_token\n\n\n Coveo\n coveo_api_key\n\n\n Databricks\n\
  \ databricks_access_token\n\n\n Salesforce\n salesforce_access_token\n\n\n Shopify\n shopify_access_token\n\n\n Shopify\n\
  \ shopify_custom_app_access_token\n\n\n Shopify\n shopify_merchant_token\n\n\n Shopify\n shopify_private_app_password\n\n\
  \n\n Extended metadata support\n These patterns now include extended metadata when detected, providing richer context about\
  \ leaked secrets.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Airtable\n airtable_api_key\n\n\n Airtable\n airtable_personal_access_token\n\
  \n\n Grafana\n grafana_cloud_api_token\n\n\n npm\n npm_access_token\n\n\n xAI\n xai_api_key\n\n\n\n Learn more\n Learn more\
  \ about secret scanning and see the full list of supported secrets in our documentation. Let us know what you think in the\
  \ community discussion .\n\n\n\n The post Secret scanning updates – June 2026 appeared first on The GitHub Blog ."
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
- at: '2026-06-17T19:23:42Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-17T20:32:00Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-17-secret-scanning-updates-june-2026
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-17T20:31:57Z'
  url: https://github.blog/changelog/2026-06-17-secret-scanning-updates-june-2026
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Since our last pattern update , we’ve expanded secret scanning’s detection coverage with new partners,\
  \ more patterns blocked by push protection by default, additional validity checks, and richer metadata for leaked secrets.\n\
  \n\n Detectors added\n Secret scanning now automatically detects the following new secret types in your repositories. This\
  \ release adds two new partners (Cloudsmith and Meraki), significantly expands GitLab token coverage, and adds detectors\
  \ for Elastic, Slack, Supabase, DataDog, and VolcEngine.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Cloudsmith\n cloudsmith_api_key\n\
  \n\n Datadog\n datadog_pat\n\n\n Datadog\n datadog_sat\n\n\n Elastic\n elastic_stack_api_key\n\n\n GitLab\n gitlab_ci_build_token\n\
  \n\n GitLab\n gitlab_deploy_token\n\n\n GitLab\n gitlab_feature_flag_client_token\n\n\n GitLab\n gitlab_feed_token_v2\n\n\
  \n GitLab\n gitlab_incoming_email_token\n\n\n GitLab\n gitlab_kubernetes_agent_token\n\n\n GitLab\n gitlab_oauth_app_secret\n\
  \n\n GitLab\n gitlab_pipeline_trigger_token\n\n\n GitLab\n gitlab_runner_auth_token\n\n\n GitLab\n gitlab_runner_registration_token\n\
  \n\n GitLab\n gitlab_scim_oauth_token\n\n\n Meraki\n meraki_api_key\n\n\n Slack\n slack_workflow_trigger_url\n\n\n Supabase\n\
  \ supabase_oauth_access_token\n\n\n Supabase\n supabase_scoped_personal_access_token\n\n\n VolcEngine\n volcengine_ark_api_key\n\
  \n\n\n Partner secrets are automatically reported to the secret issuer when found in public repositories through the secret\
  \ scanning partnership program .\n\n\n User secrets generate secret scanning alerts when found in public or private repositories.\n\
  \n\n Push protection defaults expanded\n The following detectors are now included in push protection by default. Repositories\
  \ with secret scanning enabled, including free public repositories, will have commits containing these secrets automatically\
  \ blocked.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Cloudflare\n cloudflare_account_api_token\n\n\n Cloudflare\n cloudflare_global_user_api_key\n\
  \n\n Cloudflare\n cloudflare_user_api_token\n\n\n Cockroach Labs\n ccdb_api_key\n\n\n Flutterwave\n flutterwave_test_api_secret_key\n\
  \n\n Hack Club\n hackclub_ai_api_key\n\n\n OpenRouter\n openrouter_api_key\n\n\n PostHog\n posthog_oauth_refresh_token\n\
  \n\n Supabase\n supabase_personal_access_token\n\n\n\n Patterns that are not yet enabled by default remain configurable\
  \ in your push protection settings.\n\n\n Validity checks added\n These patterns now support validity checks, so alerts\
  \ tell you whether a leaked credential is still active and help you prioritize remediation.\n\n\n\n\n\n Provider\n Secret\
  \ type\n\n\n\n\n Alibaba\n alibaba_cloud_access_key_id\n\n\n Alibaba\n alibaba_cloud_access_key_secret\n\n\n Azure\n azure_ai_services_key\n\
  \n\n Azure\n azure_anomaly_detector_ee_key\n\n\n Azure\n azure_anomaly_detector_key\n\n\n Azure\n azure_cognitive_services_key\n\
  \n\n Azure\n azure_content_moderator_key\n\n\n Azure\n azure_cosmosdb_key_identifiable\n\n\n Azure\n azure_custom_vision_prediction_key\n\
  \n\n Azure\n azure_custom_vision_training_key\n\n\n Azure\n azure_event_hub_key_identifiable\n\n\n Azure\n azure_function_key\n\
  \n\n Azure\n azure_relay_key_identifiable\n\n\n Azure\n azure_service_bus_identifiable\n\n\n Azure\n azure_storage_account_key\n\
  \n\n Azure\n azure_text_translation_key\n\n\n Coveo\n coveo_access_token\n\n\n Coveo\n coveo_api_key\n\n\n Databricks\n\
  \ databricks_access_token\n\n\n Salesforce\n salesforce_access_token\n\n\n Shopify\n shopify_access_token\n\n\n Shopify\n\
  \ shopify_custom_app_access_token\n\n\n Shopify\n shopify_merchant_token\n\n\n Shopify\n shopify_private_app_password\n\n\
  \n\n Extended metadata support\n These patterns now include extended metadata when detected, providing richer context about\
  \ leaked secrets.\n\n\n\n\n\n Provider\n Secret type\n\n\n\n\n Airtable\n airtable_api_key\n\n\n Airtable\n airtable_personal_access_token\n\
  \n\n Grafana\n grafana_cloud_api_token\n\n\n npm\n npm_access_token\n\n\n xAI\n xai_api_key\n\n\n\n Learn more\n Learn more\
  \ about secret scanning and see the full list of supported secrets in our documentation. Let us know what you think in the\
  \ community discussion .\n\n\n\n The post Secret scanning updates – June 2026 appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
