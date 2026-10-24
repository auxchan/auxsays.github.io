---
layout: aux-update
title: GitHub / Copilot EMU deletions fix official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for EMU deletions fix.
permalink: /updates/github/github/emu-deletions-fix/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-23-emu-deletions-fix
update_download_url: ''
update_version: EMU deletions fix
update_logo_text: GIT
update_published_at: '2026-10-23T18:56:18Z'
update_last_checked: '2026-10-24T07:21:14Z'
source_last_checked: '2026-10-24T07:21:14Z'
official_body_last_checked: '2026-10-24T07:21:14Z'
record_last_updated: '2026-10-24T07:21:14Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot EMU deletions fix
update_detail_title: GitHub / Copilot EMU deletions fix
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot EMU deletions fix has an official AUXSAYS record. Confirmed patch-specific consensus is deferred
  until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot EMU deletions fix.
release_summary: "Between June 1 and June 13, 2026, some Enterprise Managed User accounts that were deprovisioned through\
  \ SCIM were incorrectly deleted instead of being suspended and obfuscated as expected.\n\n\n As a result, affected users\
  \ appeared as ghost users in issues, pull requests, and audit logs, rather than retaining their expected suspended and obfuscated\
  \ user records within the enterprise.\n\n\n Who was affected\n This affected approximately 12,285 Enterprise Managed User\
  \ accounts across multiple enterprises.\n\n\n Most affected accounts had already been suspended and hard-deprovisioned,\
  \ which means they couldn’t be reprovisioned by design. A smaller group of 76 accounts were active at the time of deletion.\n\
  \n\n How to tell if you were affected\n You were affected if your enterprise audit logs contain a user.delete event for\
  \ an Enterprise Managed User account during the June 1 to June 13, 2026 window. If you do not see any such events in that\
  \ window, your enterprise was not impacted.\n\n\n If you do see these events, no action is required from you. GitHub is\
  \ restoring the affected accounts.\n\n\n What caused the issue\n On June 1, 2026, GitHub enabled a change that routed deprovisioning\
  \ requests through a new path. That path didn’t correctly check whether the account was an Enterprise Managed User account,\
  \ which caused the affected accounts to be deleted instead of following the expected suspend-and-obfuscate flow.\n\n\n GitHub\
  \ contained the issue by disabling the affected path on June 13, 2026.\n\n\n What we’re doing to fix it\n We’ve made code\
  \ changes to prevent this from happening again. We’ve also restored affected user records in October 2026.\n\n\n The restoration\
  \ process returned affected accounts to their expected suspended and obfuscated state, preserving traceability and audit\
  \ history within the enterprise. Enterprise owners don’t need to take any action.\n\n\n Hard-deprovisioned Enterprise Managed\
  \ User accounts can’t be reprovisioned by design, so this issue doesn’t affect the reprovisioning workflow.\n\n\n\n The\
  \ post EMU deletions fix appeared first on The GitHub Blog ."
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
- at: '2026-10-23T18:56:18Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-24T07:21:26Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-23-emu-deletions-fix
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-24T07:21:14Z'
  url: https://github.blog/changelog/2026-10-23-emu-deletions-fix
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Between June 1 and June 13, 2026, some Enterprise Managed User accounts that were deprovisioned\
  \ through SCIM were incorrectly deleted instead of being suspended and obfuscated as expected.\n\n\n As a result, affected\
  \ users appeared as ghost users in issues, pull requests, and audit logs, rather than retaining their expected suspended\
  \ and obfuscated user records within the enterprise.\n\n\n Who was affected\n This affected approximately 12,285 Enterprise\
  \ Managed User accounts across multiple enterprises.\n\n\n Most affected accounts had already been suspended and hard-deprovisioned,\
  \ which means they couldn’t be reprovisioned by design. A smaller group of 76 accounts were active at the time of deletion.\n\
  \n\n How to tell if you were affected\n You were affected if your enterprise audit logs contain a user.delete event for\
  \ an Enterprise Managed User account during the June 1 to June 13, 2026 window. If you do not see any such events in that\
  \ window, your enterprise was not impacted.\n\n\n If you do see these events, no action is required from you. GitHub is\
  \ restoring the affected accounts.\n\n\n What caused the issue\n On June 1, 2026, GitHub enabled a change that routed deprovisioning\
  \ requests through a new path. That path didn’t correctly check whether the account was an Enterprise Managed User account,\
  \ which caused the affected accounts to be deleted instead of following the expected suspend-and-obfuscate flow.\n\n\n GitHub\
  \ contained the issue by disabling the affected path on June 13, 2026.\n\n\n What we’re doing to fix it\n We’ve made code\
  \ changes to prevent this from happening again. We’ve also restored affected user records in October 2026.\n\n\n The restoration\
  \ process returned affected accounts to their expected suspended and obfuscated state, preserving traceability and audit\
  \ history within the enterprise. Enterprise owners don’t need to take any action.\n\n\n Hard-deprovisioned Enterprise Managed\
  \ User accounts can’t be reprovisioned by design, so this issue doesn’t affect the reprovisioning workflow.\n\n\n\n The\
  \ post EMU deletions fix appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
