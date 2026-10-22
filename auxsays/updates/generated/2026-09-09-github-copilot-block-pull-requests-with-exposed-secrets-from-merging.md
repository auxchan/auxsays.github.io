---
layout: aux-update
title: GitHub / Copilot Block pull requests with exposed secrets from merging official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Block pull requests with exposed secrets from
  merging.
permalink: /updates/github/github/block-pull-requests-with-exposed-secrets-from-merging/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-09-block-pull-requests-with-exposed-secrets-from-merging
update_download_url: ''
update_version: Block pull requests with exposed secrets from merging
update_logo_text: GIT
update_published_at: '2026-09-09T17:14:02Z'
update_last_checked: '2026-09-09T18:50:54Z'
source_last_checked: '2026-09-10T00:02:42Z'
official_body_last_checked: '2026-09-10T00:02:42Z'
record_last_updated: '2026-09-09T18:50:54Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Block pull requests with exposed secrets from merging
update_detail_title: GitHub / Copilot Block pull requests with exposed secrets from merging
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Block pull requests with exposed secrets from merging has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Block pull requests with exposed secrets from merging.
release_summary: "Repository rulesets allow you to easily add scalable protections across your repositories. Starting today,\
  \ you can use repository rulesets to block pull requests from merging when the pull request introduces secret scanning alerts.\n\
  \n\n What’s new\n You can enable the new rule require secret scanning alerts are resolved on pull requests for selected\
  \ repositories. Developers without bypass permissions must clear the block by resolving each alert.\n\n\n The rule checks\
  \ two things before a pull request can merge:\n\n\n\n A secret scan has completed for the head commit\n No alerts are open\
  \ for secrets introduced by the pull request’s commits\n\n By default, the rule runs on open pull requests and blocks secrets\
  \ found via provider patterns. You can additionally configure the rule to block other categories (e.g., custom or generic\
  \ patterns).\n\n\n This rule is available today in public preview for customers with GitHub Secret Protection or GitHub\
  \ Advanced Security.\n\n\n How this rule differs from push protection\n Push protection stops a secret at the push, before\
  \ it ever reaches the repository. This rule adds an additional layer of protection at the pull request layer, catching cases\
  \ that push protection isn’t able to or configured to catch. For example, you may keep push protection disabled for generic\
  \ pattern secret types, while keeping a ruleset to block pull requests for those secret types.\n\n\n How to configure the\
  \ rule\n\n In your repository, organization, or enterprise settings, go to the Repository > Rulesets tab.\n Create or edit\
  \ a ruleset targeting the branches you want to protect.\n Select Require secret scanning alerts are resolved .\n\n You can\
  \ also configure the rule through the REST API using the require_secret_scanning_alert_resolution rule type with a secret_types\
  \ parameter, or through GraphQL as REQUIRE_SECRET_SCANNING_ALERT_RESOLUTION .\n\n\n Learn more\n Learn more about secret\
  \ scanning and push protection in our documentation.\n\n\n See the rulesets documentation for how rules are applied and\
  \ bypassed.\n\n\n\n The post Block pull requests with exposed secrets from merging appeared first on The GitHub Blog ."
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
- at: '2026-09-09T17:14:02Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-09T18:51:12Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-09-block-pull-requests-with-exposed-secrets-from-merging
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-09T18:50:54Z'
  url: https://github.blog/changelog/2026-09-09-block-pull-requests-with-exposed-secrets-from-merging
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-09-10T00:02:42Z'
  url: https://github.blog/changelog/2026-09-09-block-pull-requests-with-exposed-secrets-from-merging
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Repository rulesets allow you to easily add scalable protections across your repositories. Starting\
  \ today, you can use repository rulesets to block pull requests from merging when the pull request introduces secret scanning\
  \ alerts.\n\n\n What’s new\n You can enable the new rule require secret scanning alerts are resolved on pull requests for\
  \ selected repositories. Developers without bypass permissions must clear the block by resolving each alert.\n\n\n The rule\
  \ checks two things before a pull request can merge:\n\n\n\n A secret scan has completed for the head commit\n No alerts\
  \ are open for secrets introduced by the pull request’s commits\n\n By default, the rule runs on open pull requests and\
  \ blocks secrets found via provider patterns. You can additionally configure the rule to block other categories (e.g., custom\
  \ or generic patterns).\n\n\n This rule is available today in public preview for customers with GitHub Secret Protection\
  \ or GitHub Advanced Security.\n\n\n How this rule differs from push protection\n Push protection stops a secret at the\
  \ push, before it ever reaches the repository. This rule adds an additional layer of protection at the pull request layer,\
  \ catching cases that push protection isn’t able to or configured to catch. For example, you may keep push protection disabled\
  \ for generic pattern secret types, while keeping a ruleset to block pull requests for those secret types.\n\n\n How to\
  \ configure the rule\n\n In your repository, organization, or enterprise settings, go to the Repository > Rulesets tab.\n\
  \ Create or edit a ruleset targeting the branches you want to protect.\n Select Require secret scanning alerts are resolved\
  \ .\n\n You can also configure the rule through the REST API using the require_secret_scanning_alert_resolution rule type\
  \ with a secret_types parameter, or through GraphQL as REQUIRE_SECRET_SCANNING_ALERT_RESOLUTION .\n\n\n Learn more\n Learn\
  \ more about secret scanning and push protection in our documentation.\n\n\n See the rulesets documentation for how rules\
  \ are applied and bypassed.\n\n\n\n The post Block pull requests with exposed secrets from merging appeared first on The\
  \ GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
