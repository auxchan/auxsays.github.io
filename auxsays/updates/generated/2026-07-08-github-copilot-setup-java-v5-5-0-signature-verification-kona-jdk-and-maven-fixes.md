---
layout: aux-update
title: 'GitHub / Copilot setup-java v5.5.0: signature verification, Kona JDK, and Maven fixes official update breakdown'
description: Official GitHub / Copilot update record captured from GitHub.
permalink: /updates/github/github/setup-java-v5-5-0-signature-verification-kona-jdk-and-maven-fixes/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-07-08-setup-java-v5-5-0-signature-verification-kona-jdk-and-maven-fixes
update_download_url: ''
update_version: 'setup-java v5.5.0: signature verification, Kona JDK, and Maven fixes'
update_logo_text: GIT
update_published_at: '2026-07-08T17:05:06Z'
update_last_checked: '2026-07-08T19:57:41Z'
source_last_checked: '2026-07-08T19:57:41Z'
official_body_last_checked: '2026-07-08T19:57:41Z'
record_last_updated: '2026-07-08T19:57:41Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: 'GitHub / Copilot setup-java v5.5.0: signature verification, Kona JDK, and Maven fixes'
update_detail_title: 'GitHub / Copilot setup-java v5.5.0: signature verification, Kona JDK, and Maven fixes'
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: 'GitHub / Copilot setup-java v5.5.0: signature verification, Kona JDK, and Maven fixes has an official AUXSAYS
  record. Confirmed patch-specific consensus is deferred until the consensus refresh pipeline is active.'
official_summary: 'GitHub published GitHub / Copilot setup-java v5.5.0: signature verification, Kona JDK, and Maven fixes.'
release_summary: "The actions/setup-java v5.5.0 release adds cryptographic signature verification for downloaded JDKs, support\
  \ for a new distribution, and several quality-of-life improvements for Maven users. Here’s what changed since v5.4.0.\n\n\
  \n\n Verify JDK download signatures: Set verify-signature: true and the action downloads the detached GPG signature and\
  \ validates the JDK archive before installing it. Verification is supported today for the Temurin and Microsoft distributions,\
  \ and enabling it for a distribution that doesn’t support it fails fast rather than silently skipping the check. You can\
  \ supply your own trusted key with verify-signature-public-key .\n New Tencent Kona JDK distribution: The new kona distribution\
  \ lets you install Tencent Kona JDK directly.\n Install a JDK without making it the default. With set-default: false , the\
  \ action leaves JAVA_HOME and PATH untouched while still exporting JAVA_HOME__ and registering the JDK in Maven toolchains,\
  \ so a single step can use a specific JDK without disturbing the rest of your workflow.\n Auto-detect the distribution from\
  \ .sdkmanrc : When you drive your Java version from a .sdkmanrc file, the action now infers the distribution from the SDKMAN\
  \ identifier suffix (e.g., -tem resolves to Temurin), so you no longer have to repeat it in the distribution input.\n Cleaner\
  \ Maven build logs by default: The action now sets --no-transfer-progress in MAVEN_ARGS by default for Maven 3.9+ and the\
  \ Maven Wrapper, giving you quieter logs out of the box. Any existing MAVEN_ARGS value is preserved, and you can restore\
  \ the progress output with show-download-progress: true . The generated settings.xml also disables interactive mode so Maven\
  \ never blocks a CI run waiting on a prompt.\n Fixed Maven toolchains no longer grow unexpectedly: Running the action multiple\
  \ times in a job previously appended duplicate entries to toolchains.xml . The generated file is now deduplicated by toolchain\
  \ type and id, and your existing root attributes and non-JDK toolchains are preserved.\n\n The v5.4.0 release shipped without\
  \ a changelog post, so a few notable additions from that version are worth calling out too:\n\n\n\n The free GraalVM Community\
  \ distribution ( graalvm-community )\n A javac problem matcher that surfaces compiler errors and warnings as inline annotations\
  \ on your pull requests\n Maven Wrapper caching when you enable cache: maven\n\n For reproducible, supply-chain-safe builds,\
  \ pin the action to the exact v5.5.0 release tag or to its full commit SHA ( 0f481fcb613427c0f801b606911222b5b6f3083a )\
  \ for the strongest guarantee, rather than the floating v5 major tag.\n\n\n For the full list of inputs and examples, see\
  \ the setup-java advanced usage guide and the v5.5.0 release notes . As always, we welcome feedback and issues in the actions/setup-java\
  \ repository.\n\n\n\n The post setup-java v5.5.0: signature verification, Kona JDK, and Maven fixes appeared first on The\
  \ GitHub Blog ."
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
- at: '2026-07-08T17:05:06Z'
  label: Published
  note: Official source entry detected.
- at: '2026-07-08T19:57:45Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-07-08-setup-java-v5-5-0-signature-verification-kona-jdk-and-maven-fixes
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-07-08T19:57:41Z'
  url: https://github.blog/changelog/2026-07-08-setup-java-v5-5-0-signature-verification-kona-jdk-and-maven-fixes
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "The actions/setup-java v5.5.0 release adds cryptographic signature verification for downloaded\
  \ JDKs, support for a new distribution, and several quality-of-life improvements for Maven users. Here’s what changed since\
  \ v5.4.0.\n\n\n\n Verify JDK download signatures: Set verify-signature: true and the action downloads the detached GPG signature\
  \ and validates the JDK archive before installing it. Verification is supported today for the Temurin and Microsoft distributions,\
  \ and enabling it for a distribution that doesn’t support it fails fast rather than silently skipping the check. You can\
  \ supply your own trusted key with verify-signature-public-key .\n New Tencent Kona JDK distribution: The new kona distribution\
  \ lets you install Tencent Kona JDK directly.\n Install a JDK without making it the default. With set-default: false , the\
  \ action leaves JAVA_HOME and PATH untouched while still exporting JAVA_HOME__ and registering the JDK in Maven toolchains,\
  \ so a single step can use a specific JDK without disturbing the rest of your workflow.\n Auto-detect the distribution from\
  \ .sdkmanrc : When you drive your Java version from a .sdkmanrc file, the action now infers the distribution from the SDKMAN\
  \ identifier suffix (e.g., -tem resolves to Temurin), so you no longer have to repeat it in the distribution input.\n Cleaner\
  \ Maven build logs by default: The action now sets --no-transfer-progress in MAVEN_ARGS by default for Maven 3.9+ and the\
  \ Maven Wrapper, giving you quieter logs out of the box. Any existing MAVEN_ARGS value is preserved, and you can restore\
  \ the progress output with show-download-progress: true . The generated settings.xml also disables interactive mode so Maven\
  \ never blocks a CI run waiting on a prompt.\n Fixed Maven toolchains no longer grow unexpectedly: Running the action multiple\
  \ times in a job previously appended duplicate entries to toolchains.xml . The generated file is now deduplicated by toolchain\
  \ type and id, and your existing root attributes and non-JDK toolchains are preserved.\n\n The v5.4.0 release shipped without\
  \ a changelog post, so a few notable additions from that version are worth calling out too:\n\n\n\n The free GraalVM Community\
  \ distribution ( graalvm-community )\n A javac problem matcher that surfaces compiler errors and warnings as inline annotations\
  \ on your pull requests\n Maven Wrapper caching when you enable cache: maven\n\n For reproducible, supply-chain-safe builds,\
  \ pin the action to the exact v5.5.0 release tag or to its full commit SHA ( 0f481fcb613427c0f801b606911222b5b6f3083a )\
  \ for the strongest guarantee, rather than the floating v5 major tag.\n\n\n For the full list of inputs and examples, see\
  \ the setup-java advanced usage guide and the v5.5.0 release notes . As always, we welcome feedback and issues in the actions/setup-java\
  \ repository.\n\n\n\n The post setup-java v5.5.0: signature verification, Kona JDK, and Maven fixes appeared first on The\
  \ GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
