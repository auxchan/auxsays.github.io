---
layout: aux-update
title: GitHub / Copilot New features and Claude as agent provider preview in JetBrains IDEs official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/new-features-and-claude-as-agent-provider-preview-in-jetbrains-ides/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-22-new-features-and-claude-as-agent-provider-preview-in-jetbrains-ides
update_download_url: ''
update_version: New features and Claude as agent provider preview in JetBrains IDEs
update_logo_text: GIT
update_published_at: '2026-06-22T15:34:00Z'
update_last_checked: '2026-06-23T04:32:32Z'
source_last_checked: '2026-06-23T10:05:49Z'
official_body_last_checked: '2026-06-23T10:05:49Z'
record_last_updated: '2026-06-23T04:32:32Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot New features and Claude as agent provider preview in JetBrains IDEs
update_detail_title: GitHub / Copilot New features and Claude as agent provider preview in JetBrains IDEs
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot New features and Claude as agent provider preview in JetBrains IDEs has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot New features and Claude as agent provider preview in JetBrains IDEs.
release_summary: "This update adds support for organization and enterprise agents from GitHub, lets you queue and steer messages\
  \ in Copilot CLI sessions, introduces a new agent debug logs summary view, and brings Claude as agent provider into public\
  \ preview in GitHub Copilot for JetBrains IDEs.\n\n\n It also includes model picker enhancements, a per-turn AI credits\
  \ indicator, and a set of user experience and reliability improvements. Cloud agent is now generally available.\n\n\n New\
  \ features\n Support for organization and enterprise agents from GitHub\n You can now use custom agents defined at the GitHub\
  \ organization and enterprise level directly inside JetBrains IDEs. Administrators can publish a curated set of agents that\
  \ are automatically available to everyone in the organization or enterprise. This makes it easier to share, standardize,\
  \ and govern agent workflows across your team.\n\n\n In order to use it:\n\n\n\n Administrators define agents in GitHub:\
  \ An organization or enterprise admin creates custom agents and publishes them so they are available to members. Once published,\
  \ these agents are automatically distributed to all eligible users.\n Open the agent picker in Copilot Chat: In your JetBrains\
  \ IDE, open the Copilot Chat panel and click the agent picker.\n Select an organization or enterprise agent: Available agents\
  \ are grouped and you can choose the one that fits your task.\n Start working: The selected agent runs with the configuration\
  \ defined by your admin, helping ensure consistent behavior and standards across your team.\n\n For more details, see Preparing\
  \ to use custom agents in your organization and Preparing to use custom agents in your enterprise .\n\n\n\n\n\n Send messages\
  \ while a request is running (CLI)\n When working on longer tasks in Copilot CLI sessions, you had to wait for a response\
  \ to complete or previously cancel it. Now you can send follow-up messages while a request is still running.\n\n\n While\
  \ a request is in progress, the Send button changes to a dropdown with three options:\n\n\n\n Add to Queue : Queue a message\
  \ to be processed after the current response completes.\n Steer with Message : Tell the current request to yield once the\
  \ active tool execution finishes, then process your new message immediately. Use this to redirect the agent when it’s heading\
  \ in the wrong direction.\n Stop and Send : Stop the current turn and immediately send your new message.\n\n\n\n\n Agent\
  \ debug logs summary view\n We’ve enhanced the Agent Debug panel with a new logs summary view that gives you a consolidated\
  \ overview of agent activity, making it easier to review and debug session behavior.\n\n\n You can select the session name\
  \ from the session list to navigate to the summary view. It will show aggregate stats for the session.\n\n\n\n\n\n Claude\
  \ as agent provider in public preview\n Claude as agent provider is now available in public preview, giving you more flexibility\
  \ to pick the agent that best fits your task, all without leaving your JetBrains IDE.\n\n\n To use it, first install the\
  \ Claude Code CLI on your machine. Then go to Settings > Tools > GitHub Copilot > Chat and set the Claude Code CLI path.\
  \ Once configured, select Claude from the agent picker in the Copilot Chat panel to start a session.\n\n\n\n Note: The Claude\
  \ agent currently runs in bypass permissions mode, so all file edits and tool calls are automatically approved. Configurable\
  \ permissions are coming in a future release. Also, if you’re a Copilot Business or Copilot Enterprise subscriber, an administrator\
  \ will need to enable the Editor preview features policy before you can use this feature.\n\n\n\n\n\n\n Model picker enhancements\n\
  \ We’ve made several improvements to the model picker:\n\n\n\n /models slash command : Open the model picker directly, with\
  \ support for both Copilot CLI and Claude agent.\n\n\n Larger context window selection : Select a larger context window\
  \ directly from the model picker, giving you more room for context-heavy tasks.\n\n\n\n\n Recently used models : The local\
  \ agent model picker now includes a recently used model section, so you can quickly select the models you use the most.\n\
  \n\n\n\n Per-turn AI credits indicator\n Local, CLI, and Claude agent sessions now display a per-turn AI credits indicator,\
  \ giving you clearer visibility into how many AI credits each turn consumes as you work.\n\n\n To learn more about how GitHub\
  \ AI Credits work, see Usage-based billing for individuals and Usage-based billing for organizations and enterprises .\n\
  \n\n\n\n\n User experience\n We have made several refinements to improve day-to-day workflows and responsiveness across\
  \ JetBrains IDEs:\n\n\n\n Improved chat input layout for better reliability\n Improved the inline chat experience by ensuring\
  \ state resets when closed during a response\n Improved code block rendering performance\n Improved next edit suggestions\
  \ by adding richer code diagnostic information for better suggestions\n\n Bug fixes\n This release also includes important\
  \ reliability and stability fixes:\n\n\n\n Fixed an issue where diff views would open for every agent edit\n Fixed an issue\
  \ that could cause no completion models to be shown in settings\n Fixed multiple UI freeze issues\n\n Availability updates\n\
  \ Cloud agent is now generally available (no longer behind the Editor Preview feature flag).\n\n\n Try it out\n We encourage\
  \ you to try out the latest version of the GitHub Copilot plugin and share your feedback. Your input is invaluable in helping\
  \ us refine and improve the product.\n\n\n Share your feedback\n Your feedback drives improvements. We’d love to hear about\
  \ your experience in the following channels:\n\n\n\n In-product feedback: Use the feedback options within your IDE.\n Community\
  \ feedback: Share your thoughts in the GitHub Copilot for JetBrains IDEs issues , or take our short survey .\n\n\n The post\
  \ New features and Claude as agent provider preview in JetBrains IDEs appeared first on The GitHub Blog ."
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
- at: '2026-06-22T15:34:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-23T04:32:34Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-22-new-features-and-claude-as-agent-provider-preview-in-jetbrains-ides
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-23T04:32:32Z'
  url: https://github.blog/changelog/2026-06-22-new-features-and-claude-as-agent-provider-preview-in-jetbrains-ides
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-06-23T10:05:49Z'
  url: https://github.blog/changelog/2026-06-22-new-features-and-claude-as-agent-provider-preview-in-jetbrains-ides
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "This update adds support for organization and enterprise agents from GitHub, lets you queue and\
  \ steer messages in Copilot CLI sessions, introduces a new agent debug logs summary view, and brings Claude as agent provider\
  \ into public preview in GitHub Copilot for JetBrains IDEs.\n\n\n It also includes model picker enhancements, a per-turn\
  \ AI credits indicator, and a set of user experience and reliability improvements. Cloud agent is now generally available.\n\
  \n\n New features\n Support for organization and enterprise agents from GitHub\n You can now use custom agents defined at\
  \ the GitHub organization and enterprise level directly inside JetBrains IDEs. Administrators can publish a curated set\
  \ of agents that are automatically available to everyone in the organization or enterprise. This makes it easier to share,\
  \ standardize, and govern agent workflows across your team.\n\n\n In order to use it:\n\n\n\n Administrators define agents\
  \ in GitHub: An organization or enterprise admin creates custom agents and publishes them so they are available to members.\
  \ Once published, these agents are automatically distributed to all eligible users.\n Open the agent picker in Copilot Chat:\
  \ In your JetBrains IDE, open the Copilot Chat panel and click the agent picker.\n Select an organization or enterprise\
  \ agent: Available agents are grouped and you can choose the one that fits your task.\n Start working: The selected agent\
  \ runs with the configuration defined by your admin, helping ensure consistent behavior and standards across your team.\n\
  \n For more details, see Preparing to use custom agents in your organization and Preparing to use custom agents in your\
  \ enterprise .\n\n\n\n\n\n Send messages while a request is running (CLI)\n When working on longer tasks in Copilot CLI\
  \ sessions, you had to wait for a response to complete or previously cancel it. Now you can send follow-up messages while\
  \ a request is still running.\n\n\n While a request is in progress, the Send button changes to a dropdown with three options:\n\
  \n\n\n Add to Queue : Queue a message to be processed after the current response completes.\n Steer with Message : Tell\
  \ the current request to yield once the active tool execution finishes, then process your new message immediately. Use this\
  \ to redirect the agent when it’s heading in the wrong direction.\n Stop and Send : Stop the current turn and immediately\
  \ send your new message.\n\n\n\n\n Agent debug logs summary view\n We’ve enhanced the Agent Debug panel with a new logs\
  \ summary view that gives you a consolidated overview of agent activity, making it easier to review and debug session behavior.\n\
  \n\n You can select the session name from the session list to navigate to the summary view. It will show aggregate stats\
  \ for the session.\n\n\n\n\n\n Claude as agent provider in public preview\n Claude as agent provider is now available in\
  \ public preview, giving you more flexibility to pick the agent that best fits your task, all without leaving your JetBrains\
  \ IDE.\n\n\n To use it, first install the Claude Code CLI on your machine. Then go to Settings > Tools > GitHub Copilot\
  \ > Chat and set the Claude Code CLI path. Once configured, select Claude from the agent picker in the Copilot Chat panel\
  \ to start a session.\n\n\n\n Note: The Claude agent currently runs in bypass permissions mode, so all file edits and tool\
  \ calls are automatically approved. Configurable permissions are coming in a future release. Also, if you’re a Copilot Business\
  \ or Copilot Enterprise subscriber, an administrator will need to enable the Editor preview features policy before you can\
  \ use this feature.\n\n\n\n\n\n\n Model picker enhancements\n We’ve made several improvements to the model picker:\n\n\n\
  \n /models slash command : Open the model picker directly, with support for both Copilot CLI and Claude agent.\n\n\n Larger\
  \ context window selection : Select a larger context window directly from the model picker, giving you more room for context-heavy\
  \ tasks.\n\n\n\n\n Recently used models : The local agent model picker now includes a recently used model section, so you\
  \ can quickly select the models you use the most.\n\n\n\n\n Per-turn AI credits indicator\n Local, CLI, and Claude agent\
  \ sessions now display a per-turn AI credits indicator, giving you clearer visibility into how many AI credits each turn\
  \ consumes as you work.\n\n\n To learn more about how GitHub AI Credits work, see Usage-based billing for individuals and\
  \ Usage-based billing for organizations and enterprises .\n\n\n\n\n\n User experience\n We have made several refinements\
  \ to improve day-to-day workflows and responsiveness across JetBrains IDEs:\n\n\n\n Improved chat input layout for better\
  \ reliability\n Improved the inline chat experience by ensuring state resets when closed during a response\n Improved code\
  \ block rendering performance\n Improved next edit suggestions by adding richer code diagnostic information for better suggestions\n\
  \n Bug fixes\n This release also includes important reliability and stability fixes:\n\n\n\n Fixed an issue where diff views\
  \ would open for every agent edit\n Fixed an issue that could cause no completion models to be shown in settings\n Fixed\
  \ multiple UI freeze issues\n\n Availability updates\n Cloud agent is now generally available (no longer behind the Editor\
  \ Preview feature flag).\n\n\n Try it out\n We encourage you to try out the latest version of the GitHub Copilot plugin\
  \ and share your feedback. Your input is invaluable in helping us refine and improve the product.\n\n\n Share your feedback\n\
  \ Your feedback drives improvements. We’d love to hear about your experience in the following channels:\n\n\n\n In-product\
  \ feedback: Use the feedback options within your IDE.\n Community feedback: Share your thoughts in the GitHub Copilot for\
  \ JetBrains IDEs issues , or take our short survey .\n\n\n The post New features and Claude as agent provider preview in\
  \ JetBrains IDEs appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
