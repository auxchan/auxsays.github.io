---
layout: aux-update
title: GitHub / Copilot GitHub package firewall in public preview official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for GitHub package firewall in public preview.
permalink: /updates/github/github/github-package-firewall-in-public-preview/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-20-github-package-firewall-in-public-preview
update_download_url: ''
update_version: GitHub package firewall in public preview
update_logo_text: GIT
update_published_at: '2026-10-20T16:11:53Z'
update_last_checked: '2026-10-21T00:20:53Z'
source_last_checked: '2026-10-21T00:20:53Z'
official_body_last_checked: '2026-10-21T00:20:53Z'
record_last_updated: '2026-10-21T00:20:53Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub package firewall in public preview
update_detail_title: GitHub / Copilot GitHub package firewall in public preview
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub package firewall in public preview has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub package firewall in public preview.
release_summary: "An increasing number of malware attacks exploit systems at package installation time, harvesting credentials\
  \ on CI/CD hosts or developer workstations without even running the package’s code. To stem this tide of attacks, GitHub\
  \ is introducing a new package firewall capability. The package firewall sits between endpoints like Actions runners or\
  \ coding agents and the upstream package repositories, inspecting both metadata requests and package downloads for signs\
  \ of malicious activity. The package firewall is available today in public preview for all GitHub Enterprise Cloud customers,\
  \ including data-resident GitHub Enterprise Cloud.\n\n\n How it works\n First, administrators set policy controls for their\
  \ enterprise. The controls available today include a configurable cooldown period, checking the GitHub Advisory Database\
  \ for malware or vulnerability alerts, and supply-chain checks like attestation downgrades.\n\n\n Then endpoints like coding\
  \ agents and CI/CD hosts need configuration to use the firewall for their requests instead of pointing directly at the upstream\
  \ package registries. Metadata requests for package lists as well as the actual package downloads then flow through the\
  \ firewall, which evaluates them against the policy. If a package is blocked erroneously, the user can request an exception\
  \ with a workflow similar to other GitHub Advanced Security features.\n\n\n Availability and limitations\n The package firewall\
  \ is available in public preview as we scale up the infrastructure behind it and continue to add features based on customer\
  \ demand. It is available to GitHub Enterprise Cloud customers, including GitHub Enterprise Cloud with data residency. The\
  \ service is free while in the preview period. When it reaches general availability, it will be charged based on metered\
  \ usage, similar to Actions billing.\n\n\n Currently the package firewall only supports npm packages.\n\n\n How to use it\n\
  \ For detailed setup instructions, see Protecting endpoints with package firewall . Join the discussion in GitHub Community\
  \ .\n\n\n\n The post GitHub package firewall in public preview appeared first on The GitHub Blog ."
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
- at: '2026-10-20T16:11:53Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-21T00:21:04Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-20-github-package-firewall-in-public-preview
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-21T00:20:53Z'
  url: https://github.blog/changelog/2026-10-20-github-package-firewall-in-public-preview
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "An increasing number of malware attacks exploit systems at package installation time, harvesting\
  \ credentials on CI/CD hosts or developer workstations without even running the package’s code. To stem this tide of attacks,\
  \ GitHub is introducing a new package firewall capability. The package firewall sits between endpoints like Actions runners\
  \ or coding agents and the upstream package repositories, inspecting both metadata requests and package downloads for signs\
  \ of malicious activity. The package firewall is available today in public preview for all GitHub Enterprise Cloud customers,\
  \ including data-resident GitHub Enterprise Cloud.\n\n\n How it works\n First, administrators set policy controls for their\
  \ enterprise. The controls available today include a configurable cooldown period, checking the GitHub Advisory Database\
  \ for malware or vulnerability alerts, and supply-chain checks like attestation downgrades.\n\n\n Then endpoints like coding\
  \ agents and CI/CD hosts need configuration to use the firewall for their requests instead of pointing directly at the upstream\
  \ package registries. Metadata requests for package lists as well as the actual package downloads then flow through the\
  \ firewall, which evaluates them against the policy. If a package is blocked erroneously, the user can request an exception\
  \ with a workflow similar to other GitHub Advanced Security features.\n\n\n Availability and limitations\n The package firewall\
  \ is available in public preview as we scale up the infrastructure behind it and continue to add features based on customer\
  \ demand. It is available to GitHub Enterprise Cloud customers, including GitHub Enterprise Cloud with data residency. The\
  \ service is free while in the preview period. When it reaches general availability, it will be charged based on metered\
  \ usage, similar to Actions billing.\n\n\n Currently the package firewall only supports npm packages.\n\n\n How to use it\n\
  \ For detailed setup instructions, see Protecting endpoints with package firewall . Join the discussion in GitHub Community\
  \ .\n\n\n\n The post GitHub package firewall in public preview appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
