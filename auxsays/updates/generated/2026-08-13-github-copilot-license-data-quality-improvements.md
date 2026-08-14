---
layout: aux-update
title: GitHub / Copilot License data quality improvements official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/license-data-quality-improvements/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-13-license-data-quality-improvements
update_download_url: ''
update_version: License data quality improvements
update_logo_text: GIT
update_published_at: '2026-08-13T19:14:12Z'
update_last_checked: '2026-08-13T20:28:29Z'
source_last_checked: '2026-08-14T09:00:48Z'
official_body_last_checked: '2026-08-14T09:00:48Z'
record_last_updated: '2026-08-13T20:28:29Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot License data quality improvements
update_detail_title: GitHub / Copilot License data quality improvements
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot License data quality improvements has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot License data quality improvements.
release_summary: "GitHub now uses package registries like npmjs.org and PyPI to determine license information for software\
  \ components in the dependency graph. This improves the accuracy and completeness of the licenses shown in dependency insights,\
  \ software bills of materials (SBOMs), the open source license compliance feature in GitHub Advanced Security, and the dependency\
  \ review action.\n\n\n Previously, the primary source of license information on GitHub was the ClearlyDefined service .\
  \ While we still use and contribute to ClearlyDefined, we’ve found that its focus on depth-first file scanning led to complex\
  \ results that users found confusing. We’ll still fall back to ClearlyDefined data, but will now prioritize license information\
  \ from the package registries. Early results show that we’ve cut the number of missing licenses in half, from 45% of the\
  \ 170 million packages in the dependency graph down to 24%. Additionally, the system now tracks version ranges instead of\
  \ requiring a specific database entry for every version, so the actual coverage will be higher.\n\n\n To explain further,\
  \ the dependency graph service now uses metadata from the canonical registry for a given package ecosystem, as described\
  \ in the following table.\n\n\n\n\n\n Package Manager\n Registry\n\n\n\n\n npm\n npmjs.org\n\n\n NuGet\n nuget.org\n\n\n\
  \ Python\n pypi.org\n\n\n Rubygems\n rubygems.org\n\n\n Rust\n crates.io\n\n\n Go\n pkg.go.dev\n\n\n Maven\n deps.dev\n\n\
  \n Dart\n pub.dev\n\n\n PHP\n packagist.org\n\n\n\n The dependency graph service keeps license history based on version\
  \ ranges. For example, Grafana, which relicensed from Apache to AGPL, has two entries: one covering 1.0.0 through 7.5.17\
  \ for Apache-2.0, and one from 8.0.0 or newer for AGPLv3. This both reduces the complexity of the database and provides\
  \ license information for new versions without requiring each one to be added explicitly.\n\n\n Updated license information\
  \ is available now across all of GitHub.\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post License data\
  \ quality improvements appeared first on The GitHub Blog ."
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
- at: '2026-08-13T19:14:12Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-13T20:28:34Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-13-license-data-quality-improvements
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-13T20:28:29Z'
  url: https://github.blog/changelog/2026-08-13-license-data-quality-improvements
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-14T03:54:24Z'
  url: https://github.blog/changelog/2026-08-13-license-data-quality-improvements
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-14T09:00:48Z'
  url: https://github.blog/changelog/2026-08-13-license-data-quality-improvements
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub now uses package registries like npmjs.org and PyPI to determine license information for\
  \ software components in the dependency graph. This improves the accuracy and completeness of the licenses shown in dependency\
  \ insights, software bills of materials (SBOMs), the open source license compliance feature in GitHub Advanced Security,\
  \ and the dependency review action.\n\n\n Previously, the primary source of license information on GitHub was the ClearlyDefined\
  \ service . While we still use and contribute to ClearlyDefined, we’ve found that its focus on depth-first file scanning\
  \ led to complex results that users found confusing. We’ll still fall back to ClearlyDefined data, but will now prioritize\
  \ license information from the package registries. Early results show that we’ve cut the number of missing licenses in half,\
  \ from 45% of the 170 million packages in the dependency graph down to 24%. Additionally, the system now tracks version\
  \ ranges instead of requiring a specific database entry for every version, so the actual coverage will be higher.\n\n\n\
  \ To explain further, the dependency graph service now uses metadata from the canonical registry for a given package ecosystem,\
  \ as described in the following table.\n\n\n\n\n\n Package Manager\n Registry\n\n\n\n\n npm\n npmjs.org\n\n\n NuGet\n nuget.org\n\
  \n\n Python\n pypi.org\n\n\n Rubygems\n rubygems.org\n\n\n Rust\n crates.io\n\n\n Go\n pkg.go.dev\n\n\n Maven\n deps.dev\n\
  \n\n Dart\n pub.dev\n\n\n PHP\n packagist.org\n\n\n\n The dependency graph service keeps license history based on version\
  \ ranges. For example, Grafana, which relicensed from Apache to AGPL, has two entries: one covering 1.0.0 through 7.5.17\
  \ for Apache-2.0, and one from 8.0.0 or newer for AGPLv3. This both reduces the complexity of the database and provides\
  \ license information for new versions without requiring each one to be added explicitly.\n\n\n Updated license information\
  \ is available now across all of GitHub.\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post License data\
  \ quality improvements appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
