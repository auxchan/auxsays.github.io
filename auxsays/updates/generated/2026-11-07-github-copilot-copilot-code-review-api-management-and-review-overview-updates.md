---
layout: aux-update
title: 'GitHub / Copilot Copilot code review: API management and review overview updates official update breakdown'
description: 'Official GitHub / Copilot update record captured from GitHub for Copilot code review: API management and review
  overview updates.'
permalink: /updates/github/github/copilot-code-review-api-management-and-review-overview-updates/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-06-copilot-code-review-api-management-and-review-overview-updates
update_download_url: ''
update_version: 'Copilot code review: API management and review overview updates'
update_logo_text: GIT
update_published_at: '2026-11-07T00:27:19Z'
update_last_checked: '2026-11-07T08:11:38Z'
source_last_checked: '2026-11-07T15:16:00Z'
official_body_last_checked: '2026-11-07T15:16:00Z'
record_last_updated: '2026-11-07T08:11:38Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot Copilot code review: API management and review overview updates'
update_detail_title: 'GitHub / Copilot Copilot code review: API management and review overview updates'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot Copilot code review: API management and review overview updates has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot Copilot code review: API management and review overview updates.'
release_summary: "You can now manage GitHub Copilot code review settings through the REST and GraphQL APIs, from enterprise\
  \ policy down to individual repositories. Copilot’s review overview comment is now more compact, and this update includes\
  \ fixes for billing, automatic reviews, and reliability.\n\n\n These updates are available to Copilot Pro, Pro+, Max, Business,\
  \ and Enterprise plans.\n\n\n \U0001F50C Manage settings and identify Copilot’s output through the API\n You can already\
  \ request reviews, choose their effort level, and get information back through the REST API. You can now also:\n\n\n\n Identify\
  \ Copilot’s reviews and comments through explicit attribution fields.\n See the review effort a review used, when that metadata\
  \ is available.\n See which skills, MCP servers, and custom instructions Copilot reported as sources for a comment.\n\n\
  \ Depending on your role, you can also read and update code review settings:\n\n\n\n Enterprise administrators can enable\
  \ or disable code review for all organizations, or leave the choice to organization administrators.\n Organization administrators\
  \ can manage code review enablement, the default review effort, and the runner configuration. Settings your enterprise manages\
  \ can’t be overridden.\n Repository administrators can manage review effort and whether reviews use custom instructions\
  \ and MCP tools.\n\n The REST API accepts the same review effort levels as the web interface, and organization and repository\
  \ settings responses list the levels available to you.\n\n\n ⚠️ The enterprise and organization settings endpoints, including\
  \ the organization runner endpoint, don’t support GitHub Apps or fine-grained personal access tokens. The repository settings\
  \ endpoints support both, with Administration: read permission to read settings and Administration: write permission to\
  \ update them. Classic personal access tokens need repository administrator access.\n\n\n To get started, see Configuring\
  \ Copilot code review with the API .\n\n\n \U0001F4CB A more compact review overview\n New review overviews keep your findings\
  \ together at the top:\n\n\n\n The review effort used and any surveys move into a compact footer.\n Skipped and content-excluded\
  \ files share one “Files not reviewed” section, with filenames and linked exclusion reasons.\n Empty sections are left out,\
  \ and long lists show an overflow count.\n\n You can also tell us what’s wrong with an overview. After you give it a \U0001F44E\
  , choose Add a reason and pick the main problem, such as an approval assessment you disagree with, a comment that’s too\
  \ verbose, or findings that are incorrect or nitpicky. We use this feedback to improve Copilot’s findings.\n\n\n\n\n\n ✨\
  \ Other improvements\n\n\n\n\n Copilot code review agent sessions now show the AI credits consumed in a review.\n The Automatically\
  \ request Copilot code review repository rule now supports the bypass list, so exempt actors in the list will not receive\
  \ an automatic review from Copilot.\n Copilot code review organization and repository settings pages have clearer wording\
  \ and layout.\n On later reviews of the same pull request, findings unrelated to your recent changes are collapsed and then\
  \ hidden.\n Balanced effort reviews now use three reviewer models, with another model combining their findings.\n\n \U0001F41B\
  \ Bug fixes\n\n Billing and preview settings are now preserved when you turn code review off and on again.\n Failed or timed-out\
  \ reviews are retried once automatically, and Copilot can switch to another eligible model when the preferred one is unavailable.\n\
  \ GitHub Actions, Dependabot, and apps your organization or enterprise owns can request reviews on bot-authored pull requests\
  \ again when Block reviews requested with an external Copilot license is on, as long as your organization pays for the review.\n\
  \ Reviews no longer report a false failure just after starting and discard their results.\n Reviews in progress during a\
  \ service update now get more time to finish.\n Review surveys no longer appear when your organization has opted out of\
  \ feedback collection.\n\n\n The post Copilot code review: API management and review overview updates appeared first on\
  \ The GitHub Blog ."
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
- at: '2026-11-07T00:27:19Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-07T08:11:51Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-06-copilot-code-review-api-management-and-review-overview-updates
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-07T08:11:38Z'
  url: https://github.blog/changelog/2026-11-06-copilot-code-review-api-management-and-review-overview-updates
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-11-07T15:16:00Z'
  url: https://github.blog/changelog/2026-11-06-copilot-code-review-api-management-and-review-overview-updates
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now manage GitHub Copilot code review settings through the REST and GraphQL APIs, from\
  \ enterprise policy down to individual repositories. Copilot’s review overview comment is now more compact, and this update\
  \ includes fixes for billing, automatic reviews, and reliability.\n\n\n These updates are available to Copilot Pro, Pro+,\
  \ Max, Business, and Enterprise plans.\n\n\n \U0001F50C Manage settings and identify Copilot’s output through the API\n\
  \ You can already request reviews, choose their effort level, and get information back through the REST API. You can now\
  \ also:\n\n\n\n Identify Copilot’s reviews and comments through explicit attribution fields.\n See the review effort a review\
  \ used, when that metadata is available.\n See which skills, MCP servers, and custom instructions Copilot reported as sources\
  \ for a comment.\n\n Depending on your role, you can also read and update code review settings:\n\n\n\n Enterprise administrators\
  \ can enable or disable code review for all organizations, or leave the choice to organization administrators.\n Organization\
  \ administrators can manage code review enablement, the default review effort, and the runner configuration. Settings your\
  \ enterprise manages can’t be overridden.\n Repository administrators can manage review effort and whether reviews use custom\
  \ instructions and MCP tools.\n\n The REST API accepts the same review effort levels as the web interface, and organization\
  \ and repository settings responses list the levels available to you.\n\n\n ⚠️ The enterprise and organization settings\
  \ endpoints, including the organization runner endpoint, don’t support GitHub Apps or fine-grained personal access tokens.\
  \ The repository settings endpoints support both, with Administration: read permission to read settings and Administration:\
  \ write permission to update them. Classic personal access tokens need repository administrator access.\n\n\n To get started,\
  \ see Configuring Copilot code review with the API .\n\n\n \U0001F4CB A more compact review overview\n New review overviews\
  \ keep your findings together at the top:\n\n\n\n The review effort used and any surveys move into a compact footer.\n Skipped\
  \ and content-excluded files share one “Files not reviewed” section, with filenames and linked exclusion reasons.\n Empty\
  \ sections are left out, and long lists show an overflow count.\n\n You can also tell us what’s wrong with an overview.\
  \ After you give it a \U0001F44E, choose Add a reason and pick the main problem, such as an approval assessment you disagree\
  \ with, a comment that’s too verbose, or findings that are incorrect or nitpicky. We use this feedback to improve Copilot’s\
  \ findings.\n\n\n\n\n\n ✨ Other improvements\n\n\n\n\n Copilot code review agent sessions now show the AI credits consumed\
  \ in a review.\n The Automatically request Copilot code review repository rule now supports the bypass list, so exempt actors\
  \ in the list will not receive an automatic review from Copilot.\n Copilot code review organization and repository settings\
  \ pages have clearer wording and layout.\n On later reviews of the same pull request, findings unrelated to your recent\
  \ changes are collapsed and then hidden.\n Balanced effort reviews now use three reviewer models, with another model combining\
  \ their findings.\n\n \U0001F41B Bug fixes\n\n Billing and preview settings are now preserved when you turn code review\
  \ off and on again.\n Failed or timed-out reviews are retried once automatically, and Copilot can switch to another eligible\
  \ model when the preferred one is unavailable.\n GitHub Actions, Dependabot, and apps your organization or enterprise owns\
  \ can request reviews on bot-authored pull requests again when Block reviews requested with an external Copilot license\
  \ is on, as long as your organization pays for the review.\n Reviews no longer report a false failure just after starting\
  \ and discard their results.\n Reviews in progress during a service update now get more time to finish.\n Review surveys\
  \ no longer appear when your organization has opted out of feedback collection.\n\n\n The post Copilot code review: API\
  \ management and review overview updates appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
