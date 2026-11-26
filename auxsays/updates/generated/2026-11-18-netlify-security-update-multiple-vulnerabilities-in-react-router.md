---
layout: aux-update
title: 'Netlify Security Update: Multiple vulnerabilities in React Router official update breakdown'
description: 'Official Netlify update record captured from Netlify for Security Update: Multiple vulnerabilities in React
  Router.'
permalink: /updates/netlify/netlify/security-update-multiple-vulnerabilities-in-react-router/
update_entry: true
company_id: netlify
product_id: netlify
update_brand_id: netlify
update_product: Netlify
update_category: Dev / Web
update_type: official-source
update_source_name: Netlify
update_source_url: https://www.netlify.com/changelog/2026-11-18-react-router-security-vulnerabilities/
update_download_url: ''
update_version: 'Security Update: Multiple vulnerabilities in React Router'
update_logo_text: NET
update_published_at: '2026-11-18T00:00:00Z'
update_last_checked: '2026-11-26T01:35:11Z'
source_last_checked: '2026-11-26T01:35:11Z'
official_body_last_checked: '2026-11-26T01:35:11Z'
record_last_updated: '2026-11-26T01:35:11Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'Netlify Security Update: Multiple vulnerabilities in React Router'
update_detail_title: 'Netlify Security Update: Multiple vulnerabilities in React Router'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'Netlify Security Update: Multiple vulnerabilities in React Router has an official AUXSAYS record. Confirmed
  patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'Netlify published Netlify Security Update: Multiple vulnerabilities in React Router.'
release_summary: '← All changelog entries November 18, 2026 Security Update: Multiple vulnerabilities in React Router security
  remix The React Router team has disclosed seven security vulnerabilities in React Router. Most have limited impact on Netlify,
  but if your site uses React Router, you should update it. If your site doesn’t use React Router, you don’t need to do anything.
  Am I affected? Your site may be affected if it uses.'
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
- at: '2026-11-18T00:00:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-26T01:35:38Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: html-changelog
primary_official_source: https://www.netlify.com/changelog/
fallback_official_sources: []
official_patch_notes_capture_status: captured-from-official-html
official_patch_notes_source_url: https://www.netlify.com/changelog/2026-11-18-react-router-security-vulnerabilities/
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: html-changelog
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-11-26T01:35:11Z'
  url: https://www.netlify.com/changelog/2026-11-18-react-router-security-vulnerabilities/
  status: captured-from-official-html
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "← All changelog entries November 18, 2026 Security Update: Multiple vulnerabilities in React Router\
  \ security remix The React Router team has disclosed seven security vulnerabilities in React Router. Most have limited impact\
  \ on Netlify, but if your site uses React Router, you should update it. If your site doesn’t use React Router, you don’t\
  \ need to do anything.\n\n\n Am I affected?\n Your site may be affected if it uses React Router 6, 7, or 8, either directly\
  \ or through a framework built on it. These frameworks include, but aren’t limited to:\n\n\n\n Remix 2, which uses React\
  \ Router 6\n Shopify Hydrogen, which uses React Router 7\n\n Sites that don’t use React Router aren’t affected.\n\n\n To\
  \ check:\n\n\n\n In your site’s folder, install your dependencies, then list the installed React Router packages, using\
  \ the commands for your package manager in the table below. In a monorepo, run them in the folder of the site you deploy,\
  \ not the repository root. This lists every installed copy and its version, including copies that another framework, such\
  \ as Remix 2, brings in. It only sees installed packages, so install first.\n This checks the code in your project folder,\
  \ not what’s deployed. Older deploys keep running the code they were built with, as explained under “What should I do?”.\n\
  \ You can also open your project’s package.json file and look for react-router or packages starting with @react-router/\
  \ . A framework built on React Router may not list it there, so listing the installed packages is more reliable.\n If an\
  \ AI tool built your site and you’re not sure, ask it: “Does this project use React Router, directly or through another\
  \ package? If so, which version?”\n If you have a Credit plan with Agent Runners, you can ask the same question in Ask mode\
  \ .\n\n\n\n\n Step\n npm\n pnpm\n Yarn\n\n\n\n\n Install dependencies\n npm install\n pnpm install\n yarn install\n\n\n\
  \ List installed versions\n npm ls react-router @react-router/node @react-router/serve @react-router/dev\n pnpm why react-router\
  \ @react-router/node @react-router/serve @react-router/dev\n yarn why react-router , then repeat for @react-router/node\
  \ , @react-router/serve , and @react-router/dev\n\n\n Update within your version range\n npm update react-router react-router-dom\
  \ @react-router/node @react-router/serve @react-router/dev\n pnpm update react-router react-router-dom @react-router/node\
  \ @react-router/serve @react-router/dev\n Install the patched version for your major version directly (next row)\n\n\n Install\
  \ a patched version directly\n npm install react-router@^7.18.6 (7.x) or npm install react-router@^8.5.1 (8.x)\n pnpm add\
  \ react-router@^7.18.6 (7.x) or pnpm add react-router@^8.5.1 (8.x)\n yarn add react-router@^7.18.6 (7.x) or yarn add react-router@^8.5.1\
  \ (8.x)\n\n\n\n What should I do?\n If your site uses React Router 7 or 8, update it to a patched version and deploy again:\n\
  \n\n\n Check that your package.json lists React Router packages with a ^ or ~ version range, such as ^7.17.0 . A range such\
  \ as * lets the update move you to a new major version, which can include breaking changes.\n In the same folder, run the\
  \ update command for your package manager from the table above. With npm and pnpm, it only installs versions that your package.json\
  \ allows, so it keeps you on your current major version. With Yarn, install the patched version for your current major version.\n\
  \ List the installed versions again and compare each package with its patched version below. If any are still affected:\n\
  \n If the affected copy is nested under another package, such as react-router-dom or a framework, update that package. Installing\
  \ react-router on its own doesn’t replace a copy that another package pins.\n Otherwise, install a patched version directly,\
  \ such as react-router@^7.18.6 or react-router@^8.5.1 , and do the same for any @react-router/ packages you use. Then list\
  \ the installed versions again to confirm every copy is patched.\n\n\n Commit every file the update changed, including package.json\
  \ and your lockfile, such as package-lock.json , pnpm-lock.yaml , or yarn.lock , then deploy.\n\n If an AI tool built your\
  \ site, you can ask it to “update React Router to the latest patched version”.\n\n\n The patched versions are:\n\n\n\n react-router\
  \ 8.5.1 or later (for React Router 8.x)\n react-router 7.18.5 or later (for React Router 7.x)\n @react-router/node , @react-router/serve\
  \ , and @react-router/dev 8.5.1 or later (for React Router 8.x)\n @react-router/node and @react-router/serve 7.18.6 or later\
  \ (for React Router 7.x)\n\n React Router 6 and Remix 2: there is no patched React Router 6.x release for GHSA-x8j4-g9rr-8j87\
  \ or GHSA-7m2v-44vx-v55w, and npm update can’t fix them. To fix these two issues, you need to upgrade to a patched React\
  \ Router 7 or 8 release listed above. Remix 2 apps use React Router 6, so they need to move to React Router 7 .\n\n\n Make\
  \ sure the IS_RR_BUILD_REQUEST environment variable is not set on your site or as a shared environment variable on your\
  \ team. React Router sets it automatically during builds, and it should never be configured in your environment variables.\
  \ If you find it, remove it, then create and publish a new deploy. Existing deploys keep the environment variables they\
  \ were deployed with, so older deploys created while the variable was set stay affected until they’re deleted (see the next\
  \ paragraph).\n\n\n Note that older deploys keep running the code they were built with. Publicly available deploy previews\
  \ and older production deploys may remain vulnerable until they are automatically deleted , and Netlify never automatically\
  \ deletes the most recent successful deploy of each branch, so branch deploys can stay vulnerable indefinitely. If you’ve\
  \ locked auto publishing, Netlify builds your patched deploy but doesn’t publish it, so publish it manually. You can’t delete\
  \ a deploy while it’s published. Check your deploys and delete vulnerable ones manually .\n\n\n Vulnerabilities\n\n\n\n\
  \ Vulnerability\n Affected versions\n Fixed in\n\n\n\n\n GHSA-2rq8-3rm6-2w8f - Server-rendering DoS\n react-router 7.0.0–7.18.4,\
  \ 8.0.0"
official_checksums_body: ''
official_checksums_capture_status: not-present
---
