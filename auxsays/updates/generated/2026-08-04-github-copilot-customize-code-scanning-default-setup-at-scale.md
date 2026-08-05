---
layout: aux-update
title: GitHub / Copilot Customize code scanning default setup at scale official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/customize-code-scanning-default-setup-at-scale/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-04-customize-code-scanning-default-setup-at-scale
update_download_url: ''
update_version: Customize code scanning default setup at scale
update_logo_text: GIT
update_published_at: '2026-08-04T19:15:23Z'
update_last_checked: '2026-08-05T07:31:35Z'
source_last_checked: '2026-08-05T07:31:35Z'
official_body_last_checked: '2026-08-05T07:31:35Z'
record_last_updated: '2026-08-05T07:31:35Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Customize code scanning default setup at scale
update_detail_title: GitHub / Copilot Customize code scanning default setup at scale
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Customize code scanning default setup at scale has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Customize code scanning default setup at scale.
release_summary: "You can now apply your own configuration file to code scanning default setup, using the new github-codeql-config-file\
  \ repository property. This gives you control over how CodeQL scans your code for security vulnerabilities, whether that’s\
  \ on one repository or across your whole organization. We recommend using this way to customize your security analysis at\
  \ scale. You get the granular control of advanced setup without writing or maintaining a GitHub Actions workflow file in\
  \ every repository.\n\n\n Apply a custom configuration file to default setup\n Set the github-codeql-config-file repository\
  \ property to the path of a CodeQL configuration file, and code scanning now merges your settings with its built-in defaults.\
  \ You can add queries, exclude paths, or set threat models, and still keep default setup’s low-maintenance benefits. Any\
  \ threat models and CodeQL model packs you picked in the default setup user interface are kept in the merged configuration.\n\
  \n\n Repository properties support organization-wide default values, and organization owners decide whether individual repositories\
  \ are allowed to override it. So you can keep one configuration file in a central repository and have every repository automatically\
  \ pick it up, enforce it everywhere, or let teams tailor it where they need to. You can also try a value out on one repository\
  \ before rolling it out. For more information, see customizing default setup with a configuration file .\n\n\n How to use\
  \ configuration files from other repositories\n There’s a new, more flexible syntax for pointing at a configuration file\
  \ that lives in another repository. Only the repository name is required. If you leave out the ref and the file path, the\
  \ reference falls back to a default configuration file path on the main branch of a repository in the same organization\
  \ as the one being analyzed. For more information, see how to reference a configuration file in another repository .\n\n\
  \n If that repository is private, you can now grant default setup access to it by configuring a Git Source private registry\
  \ for your organization, instead of managing a token in a workflow. For more information, see giving your organization access\
  \ to private registries .\n\n\n This is now generally available on github.com and will ship with GitHub Enterprise Server\
  \ 3.23. To get started, see repository properties for code scanning .\n\n\n\n The post Customize code scanning default setup\
  \ at scale appeared first on The GitHub Blog ."
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
- at: '2026-08-04T19:15:23Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-05T07:31:40Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-04-customize-code-scanning-default-setup-at-scale
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-05T07:31:35Z'
  url: https://github.blog/changelog/2026-08-04-customize-code-scanning-default-setup-at-scale
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "You can now apply your own configuration file to code scanning default setup, using the new github-codeql-config-file\
  \ repository property. This gives you control over how CodeQL scans your code for security vulnerabilities, whether that’s\
  \ on one repository or across your whole organization. We recommend using this way to customize your security analysis at\
  \ scale. You get the granular control of advanced setup without writing or maintaining a GitHub Actions workflow file in\
  \ every repository.\n\n\n Apply a custom configuration file to default setup\n Set the github-codeql-config-file repository\
  \ property to the path of a CodeQL configuration file, and code scanning now merges your settings with its built-in defaults.\
  \ You can add queries, exclude paths, or set threat models, and still keep default setup’s low-maintenance benefits. Any\
  \ threat models and CodeQL model packs you picked in the default setup user interface are kept in the merged configuration.\n\
  \n\n Repository properties support organization-wide default values, and organization owners decide whether individual repositories\
  \ are allowed to override it. So you can keep one configuration file in a central repository and have every repository automatically\
  \ pick it up, enforce it everywhere, or let teams tailor it where they need to. You can also try a value out on one repository\
  \ before rolling it out. For more information, see customizing default setup with a configuration file .\n\n\n How to use\
  \ configuration files from other repositories\n There’s a new, more flexible syntax for pointing at a configuration file\
  \ that lives in another repository. Only the repository name is required. If you leave out the ref and the file path, the\
  \ reference falls back to a default configuration file path on the main branch of a repository in the same organization\
  \ as the one being analyzed. For more information, see how to reference a configuration file in another repository .\n\n\
  \n If that repository is private, you can now grant default setup access to it by configuring a Git Source private registry\
  \ for your organization, instead of managing a token in a workflow. For more information, see giving your organization access\
  \ to private registries .\n\n\n This is now generally available on github.com and will ship with GitHub Enterprise Server\
  \ 3.23. To get started, see repository properties for code scanning .\n\n\n\n The post Customize code scanning default setup\
  \ at scale appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
