---
layout: aux-update
title: GitHub / Copilot Purpose-built model for leaked secret detection official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Purpose-built model for leaked secret detection.
permalink: /updates/github/github/purpose-built-model-for-leaked-secret-detection/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-10-07-purpose-built-model-for-leaked-secret-detection
update_download_url: ''
update_version: Purpose-built model for leaked secret detection
update_logo_text: GIT
update_published_at: '2026-10-07T16:13:56Z'
update_last_checked: '2026-10-08T01:59:39Z'
source_last_checked: '2026-10-08T01:59:39Z'
official_body_last_checked: '2026-10-08T01:59:39Z'
record_last_updated: '2026-10-08T01:59:39Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Purpose-built model for leaked secret detection
update_detail_title: GitHub / Copilot Purpose-built model for leaked secret detection
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Purpose-built model for leaked secret detection has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Purpose-built model for leaked secret detection.
release_summary: "Secret protection should keep pace with the way you build software, whether you write code yourself or work\
  \ with an AI agent. With our new purpose-built model, we’re bringing context-aware detection into more developer workflows\
  \ to help you catch secrets before they’re exposed.\n\n\n What’s new\n Today, we’re sharing plans for AI secret detection\
  \ across secret scanning alerts, push protection, and GitHub Copilot security reviews. These features leverage GitHub’s\
  \ fine-tuned model for secret detection. It reads surrounding code to identify likely credentials, including passwords without\
  \ a recognizable token format, without generating code or prose.\n\n\n Model availability:\n\n\n\n Customers with AI-detected\
  \ Password alerts have automatically been upgraded to the new model.\n AI-detected secrets in push protection is available\
  \ in private preview.\n AI-based secret scanning with the GitHub Copilot /security-review command for the Copilot CLI and\
  \ Copilot app available soon in private preview.\n\n Billing notice and availability\n AI-detected secret alerts will remain\
  \ included in GHSP and GHAS at no additional charge. The new opt-in checks for push protection and the security review command\
  \ will consume GitHub AI Credits.\n\n\n We’re sharing their planned billing model ahead of broader availability so you can\
  \ review access and spending before enabling them.\n\n\n This notice applies to the following features:\n\n\n\n AI-detected\
  \ secrets in push protection for GitHub Secret Protection (GHSP) and GitHub Advanced Security (GHAS)\n AI-based secret scanning\
  \ with the GitHub Copilot /security-review command\n\n AI Credit usage for these opt-in checks will be introduced in the\
  \ coming weeks.\n\n\n AI-detected alerts remain included with Secret Protection\n Starting today, existing AI-detected secret\
  \ alert scans will automatically switch to the new model at no additional charge for GHSP and GHAS customers. These scans\
  \ remain included in GHSP and GHAS, separate from the new credit-consuming checks.\n\n\n AI-detected alerts are coming to\
  \ GitHub Enterprise Server\n The model will also bring AI-detected alerts to GHES 3.23 in public preview. This feature is\
  \ included with an enterprise’s existing purchase of GHSP and GHAS.\n\n\n AI secret detection in push protection\n AI push\
  \ protection checks for unstructured credentials at push time, giving you a chance to remove a secret before it enters repository\
  \ history. The feature will be available to customers on GitHub Enterprise Cloud or GitHub Teams with a purchase of GHSP\
  \ or GHAS. An administrator must enable it, subject to your organization’s or enterprise’s policies.\n\n\n The planned AI\
  \ Credit usage will be billed to the organization that owns the repository. A check can consume credits even if it doesn’t\
  \ block a push. Outside of user-namespace repositories for enterprise-managed users (EMUs), where usage is attributed to\
  \ the pusher and apply to the user’s allocated credits, AI Credit usage will be attributed to the organization and will\
  \ not apply to any specific user’s allocated credits. Usage will be listed under AI Credit consumption for the Secret Protection\
  \ AI Credits SKU in your AI usage insights.\n\n\n Billing begins once your organization opts into the public preview and\
  \ enables the feature.\n\n\n AI secret checks in GitHub Copilot /security-review\n In a supported Copilot CLI or Copilot\
  \ App session, use /security-review before committing, pushing, or requesting pull request review. It reviews active changes\
  \ for security vulnerabilities and returns prioritized findings with remediation suggestions.\n\n\n Developers and coding\
  \ agents can use the built-in security-review specialist, address confirmed findings with the appropriate authorization,\
  \ and run the review again after fixes. The review is read-only—existing Copilot policies and billing apply.\n\n\n Coming\
  \ soon, GitHub is adding checks from the secret classifier alongside the existing LLM-based review. You don’t need a GHSP\
  \ or GHAS license to use these checks. The new checks will consume AI Credits in addition to the review’s existing usage.\
  \ The billing account for your active Copilot plan will receive this usage, reported under GHSP in your AI usage insights.\
  \ Billing begins once you opt into the public preview and enable the feature.\n\n\n The new checks will be off by default.\
  \ Running /security-review won’t enable them. You must opt in where your plan and policies allow. Agents shouldn’t enable\
  \ credit-consuming features or change policies or budgets without explicit authorization.\n\n\n See the Copilot CLI security-review\
  \ agent documentation and security-review instructions for Copilot App sessions .\n\n\n Plans and platforms\n GitHub hosting\
  \ plans, GHSP licenses, and Copilot subscriptions are separate. GitHub Enterprise (GHE) includes GitHub Enterprise Cloud\
  \ (GHEC) and GitHub Enterprise Server (GHES). Copilot Enterprise is a separate Copilot subscription.\n\n\n\n\n\n Plan or\
  \ platform\n Eligibility for these updates\n\n\n\n\n GitHub Team and GHEC on github.com\n AI push protection requires paid\
  \ GHSP or GHAS coverage. Public, private, and internal repositories can qualify.\n\n\n GHEC with data residency on ghe.com\n\
  \ Copilot Business and Enterprise are supported plans on this platform with the Copilot security review command. AI push\
  \ protection is planned with paid GHSP/GHAS coverage.\n\n\n GHES\n The new model is planned for AI-detected alerts in GHES\
  \ 3.23, at no additional charge with GHSP/GHAS. AI push protection isn’t part of this Server release. The Copilot security\
  \ review command isn’t part of this Server release.\n\n\n Individual Copilot plans : Pro, Pro+, Max, Free, and Student\n\
  \ Eligible for security review checks with the new model, subject to access controls and credit consumption. No GHSP or\
  \ GHAS license is required.\n\n\n Copilot Business and Copilot Enterprise\n Eligible for security review checks with the\
  \ new model on supported platforms, subject to invitation and administrator policies. These subscriptions don’t replace\
  \ the GHSP license required for AI push protection.\n\n\n\n Manage access and spending\n Organization and enterprise administrators\
  \ will be able to disable the new capabilities by policy and set budgets for their AI Credit usage. Opting in won’t override\
  \ those controls. Applicable included credits and any additional paid usage follow your account’s billing policies and limits.\n\
  \n\n To set a dedicated budget, open Billing and licensing and select Budgets and alerts . Choose SKU-level budget , Advanced\
  \ Security as the product, and Secret Protection AI Credits as the SKU. An all AI Credits budget can cover multiple credit-consuming\
  \ SKUs.\n\n\n Budget alerts alone don’t stop usage. Configure Stop usage when budget limit is reached where available if\
  \ you want a spending cap.\n\n\n If you’re already using AI push protection in private preview, continued use after this\
  \ billing change takes effect will consume AI Credits. Disable it beforehand if you don’t want that usage. AI-detected alert\
  \ scanning remains included at no additional charge.\n\n\n Before enabling or continuing the new checks, review the eligibility,\
  \ AI Credit pricing, and billing details above, along with your budget settings and documentation for usage-based billing\
  \ .\n\n\n\n The post Purpose-built model for leaked secret detection appeared first on The GitHub Blog ."
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
- at: '2026-10-07T16:13:56Z'
  label: Published
  note: Official source entry detected.
- at: '2026-10-08T02:00:02Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-10-07-purpose-built-model-for-leaked-secret-detection
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-10-08T01:59:39Z'
  url: https://github.blog/changelog/2026-10-07-purpose-built-model-for-leaked-secret-detection
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "Secret protection should keep pace with the way you build software, whether you write code yourself\
  \ or work with an AI agent. With our new purpose-built model, we’re bringing context-aware detection into more developer\
  \ workflows to help you catch secrets before they’re exposed.\n\n\n What’s new\n Today, we’re sharing plans for AI secret\
  \ detection across secret scanning alerts, push protection, and GitHub Copilot security reviews. These features leverage\
  \ GitHub’s fine-tuned model for secret detection. It reads surrounding code to identify likely credentials, including passwords\
  \ without a recognizable token format, without generating code or prose.\n\n\n Model availability:\n\n\n\n Customers with\
  \ AI-detected Password alerts have automatically been upgraded to the new model.\n AI-detected secrets in push protection\
  \ is available in private preview.\n AI-based secret scanning with the GitHub Copilot /security-review command for the Copilot\
  \ CLI and Copilot app available soon in private preview.\n\n Billing notice and availability\n AI-detected secret alerts\
  \ will remain included in GHSP and GHAS at no additional charge. The new opt-in checks for push protection and the security\
  \ review command will consume GitHub AI Credits.\n\n\n We’re sharing their planned billing model ahead of broader availability\
  \ so you can review access and spending before enabling them.\n\n\n This notice applies to the following features:\n\n\n\
  \n AI-detected secrets in push protection for GitHub Secret Protection (GHSP) and GitHub Advanced Security (GHAS)\n AI-based\
  \ secret scanning with the GitHub Copilot /security-review command\n\n AI Credit usage for these opt-in checks will be introduced\
  \ in the coming weeks.\n\n\n AI-detected alerts remain included with Secret Protection\n Starting today, existing AI-detected\
  \ secret alert scans will automatically switch to the new model at no additional charge for GHSP and GHAS customers. These\
  \ scans remain included in GHSP and GHAS, separate from the new credit-consuming checks.\n\n\n AI-detected alerts are coming\
  \ to GitHub Enterprise Server\n The model will also bring AI-detected alerts to GHES 3.23 in public preview. This feature\
  \ is included with an enterprise’s existing purchase of GHSP and GHAS.\n\n\n AI secret detection in push protection\n AI\
  \ push protection checks for unstructured credentials at push time, giving you a chance to remove a secret before it enters\
  \ repository history. The feature will be available to customers on GitHub Enterprise Cloud or GitHub Teams with a purchase\
  \ of GHSP or GHAS. An administrator must enable it, subject to your organization’s or enterprise’s policies.\n\n\n The planned\
  \ AI Credit usage will be billed to the organization that owns the repository. A check can consume credits even if it doesn’t\
  \ block a push. Outside of user-namespace repositories for enterprise-managed users (EMUs), where usage is attributed to\
  \ the pusher and apply to the user’s allocated credits, AI Credit usage will be attributed to the organization and will\
  \ not apply to any specific user’s allocated credits. Usage will be listed under AI Credit consumption for the Secret Protection\
  \ AI Credits SKU in your AI usage insights.\n\n\n Billing begins once your organization opts into the public preview and\
  \ enables the feature.\n\n\n AI secret checks in GitHub Copilot /security-review\n In a supported Copilot CLI or Copilot\
  \ App session, use /security-review before committing, pushing, or requesting pull request review. It reviews active changes\
  \ for security vulnerabilities and returns prioritized findings with remediation suggestions.\n\n\n Developers and coding\
  \ agents can use the built-in security-review specialist, address confirmed findings with the appropriate authorization,\
  \ and run the review again after fixes. The review is read-only—existing Copilot policies and billing apply.\n\n\n Coming\
  \ soon, GitHub is adding checks from the secret classifier alongside the existing LLM-based review. You don’t need a GHSP\
  \ or GHAS license to use these checks. The new checks will consume AI Credits in addition to the review’s existing usage.\
  \ The billing account for your active Copilot plan will receive this usage, reported under GHSP in your AI usage insights.\
  \ Billing begins once you opt into the public preview and enable the feature.\n\n\n The new checks will be off by default.\
  \ Running /security-review won’t enable them. You must opt in where your plan and policies allow. Agents shouldn’t enable\
  \ credit-consuming features or change policies or budgets without explicit authorization.\n\n\n See the Copilot CLI security-review\
  \ agent documentation and security-review instructions for Copilot App sessions .\n\n\n Plans and platforms\n GitHub hosting\
  \ plans, GHSP licenses, and Copilot subscriptions are separate. GitHub Enterprise (GHE) includes GitHub Enterprise Cloud\
  \ (GHEC) and GitHub Enterprise Server (GHES). Copilot Enterprise is a separate Copilot subscription.\n\n\n\n\n\n Plan or\
  \ platform\n Eligibility for these updates\n\n\n\n\n GitHub Team and GHEC on github.com\n AI push protection requires paid\
  \ GHSP or GHAS coverage. Public, private, and internal repositories can qualify.\n\n\n GHEC with data residency on ghe.com\n\
  \ Copilot Business and Enterprise are supported plans on this platform with the Copilot security review command. AI push\
  \ protection is planned with paid GHSP/GHAS coverage.\n\n\n GHES\n The new model is planned for AI-detected alerts in GHES\
  \ 3.23, at no additional charge with GHSP/GHAS. AI push protection isn’t part of this Server release. The Copilot security\
  \ review command isn’t part of this Server release.\n\n\n Individual Copilot plans : Pro, Pro+, Max, Free, and Student\n\
  \ Eligible for security review checks with the new model, subject to access controls and credit consumption. No GHSP or\
  \ GHAS license is required.\n\n\n Copilot Business and Copilot Enterprise\n Eligible for security review checks with the\
  \ new model on supported platforms, subject to invitation and administrator policies. These subscriptions don’t replace\
  \ the GHSP license required for AI push protection.\n\n\n\n Manage access and spending\n Organization and enterprise administrators\
  \ will be able to disable the new capabilities by policy and set budgets for their AI Credit usage. Opting in won’t override\
  \ those controls. Applicable included credits and any additional paid usage follow your account’s billing policies and limits.\n\
  \n\n To set a dedicated budget, open Billing and licensing and select Budgets and alerts . Choose SKU-level budget , Advanced\
  \ Security as the product, and Secret Protection AI Credits as the SKU. An all AI Credits budget can cover multiple credit-consuming\
  \ SKUs.\n\n\n Budget alerts alone don’t stop usage. Configure Stop usage when budget limit is reached where available if\
  \ you want a spending cap.\n\n\n If you’re already using AI push protection in private preview, continued use after this\
  \ billing change takes effect will consume AI Credits. Disable it beforehand if you don’t want that usage. AI-detected alert\
  \ scanning remains included at no additional charge.\n\n\n Before enabling or continuing the new checks, review the eligibility,\
  \ AI Credit pricing, and billing details above, along with your budget settings and documentation for usage-based billing\
  \ .\n\n\n\n The post Purpose-built model for leaked secret detection appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
