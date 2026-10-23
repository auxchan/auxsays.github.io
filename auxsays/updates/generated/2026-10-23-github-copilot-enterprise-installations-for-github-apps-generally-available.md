---
layout: aux-update
title: GitHub / Copilot Enterprise installations for GitHub Apps generally available official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Enterprise installations for GitHub Apps generally
  available.
permalink: /updates/github/github/enterprise-installations-for-github-apps-generally-available/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-23-enterprise-installations-for-github-apps-generally-available
update_download_url: ''
update_version: Enterprise installations for GitHub Apps generally available
update_logo_text: GIT
update_published_at: '2026-10-23T15:03:30Z'
update_last_checked: '2026-10-23T19:54:21Z'
source_last_checked: '2026-10-23T19:54:21Z'
official_body_last_checked: '2026-10-23T19:54:21Z'
record_last_updated: '2026-10-23T19:54:21Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Enterprise installations for GitHub Apps generally available
update_detail_title: GitHub / Copilot Enterprise installations for GitHub Apps generally available
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Enterprise installations for GitHub Apps generally available has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Enterprise installations for GitHub Apps generally available.
release_summary: "Installing GitHub Apps on your enterprise is now generally available. You can replace classic PATs with\
  \ GitHub Apps in more of your enterprise and organization automation with the expanded API support detailed below. These\
  \ new and expanded permissions are focused on governance, security, and administrative settings for your enterprise, with\
  \ two gaps at the organization level also closed.\n\n\n What’s new for GitHub Apps\n\n Governance: Manage enterprise-level\
  \ repository policies and rulesets as well as read delegated bypass requests.\n Security: Configure two-factor authentication\
  \ requirements, verify domains, manage IP allowlists, and control enterprise access restrictions.\n Administration: Update\
  \ enterprise profiles and manage both member privileges and repository access settings across the enterprise.\n\n New permissions\
  \ and API coverage\n Choose the permissions your workflow needs in your GitHub App settings.\n\n\n\n\n\n Permission\n Access\n\
  \ Newly supported APIs and GraphQL data\n\n\n\n\n Enterprise organization and repository policies\n Read/write\n Read policy\
  \ fields on EnterpriseOwnerInfo . Update private repository forking , default repository permissions , repository visibility\
  \ changes , repository creation , repository deletion , issue deletion , collaborator invitations , deploy keys , protected\
  \ branch updates , dependency insights setting , organization projects setting , and repository projects .\n\n\n Enterprise\
  \ bypass requests\n Read\n Read push-rule and repository-policy bypass requests .\n\n\n Enterprise settings\n Read/write\n\
  \ Read enterprise data through EnterpriseOwnerInfo , including server installations and organization invitations. Update\
  \ the enterprise profile . Read is required for access to the enterprise organization and repository policies.\n\n\n Enterprise\
  \ two-factor authentication\n Read/write\n Read two-factor fields on EnterpriseOwnerInfo . Update two-factor requirements\
  \ and disallowed authentication methods .\n\n\n Enterprise verifiable domains; organization verifiable domains\n Write\n\
  \ Access VerifiableDomain s for enterprises or organizations.\n\n\n Enterprise IP allowlist; organization IP allowlist\n\
  \ Read/write\n Access IpAllowListEntry and associated mutations to create, update, and delete entries on an enterprise or\
  \ organization IP allowlist. Also toggle allowlist enforcement, trust of GitHub Apps, and user-level enforcement for Enterprise\
  \ Managed Users.\n\n\n Enterprise access restrictions\n Write\n Enable or disable enterprise access restrictions .\n\n\n\
  \ Enterprise repository rulesets\n Write\n Manage rulesets through the enterprise rules REST APIs and RepositoryRuleset\
  \ in GraphQL .\n\n\n\n More coverage with existing permissions\n Some APIs and objects had gaps in their support for GitHub\
  \ Apps. These fixes should unblock more automation scenarios with those permissions.\n\n\n\n\n\n Permission\n Access\n Newly\
  \ supported APIs and GraphQL data\n\n\n\n\n Enterprise people\n Read/write\n Read EnterpriseRepositoryInfo , including repository\
  \ details through EnterpriseOwnerInfo.outsideCollaborators . Add yourself to an organization with the owner or member role\
  \ .\n\n\n Enterprise billing\n Write\n Update the member purchasing setting for the Marketplace.\n\n\n\n To get started,\
  \ choose permissions for your GitHub App for the workflows you want to migrate.\n\n\n These updates will be available in\
  \ GHES 3.24. For details on using GraphQL with a GitHub App, see Managing an enterprise account with GraphQL . To learn\
  \ more about enterprise app installations, see Installing a GitHub App on your enterprise .\n\n\n\n The post Enterprise\
  \ installations for GitHub Apps generally available appeared first on The GitHub Blog ."
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
- at: '2026-10-23T15:03:30Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-23T19:54:29Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-23-enterprise-installations-for-github-apps-generally-available
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-23T19:54:21Z'
  url: https://github.blog/changelog/2026-10-23-enterprise-installations-for-github-apps-generally-available
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Installing GitHub Apps on your enterprise is now generally available. You can replace classic\
  \ PATs with GitHub Apps in more of your enterprise and organization automation with the expanded API support detailed below.\
  \ These new and expanded permissions are focused on governance, security, and administrative settings for your enterprise,\
  \ with two gaps at the organization level also closed.\n\n\n What’s new for GitHub Apps\n\n Governance: Manage enterprise-level\
  \ repository policies and rulesets as well as read delegated bypass requests.\n Security: Configure two-factor authentication\
  \ requirements, verify domains, manage IP allowlists, and control enterprise access restrictions.\n Administration: Update\
  \ enterprise profiles and manage both member privileges and repository access settings across the enterprise.\n\n New permissions\
  \ and API coverage\n Choose the permissions your workflow needs in your GitHub App settings.\n\n\n\n\n\n Permission\n Access\n\
  \ Newly supported APIs and GraphQL data\n\n\n\n\n Enterprise organization and repository policies\n Read/write\n Read policy\
  \ fields on EnterpriseOwnerInfo . Update private repository forking , default repository permissions , repository visibility\
  \ changes , repository creation , repository deletion , issue deletion , collaborator invitations , deploy keys , protected\
  \ branch updates , dependency insights setting , organization projects setting , and repository projects .\n\n\n Enterprise\
  \ bypass requests\n Read\n Read push-rule and repository-policy bypass requests .\n\n\n Enterprise settings\n Read/write\n\
  \ Read enterprise data through EnterpriseOwnerInfo , including server installations and organization invitations. Update\
  \ the enterprise profile . Read is required for access to the enterprise organization and repository policies.\n\n\n Enterprise\
  \ two-factor authentication\n Read/write\n Read two-factor fields on EnterpriseOwnerInfo . Update two-factor requirements\
  \ and disallowed authentication methods .\n\n\n Enterprise verifiable domains; organization verifiable domains\n Write\n\
  \ Access VerifiableDomain s for enterprises or organizations.\n\n\n Enterprise IP allowlist; organization IP allowlist\n\
  \ Read/write\n Access IpAllowListEntry and associated mutations to create, update, and delete entries on an enterprise or\
  \ organization IP allowlist. Also toggle allowlist enforcement, trust of GitHub Apps, and user-level enforcement for Enterprise\
  \ Managed Users.\n\n\n Enterprise access restrictions\n Write\n Enable or disable enterprise access restrictions .\n\n\n\
  \ Enterprise repository rulesets\n Write\n Manage rulesets through the enterprise rules REST APIs and RepositoryRuleset\
  \ in GraphQL .\n\n\n\n More coverage with existing permissions\n Some APIs and objects had gaps in their support for GitHub\
  \ Apps. These fixes should unblock more automation scenarios with those permissions.\n\n\n\n\n\n Permission\n Access\n Newly\
  \ supported APIs and GraphQL data\n\n\n\n\n Enterprise people\n Read/write\n Read EnterpriseRepositoryInfo , including repository\
  \ details through EnterpriseOwnerInfo.outsideCollaborators . Add yourself to an organization with the owner or member role\
  \ .\n\n\n Enterprise billing\n Write\n Update the member purchasing setting for the Marketplace.\n\n\n\n To get started,\
  \ choose permissions for your GitHub App for the workflows you want to migrate.\n\n\n These updates will be available in\
  \ GHES 3.24. For details on using GraphQL with a GitHub App, see Managing an enterprise account with GraphQL . To learn\
  \ more about enterprise app installations, see Installing a GitHub App on your enterprise .\n\n\n\n The post Enterprise\
  \ installations for GitHub Apps generally available appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
