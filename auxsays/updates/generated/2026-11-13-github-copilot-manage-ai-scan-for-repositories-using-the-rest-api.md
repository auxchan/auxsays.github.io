---
layout: aux-update
title: GitHub / Copilot Manage AI Scan for repositories using the REST API official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Manage AI Scan for repositories using the REST
  API.
permalink: /updates/github/github/manage-ai-scan-for-repositories-using-the-rest-api/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-11-13-manage-ai-scan-for-repositories-using-the-rest-api
update_download_url: ''
update_version: Manage AI Scan for repositories using the REST API
update_logo_text: GIT
update_published_at: '2026-11-13T12:22:41Z'
update_last_checked: '2026-11-14T08:46:12Z'
source_last_checked: '2026-11-14T08:46:12Z'
official_body_last_checked: '2026-11-14T08:46:12Z'
record_last_updated: '2026-11-14T08:46:12Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Manage AI Scan for repositories using the REST API
update_detail_title: GitHub / Copilot Manage AI Scan for repositories using the REST API
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Manage AI Scan for repositories using the REST API has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Manage AI Scan for repositories using the REST API.
release_summary: "You can now turn GitHub code scanning’s AI Scan for repositories on or off with the REST API at the organization\
  \ and repository levels. This public preview adds a repository_scan setting to the existing AI Scan enablement endpoints.\
  \ You can roll out AI Scan for repositories with scripts and infrastructure as code instead of changing settings one organization\
  \ or repository at a time.\n\n\n Manage AI Scan for repositories at scale\n Set the repository_scan property to enabled\
  \ or disabled on the AI Scan enablement endpoints :\n\n\n\n GET and PATCH /orgs/{org}/code-scanning/ai-scan\n GET and PATCH\
  \ /repos/{owner}/{repo}/code-scanning/ai-scan\n\n The setting works the same way as the existing pr_scan setting for AI\
  \ Scan for pull requests:\n\n\n\n When an organization disables AI Scan for repositories, its repositories can’t enable\
  \ it\n When an organization enables it, its repositories inherit the setting and can opt out individually\n When an enterprise\
  \ policy doesn’t allow AI Scan, requests to enable it return a 422 error\n\n You can update pr_scan and repository_scan\
  \ in the same request. If either change is blocked, the request returns a 422 error and neither setting changes.\n\n\n Turning\
  \ on AI Scan for repositories doesn’t start a scan. Users with write access still run scans on demand, and each scan consumes\
  \ GitHub Code Security AI credits.\n\n\n Who can use it\n Organization owners and security managers can manage the organization\
  \ setting. Repository administrators can opt individual repositories out. AI Scan for repositories is available for public\
  \ repositories owned by organizations and for private or internal repositories with GitHub Code Security or GitHub Advanced\
  \ Security. Enterprise owners must first allow AI Scan in the enterprise policy. GitHub Enterprise Server isn’t supported.\n\
  \n\n To get started, see REST API endpoints for code scanning and AI Scan for a repository’s backlog .\n\n\n Join the discussion\
  \ in the GitHub Community .\n\n\n\n The post Manage AI Scan for repositories using the REST API appeared first on The GitHub\
  \ Blog ."
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
- at: '2026-11-13T12:22:41Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-14T08:46:39Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-11-13-manage-ai-scan-for-repositories-using-the-rest-api
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-14T08:46:12Z'
  url: https://github.blog/changelog/2026-11-13-manage-ai-scan-for-repositories-using-the-rest-api
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now turn GitHub code scanning’s AI Scan for repositories on or off with the REST API at\
  \ the organization and repository levels. This public preview adds a repository_scan setting to the existing AI Scan enablement\
  \ endpoints. You can roll out AI Scan for repositories with scripts and infrastructure as code instead of changing settings\
  \ one organization or repository at a time.\n\n\n Manage AI Scan for repositories at scale\n Set the repository_scan property\
  \ to enabled or disabled on the AI Scan enablement endpoints :\n\n\n\n GET and PATCH /orgs/{org}/code-scanning/ai-scan\n\
  \ GET and PATCH /repos/{owner}/{repo}/code-scanning/ai-scan\n\n The setting works the same way as the existing pr_scan setting\
  \ for AI Scan for pull requests:\n\n\n\n When an organization disables AI Scan for repositories, its repositories can’t\
  \ enable it\n When an organization enables it, its repositories inherit the setting and can opt out individually\n When\
  \ an enterprise policy doesn’t allow AI Scan, requests to enable it return a 422 error\n\n You can update pr_scan and repository_scan\
  \ in the same request. If either change is blocked, the request returns a 422 error and neither setting changes.\n\n\n Turning\
  \ on AI Scan for repositories doesn’t start a scan. Users with write access still run scans on demand, and each scan consumes\
  \ GitHub Code Security AI credits.\n\n\n Who can use it\n Organization owners and security managers can manage the organization\
  \ setting. Repository administrators can opt individual repositories out. AI Scan for repositories is available for public\
  \ repositories owned by organizations and for private or internal repositories with GitHub Code Security or GitHub Advanced\
  \ Security. Enterprise owners must first allow AI Scan in the enterprise policy. GitHub Enterprise Server isn’t supported.\n\
  \n\n To get started, see REST API endpoints for code scanning and AI Scan for a repository’s backlog .\n\n\n Join the discussion\
  \ in the GitHub Community .\n\n\n\n The post Manage AI Scan for repositories using the REST API appeared first on The GitHub\
  \ Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
