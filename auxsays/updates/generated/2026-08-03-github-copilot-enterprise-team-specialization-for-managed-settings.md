---
layout: aux-update
title: GitHub / Copilot Enterprise team specialization for managed settings official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/enterprise-team-specialization-for-managed-settings/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-08-03-enterprise-team-specialization-for-managed-settings
update_download_url: ''
update_version: Enterprise team specialization for managed settings
update_logo_text: GIT
update_published_at: '2026-08-03T22:55:29Z'
update_last_checked: '2026-08-03T23:57:20Z'
source_last_checked: '2026-08-04T07:29:13Z'
official_body_last_checked: '2026-08-04T07:29:13Z'
record_last_updated: '2026-08-03T23:57:20Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Enterprise team specialization for managed settings
update_detail_title: GitHub / Copilot Enterprise team specialization for managed settings
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Enterprise team specialization for managed settings has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Enterprise team specialization for managed settings.
release_summary: "Enterprise administrators can now customize managed settings by targeting enterprise teams with itemized\
  \ configuration files. Large enterprises can scale governance without bottlenecking every configuration change through central\
  \ administrators or one-size-fits-all policies. Teams gain the flexibility to adapt Copilot to their workflows while staying\
  \ within the boundaries you’ve defined.\n\n\n The AI ecosystem evolves frequently and maintaining effective guardrails is\
  \ a shared responsibility. Set your AI standards source .github-private repository to internal visibility and let your users\
  \ open pull requests to suggest changes that keep their specialized governance configuration up to date.\n\n\n What you\
  \ can do\n After you’ve configured your managed-settings.json file, you can make individual keys eligible for team-specific\
  \ values.\n\n\n\n Mark keys as overridable: In your copilot/managed-settings.json file, use the { \"overridable\": } syntax\
  \ to specialize the key’s configuration on a per-team basis. An overridable key uses the team’s value when set or falls\
  \ back to your enterprise default when the team leaves it unset. Keys you don’t mark overridable remain an enterprise-level\
  \ decision that teams can’t modify. In practice, you can set \"disableBypassPermissionsMode\": \"unmanaged\" and \"model\"\
  : \"unmanaged\" in a team settings file, providing a specialization that takes precedence over managed-settings.json for\
  \ members of that team.\n For example, let your AI Pioneers team pick their own default model and bypass permissions, while\
  \ every other team inherits your enterprise defaults.\n\n\n\n\n Team-based plugin extensibility: Let plugins and marketplaces\
  \ grow team-by-team, not shrink. enabledPlugins and extraKnownMarketplaces are additive (i.e, your enterprise baseline is\
  \ guaranteed everywhere, and individual teams can layer on the extras they need for specific job roles without weakening\
  \ the floor).\n\n\n\n\n Map settings files to teams: Ship different policies to different teams from one place. Map each\
  \ team settings file to one or more team slugs in team-mappings.json . Each entry pairs a settings file with the teams that\
  \ use it, so you can apply one file across multiple teams.\n\n\n For example, a single ai-users.json file can be applied\
  \ to all teams that have completed training. Additional specializations can be applied for other job roles like devs.json\
  \ .\n\n\n\n\n Create the team settings file: Add the team’s configuration under copilot/teams/ . Only include the keys you\
  \ marked as overridable. Anything else falls back to your enterprise platform decision.\n\n\n\n\n Trust that enterprise\
  \ decisions always win: Keys you don’t mark overridable set a ceiling, so compliance-critical settings stay locked down\
  \ by default. Unmanaged or overridable keys set a floor. If a user belongs to multiple teams, the team-level settings are\
  \ combined using the least restrictive value for each key, then applied beneath the enterprise file.\n\n\n\n\n Supported\
  \ clients\n Today the configuration defined in managed-settings.json is enforced in VS Code, Copilot CLI, the Copilot App,\
  \ and Copilot cloud agent whenever a user has a Copilot Business or Copilot Enterprise license issued from the enterprise\
  \ or one of its organizations. We are working to extend this support across all Copilot clients through the Copilot SDK.\n\
  \n\n To learn more, see configuring enterprise managed settings .\n\n\n Join the discussion within GitHub Community .\n\n\
  \n\n\n\n\n The post Enterprise team specialization for managed settings appeared first on The GitHub Blog ."
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
- at: '2026-08-03T22:55:29Z'
  label: Published
  note: Official source entry detected.
- at: '2026-08-03T23:57:25Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-08-03-enterprise-team-specialization-for-managed-settings
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-08-03T23:57:20Z'
  url: https://github.blog/changelog/2026-08-03-enterprise-team-specialization-for-managed-settings
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-08-04T07:29:13Z'
  url: https://github.blog/changelog/2026-08-03-enterprise-team-specialization-for-managed-settings
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Enterprise administrators can now customize managed settings by targeting enterprise teams with\
  \ itemized configuration files. Large enterprises can scale governance without bottlenecking every configuration change\
  \ through central administrators or one-size-fits-all policies. Teams gain the flexibility to adapt Copilot to their workflows\
  \ while staying within the boundaries you’ve defined.\n\n\n The AI ecosystem evolves frequently and maintaining effective\
  \ guardrails is a shared responsibility. Set your AI standards source .github-private repository to internal visibility\
  \ and let your users open pull requests to suggest changes that keep their specialized governance configuration up to date.\n\
  \n\n What you can do\n After you’ve configured your managed-settings.json file, you can make individual keys eligible for\
  \ team-specific values.\n\n\n\n Mark keys as overridable: In your copilot/managed-settings.json file, use the { \"overridable\"\
  : } syntax to specialize the key’s configuration on a per-team basis. An overridable key uses the team’s value when set\
  \ or falls back to your enterprise default when the team leaves it unset. Keys you don’t mark overridable remain an enterprise-level\
  \ decision that teams can’t modify. In practice, you can set \"disableBypassPermissionsMode\": \"unmanaged\" and \"model\"\
  : \"unmanaged\" in a team settings file, providing a specialization that takes precedence over managed-settings.json for\
  \ members of that team.\n For example, let your AI Pioneers team pick their own default model and bypass permissions, while\
  \ every other team inherits your enterprise defaults.\n\n\n\n\n Team-based plugin extensibility: Let plugins and marketplaces\
  \ grow team-by-team, not shrink. enabledPlugins and extraKnownMarketplaces are additive (i.e, your enterprise baseline is\
  \ guaranteed everywhere, and individual teams can layer on the extras they need for specific job roles without weakening\
  \ the floor).\n\n\n\n\n Map settings files to teams: Ship different policies to different teams from one place. Map each\
  \ team settings file to one or more team slugs in team-mappings.json . Each entry pairs a settings file with the teams that\
  \ use it, so you can apply one file across multiple teams.\n\n\n For example, a single ai-users.json file can be applied\
  \ to all teams that have completed training. Additional specializations can be applied for other job roles like devs.json\
  \ .\n\n\n\n\n Create the team settings file: Add the team’s configuration under copilot/teams/ . Only include the keys you\
  \ marked as overridable. Anything else falls back to your enterprise platform decision.\n\n\n\n\n Trust that enterprise\
  \ decisions always win: Keys you don’t mark overridable set a ceiling, so compliance-critical settings stay locked down\
  \ by default. Unmanaged or overridable keys set a floor. If a user belongs to multiple teams, the team-level settings are\
  \ combined using the least restrictive value for each key, then applied beneath the enterprise file.\n\n\n\n\n Supported\
  \ clients\n Today the configuration defined in managed-settings.json is enforced in VS Code, Copilot CLI, the Copilot App,\
  \ and Copilot cloud agent whenever a user has a Copilot Business or Copilot Enterprise license issued from the enterprise\
  \ or one of its organizations. We are working to extend this support across all Copilot clients through the Copilot SDK.\n\
  \n\n To learn more, see configuring enterprise managed settings .\n\n\n Join the discussion within GitHub Community .\n\n\
  \n\n\n\n\n The post Enterprise team specialization for managed settings appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
