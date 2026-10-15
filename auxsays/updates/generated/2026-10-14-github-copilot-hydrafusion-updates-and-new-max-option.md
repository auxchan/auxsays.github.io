---
layout: aux-update
title: GitHub / Copilot HydraFusion updates and new Max option official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for HydraFusion updates and new Max option.
permalink: /updates/github/github/hydrafusion-updates-and-new-max-option/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-14-hydrafusion-updates-and-new-max-option
update_download_url: ''
update_version: HydraFusion updates and new Max option
update_logo_text: GIT
update_published_at: '2026-10-14T20:01:35Z'
update_last_checked: '2026-10-15T00:29:19Z'
source_last_checked: '2026-10-15T07:07:37Z'
official_body_last_checked: '2026-10-15T07:07:37Z'
record_last_updated: '2026-10-15T00:29:19Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot HydraFusion updates and new Max option
update_detail_title: GitHub / Copilot HydraFusion updates and new Max option
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot HydraFusion updates and new Max option has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot HydraFusion updates and new Max option.
release_summary: "HydraFusion has an updated model pool, improved orchestration workflows, and introduces HydraFusion Max.\
  \ Both HydraFusion and HydraFusion Max are available across VS Code, the GitHub Copilot app, and GitHub Copilot CLI and\
  \ remain in research preview.\n\n\n HydraFusion orchestrates multiple models to produce a single response, bringing together\
  \ their strengths so you don’t have to choose an individual model for each task.\n\n\n What’s new in HydraFusion\n\n Latest\
  \ frontier models: HydraFusion and HydraFusion Max draw from a pool that now includes Claude Opus 5.5, GPT-6 Astra, GPT-6.1\
  \ Sol, and GPT-6 Luna. The models used for each task vary based on the orchestration workflow.\n Reasoning effort tailored\
  \ to each step: Previously, HydraFusion only used each model’s default reasoning effort. With this update, it explicitly\
  \ tailors effort to each stage, using medium effort for initial drafts and high effort for review. This keeps drafting efficient\
  \ while dedicating deeper reasoning to checking and improving the work.\n Optimized Cascade and Critique workflows:\n\n\
  \ Cascade: Previously used an initial model to solve the task, with escalation to a stronger model when needed. It can now\
  \ include a judging step that inspects the initial work and requests a repair only when needed.\n Critique: Previously relied\
  \ heavily on text summaries. It now relies more on tools to inspect the actual workspace directly. Critique now also uses\
  \ parallel critic models to inspect work.\n\n\n\n Introducing HydraFusion Max\n HydraFusion Max is built on the same architecture\
  \ and uses the same workflow techniques as HydraFusion, but is tuned for frontier capability on more demanding tasks. It\
  \ applies higher reasoning efforts where depth and thoroughness matter most, while still using orchestration to consider\
  \ token efficiency.\n\n\n\n\n\n Option\n Description\n Typical use case\n\n\n\n\n HydraFusion\n Balanced approach with moderate\
  \ token savings.\n Agentic tasks that require a balance of speed, cost, and performance.\n\n\n HydraFusion Max\n Frontier\
  \ capability for more demanding tasks, with token efficiency considered through orchestration.\n Tasks requiring the deepest\
  \ possible reasoning and most thorough analysis.\n\n\n\n Both options are supported across all three clients, so you can\
  \ access the latest HydraFusion experience whether you work in VS Code, the GitHub Copilot app, or the terminal.\n\n\n HydraFusion\
  \ and HydraFusion Max are available on Copilot Pro, Pro+, Business, and Enterprise plans with experimental or preview features\
  \ enabled, subject to your organization’s model policies.\n\n\n Learn more in the HydraFusion documentation .\n\n\n Share\
  \ your feedback in the HydraFusion discussion .\n\n\n\n The post HydraFusion updates and new Max option appeared first on\
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
- at: '2026-10-14T20:01:35Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-15T00:29:30Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-14-hydrafusion-updates-and-new-max-option
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-15T00:29:19Z'
  url: https://github.blog/changelog/2026-10-14-hydrafusion-updates-and-new-max-option
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-15T07:07:37Z'
  url: https://github.blog/changelog/2026-10-14-hydrafusion-updates-and-new-max-option
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "HydraFusion has an updated model pool, improved orchestration workflows, and introduces HydraFusion\
  \ Max. Both HydraFusion and HydraFusion Max are available across VS Code, the GitHub Copilot app, and GitHub Copilot CLI\
  \ and remain in research preview.\n\n\n HydraFusion orchestrates multiple models to produce a single response, bringing\
  \ together their strengths so you don’t have to choose an individual model for each task.\n\n\n What’s new in HydraFusion\n\
  \n Latest frontier models: HydraFusion and HydraFusion Max draw from a pool that now includes Claude Opus 5.5, GPT-6 Astra,\
  \ GPT-6.1 Sol, and GPT-6 Luna. The models used for each task vary based on the orchestration workflow.\n Reasoning effort\
  \ tailored to each step: Previously, HydraFusion only used each model’s default reasoning effort. With this update, it explicitly\
  \ tailors effort to each stage, using medium effort for initial drafts and high effort for review. This keeps drafting efficient\
  \ while dedicating deeper reasoning to checking and improving the work.\n Optimized Cascade and Critique workflows:\n\n\
  \ Cascade: Previously used an initial model to solve the task, with escalation to a stronger model when needed. It can now\
  \ include a judging step that inspects the initial work and requests a repair only when needed.\n Critique: Previously relied\
  \ heavily on text summaries. It now relies more on tools to inspect the actual workspace directly. Critique now also uses\
  \ parallel critic models to inspect work.\n\n\n\n Introducing HydraFusion Max\n HydraFusion Max is built on the same architecture\
  \ and uses the same workflow techniques as HydraFusion, but is tuned for frontier capability on more demanding tasks. It\
  \ applies higher reasoning efforts where depth and thoroughness matter most, while still using orchestration to consider\
  \ token efficiency.\n\n\n\n\n\n Option\n Description\n Typical use case\n\n\n\n\n HydraFusion\n Balanced approach with moderate\
  \ token savings.\n Agentic tasks that require a balance of speed, cost, and performance.\n\n\n HydraFusion Max\n Frontier\
  \ capability for more demanding tasks, with token efficiency considered through orchestration.\n Tasks requiring the deepest\
  \ possible reasoning and most thorough analysis.\n\n\n\n Both options are supported across all three clients, so you can\
  \ access the latest HydraFusion experience whether you work in VS Code, the GitHub Copilot app, or the terminal.\n\n\n HydraFusion\
  \ and HydraFusion Max are available on Copilot Pro, Pro+, Business, and Enterprise plans with experimental or preview features\
  \ enabled, subject to your organization’s model policies.\n\n\n Learn more in the HydraFusion documentation .\n\n\n Share\
  \ your feedback in the HydraFusion discussion .\n\n\n\n The post HydraFusion updates and new Max option appeared first on\
  \ The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
