---
layout: aux-update
title: GitHub / Copilot GitHub Copilot in VS Code, Universe releases official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for GitHub Copilot in VS Code, Universe releases.
permalink: /updates/github/github/github-copilot-in-vs-code-universe-releases/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-28-github-copilot-in-vs-code-universe-releases
update_download_url: ''
update_version: GitHub Copilot in VS Code, Universe releases
update_logo_text: GIT
update_published_at: '2026-10-28T15:33:00Z'
update_last_checked: '2026-10-30T01:26:56Z'
source_last_checked: '2026-10-30T01:26:56Z'
official_body_last_checked: '2026-10-30T01:26:56Z'
record_last_updated: '2026-10-30T01:26:56Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub Copilot in VS Code, Universe releases
update_detail_title: GitHub / Copilot GitHub Copilot in VS Code, Universe releases
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub Copilot in VS Code, Universe releases has an official AUXSAYS record. Confirmed patch-specific
  consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub Copilot in VS Code, Universe releases.
release_summary: "This year, we focused on giving you more choice in how you work with GitHub Copilot in Visual Studio Code:\
  \ which models you use, where your agents run, and how you stay involved.\n\n\n Keep work moving without staying at your\
  \ desk or in one tool. With GitHub Copilot in Visual Studio Code, start a cloud agent session from your phone at standup,\
  \ steer it from VS Code at your desk, and check on it from github.com at lunch. Session continuity lets you pick up the\
  \ same session across these clients while your agent keeps working in the cloud.\n\n\n Start and follow cloud sessions across\
  \ Copilot clients\n Hand off work without keeping your computer on. Start a cloud agent session from the Agents window in\
  \ VS Code. The work runs on GitHub’s infrastructure, so closing your laptop doesn’t stop it.\n\n\n Find and continue the\
  \ same session in VS Code, the GitHub Copilot app, GitHub Mobile, github.com, or Copilot CLI. Sessions started in a Slack\
  \ or Microsoft Teams DM can also be continued in these clients.\n\n\n\n\n\n\n\n Keep agents working on your own machines\n\
  \ Move on to another task or project without worrying about losing your session. The new Agent Host isolates your Copilot\
  \ sessions from individual VS Code windows, so work continues in the background after you close the project folder or window.\n\
  \n\n You can also run agents on a separate machine while you use your primary development machine for other work. The power\
  \ and flexibility of VS Code’s Remote SSH and dev tunnels extends to the Agents window. The remote agent works with the\
  \ same code, tools, and dependencies, and can keep running when you disconnect or quit VS Code locally. The remote machine\
  \ and its Agent Host must remain running.\n\n\n\n\n\n Move between the editor and Agents windows\n Switch between the editor\
  \ and the Agents window without starting over. Both views stay in sync with the same live Copilot session.\n\n\n\n\n\n\n\
  \n Control agents on your machine from your phone\n Check progress, give direction, or start a new task on your development\
  \ machine from GitHub Mobile. Your phone provides the controls, and the agent does the work on your development machine.\
  \ To get started, open a terminal on that machine and run the VS Code CLI command code agent host --github-environment from\
  \ your project folder. Keep the machine and its Agent Host running while you use it from your phone.\n\n\n\n\n\n\n\n Get\
  \ a more consistent GitHub Copilot\n Get more consistent agent behavior across VS Code, Copilot CLI, and the GitHub Copilot\
  \ app. The Copilot harness, built on the Microsoft Copilot SDK, is now the default for new sessions in both the editor and\
  \ the Agents window.\n\n\n\n\n\n Install GitHub Copilot CLI with VS Code\n Bring Copilot to your terminal with less setup.\
  \ Install GitHub Copilot CLI through the VS Code installer on Windows, when adding VS Code to your path on macOS, or by\
  \ running copilot on Linux.\n\n\n\n\n\n Compare model results\n Explore different approaches to the same coding task. Run\
  \ models and harnesses in parallel in the Agents window, then review their results side by side. You can ask a Judge model\
  \ to recommend a solution and choose Synthesize to combine ideas from the other attempts. This is in preview.\n\n\n\n\n\n\
  \n\n Let your agent use your desktop apps\n Give your agent tasks that need more than code or terminal commands. With computer\
  \ use, Copilot can read and interact with desktop apps, including clicking controls and editing text.\n\n\n On macOS or\
  \ Windows, open VS Code Settings , search for chat.agentHost.computerUse.enabled , and enable it. Restart VS Code, then\
  \ run /computer on in a Copilot session running on your computer.\n\n\n Each application requires your approval. Computer\
  \ use shares its setup with Copilot CLI and the GitHub Copilot app, so on macOS you grant the required system permissions\
  \ once. Organizations can disable computer use through policy.\n\n\n This is an experimental feature.\n\n\n\n\n\n\n\n Build\
  \ your own client\n Bring session continuity to your own app. Build a client that connects to an Agent Host and works with\
  \ the same live sessions as VS Code.\n\n\n The open Agent Host Protocol (AHP) lets connected clients stay in sync and catch\
  \ up after reconnecting. Run code agent host , then connect with a client library for TypeScript, Rust, Go, Kotlin, or Swift.\n\
  \n\n\n\n\n Discover marketplace customizations\n Create, discover, and manage agent customizations from one place in VS\
  \ Code. Open Customizations in the Agents window sidebar or run Chat: Open Customizations . Its “Browse” page brings together\
  \ skills, MCP servers, plugins, and other customizations from available sources.\n\n\n The Customization Marketplace is\
  \ in preview and enabled by default. Business and Enterprise administrators need to allow Editor preview features . Learn\
  \ more about the Agent Customizations editor and marketplace .\n\n\n Strengthen existing plugin and marketplace controls\n\
  \ Make existing plugin and marketplace controls more reliable. In VS Code, administrators can use policies to require or\
  \ block named plugins, add marketplaces, and restrict installation to approved sources. Enterprise-managed strict marketplace\
  \ settings can also turn off built-in marketplaces. Policy-managed plugin toggles are locked in Customize > Plugins . For\
  \ controls across Copilot clients, administrators can use enterprise-managed settings .\n\n\n At the repository level, .github/copilot/settings.json\
  \ can register plugin marketplaces and enable default plugins. These are defaults, not enforcement: contributors can turn\
  \ plugins off unless enterprise policy requires them. Learn more about plugin marketplaces and workspace recommendations\
  \ .\n\n\n Connect services with Copilot connectors\n Bring context from services such as Slack, Notion, and Microsoft Learn\
  \ into agent sessions without installing or managing an MCP server. Connect once from “Browse” and reuse the connection\
  \ across supported Copilot clients signed in with the same account.\n\n\n Connectors are in preview, available on all Copilot\
  \ plans, and work with the Copilot harness. Business and Enterprise administrators need to allow Editor preview features\
  \ . Learn more about Copilot connectors in VS Code .\n\n\n Learn more\n Learn more in the VS Code release notes , the Agent\
  \ Host deep dive , and About computer use in GitHub Copilot .\n\n\n Happy coding! \U0001F499\n\n\n\n The post GitHub Copilot\
  \ in VS Code, Universe releases appeared first on The GitHub Blog ."
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
- at: '2026-10-28T15:33:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-30T01:27:22Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-28-github-copilot-in-vs-code-universe-releases
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-30T01:26:56Z'
  url: https://github.blog/changelog/2026-10-28-github-copilot-in-vs-code-universe-releases
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "This year, we focused on giving you more choice in how you work with GitHub Copilot in Visual\
  \ Studio Code: which models you use, where your agents run, and how you stay involved.\n\n\n Keep work moving without staying\
  \ at your desk or in one tool. With GitHub Copilot in Visual Studio Code, start a cloud agent session from your phone at\
  \ standup, steer it from VS Code at your desk, and check on it from github.com at lunch. Session continuity lets you pick\
  \ up the same session across these clients while your agent keeps working in the cloud.\n\n\n Start and follow cloud sessions\
  \ across Copilot clients\n Hand off work without keeping your computer on. Start a cloud agent session from the Agents window\
  \ in VS Code. The work runs on GitHub’s infrastructure, so closing your laptop doesn’t stop it.\n\n\n Find and continue\
  \ the same session in VS Code, the GitHub Copilot app, GitHub Mobile, github.com, or Copilot CLI. Sessions started in a\
  \ Slack or Microsoft Teams DM can also be continued in these clients.\n\n\n\n\n\n\n\n Keep agents working on your own machines\n\
  \ Move on to another task or project without worrying about losing your session. The new Agent Host isolates your Copilot\
  \ sessions from individual VS Code windows, so work continues in the background after you close the project folder or window.\n\
  \n\n You can also run agents on a separate machine while you use your primary development machine for other work. The power\
  \ and flexibility of VS Code’s Remote SSH and dev tunnels extends to the Agents window. The remote agent works with the\
  \ same code, tools, and dependencies, and can keep running when you disconnect or quit VS Code locally. The remote machine\
  \ and its Agent Host must remain running.\n\n\n\n\n\n Move between the editor and Agents windows\n Switch between the editor\
  \ and the Agents window without starting over. Both views stay in sync with the same live Copilot session.\n\n\n\n\n\n\n\
  \n Control agents on your machine from your phone\n Check progress, give direction, or start a new task on your development\
  \ machine from GitHub Mobile. Your phone provides the controls, and the agent does the work on your development machine.\
  \ To get started, open a terminal on that machine and run the VS Code CLI command code agent host --github-environment from\
  \ your project folder. Keep the machine and its Agent Host running while you use it from your phone.\n\n\n\n\n\n\n\n Get\
  \ a more consistent GitHub Copilot\n Get more consistent agent behavior across VS Code, Copilot CLI, and the GitHub Copilot\
  \ app. The Copilot harness, built on the Microsoft Copilot SDK, is now the default for new sessions in both the editor and\
  \ the Agents window.\n\n\n\n\n\n Install GitHub Copilot CLI with VS Code\n Bring Copilot to your terminal with less setup.\
  \ Install GitHub Copilot CLI through the VS Code installer on Windows, when adding VS Code to your path on macOS, or by\
  \ running copilot on Linux.\n\n\n\n\n\n Compare model results\n Explore different approaches to the same coding task. Run\
  \ models and harnesses in parallel in the Agents window, then review their results side by side. You can ask a Judge model\
  \ to recommend a solution and choose Synthesize to combine ideas from the other attempts. This is in preview.\n\n\n\n\n\n\
  \n\n Let your agent use your desktop apps\n Give your agent tasks that need more than code or terminal commands. With computer\
  \ use, Copilot can read and interact with desktop apps, including clicking controls and editing text.\n\n\n On macOS or\
  \ Windows, open VS Code Settings , search for chat.agentHost.computerUse.enabled , and enable it. Restart VS Code, then\
  \ run /computer on in a Copilot session running on your computer.\n\n\n Each application requires your approval. Computer\
  \ use shares its setup with Copilot CLI and the GitHub Copilot app, so on macOS you grant the required system permissions\
  \ once. Organizations can disable computer use through policy.\n\n\n This is an experimental feature.\n\n\n\n\n\n\n\n Build\
  \ your own client\n Bring session continuity to your own app. Build a client that connects to an Agent Host and works with\
  \ the same live sessions as VS Code.\n\n\n The open Agent Host Protocol (AHP) lets connected clients stay in sync and catch\
  \ up after reconnecting. Run code agent host , then connect with a client library for TypeScript, Rust, Go, Kotlin, or Swift.\n\
  \n\n\n\n\n Discover marketplace customizations\n Create, discover, and manage agent customizations from one place in VS\
  \ Code. Open Customizations in the Agents window sidebar or run Chat: Open Customizations . Its “Browse” page brings together\
  \ skills, MCP servers, plugins, and other customizations from available sources.\n\n\n The Customization Marketplace is\
  \ in preview and enabled by default. Business and Enterprise administrators need to allow Editor preview features . Learn\
  \ more about the Agent Customizations editor and marketplace .\n\n\n Strengthen existing plugin and marketplace controls\n\
  \ Make existing plugin and marketplace controls more reliable. In VS Code, administrators can use policies to require or\
  \ block named plugins, add marketplaces, and restrict installation to approved sources. Enterprise-managed strict marketplace\
  \ settings can also turn off built-in marketplaces. Policy-managed plugin toggles are locked in Customize > Plugins . For\
  \ controls across Copilot clients, administrators can use enterprise-managed settings .\n\n\n At the repository level, .github/copilot/settings.json\
  \ can register plugin marketplaces and enable default plugins. These are defaults, not enforcement: contributors can turn\
  \ plugins off unless enterprise policy requires them. Learn more about plugin marketplaces and workspace recommendations\
  \ .\n\n\n Connect services with Copilot connectors\n Bring context from services such as Slack, Notion, and Microsoft Learn\
  \ into agent sessions without installing or managing an MCP server. Connect once from “Browse” and reuse the connection\
  \ across supported Copilot clients signed in with the same account.\n\n\n Connectors are in preview, available on all Copilot\
  \ plans, and work with the Copilot harness. Business and Enterprise administrators need to allow Editor preview features\
  \ . Learn more about Copilot connectors in VS Code .\n\n\n Learn more\n Learn more in the VS Code release notes , the Agent\
  \ Host deep dive , and About computer use in GitHub Copilot .\n\n\n Happy coding! \U0001F499\n\n\n\n The post GitHub Copilot\
  \ in VS Code, Universe releases appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
