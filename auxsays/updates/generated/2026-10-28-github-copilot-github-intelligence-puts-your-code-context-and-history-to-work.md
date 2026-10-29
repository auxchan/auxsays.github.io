---
layout: aux-update
title: GitHub / Copilot GitHub intelligence puts your code, context, and history to work official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for GitHub intelligence puts your code, context,
  and history to work.
permalink: /updates/github/github/github-intelligence-puts-your-code-context-and-history-to-work/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-28-github-intelligence-puts-your-code-context-and-history-to-work
update_download_url: ''
update_version: GitHub intelligence puts your code, context, and history to work
update_logo_text: GIT
update_published_at: '2026-10-28T15:40:00Z'
update_last_checked: '2026-10-29T15:59:32Z'
source_last_checked: '2026-10-29T15:59:32Z'
official_body_last_checked: '2026-10-29T15:59:32Z'
record_last_updated: '2026-10-29T15:59:32Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot GitHub intelligence puts your code, context, and history to work
update_detail_title: GitHub / Copilot GitHub intelligence puts your code, context, and history to work
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot GitHub intelligence puts your code, context, and history to work has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot GitHub intelligence puts your code, context, and history to work.
release_summary: "Agents should understand more than your codebase—they should understand how your team works. Your preferences,\
  \ repository conventions, skills, and custom instructions guide how changes should be made, while code in related repositories\
  \ can show how the pieces fit together. Without that context, agents spend time rediscovering knowledge and can miss your\
  \ team’s conventions.\n\n\n GitHub intelligence is the context and learning layer sourced from the graph of GitHub data.\
  \ It makes this data useful to agents, helping them remember how you work, keep that guidance current, and find the code\
  \ and development history relevant to the next task. The goal is for agents to build on what you and your team already know,\
  \ rather than treating every session as a fresh start.\n\n\n That is the advantage of building where your team’s work already\
  \ lives. A repository memory can capture why an edge case matters and which test covers it. GitHub intelligence allows agents\
  \ to use that context, with controls over what they can access.\n\n\n Three capabilities bring this into your workflow:\n\
  \n\n\n Memory carries knowledge between sessions\n Dreaming keeps the context current\n Code search reaches beyond your\
  \ checkout.\n\n Availability and settings vary by capability.\n\n\n Memory: Pick up where you left off\n GitHub Copilot\
  \ Memory is now generally available on paid Copilot plans. Copilot can remember personal preferences and repository conventions\
  \ across sessions and clients. Memories can be created in the Copilot app, Copilot CLI, VS Code, Copilot cloud agent, Copilot\
  \ code review, Slack, Teams, and GitHub Mobile.\n\n\n You can tell Copilot, Remember to start my pull request descriptions\
  \ with a TL;DR , and it can reuse that preference across Copilot experiences. Repository memories can capture the right\
  \ test command or how your team expects Copilot to check its work, so you spend less time repeating guidance in each session.\
  \ Copilot sessions autonomously generate and curate memories, learning from every interaction.\n\n\n Among the Copilot CLI\
  \ sessions reviewed during the public preview where the agent used memory, 93% showed better adherence to developer preferences\
  \ and 42% showed more efficient workflows attributed to the memories included in the session context.\n\n\n You can interact\
  \ with memories in the Copilot app, Copilot CLI, and VS Code, or manage personal memories in your Copilot settings, where\
  \ you can view or delete saved preferences .\n\n\n Dreaming: Continuous context improvement\n Copilot dreaming, now in public\
  \ preview, reflects on past work to improve future agentic sessions.\n\n\n Three dream types are currently available:\n\n\
  \n\n Personal memory curation customizes Copilot to your personal preferences by updating memories based on your agent conversations.\n\
  \ Repository customization manages repository-scoped memories and proposes updates and improvements to existing skills and\
  \ custom instruction files.\n Code review customization turns recurring accepted code-review feedback into guidance for\
  \ Copilot code review.\n\n Dreaming can add, update, and remove personal and repository memories. Changes to checked-in\
  \ skills and instructions are proposed in pull requests for your team to review.\n\n\n Dreaming is opt-in.\n\n\n\n Individual\
  \ subscribers: Enable personal curation in your Copilot settings and repository dreams in each repository’s settings. See\
  \ personal and repository setup .\n Organizations and enterprises: Administrators enable dreaming through Copilot policies\
  \ . Enterprise administrators can delegate that choice to organization administrators. Repository dreams cover the repositories\
  \ allowed by Copilot Memory’s repository access settings. Users must also enable personal dreaming in their own Copilot\
  \ settings.\n\n Dream runs consume AI credits. See the dreaming documentation for prerequisites, setup, and costs .\n\n\n\
  \ Code Search: Reach beyond your checkout\n Software projects rarely live in a single repository. GitHub code search helps\
  \ Copilot find relevant code, configuration, schemas, and documentation across related projects and dependencies without\
  \ needing a local clone. Copilot can search for exact text and symbols, match patterns with regular expressions, and narrow\
  \ results by repository, path, or language. Semantic search can also find code by what it does, such as retrying a failed\
  \ payment, even when you don’t know the file, function name, or repository it lives in.\n\n\n For example, you’re fixing\
  \ failed payments, but retry behavior spans a payments service, a shared library, and background workers. Use /research\
  \ to ask Copilot, How do these components retry failed charges, and where could retries overlap? Copilot can inspect implementations\
  \ and callers across those repositories to help you understand how the system fits together before changing it.\n\n\n That\
  \ unlocks workflows that would otherwise require you to assemble the context yourself:\n\n\n\n Plan a migration: Use /research\
  \ to identify implementations and callers across repositories, plan the changes each service needs, and check which projects\
  \ still use the old API.\n Investigate a bug: Trace related implementations across services and shared libraries, bring\
  \ specific code references into the investigation, and use that context to propose a coordinated fix.\n Follow organizational\
  \ standards: Find existing patterns across your organization and use them to guide changes in an unfamiliar codebase.\n\n\
  \ Whether the task calls for an exact symbol, a regular expression in file contents or paths, or a natural-language description,\
  \ Copilot can search across repositories in your organization to find relevant context. You spend less time cloning projects,\
  \ tracking down files, and copying code into the conversation. In addition, Copilot gets the context it needs to make the\
  \ right changes.\n\n\n Try it today\n Your team shouldn’t have to teach every agent the same lessons. GitHub intelligence\
  \ helps agents carry those lessons forward, find the context they need, and put more of each session toward the work you\
  \ actually want done.\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post GitHub intelligence puts your\
  \ code, context, and history to work appeared first on The GitHub Blog ."
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
- at: '2026-10-28T15:40:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-29T15:59:44Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-28-github-intelligence-puts-your-code-context-and-history-to-work
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-29T15:59:32Z'
  url: https://github.blog/changelog/2026-10-28-github-intelligence-puts-your-code-context-and-history-to-work
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Agents should understand more than your codebase—they should understand how your team works. Your\
  \ preferences, repository conventions, skills, and custom instructions guide how changes should be made, while code in related\
  \ repositories can show how the pieces fit together. Without that context, agents spend time rediscovering knowledge and\
  \ can miss your team’s conventions.\n\n\n GitHub intelligence is the context and learning layer sourced from the graph of\
  \ GitHub data. It makes this data useful to agents, helping them remember how you work, keep that guidance current, and\
  \ find the code and development history relevant to the next task. The goal is for agents to build on what you and your\
  \ team already know, rather than treating every session as a fresh start.\n\n\n That is the advantage of building where\
  \ your team’s work already lives. A repository memory can capture why an edge case matters and which test covers it. GitHub\
  \ intelligence allows agents to use that context, with controls over what they can access.\n\n\n Three capabilities bring\
  \ this into your workflow:\n\n\n\n Memory carries knowledge between sessions\n Dreaming keeps the context current\n Code\
  \ search reaches beyond your checkout.\n\n Availability and settings vary by capability.\n\n\n Memory: Pick up where you\
  \ left off\n GitHub Copilot Memory is now generally available on paid Copilot plans. Copilot can remember personal preferences\
  \ and repository conventions across sessions and clients. Memories can be created in the Copilot app, Copilot CLI, VS Code,\
  \ Copilot cloud agent, Copilot code review, Slack, Teams, and GitHub Mobile.\n\n\n You can tell Copilot, Remember to start\
  \ my pull request descriptions with a TL;DR , and it can reuse that preference across Copilot experiences. Repository memories\
  \ can capture the right test command or how your team expects Copilot to check its work, so you spend less time repeating\
  \ guidance in each session. Copilot sessions autonomously generate and curate memories, learning from every interaction.\n\
  \n\n Among the Copilot CLI sessions reviewed during the public preview where the agent used memory, 93% showed better adherence\
  \ to developer preferences and 42% showed more efficient workflows attributed to the memories included in the session context.\n\
  \n\n You can interact with memories in the Copilot app, Copilot CLI, and VS Code, or manage personal memories in your Copilot\
  \ settings, where you can view or delete saved preferences .\n\n\n Dreaming: Continuous context improvement\n Copilot dreaming,\
  \ now in public preview, reflects on past work to improve future agentic sessions.\n\n\n Three dream types are currently\
  \ available:\n\n\n\n Personal memory curation customizes Copilot to your personal preferences by updating memories based\
  \ on your agent conversations.\n Repository customization manages repository-scoped memories and proposes updates and improvements\
  \ to existing skills and custom instruction files.\n Code review customization turns recurring accepted code-review feedback\
  \ into guidance for Copilot code review.\n\n Dreaming can add, update, and remove personal and repository memories. Changes\
  \ to checked-in skills and instructions are proposed in pull requests for your team to review.\n\n\n Dreaming is opt-in.\n\
  \n\n\n Individual subscribers: Enable personal curation in your Copilot settings and repository dreams in each repository’s\
  \ settings. See personal and repository setup .\n Organizations and enterprises: Administrators enable dreaming through\
  \ Copilot policies . Enterprise administrators can delegate that choice to organization administrators. Repository dreams\
  \ cover the repositories allowed by Copilot Memory’s repository access settings. Users must also enable personal dreaming\
  \ in their own Copilot settings.\n\n Dream runs consume AI credits. See the dreaming documentation for prerequisites, setup,\
  \ and costs .\n\n\n Code Search: Reach beyond your checkout\n Software projects rarely live in a single repository. GitHub\
  \ code search helps Copilot find relevant code, configuration, schemas, and documentation across related projects and dependencies\
  \ without needing a local clone. Copilot can search for exact text and symbols, match patterns with regular expressions,\
  \ and narrow results by repository, path, or language. Semantic search can also find code by what it does, such as retrying\
  \ a failed payment, even when you don’t know the file, function name, or repository it lives in.\n\n\n For example, you’re\
  \ fixing failed payments, but retry behavior spans a payments service, a shared library, and background workers. Use /research\
  \ to ask Copilot, How do these components retry failed charges, and where could retries overlap? Copilot can inspect implementations\
  \ and callers across those repositories to help you understand how the system fits together before changing it.\n\n\n That\
  \ unlocks workflows that would otherwise require you to assemble the context yourself:\n\n\n\n Plan a migration: Use /research\
  \ to identify implementations and callers across repositories, plan the changes each service needs, and check which projects\
  \ still use the old API.\n Investigate a bug: Trace related implementations across services and shared libraries, bring\
  \ specific code references into the investigation, and use that context to propose a coordinated fix.\n Follow organizational\
  \ standards: Find existing patterns across your organization and use them to guide changes in an unfamiliar codebase.\n\n\
  \ Whether the task calls for an exact symbol, a regular expression in file contents or paths, or a natural-language description,\
  \ Copilot can search across repositories in your organization to find relevant context. You spend less time cloning projects,\
  \ tracking down files, and copying code into the conversation. In addition, Copilot gets the context it needs to make the\
  \ right changes.\n\n\n Try it today\n Your team shouldn’t have to teach every agent the same lessons. GitHub intelligence\
  \ helps agents carry those lessons forward, find the context they need, and put more of each session toward the work you\
  \ actually want done.\n\n\n Join the discussion within GitHub Community .\n\n\n\n The post GitHub intelligence puts your\
  \ code, context, and history to work appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
