---
layout: aux-update
title: GitHub / Copilot GitHub App improvements for least privilege and management official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for GitHub App improvements for least privilege
  and management.
permalink: /updates/github/github/github-app-improvements-for-least-privilege-and-management/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-13-github-app-improvements-for-least-privilege-and-management
update_download_url: ''
update_version: GitHub App improvements for least privilege and management
update_logo_text: GIT
update_published_at: '2026-10-13T23:17:55Z'
update_last_checked: '2026-10-14T01:25:29Z'
source_last_checked: '2026-10-15T00:29:19Z'
official_body_last_checked: '2026-10-15T00:29:19Z'
record_last_updated: '2026-10-14T01:25:29Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub App improvements for least privilege and management
update_detail_title: GitHub / Copilot GitHub App improvements for least privilege and management
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub App improvements for least privilege and management has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub App improvements for least privilege and management.
release_summary: "We’re releasing several GitHub Apps improvements today that help developers move off of classic PATs, improve\
  \ GitHub App management, and request fewer sensitive permissions. We’ve also made it easier for repository administrators\
  \ to use apps that their administrators have approved and updated the GitHub App credential management UI in advance of\
  \ our planned workload federation features.\n\n\n New repository creation and installation management permissions\n Two\
  \ new repository fine-grained permissions have been added, available to both fine-grained PATs and GitHub Apps.\n\n\n\n\
  \ repository_creation:write : Allows the caller to create a repository in the account where it’s granted.\n installation_repositories:\
  \ write : Allows the caller to add or remove that repository from an installation in the organization.\n\n\n\n\n Create\
  \ a repository without repository_administration\n You can now use the repository_creation:write permission to create repositories\
  \ without needing the broader repository_administration:write permission.\n\n\n Previously, an app or PAT needed repository_administration:write\
  \ to create a repository. That permission also grants other repository administration features like deletion and transfer.\
  \ This could lead to administrators rejecting apps, banning PATs with this permission, or having to accept the over-privilege\
  \ risk.\n\n\n The new permission supports a least-privilege approach by granting only the ability to create repositories.\
  \ When the repository is created, the app or user that created it will be given access to it. An app using this permission\
  \ still requires an organization administrator to install the app.\n\n\n See the API docs for repository creation in organizations\
  \ , from a template , for the current user , with a fork , and via GraphQL .\n\n\n Manage installation repositories with\
  \ an app or fine-grained PAT\n The Add a repository to an installation organization-level API and its corresponding removal\
  \ API now support GitHub Apps and fine-grained PATs. Previously, these APIs only supported the coarse-grained repo scope.\n\
  \n\n These APIs support a new repository-level fine-grained permission: installation_repositories:write . Having this permission\
  \ on a repository allows the caller to add or remove that repository from any installation in the organization. If the caller\
  \ is a user, they must also be an organization owner or an administrator on the repository in question.\n\n\n This allows\
  \ organizations to build automation that controls which repositories are accessible to which GitHub Apps without relying\
  \ on an administrator’s PAT with broad permissions.\n\n\n Repository administrators can more easily add approved GitHub\
  \ Apps to repositories\n Historically, all apps that requested organization-level access were blocked from being installed\
  \ on a repository by a repository administrator, no matter what. This restriction has been relaxed in the case where the\
  \ app is already installed in the organization, meaning it’s been approved by an organization owner for that organization-level\
  \ access. Repository administrators can now edit an existing installation to add their repositories to an app without requiring\
  \ organization owner approval. The apps already have the organization-level access, so adding them to another repository\
  \ in the organization doesn’t increase that access or give the repository administrator additional privileges.\n\n\n With\
  \ the addition of the repository_creation permission above, there are now three sensitive permission sets that require organization\
  \ owner approval:\n\n\n\n All organization-level permissions\n Repository administration\n Repository creation\n\n This\
  \ change allows repository administrators to better use apps that are already approved for use in their organization.\n\n\
  \n If you’d like to prevent repository administrators from adding apps to their repositories, see “ Restricting GitHub App\
  \ Installation to Organization Owners ” in the docs. For more details on adding an app to a repository, see “ Installing\
  \ a GitHub App “.\n\n\n Use offline_access with GitHub Apps to gradually reenable short-lived, rotating tokens\n GitHub\
  \ Apps now support the offline_access scope, like OAuth apps. While GitHub Apps use short-lived, rotating tokens by default,\
  \ some developers have disabled expiration for convenience and now struggle to reenable it.\n\n\n This support helps app\
  \ developers gradually migrate to expiring user access tokens. Developers can enable token expiration for testing and rollout\
  \ without having to switch every user to expiring tokens at the same time, which would break existing clients.\n\n\n When\
  \ offline_access is requested, the app receives a refresh token in addition to the expiring access token. It only changes\
  \ that specific authentication and doesn’t impact future sessions.\n\n\n The scope parameter is still otherwise unused for\
  \ GitHub Apps—permissions are still statically selected on the application registration. For more details, see “ Refreshing\
  \ user access tokens “.\n\n\n This is available in GHES 3.23.\n\n\n GitHub Apps can fetch details about other private and\
  \ internal apps\n GitHub Apps can now use the Get an app API to fetch details about private and internal GitHub Apps, as\
  \ long as they share some ownership.\n\n\n The permitted access patterns are:\n\n\n\n Public apps: Any other app can fetch\
  \ the app’s details. This was the previously enabled level of access.\n Apps in the same organization: Apps can fetch each\
  \ other’s details regardless of visibility, if they share the same owner.\n Internal apps in the same enterprise: An internal\
  \ app’s details can be fetched by another app in the same enterprise, even across organization boundaries.\n Enterprise-to-organization\
  \ access: An enterprise-owned app can fetch details about apps owned by organizations in the same enterprise.\n\n This enables\
  \ organizations and enterprises to automate more of their GitHub App auditing and administration.\n\n\n For more details\
  \ about app visibility, see “ Making a GitHub App public or private “.\n\n\n A new credential management tab for GitHub\
  \ Apps\n GitHub App credentials are now managed from a dedicated Credentials tab instead of appearing inline with the rest\
  \ of the app configuration. This makes credentials easier to find and manage, and sets aside space for our upcoming workload\
  \ federation credentials.\n\n\n\n\n\n These improvements will be available in GHES 3.24, with the exception of offline_access\
  \ support, which will be included in GHES 3.23.\n\n\n Let us know what you think in the GitHub Community .\n\n\n\n The post\
  \ GitHub App improvements for least privilege and management appeared first on The GitHub Blog ."
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
- at: '2026-10-13T23:17:55Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-14T01:25:34Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-13-github-app-improvements-for-least-privilege-and-management
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-14T01:25:29Z'
  url: https://github.blog/changelog/2026-10-13-github-app-improvements-for-least-privilege-and-management
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-14T07:24:48Z'
  url: https://github.blog/changelog/2026-10-13-github-app-improvements-for-least-privilege-and-management
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-14T14:31:10Z'
  url: https://github.blog/changelog/2026-10-13-github-app-improvements-for-least-privilege-and-management
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-14T19:51:40Z'
  url: https://github.blog/changelog/2026-10-13-github-app-improvements-for-least-privilege-and-management
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-10-15T00:29:19Z'
  url: https://github.blog/changelog/2026-10-13-github-app-improvements-for-least-privilege-and-management
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "We’re releasing several GitHub Apps improvements today that help developers move off of classic\
  \ PATs, improve GitHub App management, and request fewer sensitive permissions. We’ve also made it easier for repository\
  \ administrators to use apps that their administrators have approved and updated the GitHub App credential management UI\
  \ in advance of our planned workload federation features.\n\n\n New repository creation and installation management permissions\n\
  \ Two new repository fine-grained permissions have been added, available to both fine-grained PATs and GitHub Apps.\n\n\n\
  \n repository_creation:write : Allows the caller to create a repository in the account where it’s granted.\n installation_repositories:\
  \ write : Allows the caller to add or remove that repository from an installation in the organization.\n\n\n\n\n Create\
  \ a repository without repository_administration\n You can now use the repository_creation:write permission to create repositories\
  \ without needing the broader repository_administration:write permission.\n\n\n Previously, an app or PAT needed repository_administration:write\
  \ to create a repository. That permission also grants other repository administration features like deletion and transfer.\
  \ This could lead to administrators rejecting apps, banning PATs with this permission, or having to accept the over-privilege\
  \ risk.\n\n\n The new permission supports a least-privilege approach by granting only the ability to create repositories.\
  \ When the repository is created, the app or user that created it will be given access to it. An app using this permission\
  \ still requires an organization administrator to install the app.\n\n\n See the API docs for repository creation in organizations\
  \ , from a template , for the current user , with a fork , and via GraphQL .\n\n\n Manage installation repositories with\
  \ an app or fine-grained PAT\n The Add a repository to an installation organization-level API and its corresponding removal\
  \ API now support GitHub Apps and fine-grained PATs. Previously, these APIs only supported the coarse-grained repo scope.\n\
  \n\n These APIs support a new repository-level fine-grained permission: installation_repositories:write . Having this permission\
  \ on a repository allows the caller to add or remove that repository from any installation in the organization. If the caller\
  \ is a user, they must also be an organization owner or an administrator on the repository in question.\n\n\n This allows\
  \ organizations to build automation that controls which repositories are accessible to which GitHub Apps without relying\
  \ on an administrator’s PAT with broad permissions.\n\n\n Repository administrators can more easily add approved GitHub\
  \ Apps to repositories\n Historically, all apps that requested organization-level access were blocked from being installed\
  \ on a repository by a repository administrator, no matter what. This restriction has been relaxed in the case where the\
  \ app is already installed in the organization, meaning it’s been approved by an organization owner for that organization-level\
  \ access. Repository administrators can now edit an existing installation to add their repositories to an app without requiring\
  \ organization owner approval. The apps already have the organization-level access, so adding them to another repository\
  \ in the organization doesn’t increase that access or give the repository administrator additional privileges.\n\n\n With\
  \ the addition of the repository_creation permission above, there are now three sensitive permission sets that require organization\
  \ owner approval:\n\n\n\n All organization-level permissions\n Repository administration\n Repository creation\n\n This\
  \ change allows repository administrators to better use apps that are already approved for use in their organization.\n\n\
  \n If you’d like to prevent repository administrators from adding apps to their repositories, see “ Restricting GitHub App\
  \ Installation to Organization Owners ” in the docs. For more details on adding an app to a repository, see “ Installing\
  \ a GitHub App “.\n\n\n Use offline_access with GitHub Apps to gradually reenable short-lived, rotating tokens\n GitHub\
  \ Apps now support the offline_access scope, like OAuth apps. While GitHub Apps use short-lived, rotating tokens by default,\
  \ some developers have disabled expiration for convenience and now struggle to reenable it.\n\n\n This support helps app\
  \ developers gradually migrate to expiring user access tokens. Developers can enable token expiration for testing and rollout\
  \ without having to switch every user to expiring tokens at the same time, which would break existing clients.\n\n\n When\
  \ offline_access is requested, the app receives a refresh token in addition to the expiring access token. It only changes\
  \ that specific authentication and doesn’t impact future sessions.\n\n\n The scope parameter is still otherwise unused for\
  \ GitHub Apps—permissions are still statically selected on the application registration. For more details, see “ Refreshing\
  \ user access tokens “.\n\n\n This is available in GHES 3.23.\n\n\n GitHub Apps can fetch details about other private and\
  \ internal apps\n GitHub Apps can now use the Get an app API to fetch details about private and internal GitHub Apps, as\
  \ long as they share some ownership.\n\n\n The permitted access patterns are:\n\n\n\n Public apps: Any other app can fetch\
  \ the app’s details. This was the previously enabled level of access.\n Apps in the same organization: Apps can fetch each\
  \ other’s details regardless of visibility, if they share the same owner.\n Internal apps in the same enterprise: An internal\
  \ app’s details can be fetched by another app in the same enterprise, even across organization boundaries.\n Enterprise-to-organization\
  \ access: An enterprise-owned app can fetch details about apps owned by organizations in the same enterprise.\n\n This enables\
  \ organizations and enterprises to automate more of their GitHub App auditing and administration.\n\n\n For more details\
  \ about app visibility, see “ Making a GitHub App public or private “.\n\n\n A new credential management tab for GitHub\
  \ Apps\n GitHub App credentials are now managed from a dedicated Credentials tab instead of appearing inline with the rest\
  \ of the app configuration. This makes credentials easier to find and manage, and sets aside space for our upcoming workload\
  \ federation credentials.\n\n\n\n\n\n These improvements will be available in GHES 3.24, with the exception of offline_access\
  \ support, which will be included in GHES 3.23.\n\n\n Let us know what you think in the GitHub Community .\n\n\n\n The post\
  \ GitHub App improvements for least privilege and management appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
