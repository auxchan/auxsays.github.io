---
layout: aux-update
title: GitHub / Copilot Copilot usage metrics reports now use GitHub-owned download URLs official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/copilot-usage-metrics-reports-now-use-github-owned-download-urls/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-05-20-copilot-usage-metrics-reports-now-use-github-owned-download-urls
update_download_url: ''
update_version: Copilot usage metrics reports now use GitHub-owned download URLs
update_logo_text: GIT
update_published_at: '2026-05-20T23:58:35Z'
update_last_checked: '2026-05-21T04:48:24Z'
source_last_checked: '2026-05-21T04:48:24Z'
official_body_last_checked: '2026-05-21T04:48:24Z'
record_last_updated: '2026-05-21T04:48:24Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Copilot usage metrics reports now use GitHub-owned download URLs
update_detail_title: GitHub / Copilot Copilot usage metrics reports now use GitHub-owned download URLs
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Copilot usage metrics reports now use GitHub-owned download URLs has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Copilot usage metrics reports now use GitHub-owned download URLs.
release_summary: "As previously announced , the download URLs for Copilot usage metrics reports have migrated from Azure Front\
  \ Door domains to a stable, GitHub-owned custom domain. This change improves URL stability and makes firewall and proxy\
  \ allowlist management easier for enterprise customers.\n\n\n What’s changed\n Starting today, Copilot usage metrics report\
  \ download links, which are returned by the Copilot Usage Metrics API , use the new domain copilot-reports.github.com instead\
  \ of the previous copilot-reports-*.b01.azurefd.net pattern.\n\n\n github.com (GHEC) customers:\n\n\n\n\n\n\n Previous\n\
  \ New\n\n\n\n\n Report download URL pattern\n https://copilot-reports-*.b01.azurefd.net/...\n https://copilot-reports.github.com/...\n\
  \n\n\n ghe.com customers:\n\n\n\n\n\n\n Previous\n New\n\n\n\n\n Report download URL pattern\n https://copilot-reports-*.b01.azurefd.net/...\n\
  \ https://copilot-reports.*.ghe.com/...\n\n\n\n What you need to do\n If your organization uses a firewall or proxy allowlist,\
  \ add the following domain:\n\n\n\n github.com: https://copilot-reports.github.com\n ghe.com: https://copilot-reports.SUBDOMAIN.ghe.com\
  \ , where SUBDOMAIN is your enterprise’s dedicated subdomain on GHE.com\n\n The legacy copilot-reports-*.b01.azurefd.net\
  \ pattern will continue to work during a transition period, but will eventually be deprecated. We recommend updating your\
  \ allowlists as soon as possible.\n\n\n\n Note: In rare cases where Azure Front Door is unavailable, report downloads may\
  \ fall back to direct Azure Blob Storage URLs ( *.blob.core.windows.net ). If your organization requires uninterrupted access\
  \ to reports during such events, you should also ensure *.blob.core.windows.net is in your allowlist.\n\n\n\n Why we made\
  \ this change\n The previous Azure Front Door domains were infrastructure-specific and could change when services were redeployed\
  \ or reconfigured. Moving to a stable, GitHub-owned domain ensures that:\n\n\n\n Report download URLs remain constant regardless\
  \ of infrastructure changes.\n Enterprise security teams have a predictable, trustworthy domain to allowlist.\n Automation\
  \ scripts and integrations are not disrupted by domain changes.\n\n For more information, see the Copilot allowlist reference\
  \ .\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post Copilot usage metrics reports now use GitHub-owned\
  \ download URLs appeared first on The GitHub Blog ."
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
- at: '2026-05-20T23:58:35Z'
  label: Published
  note: Official source entry detected.
- at: '2026-05-21T04:48:25Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-05-20-copilot-usage-metrics-reports-now-use-github-owned-download-urls
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-05-21T04:48:24Z'
  url: https://github.blog/changelog/2026-05-20-copilot-usage-metrics-reports-now-use-github-owned-download-urls
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "As previously announced , the download URLs for Copilot usage metrics reports have migrated from\
  \ Azure Front Door domains to a stable, GitHub-owned custom domain. This change improves URL stability and makes firewall\
  \ and proxy allowlist management easier for enterprise customers.\n\n\n What’s changed\n Starting today, Copilot usage metrics\
  \ report download links, which are returned by the Copilot Usage Metrics API , use the new domain copilot-reports.github.com\
  \ instead of the previous copilot-reports-*.b01.azurefd.net pattern.\n\n\n github.com (GHEC) customers:\n\n\n\n\n\n\n Previous\n\
  \ New\n\n\n\n\n Report download URL pattern\n https://copilot-reports-*.b01.azurefd.net/...\n https://copilot-reports.github.com/...\n\
  \n\n\n ghe.com customers:\n\n\n\n\n\n\n Previous\n New\n\n\n\n\n Report download URL pattern\n https://copilot-reports-*.b01.azurefd.net/...\n\
  \ https://copilot-reports.*.ghe.com/...\n\n\n\n What you need to do\n If your organization uses a firewall or proxy allowlist,\
  \ add the following domain:\n\n\n\n github.com: https://copilot-reports.github.com\n ghe.com: https://copilot-reports.SUBDOMAIN.ghe.com\
  \ , where SUBDOMAIN is your enterprise’s dedicated subdomain on GHE.com\n\n The legacy copilot-reports-*.b01.azurefd.net\
  \ pattern will continue to work during a transition period, but will eventually be deprecated. We recommend updating your\
  \ allowlists as soon as possible.\n\n\n\n Note: In rare cases where Azure Front Door is unavailable, report downloads may\
  \ fall back to direct Azure Blob Storage URLs ( *.blob.core.windows.net ). If your organization requires uninterrupted access\
  \ to reports during such events, you should also ensure *.blob.core.windows.net is in your allowlist.\n\n\n\n Why we made\
  \ this change\n The previous Azure Front Door domains were infrastructure-specific and could change when services were redeployed\
  \ or reconfigured. Moving to a stable, GitHub-owned domain ensures that:\n\n\n\n Report download URLs remain constant regardless\
  \ of infrastructure changes.\n Enterprise security teams have a predictable, trustworthy domain to allowlist.\n Automation\
  \ scripts and integrations are not disrupted by domain changes.\n\n For more information, see the Copilot allowlist reference\
  \ .\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post Copilot usage metrics reports now use GitHub-owned\
  \ download URLs appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
