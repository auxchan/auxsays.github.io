---
layout: aux-update
title: GitHub / Copilot Update your IDE to restore agent activity in Copilot usage metrics official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Update your IDE to restore agent activity in
  Copilot usage metrics.
permalink: /updates/github/github/update-your-ide-to-restore-agent-activity-in-copilot-usage-metrics/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-06-update-your-ide-to-restore-agent-activity-in-copilot-usage-metrics
update_download_url: ''
update_version: Update your IDE to restore agent activity in Copilot usage metrics
update_logo_text: GIT
update_published_at: '2026-10-06T23:43:00Z'
update_last_checked: '2026-10-07T01:07:55Z'
source_last_checked: '2026-10-07T01:07:55Z'
official_body_last_checked: '2026-10-07T01:07:55Z'
record_last_updated: '2026-10-07T01:07:55Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Update your IDE to restore agent activity in Copilot usage metrics
update_detail_title: GitHub / Copilot Update your IDE to restore agent activity in Copilot usage metrics
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Update your IDE to restore agent activity in Copilot usage metrics has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Update your IDE to restore agent activity in Copilot usage metrics.
release_summary: "If your Copilot usage metrics have shown agent activity or agent lines of code falling while Copilot usage\
  \ kept growing, we’ve found the cause, and a fix is rolling out to each IDE. Several IDEs recently moved Copilot agent sessions\
  \ to the Copilot SDK. Those sessions didn’t identify which IDE they came from, so usage metrics couldn’t attribute them\
  \ correctly. Most of that activity was left out of reports, and some was counted as Copilot CLI activity. Only IDE versions\
  \ that use the Copilot SDK for agent mode are affected. Developers on earlier versions are still counted.\n\n\n The fix\
  \ is available now in Visual Studio Code. Other IDEs will receive it in upcoming releases, which we expect to finish rolling\
  \ out by November 2026. Once developers update, their agent activity is counted again in the Copilot usage metrics dashboard\
  \ and API.\n\n\n Update your IDE\n Agent activity is counted again once developers are on these versions. If your developers\
  \ are on an affected version, update as soon as the fixed version is available, because their activity can’t be recovered\
  \ later. If you manage IDE versions centrally and rely on agent metrics, you can plan your rollout to move developers directly\
  \ to these versions.\n\n\n\n\n\n IDE\n Version\n Availability\n\n\n\n\n Visual Studio Code\n 1.139.0 and later\n Available\
  \ now\n\n\n Visual Studio\n 18.12\n Not yet released, expected in October 2026\n\n\n JetBrains IDEs\n Next plugin release\n\
  \ Not yet released, expected by late October 2026\n\n\n Eclipse\n Next plugin release\n Not yet released, expected by November\
  \ 2026\n\n\n Xcode\n Next plugin release\n Not yet released, expected by November 2026\n\n\n\n We’ll add each version to\
  \ the supported IDEs in the docs as it ships.\n\n\n What to expect in your reports\n\n Billing isn’t affected. This issue\
  \ only changed how agent activity was attributed in usage metrics, not what you were charged.\n The gap persists for any\
  \ developer on an affected IDE version until they update. Until then, their agent interactions and agent lines of code (e.g.,\
  \ loc_added_sum and loc_deleted_sum for agent_edit ) stay undercounted. This applies to enterprise, organization, and user\
  \ reports, for both 1-day and 28-day reports.\n We can’t backfill missing data. Activity from affected IDE versions doesn’t\
  \ identify which IDE it came from, so it can’t be attributed after the fact. Expect a gradual recovery as developers move\
  \ to these versions rather than a single jump.\n Copilot CLI metrics may be inflated, because some activity from other SDK-based\
  \ clients was counted as Copilot CLI activity. This will clear up as developers update those clients, but earlier Copilot\
  \ CLI metrics can’t be corrected, because that activity can’t be separated from real Copilot CLI use. Copilot CLI users\
  \ don’t need to update.\n\n Why client-side metrics can differ from other Copilot data\n Most detailed usage metrics (e.g.,\
  \ feature, language, model, and lines of code breakdowns) come from telemetry that each IDE sends. GitHub also records server-side\
  \ data when Copilot handles a request. That data reliably shows who was active, but it can’t see what happens in the editor.\
  \ When your reports and other Copilot data disagree, the gap is usually on the client side:\n\n\n\n Telemetry is turned\
  \ off in the IDE, so no detailed activity is sent.\n A network proxy or firewall blocks the Copilot telemetry endpoint.\n\
  \ The IDE or Copilot extension is out of date and doesn’t send the events that metrics rely on.\n The client changed how\
  \ it sends telemetry , as with the Copilot SDK change above.\n The client doesn’t send Copilot telemetry , such as an unsupported\
  \ or third-party editor.\n\n We’re steadily reducing how much your reports depend on client telemetry. Usage metrics now\
  \ use server-side data to count active users that client telemetry misses and to identify the IDE for those users , and\
  \ we’re continuing to expand where server-side data can fill in. Some detail, such as lines of code and accepted suggestions,\
  \ can only come from the editor, so client-side gaps won’t disappear entirely. The most reliable way to keep your metrics\
  \ complete is to manage your developers’ environments:\n\n\n\n Keep IDEs and Copilot extensions current. Use your device\
  \ management tooling to enforce minimum versions where you can.\n Keep IDE telemetry enabled and allow the Copilot telemetry\
  \ endpoint through proxies and firewalls.\n Spot outdated clients in your reports. In per-user reports, totals_by_ide includes\
  \ last_known_ide_version and last_known_plugin_version for each user.\n\n To learn how usage metrics combine client-side\
  \ and server-side telemetry, see Which usage is included? in the Copilot usage metrics documentation.\n\n\n\n The post Update\
  \ your IDE to restore agent activity in Copilot usage metrics appeared first on The GitHub Blog ."
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
- at: '2026-10-06T23:43:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-07T01:08:01Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-06-update-your-ide-to-restore-agent-activity-in-copilot-usage-metrics
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-07T01:07:55Z'
  url: https://github.blog/changelog/2026-10-06-update-your-ide-to-restore-agent-activity-in-copilot-usage-metrics
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "If your Copilot usage metrics have shown agent activity or agent lines of code falling while Copilot\
  \ usage kept growing, we’ve found the cause, and a fix is rolling out to each IDE. Several IDEs recently moved Copilot agent\
  \ sessions to the Copilot SDK. Those sessions didn’t identify which IDE they came from, so usage metrics couldn’t attribute\
  \ them correctly. Most of that activity was left out of reports, and some was counted as Copilot CLI activity. Only IDE\
  \ versions that use the Copilot SDK for agent mode are affected. Developers on earlier versions are still counted.\n\n\n\
  \ The fix is available now in Visual Studio Code. Other IDEs will receive it in upcoming releases, which we expect to finish\
  \ rolling out by November 2026. Once developers update, their agent activity is counted again in the Copilot usage metrics\
  \ dashboard and API.\n\n\n Update your IDE\n Agent activity is counted again once developers are on these versions. If your\
  \ developers are on an affected version, update as soon as the fixed version is available, because their activity can’t\
  \ be recovered later. If you manage IDE versions centrally and rely on agent metrics, you can plan your rollout to move\
  \ developers directly to these versions.\n\n\n\n\n\n IDE\n Version\n Availability\n\n\n\n\n Visual Studio Code\n 1.139.0\
  \ and later\n Available now\n\n\n Visual Studio\n 18.12\n Not yet released, expected in October 2026\n\n\n JetBrains IDEs\n\
  \ Next plugin release\n Not yet released, expected by late October 2026\n\n\n Eclipse\n Next plugin release\n Not yet released,\
  \ expected by November 2026\n\n\n Xcode\n Next plugin release\n Not yet released, expected by November 2026\n\n\n\n We’ll\
  \ add each version to the supported IDEs in the docs as it ships.\n\n\n What to expect in your reports\n\n Billing isn’t\
  \ affected. This issue only changed how agent activity was attributed in usage metrics, not what you were charged.\n The\
  \ gap persists for any developer on an affected IDE version until they update. Until then, their agent interactions and\
  \ agent lines of code (e.g., loc_added_sum and loc_deleted_sum for agent_edit ) stay undercounted. This applies to enterprise,\
  \ organization, and user reports, for both 1-day and 28-day reports.\n We can’t backfill missing data. Activity from affected\
  \ IDE versions doesn’t identify which IDE it came from, so it can’t be attributed after the fact. Expect a gradual recovery\
  \ as developers move to these versions rather than a single jump.\n Copilot CLI metrics may be inflated, because some activity\
  \ from other SDK-based clients was counted as Copilot CLI activity. This will clear up as developers update those clients,\
  \ but earlier Copilot CLI metrics can’t be corrected, because that activity can’t be separated from real Copilot CLI use.\
  \ Copilot CLI users don’t need to update.\n\n Why client-side metrics can differ from other Copilot data\n Most detailed\
  \ usage metrics (e.g., feature, language, model, and lines of code breakdowns) come from telemetry that each IDE sends.\
  \ GitHub also records server-side data when Copilot handles a request. That data reliably shows who was active, but it can’t\
  \ see what happens in the editor. When your reports and other Copilot data disagree, the gap is usually on the client side:\n\
  \n\n\n Telemetry is turned off in the IDE, so no detailed activity is sent.\n A network proxy or firewall blocks the Copilot\
  \ telemetry endpoint.\n The IDE or Copilot extension is out of date and doesn’t send the events that metrics rely on.\n\
  \ The client changed how it sends telemetry , as with the Copilot SDK change above.\n The client doesn’t send Copilot telemetry\
  \ , such as an unsupported or third-party editor.\n\n We’re steadily reducing how much your reports depend on client telemetry.\
  \ Usage metrics now use server-side data to count active users that client telemetry misses and to identify the IDE for\
  \ those users , and we’re continuing to expand where server-side data can fill in. Some detail, such as lines of code and\
  \ accepted suggestions, can only come from the editor, so client-side gaps won’t disappear entirely. The most reliable way\
  \ to keep your metrics complete is to manage your developers’ environments:\n\n\n\n Keep IDEs and Copilot extensions current.\
  \ Use your device management tooling to enforce minimum versions where you can.\n Keep IDE telemetry enabled and allow the\
  \ Copilot telemetry endpoint through proxies and firewalls.\n Spot outdated clients in your reports. In per-user reports,\
  \ totals_by_ide includes last_known_ide_version and last_known_plugin_version for each user.\n\n To learn how usage metrics\
  \ combine client-side and server-side telemetry, see Which usage is included? in the Copilot usage metrics documentation.\n\
  \n\n\n The post Update your IDE to restore agent activity in Copilot usage metrics appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
