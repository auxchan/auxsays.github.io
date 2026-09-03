---
layout: aux-update
title: 'GitHub / Copilot GitHub CLI: Media in issues, pull requests, and comments official update breakdown'
description: 'Official GitHub / Copilot update record captured from GitHub for GitHub CLI: Media in issues, pull requests,
  and comments.'
permalink: /updates/github/github/github-cli-media-in-issues-pull-requests-and-comments/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-01-github-cli-media-in-issues-pull-requests-and-comments
update_download_url: ''
update_version: 'GitHub CLI: Media in issues, pull requests, and comments'
update_logo_text: GIT
update_published_at: '2026-09-01T12:35:59Z'
update_last_checked: '2026-09-02T13:17:21Z'
source_last_checked: '2026-09-02T13:17:21Z'
official_body_last_checked: '2026-09-02T13:17:21Z'
record_last_updated: '2026-09-02T13:17:21Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot GitHub CLI: Media in issues, pull requests, and comments'
update_detail_title: 'GitHub / Copilot GitHub CLI: Media in issues, pull requests, and comments'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot GitHub CLI: Media in issues, pull requests, and comments has an official AUXSAYS record.
  Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot GitHub CLI: Media in issues, pull requests, and comments.'
release_summary: "GitHub CLI now has a repeatable --attach flag that uploads a local image or video and references it inline\
  \ in an issue, pull request, or comment body.\n\n\n This is now generally available to all users on GitHub across all plans.\
  \ You just need to update gh to v2.99.0.\n\n\n Why this matters?\n Some things are easier to show than to describe (i.e.,\
  \ a UI bug, a rendered result, an error on screen). Previously, gh only wrote text, so adding an image or video to an issue\
  \ or pull request meant stopping to open the browser, drag the file into the comment box, and copy the result back. Now,\
  \ gh can attach images and videos directly from the command line.\n\n\n --attach puts the image in the same command that\
  \ writes Markdown. File the bug, and the screenshot lands with it, so the issue shows the actual problem the first time.\
  \ Open the pull request with a before and after, and the reviewer sees the change instead of pulling the branch to check.\
  \ Your coding agents get this too, so they can show a result rather than describe it.\n\n\n Capabilities\n\n Attach from\
  \ commands that write Markdown text: --attach is repeatable and works on gh issue create , gh issue edit , gh issue comment\
  \ , gh pr create , gh pr edit , and gh pr comment .\n Keep your Markdown as written: A local path already referenced in\
  \ the body is rewritten in place, so ![alt](./login.png) keeps its alt text and becomes the uploaded asset. Anything attached\
  \ but never referenced is appended at the end.\n Post images and video: PNG, JPEG, GIF, WebP, SVG, MP4, MOV, and WebM are\
  \ all supported.\n Describe what you attach: Alt text follows the path after # , as in --attach './login.png#The login error\
  \ state' . Omit it and gh falls back to the filename.\n\n Security and access controls\n Uploads authenticate with the common\
  \ token types gh already uses, either the OAuth token from gh auth login or a classic personal access token. Write access\
  \ to the repository you are attaching to is required for image uploading.\n\n\n --attach is generally available to all users\
  \ on GitHub across all plans, with no preview period. Size limits match the web upload flow: 10 MB for images and GIFs,\
  \ 10 MB for video on Free plans, and 100 MB for video on paid plans. GitHub Enterprise Server is not supported in this release.\n\
  \n\n Getting started\n Update gh to v2.99.0, then run gh issue comment --attach ./screenshot.png . --attach works the same\
  \ way on gh issue and gh pr create, edit, and comment. Run gh help for the full flag reference.\n\n\n\n\n\n Join the discussion\
  \ on the GitHub Community and read the docs to learn more about attaching files from the command line.\n\n\n Editor’s note\
  \ (September 1, 2026): Updated the doc link.\n\n\n\n The post GitHub CLI: Media in issues, pull requests, and comments appeared\
  \ first on The GitHub Blog ."
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
- at: '2026-09-01T12:35:59Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-02T13:17:29Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-01-github-cli-media-in-issues-pull-requests-and-comments
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-02T13:17:21Z'
  url: https://github.blog/changelog/2026-09-01-github-cli-media-in-issues-pull-requests-and-comments
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "GitHub CLI now has a repeatable --attach flag that uploads a local image or video and references\
  \ it inline in an issue, pull request, or comment body.\n\n\n This is now generally available to all users on GitHub across\
  \ all plans. You just need to update gh to v2.99.0.\n\n\n Why this matters?\n Some things are easier to show than to describe\
  \ (i.e., a UI bug, a rendered result, an error on screen). Previously, gh only wrote text, so adding an image or video to\
  \ an issue or pull request meant stopping to open the browser, drag the file into the comment box, and copy the result back.\
  \ Now, gh can attach images and videos directly from the command line.\n\n\n --attach puts the image in the same command\
  \ that writes Markdown. File the bug, and the screenshot lands with it, so the issue shows the actual problem the first\
  \ time. Open the pull request with a before and after, and the reviewer sees the change instead of pulling the branch to\
  \ check. Your coding agents get this too, so they can show a result rather than describe it.\n\n\n Capabilities\n\n Attach\
  \ from commands that write Markdown text: --attach is repeatable and works on gh issue create , gh issue edit , gh issue\
  \ comment , gh pr create , gh pr edit , and gh pr comment .\n Keep your Markdown as written: A local path already referenced\
  \ in the body is rewritten in place, so ![alt](./login.png) keeps its alt text and becomes the uploaded asset. Anything\
  \ attached but never referenced is appended at the end.\n Post images and video: PNG, JPEG, GIF, WebP, SVG, MP4, MOV, and\
  \ WebM are all supported.\n Describe what you attach: Alt text follows the path after # , as in --attach './login.png#The\
  \ login error state' . Omit it and gh falls back to the filename.\n\n Security and access controls\n Uploads authenticate\
  \ with the common token types gh already uses, either the OAuth token from gh auth login or a classic personal access token.\
  \ Write access to the repository you are attaching to is required for image uploading.\n\n\n --attach is generally available\
  \ to all users on GitHub across all plans, with no preview period. Size limits match the web upload flow: 10 MB for images\
  \ and GIFs, 10 MB for video on Free plans, and 100 MB for video on paid plans. GitHub Enterprise Server is not supported\
  \ in this release.\n\n\n Getting started\n Update gh to v2.99.0, then run gh issue comment --attach ./screenshot.png . --attach\
  \ works the same way on gh issue and gh pr create, edit, and comment. Run gh help for the full flag reference.\n\n\n\n\n\
  \n Join the discussion on the GitHub Community and read the docs to learn more about attaching files from the command line.\n\
  \n\n Editor’s note (September 1, 2026): Updated the doc link.\n\n\n\n The post GitHub CLI: Media in issues, pull requests,\
  \ and comments appeared first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
