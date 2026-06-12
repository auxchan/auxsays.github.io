---
layout: aux-update
title: 'GitHub / Copilot GitHub Actions: Minimum version enforcement timeline for self-hosted runners official update breakdown'
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/github-actions-minimum-version-enforcement-timeline-for-self-hosted-runners/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-12-github-actions-minimum-version-enforcement-timeline-for-self-hosted-runners
update_download_url: ''
update_version: 'GitHub Actions: Minimum version enforcement timeline for self-hosted runners'
update_logo_text: GIT
update_published_at: '2026-06-12T16:04:57Z'
update_last_checked: '2026-06-12T20:29:04Z'
source_last_checked: '2026-06-12T20:29:04Z'
official_body_last_checked: '2026-06-12T20:29:04Z'
record_last_updated: '2026-06-12T20:29:04Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot GitHub Actions: Minimum version enforcement timeline for self-hosted runners'
update_detail_title: 'GitHub / Copilot GitHub Actions: Minimum version enforcement timeline for self-hosted runners'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot GitHub Actions: Minimum version enforcement timeline for self-hosted runners has an official
  AUXSAYS record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot GitHub Actions: Minimum version enforcement timeline for self-hosted
  runners.'
release_summary: "GitHub Actions is resuming enforcement of version requirements for self-hosted runners on github.com and\
  \ GitHub Enterprise Cloud with Data Residency. This change is part of a broader effort to rebuild the core of GitHub Actions\
  \ to increase our reliability and availability. In early 2024, the Actions team began rearchitecting the backend services\
  \ that power job execution and runner communication—a foundational investment in the reliability, availability, and performance\
  \ our customers depend on. The new architecture now handles over 120 million jobs per day, more than three times the volume\
  \ before the migration, and enables enterprises to start seven times more jobs per minute than previously possible. Resuming\
  \ version enforcement is the next step in completing this migration: as all runners move onto the new platform, older runner\
  \ versions that are incompatible with the updated infrastructure can no longer be supported.\n\n\n There are two requirements\
  \ that together keep a runner compatible with the new platform:\n\n\n\n To configure or (re)register a runner: The runner\
  \ must be on version 2.329.0 or later. This is the minimum version required for the new architecture to recognize the runner\
  \ and allow it to connect.\n To continue executing workflow jobs: The runner must stay up to date by installing each new\
  \ runner release within 30 days of its publication. This is an existing requirement but was not consistently enforced in\
  \ some cases.\n\n Version 2.329.0 is only the minimum required to register with the new platform and receive updates. It\
  \ is not a permanent minimum version for running jobs. The effective minimum version for job execution moves forward over\
  \ time as new runner releases are published.\n\n\n Runners with auto-update enabled meet the 30-day requirement automatically,\
  \ as long as they can reach the update service.\n\n\n Runners with auto-update disabled must be upgraded manually on a regular\
  \ cadence. Meeting the registration minimum on its own isn’t enough. A runner pinned to 2.329.0 that never updates again\
  \ will not pick up jobs.\n\n\n Any release of the software, whether a major, minor, or patch version, qualifies as an available\
  \ update. If the runner is not updated within 30 days of an update being available, the GitHub Actions service will stop\
  \ queuing jobs to it. Additionally, when a critical security update is published, GitHub Actions will pause job queuing\
  \ to the runner until the update has been applied.\n\n\n Enforcement timeline\n Ahead of each enforcement date, Actions\
  \ will run temporary brownouts. Brownouts will start by intermittently blocking registration of unsupported runner versions,\
  \ then expand to also intermittently blocking job execution on unsupported runners. These brownouts help you identify outdated\
  \ runners and take action before enforcement begins.\n\n\n GitHub Enterprise Cloud with Data Residency: Full enforcement\
  \ begins July 31, 2026.\n\n\n GitHub Enterprise Cloud: Full enforcement begins September 25, 2026.\n\n\n After each enforcement\
  \ date:\n\n\n\n Self-hosted runners below the minimum version required for registration (e.g., runners older than 2.329)\
  \ won’t be able to register or reregister.\n Existing runners below the minimum version required to execute workflow jobs\
  \ (i.e., a higher version than the registration minimum) will stop running workflow jobs, even if they were previously registered.\n\
  \n\n All brownouts run from 11:00 AM to 3:00 PM ET on the dates listed below.\n\n\n\n GitHub Enterprise Cloud with Data\
  \ Residency\n Enforcement date: July 31, 2026\n\n\n\n\n\n Week\n Cadence\n Type\n Outcome\n Dates\n\n\n\n\n Week 1\n 1 day\n\
  \ Config\n Runners on older versions cannot be registered\n June 29\n\n\n Week 2\n 2 days\n Config\n Runners on older versions\
  \ cannot be registered\n July 6, July 8\n\n\n Week 3\n 3 days\n Config, and Config + Runtime\n Runners on older versions\
  \ cannot be registered; on the Config + Runtime day, they also will not execute jobs\n July 13 (Config), July 15 (Config\
  \ + Runtime), July 17 (Config)\n\n\n Week 4\n 3 days\n Config + Runtime\n Runners on older versions cannot be registered\
  \ and will not execute jobs\n July 20, July 22, July 24\n\n\n Enforcement\n —\n —\n Full enforcement begins\n July 31, 2026\n\
  \n\n\n GitHub Enterprise Cloud\n Enforcement date: September 25, 2026\n\n\n\n\n\n Week\n Cadence\n Type\n Outcome\n Dates\n\
  \n\n\n\n Week 1\n 1 day\n Config\n Runners on older versions cannot be registered\n August 24\n\n\n Week 2\n 2 days\n Config\n\
  \ Runners on older versions cannot be registered\n August 31, September 2\n\n\n Week 3\n 3 days\n Config, and Config + Runtime\n\
  \ Runners on older versions cannot be registered; on the Config + Runtime day, they also will not execute jobs\n September\
  \ 7 (Config), September 9 (Config + Runtime), September 11 (Config)\n\n\n Week 4\n 3 days\n Config + Runtime\n Runners on\
  \ older versions cannot be registered and will not execute jobs\n September 14, September 16, September 18\n\n\n Enforcement\n\
  \ —\n —\n Full enforcement begins\n September 25, 2026\n\n\n\n What you’ll see before enforcement\n To help you prepare,\
  \ Actions will provide:\n\n\n\n Runtime job annotations when workflows run on outdated runners.\n APIs and tooling to help\
  \ you identify unsupported runner versions and plan upgrades. To start, we have added the runner version to the REST API.\n\
  \n If you don’t upgrade your self-hosted runners before enforcement:\n\n\n\n New runners may fail to register with Actions.\n\
  \ Existing runners may stop picking up or executing jobs.\n Workflows targeting unsupported runners may remain queued or\
  \ fail.\n\n Identify runners that need upgrading\n If your organization uses GitHub Enterprise Cloud or GitHub Enterprise\
  \ Cloud with Data Residency , enterprise owners can audit which runner versions are currently registering by querying the\
  \ audit log for the following runner registration events, each of which includes the runner version:\n\n\n\n org.register_self_hosted_runner\
  \ : Registration events scoped to an organization\n repo.register_self_hosted_runner : Registration events scoped to a repository\n\
  \ enterprise.register_self_hosted_runner : Registration events scoped to the enterprise\n\n\n Note: Audit log events are\
  \ recorded at registration time. This gives you visibility into runners that are actively registering, but is not a complete\
  \ inventory of all connected runners. For large fleets, consider querying via the audit log REST API rather than the UI.\n\
  \n\n\n What you need to do\n To avoid disruption to your CI/CD workflows:\n\n\n\n Upgrade all self-hosted runners to the\
  \ latest supported version.\n Update installation scripts, VM images, container images, and deployment automation.\n Recreate\
  \ runners you’ve built from older cached images or templates.\n\n\n Note: This change applies to github.com, including GitHub\
  \ Enterprise Cloud and GitHub Enterprise Cloud with Data Residency. GitHub Enterprise Server isn’t impacted at this time.\n\
  \n\n\n Upgrading your self-hosted runners ahead of time is the best way to ensure uninterrupted use of Actions. For more\
  \ information, see the self-hosted runner documentation .\n\n\n Share your feedback\n Join the GitHub Community to share\
  \ your feedback or for any questions.\n\n\n\n The post GitHub Actions: Minimum version enforcement timeline for self-hosted\
  \ runners appeared first on The GitHub Blog ."
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
- at: '2026-06-12T16:04:57Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-12T20:29:06Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-12-github-actions-minimum-version-enforcement-timeline-for-self-hosted-runners
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-12T20:29:04Z'
  url: https://github.blog/changelog/2026-06-12-github-actions-minimum-version-enforcement-timeline-for-self-hosted-runners
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub Actions is resuming enforcement of version requirements for self-hosted runners on github.com\
  \ and GitHub Enterprise Cloud with Data Residency. This change is part of a broader effort to rebuild the core of GitHub\
  \ Actions to increase our reliability and availability. In early 2024, the Actions team began rearchitecting the backend\
  \ services that power job execution and runner communication—a foundational investment in the reliability, availability,\
  \ and performance our customers depend on. The new architecture now handles over 120 million jobs per day, more than three\
  \ times the volume before the migration, and enables enterprises to start seven times more jobs per minute than previously\
  \ possible. Resuming version enforcement is the next step in completing this migration: as all runners move onto the new\
  \ platform, older runner versions that are incompatible with the updated infrastructure can no longer be supported.\n\n\n\
  \ There are two requirements that together keep a runner compatible with the new platform:\n\n\n\n To configure or (re)register\
  \ a runner: The runner must be on version 2.329.0 or later. This is the minimum version required for the new architecture\
  \ to recognize the runner and allow it to connect.\n To continue executing workflow jobs: The runner must stay up to date\
  \ by installing each new runner release within 30 days of its publication. This is an existing requirement but was not consistently\
  \ enforced in some cases.\n\n Version 2.329.0 is only the minimum required to register with the new platform and receive\
  \ updates. It is not a permanent minimum version for running jobs. The effective minimum version for job execution moves\
  \ forward over time as new runner releases are published.\n\n\n Runners with auto-update enabled meet the 30-day requirement\
  \ automatically, as long as they can reach the update service.\n\n\n Runners with auto-update disabled must be upgraded\
  \ manually on a regular cadence. Meeting the registration minimum on its own isn’t enough. A runner pinned to 2.329.0 that\
  \ never updates again will not pick up jobs.\n\n\n Any release of the software, whether a major, minor, or patch version,\
  \ qualifies as an available update. If the runner is not updated within 30 days of an update being available, the GitHub\
  \ Actions service will stop queuing jobs to it. Additionally, when a critical security update is published, GitHub Actions\
  \ will pause job queuing to the runner until the update has been applied.\n\n\n Enforcement timeline\n Ahead of each enforcement\
  \ date, Actions will run temporary brownouts. Brownouts will start by intermittently blocking registration of unsupported\
  \ runner versions, then expand to also intermittently blocking job execution on unsupported runners. These brownouts help\
  \ you identify outdated runners and take action before enforcement begins.\n\n\n GitHub Enterprise Cloud with Data Residency:\
  \ Full enforcement begins July 31, 2026.\n\n\n GitHub Enterprise Cloud: Full enforcement begins September 25, 2026.\n\n\n\
  \ After each enforcement date:\n\n\n\n Self-hosted runners below the minimum version required for registration (e.g., runners\
  \ older than 2.329) won’t be able to register or reregister.\n Existing runners below the minimum version required to execute\
  \ workflow jobs (i.e., a higher version than the registration minimum) will stop running workflow jobs, even if they were\
  \ previously registered.\n\n\n All brownouts run from 11:00 AM to 3:00 PM ET on the dates listed below.\n\n\n\n GitHub Enterprise\
  \ Cloud with Data Residency\n Enforcement date: July 31, 2026\n\n\n\n\n\n Week\n Cadence\n Type\n Outcome\n Dates\n\n\n\n\
  \n Week 1\n 1 day\n Config\n Runners on older versions cannot be registered\n June 29\n\n\n Week 2\n 2 days\n Config\n Runners\
  \ on older versions cannot be registered\n July 6, July 8\n\n\n Week 3\n 3 days\n Config, and Config + Runtime\n Runners\
  \ on older versions cannot be registered; on the Config + Runtime day, they also will not execute jobs\n July 13 (Config),\
  \ July 15 (Config + Runtime), July 17 (Config)\n\n\n Week 4\n 3 days\n Config + Runtime\n Runners on older versions cannot\
  \ be registered and will not execute jobs\n July 20, July 22, July 24\n\n\n Enforcement\n —\n —\n Full enforcement begins\n\
  \ July 31, 2026\n\n\n\n GitHub Enterprise Cloud\n Enforcement date: September 25, 2026\n\n\n\n\n\n Week\n Cadence\n Type\n\
  \ Outcome\n Dates\n\n\n\n\n Week 1\n 1 day\n Config\n Runners on older versions cannot be registered\n August 24\n\n\n Week\
  \ 2\n 2 days\n Config\n Runners on older versions cannot be registered\n August 31, September 2\n\n\n Week 3\n 3 days\n\
  \ Config, and Config + Runtime\n Runners on older versions cannot be registered; on the Config + Runtime day, they also\
  \ will not execute jobs\n September 7 (Config), September 9 (Config + Runtime), September 11 (Config)\n\n\n Week 4\n 3 days\n\
  \ Config + Runtime\n Runners on older versions cannot be registered and will not execute jobs\n September 14, September\
  \ 16, September 18\n\n\n Enforcement\n —\n —\n Full enforcement begins\n September 25, 2026\n\n\n\n What you’ll see before\
  \ enforcement\n To help you prepare, Actions will provide:\n\n\n\n Runtime job annotations when workflows run on outdated\
  \ runners.\n APIs and tooling to help you identify unsupported runner versions and plan upgrades. To start, we have added\
  \ the runner version to the REST API.\n\n If you don’t upgrade your self-hosted runners before enforcement:\n\n\n\n New\
  \ runners may fail to register with Actions.\n Existing runners may stop picking up or executing jobs.\n Workflows targeting\
  \ unsupported runners may remain queued or fail.\n\n Identify runners that need upgrading\n If your organization uses GitHub\
  \ Enterprise Cloud or GitHub Enterprise Cloud with Data Residency , enterprise owners can audit which runner versions are\
  \ currently registering by querying the audit log for the following runner registration events, each of which includes the\
  \ runner version:\n\n\n\n org.register_self_hosted_runner : Registration events scoped to an organization\n repo.register_self_hosted_runner\
  \ : Registration events scoped to a repository\n enterprise.register_self_hosted_runner : Registration events scoped to\
  \ the enterprise\n\n\n Note: Audit log events are recorded at registration time. This gives you visibility into runners\
  \ that are actively registering, but is not a complete inventory of all connected runners. For large fleets, consider querying\
  \ via the audit log REST API rather than the UI.\n\n\n\n What you need to do\n To avoid disruption to your CI/CD workflows:\n\
  \n\n\n Upgrade all self-hosted runners to the latest supported version.\n Update installation scripts, VM images, container\
  \ images, and deployment automation.\n Recreate runners you’ve built from older cached images or templates.\n\n\n Note:\
  \ This change applies to github.com, including GitHub Enterprise Cloud and GitHub Enterprise Cloud with Data Residency.\
  \ GitHub Enterprise Server isn’t impacted at this time.\n\n\n\n Upgrading your self-hosted runners ahead of time is the\
  \ best way to ensure uninterrupted use of Actions. For more information, see the self-hosted runner documentation .\n\n\n\
  \ Share your feedback\n Join the GitHub Community to share your feedback or for any questions.\n\n\n\n The post GitHub Actions:\
  \ Minimum version enforcement timeline for self-hosted runners appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
