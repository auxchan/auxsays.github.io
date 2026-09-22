---
layout: aux-update
title: GitHub / Copilot Security improvements for SSH official update breakdown
description: Official GitHub / Copilot update record captured from GitHub for Security improvements for SSH.
permalink: /updates/github/github/security-improvements-for-ssh/
update_entry: true
company_id: github
product_id: github
update_brand_id: github
update_product: GitHub / Copilot
update_category: Dev / Web
update_type: official-source
update_source_name: GitHub
update_source_url: https://github.blog/changelog/2026-09-22-security-improvements-for-ssh
update_download_url: ''
update_version: Security improvements for SSH
update_logo_text: GIT
update_published_at: '2026-09-22T14:11:47Z'
update_last_checked: '2026-09-22T23:24:44Z'
source_last_checked: '2026-09-22T23:24:44Z'
official_body_last_checked: '2026-09-22T23:24:44Z'
record_last_updated: '2026-09-22T23:24:44Z'
patch_file_size: ''
patch_file_size_note: ''
patch_file_size_status: pending_adapter_support
update_status: current
update_feed_title: GitHub / Copilot Security improvements for SSH
update_detail_title: GitHub / Copilot Security improvements for SSH
update_consensus_label: Insufficient data
update_report_count: 0
update_consensus_confidence: Low
quick_verdict: GitHub / Copilot Security improvements for SSH has an official AUXSAYS record. Confirmed patch-specific consensus
  is deferred until the consensus refresh pipeline is active.
official_summary: GitHub published GitHub / Copilot Security improvements for SSH.
release_summary: "We’re removing several SSH algorithms, adding a new algorithm, and requiring larger RSA SSH keys to improve\
  \ security.\n\n\n The changes are as follows:\n\n\n\n We’re removing the ability to use RSA keys using SHA-1 in SSH (i.e.,\
  \ the ssh-rsa signature type, including ssh-rsa-cert-v01@openssh.com certificates using SHA-1).\n We’re removing the key\
  \ exchange mechanism diffie-hellman-group-exchange-sha256 .\n All new RSA SSH keys uploaded after October 14, 2026 must\
  \ be at least 3072 bits in size, both for signing and authentication.\n We’re additionally supporting the post-quantum key\
  \ exchange method mlkem768x25519-sha256 for SSH sessions on github.com and GitHub Enterprise Cloud with Data Residency,\
  \ except for the U.S. region.\n\n Adding ML-KEM lets us offer a newer, more performant key exchange method that is secure\
  \ against quantum computers.\n\n\n We’re also removing the older Diffie-Hellman method, a slow, little-used algorithm that\
  \ could be broken with advances in quantum computing. For RSA, we’re removing the use of SHA-1 since it’s known to be weak,\
  \ as well as increasing key sizes to align with 128-bit security requirements.\n\n\n Schedule\n\n October 14, 2026: The\
  \ new RSA key size requirements take effect. In addition, mlkem768x25519-sha256 will be enabled on github.com and GitHub\
  \ Enterprise Cloud with Data Residency (except for the U.S. region).\n November 4, 2026: We’ll have a brownout of the removal\
  \ of the ssh-rsa signature type (i.e., RSA keys using SHA-1) and the diffie-hellman-group-exchange-sha256 key exchange algorithm.\n\
  \ December 9, 2026: We’ll have another brownout for the ssh-rsa signature type and the diffie-hellman-group-exchange-sha256\
  \ key exchange algorithm.\n January 13, 2026: We’ll remove the ssh-rsa signature type and diffie-hellman-group-exchange-sha256\
  \ key exchange algorithm.\n\n These changes will all take effect in GitHub Enterprise Server in version 3.25, except for\
  \ the addition of mlkem768x25519-sha256 , which will take effect in version 3.24.\n\n\n Preparing for these changes\n The\
  \ only affected users are those connecting with a Git client over SSH or those using the unauthenticated Git protocol on\
  \ GitHub Enterprise Server. If your Git remotes start with https:// , nothing here will affect you.\n\n\n RSA key changes\n\
  \ If you’re using an existing RSA key, make sure you’re using RSA with SHA-2 (i.e., the rsa-sha2-256 and rsa-sha2-512 signature\
  \ types). You do not need to generate a new key, since all RSA keys are capable of signing with all hash algorithms. As\
  \ long as the SSH program or library you’re using supports RSA with SHA-2, you can continue to use the same key without\
  \ a problem and most SSH implementations supporting RSA with SHA-2 will choose it automatically.\n\n\n Note the distinction\
  \ between the key type ssh-rsa , which applies generically to all RSA keys regardless of signature algorithm, and the confusingly\
  \ named signature type ssh-rsa , which indicates an RSA key using SHA-1 (as opposed to rsa-sha2-256 and rsa-sha2-512 , which\
  \ refer to RSA keys using SHA-256 and SHA-512, respectively).\n\n\n Here’s a list of some common software that uses SSH\
  \ to connect to GitHub and the version necessary to support RSA with SHA-2 robustly with the default configuration:\n\n\n\
  \n\n\n Software\n Minimum Version\n\n\n\n\n OpenSSH\n 7.2p1\n\n\n JSch\n 0.1.66 from this fork\n\n\n TeamCity\n 2021.2.3\n\
  \n\n Go SSH\n 0.16.0\n\n\n libssh2\n 1.11.0\n\n\n PuTTY\n 0.82\n\n\n\n Alternatively, if you’re using older software and\
  \ can’t upgrade, you may be able to use an Ed25519 or ECDSA key instead. All Ed25519 and ECDSA keys we support are strong,\
  \ secure, and will continue to work for the indefinite future.\n\n\n For generating new keys, we recommend using an Ed25519\
  \ key whenever possible. However, if you still need an RSA key for compatibility with other services, you can generate one\
  \ as long as it as at least 3072 bits in size.\n\n\n Removal of diffie-hellman-group-exchange-sha256\n If you’re using one\
  \ of the SSH implementations above that supports RSA with SHA-2, it should also support a strong key exchange mechanism.\n\
  \n\n New post-quantum algorithms\n The addition of the mlkem768x25519-sha256 shouldn’t require any changes from users. SSH\
  \ clients will automatically use the new algorithm by default if configured to prefer it. Users who use an older SSH client\
  \ should automatically fall back to an older key exchange algorithm.\n\n\n\n The post Security improvements for SSH appeared\
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
- at: '2026-09-22T14:11:47Z'
  label: Published
  note: Official source entry detected.
- at: '2026-09-22T23:25:04Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
official_patch_notes_source_type: rss-feed
primary_official_source: https://github.blog/changelog/
fallback_official_sources:
- https://github.blog/changelog/label/copilot/
official_patch_notes_capture_status: captured-from-rss-feed
official_patch_notes_source_url: https://github.blog/changelog/2026-09-22-security-improvements-for-ssh
official_note_status: official_source_captured
official_note_label: Official source summary
official_source_type: rss-feed
official_source_classification_note: Official vendor sources are classified before display so feature summaries, release notes,
  fixed issues, and vendor announcements are not mislabeled.
official_sources: []
official_source_attempts:
- at: '2026-09-22T23:24:44Z'
  url: https://github.blog/changelog/2026-09-22-security-improvements-for-ssh
  status: captured-from-rss-feed
  body_captured: true
  checksums_captured: false
official_patch_notes_body: "We’re removing several SSH algorithms, adding a new algorithm, and requiring larger RSA SSH keys\
  \ to improve security.\n\n\n The changes are as follows:\n\n\n\n We’re removing the ability to use RSA keys using SHA-1\
  \ in SSH (i.e., the ssh-rsa signature type, including ssh-rsa-cert-v01@openssh.com certificates using SHA-1).\n We’re removing\
  \ the key exchange mechanism diffie-hellman-group-exchange-sha256 .\n All new RSA SSH keys uploaded after October 14, 2026\
  \ must be at least 3072 bits in size, both for signing and authentication.\n We’re additionally supporting the post-quantum\
  \ key exchange method mlkem768x25519-sha256 for SSH sessions on github.com and GitHub Enterprise Cloud with Data Residency,\
  \ except for the U.S. region.\n\n Adding ML-KEM lets us offer a newer, more performant key exchange method that is secure\
  \ against quantum computers.\n\n\n We’re also removing the older Diffie-Hellman method, a slow, little-used algorithm that\
  \ could be broken with advances in quantum computing. For RSA, we’re removing the use of SHA-1 since it’s known to be weak,\
  \ as well as increasing key sizes to align with 128-bit security requirements.\n\n\n Schedule\n\n October 14, 2026: The\
  \ new RSA key size requirements take effect. In addition, mlkem768x25519-sha256 will be enabled on github.com and GitHub\
  \ Enterprise Cloud with Data Residency (except for the U.S. region).\n November 4, 2026: We’ll have a brownout of the removal\
  \ of the ssh-rsa signature type (i.e., RSA keys using SHA-1) and the diffie-hellman-group-exchange-sha256 key exchange algorithm.\n\
  \ December 9, 2026: We’ll have another brownout for the ssh-rsa signature type and the diffie-hellman-group-exchange-sha256\
  \ key exchange algorithm.\n January 13, 2026: We’ll remove the ssh-rsa signature type and diffie-hellman-group-exchange-sha256\
  \ key exchange algorithm.\n\n These changes will all take effect in GitHub Enterprise Server in version 3.25, except for\
  \ the addition of mlkem768x25519-sha256 , which will take effect in version 3.24.\n\n\n Preparing for these changes\n The\
  \ only affected users are those connecting with a Git client over SSH or those using the unauthenticated Git protocol on\
  \ GitHub Enterprise Server. If your Git remotes start with https:// , nothing here will affect you.\n\n\n RSA key changes\n\
  \ If you’re using an existing RSA key, make sure you’re using RSA with SHA-2 (i.e., the rsa-sha2-256 and rsa-sha2-512 signature\
  \ types). You do not need to generate a new key, since all RSA keys are capable of signing with all hash algorithms. As\
  \ long as the SSH program or library you’re using supports RSA with SHA-2, you can continue to use the same key without\
  \ a problem and most SSH implementations supporting RSA with SHA-2 will choose it automatically.\n\n\n Note the distinction\
  \ between the key type ssh-rsa , which applies generically to all RSA keys regardless of signature algorithm, and the confusingly\
  \ named signature type ssh-rsa , which indicates an RSA key using SHA-1 (as opposed to rsa-sha2-256 and rsa-sha2-512 , which\
  \ refer to RSA keys using SHA-256 and SHA-512, respectively).\n\n\n Here’s a list of some common software that uses SSH\
  \ to connect to GitHub and the version necessary to support RSA with SHA-2 robustly with the default configuration:\n\n\n\
  \n\n\n Software\n Minimum Version\n\n\n\n\n OpenSSH\n 7.2p1\n\n\n JSch\n 0.1.66 from this fork\n\n\n TeamCity\n 2021.2.3\n\
  \n\n Go SSH\n 0.16.0\n\n\n libssh2\n 1.11.0\n\n\n PuTTY\n 0.82\n\n\n\n Alternatively, if you’re using older software and\
  \ can’t upgrade, you may be able to use an Ed25519 or ECDSA key instead. All Ed25519 and ECDSA keys we support are strong,\
  \ secure, and will continue to work for the indefinite future.\n\n\n For generating new keys, we recommend using an Ed25519\
  \ key whenever possible. However, if you still need an RSA key for compatibility with other services, you can generate one\
  \ as long as it as at least 3072 bits in size.\n\n\n Removal of diffie-hellman-group-exchange-sha256\n If you’re using one\
  \ of the SSH implementations above that supports RSA with SHA-2, it should also support a strong key exchange mechanism.\n\
  \n\n New post-quantum algorithms\n The addition of the mlkem768x25519-sha256 shouldn’t require any changes from users. SSH\
  \ clients will automatically use the new algorithm by default if configured to prefer it. Users who use an older SSH client\
  \ should automatically fall back to an older key exchange algorithm.\n\n\n\n The post Security improvements for SSH appeared\
  \ first on The GitHub Blog ."
official_checksums_body: ''
official_checksums_capture_status: not-present
---
