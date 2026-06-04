---
layout: aux-update
title: GitHub / Copilot GitHub Copilot in Visual Studio Code, May releases official update breakdown
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/github-copilot-in-visual-studio-code-may-releases/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-06-03-github-copilot-in-visual-studio-code-may-releases
update_download_url: ''
update_version: GitHub Copilot in Visual Studio Code, May releases
update_logo_text: GIT
update_published_at: '2026-06-03T13:30:58Z'
update_last_checked: '2026-06-03T17:21:09Z'
source_last_checked: '2026-06-04T05:12:42Z'
official_body_last_checked: '2026-06-04T05:12:42Z'
record_last_updated: '2026-06-03T17:21:09Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub Copilot in Visual Studio Code, May releases
update_detail_title: GitHub / Copilot GitHub Copilot in Visual Studio Code, May releases
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub Copilot in Visual Studio Code, May releases has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub Copilot in Visual Studio Code, May releases.
release_summary: "VS Code continues with weekly stable releases. This changelog covers releases v1.120 through v1.123 , the\
  \ releases we shipped throughout May and early June 2026.\n\n\n In May, we made the Agents window available in VS Code Stable\
  \ as a preview, giving users an agent-first experience focused on completing tasks rather than editing code. We also improved\
  \ support for remotely controlling longer-running, more complex agent sessions.\n\n\n VS Code supports bring-your-own-key\
  \ (BYOK) models, letting you use your own language model API keys. This month, we expanded BYOK to air-gapped environments\
  \ and added controls to specify which models handle utility tasks like commit message generation.\n\n\n Agents window\n\n\
  \ Agents window in Stable (preview) : Work agent-first across multiple projects with a dedicated surface for faster navigation\
  \ and change review.\n Remote agents (preview) : Run sessions on remote machines over SSH or Dev Tunnels, with sessions\
  \ continuing even when the client disconnects.\n Agent Host Protocol (AHP) : Continued investment in an open protocol for\
  \ synchronizing agent session state across multiple clients.\n Session preferences persist in new sessions : New sessions\
  \ keep your recent choices, including agent harness and isolation mode.\n Sessions and Git flow improvements : New sessions\
  \ can pull base branch updates before the agent starts edits, the Agents window refreshes Git state automatically after\
  \ commits, syncs, and related operations, and agents can trigger tasks on remote machines.\n Session sync : Chat sessions\
  \ now sync automatically to your GitHub account, giving you a searchable history of your work across machines and workspaces.\n\
  \ Chronicle : Use /chronicle commands to query past sessions, generate standup reports, and get personalized productivity\
  \ tips.\n Multiple sessions side-by-side : Open more than one agent session at the same time in the Agents window. Drag,\
  \ Alt-click, or use Open to the Side to compare or review work in parallel.\n Retry network-dependent commands in sandbox\
  \ : Terminal commands that require network access are automatically retried with broader network permissions, while keeping\
  \ filesystem protections in place.\n\n Language models and BYOK\n\n Air-gapped BYOK : Bring-your-own-key models can run\
  \ in isolated environments without GitHub authentication.\n Custom Endpoint provider : Add endpoints compatible with chat\
  \ completions, responses, or messages from one provider flow.\n Model picker by provider : Find and switch models more easily\
  \ in multi-provider environments.\n BYOK token visibility : The context window now reports real token usage for bring-your-own-key\
  \ models.\n Reasoning effort controls : Configure thinking effort directly from the model picker to balance quality, latency,\
  \ and cost.\n Configurable utility models : Choose which models handle titles, summaries, rename suggestions, commit messages,\
  \ and intent detection.\n\n Terminal safety and efficiency\n\n Expanded terminal output compression : More verbose output\
  \ patterns from tests, builds, linters, Docker, and package managers are compressed before reaching the model to optimize\
  \ token usage and help reduce costs.\n Command risk assessment (experimental) : Terminal confirmations include AI-generated\
  \ risk levels and short safety explanations.\n Sensitive prompts stay in terminal : Passwords, passphrases, PINs, and verification\
  \ codes are entered directly in the terminal and are not shared with the LLM.\n Better background command UX : There are\
  \ now clearer running-state indicators in chat, plus automatic cleanup of completed background agent terminals to help save\
  \ resources on your machine and keep things more manageable.\n Agent-aware terminal commands : The VSCODE_AGENT environment\
  \ variable lets CLIs adapt behavior for agent-initiated commands.\n\n Also new\n\n Integrated browser : Adds device emulation\
  \ to test your website’s responsiveness. New screenshot options let you capture the viewport, a selected area, or the full\
  \ page and attach any of them as chat context to help reproduce and explain UI issues. You can also save favorite pages\
  \ for quick access alongside open tabs.\n HTML file preview : Preview local HTML files directly in the integrated browser\
  \ without installing an extension. Right-click a file in the Explorer or editor tab and select Open in Integrated Browser.\n\
  \ Search only in changed files : There’s a new search panel toggle that can scope results to locally modified, uncommitted\
  \ files.\n Markdown preview improvements : Mermaid diagram rendering and YAML front matter display are now built in, without\
  \ requiring separate extensions. You can also view Markdown diffs as rendered preview instead of raw source when opening\
  \ files from Source Control.\n Quick suggestions default tuning : Experience reduced noise when inline completions are available.\n\
  \ Issue reporter wizard : New issue filing flow with support for screenshots and video recordings.\n Accessibility and UX\
  \ updates : Ongoing improvements across editor surfaces.\n\n Happy coding!\n\n\n Join the discussion within GitHub Community\
  \ .\n\n\n\n The post GitHub Copilot in Visual Studio Code, May releases appeared first on The GitHub Blog ."
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
- at: '2026-06-03T13:30:58Z'
  label: Published
  note: Official source entry detected.
- at: '2026-06-03T17:21:10Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-06-03-github-copilot-in-visual-studio-code-may-releases
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-06-03T17:21:09Z'
  url: https://github.blog/changelog/2026-06-03-github-copilot-in-visual-studio-code-may-releases
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-06-03T21:31:39Z'
  url: https://github.blog/changelog/2026-06-03-github-copilot-in-visual-studio-code-may-releases
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
- at: '2026-06-04T05:12:42Z'
  url: https://github.blog/changelog/2026-06-03-github-copilot-in-visual-studio-code-may-releases
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "VS Code continues with weekly stable releases. This changelog covers releases v1.120 through v1.123\
  \ , the releases we shipped throughout May and early June 2026.\n\n\n In May, we made the Agents window available in VS\
  \ Code Stable as a preview, giving users an agent-first experience focused on completing tasks rather than editing code.\
  \ We also improved support for remotely controlling longer-running, more complex agent sessions.\n\n\n VS Code supports\
  \ bring-your-own-key (BYOK) models, letting you use your own language model API keys. This month, we expanded BYOK to air-gapped\
  \ environments and added controls to specify which models handle utility tasks like commit message generation.\n\n\n Agents\
  \ window\n\n Agents window in Stable (preview) : Work agent-first across multiple projects with a dedicated surface for\
  \ faster navigation and change review.\n Remote agents (preview) : Run sessions on remote machines over SSH or Dev Tunnels,\
  \ with sessions continuing even when the client disconnects.\n Agent Host Protocol (AHP) : Continued investment in an open\
  \ protocol for synchronizing agent session state across multiple clients.\n Session preferences persist in new sessions\
  \ : New sessions keep your recent choices, including agent harness and isolation mode.\n Sessions and Git flow improvements\
  \ : New sessions can pull base branch updates before the agent starts edits, the Agents window refreshes Git state automatically\
  \ after commits, syncs, and related operations, and agents can trigger tasks on remote machines.\n Session sync : Chat sessions\
  \ now sync automatically to your GitHub account, giving you a searchable history of your work across machines and workspaces.\n\
  \ Chronicle : Use /chronicle commands to query past sessions, generate standup reports, and get personalized productivity\
  \ tips.\n Multiple sessions side-by-side : Open more than one agent session at the same time in the Agents window. Drag,\
  \ Alt-click, or use Open to the Side to compare or review work in parallel.\n Retry network-dependent commands in sandbox\
  \ : Terminal commands that require network access are automatically retried with broader network permissions, while keeping\
  \ filesystem protections in place.\n\n Language models and BYOK\n\n Air-gapped BYOK : Bring-your-own-key models can run\
  \ in isolated environments without GitHub authentication.\n Custom Endpoint provider : Add endpoints compatible with chat\
  \ completions, responses, or messages from one provider flow.\n Model picker by provider : Find and switch models more easily\
  \ in multi-provider environments.\n BYOK token visibility : The context window now reports real token usage for bring-your-own-key\
  \ models.\n Reasoning effort controls : Configure thinking effort directly from the model picker to balance quality, latency,\
  \ and cost.\n Configurable utility models : Choose which models handle titles, summaries, rename suggestions, commit messages,\
  \ and intent detection.\n\n Terminal safety and efficiency\n\n Expanded terminal output compression : More verbose output\
  \ patterns from tests, builds, linters, Docker, and package managers are compressed before reaching the model to optimize\
  \ token usage and help reduce costs.\n Command risk assessment (experimental) : Terminal confirmations include AI-generated\
  \ risk levels and short safety explanations.\n Sensitive prompts stay in terminal : Passwords, passphrases, PINs, and verification\
  \ codes are entered directly in the terminal and are not shared with the LLM.\n Better background command UX : There are\
  \ now clearer running-state indicators in chat, plus automatic cleanup of completed background agent terminals to help save\
  \ resources on your machine and keep things more manageable.\n Agent-aware terminal commands : The VSCODE_AGENT environment\
  \ variable lets CLIs adapt behavior for agent-initiated commands.\n\n Also new\n\n Integrated browser : Adds device emulation\
  \ to test your website’s responsiveness. New screenshot options let you capture the viewport, a selected area, or the full\
  \ page and attach any of them as chat context to help reproduce and explain UI issues. You can also save favorite pages\
  \ for quick access alongside open tabs.\n HTML file preview : Preview local HTML files directly in the integrated browser\
  \ without installing an extension. Right-click a file in the Explorer or editor tab and select Open in Integrated Browser.\n\
  \ Search only in changed files : There’s a new search panel toggle that can scope results to locally modified, uncommitted\
  \ files.\n Markdown preview improvements : Mermaid diagram rendering and YAML front matter display are now built in, without\
  \ requiring separate extensions. You can also view Markdown diffs as rendered preview instead of raw source when opening\
  \ files from Source Control.\n Quick suggestions default tuning : Experience reduced noise when inline completions are available.\n\
  \ Issue reporter wizard : New issue filing flow with support for screenshots and video recordings.\n Accessibility and UX\
  \ updates : Ongoing improvements across editor surfaces.\n\n Happy coding!\n\n\n Join the discussion within GitHub Community\
  \ .\n\n\n\n The post GitHub Copilot in Visual Studio Code, May releases appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
