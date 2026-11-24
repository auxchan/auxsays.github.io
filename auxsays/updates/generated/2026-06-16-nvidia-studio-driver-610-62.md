---
layout: aux-update
title: NVIDIA Studio Driver 610.62 official update breakdown
description: Official NVIDIA Studio Driver update record captured from NVIDIA for 610.62.
permalink: /updates/nvidia/nvidia-studio-driver/610-62/
update_entry: true
company_id: nvidia
product_id: nvidia-studio-driver
update_brand_id: nvidia-studio-driver
update_product: NVIDIA Studio Driver
update_category: Hardware / Drivers
update_type: official-source
update_source_name: NVIDIA
update_source_url: https://www.nvidia.com/en-us/drivers/details/272766/
update_download_url: https://www.nvidia.com/en-us/drivers/details/272766/
update_version: '610.62'
update_logo_text: NSD
update_published_at: '2026-06-16T00:00:00Z'
update_last_checked: '2026-11-20T23:12:58Z'
source_last_checked: '2026-11-20T23:12:58Z'
official_body_last_checked: '2026-11-20T23:12:58Z'
record_last_updated: '2026-11-24T01:46:22.773157Z'
patch_file_size: 978.43 MB
patch_file_size_note: Installer size as NVIDIA lists it for the Windows desktop DCH package.
patch_file_size_status: captured
update_status: current
update_feed_title: NVIDIA Studio Driver 610.62
update_detail_title: NVIDIA Studio Driver 610.62
update_consensus_label: Negative
update_report_count: 1
update_consensus_confidence: Low
quick_verdict: NVIDIA Studio Driver 610.62 has an official AUXSAYS record. Confirmed patch-specific consensus is
  deferred until the consensus refresh pipeline is active.
official_summary: NVIDIA published NVIDIA Studio Driver 610.62 on 2026-06-16.
release_summary: NVIDIA lists NVIDIA Studio Driver 610.62 (branch R610) for Windows desktop, released 2026-06-16.
consensus_report: '1 user report found for NVIDIA Studio Driver 610.62. Current reports mention crash or driver
  reset. Too few reports for a firm verdict yet. Sources represented: NVIDIA GeForce forum (user reports).'
evidence_state: pilot_sample
evidence_state_label: Verified reports
intelligence_stage: pilot
official_source_captured: true
confirmed_patch_specific_report_count: 1
evidence_last_checked: '2026-11-22T20:47:30Z'
known_issues_present: null
consensus_collection_status: pilot_initial_sample
consensus_match_policy: confirmed_patch_specific_reports_v1
consensus_match_policy_label: Confirmed patch-specific reports only
consensus_report_count_label: user reports found
consensus_report_weighting: equal_per_confirmed_report
consensus_low_context_policy: excluded
complaint_themes: []
status_events:
- at: '2026-06-16T00:00:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-20T23:13:15Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
- at: '2026-11-22T21:19:58.084077Z'
  label: User reports found
  note: User report count updated to 1.
official_patch_notes_source_type: download_portal
primary_official_source: https://www.nvidia.com/en-us/geforce/drivers/
fallback_official_sources: []
official_patch_notes_capture_status: captured-from-official-nvidia-driver-listing
official_patch_notes_source_url: https://www.nvidia.com/en-us/drivers/details/272766/
official_note_status: official_source_captured
official_note_label: Official driver listing
official_source_type: download_portal
official_source_classification_note: NVIDIA's driver listing is treated as an official download-portal source. It
  confirms the driver family, version, branch and release date; community evidence remains separate.
official_sources:
- label: NVIDIA driver page
  url: https://www.nvidia.com/en-us/drivers/details/272766/
  source_type: download_portal
  trust_level: official
  extraction_status: version_metadata_captured
- label: NVIDIA release notes (PDF)
  url: https://us.download.nvidia.com/Windows/610.62/610.62-win10-win11-nsd-release-notes.pdf
  source_type: release_notes
  trust_level: official
  extraction_status: linked_not_captured
official_source_attempts:
- at: '2026-11-20T23:12:58Z'
  url: https://www.nvidia.com/en-us/drivers/details/272766/
  status: captured-from-official-nvidia-driver-listing
  body_captured: true
  checksums_captured: false
official_patch_notes_body: 'NVIDIA driver listing: NVIDIA Studio Driver 610.62


  - Driver family: NVIDIA Studio (as named by NVIDIA)

  - Driver branch: R610

  - Release date: 2026-06-16 (NVIDIA lists the date only, no time of day)

  - WHQL: not flagged in NVIDIA listing

  - Package: desktop, DCH, for Windows 10 64-bit, Windows 11

  - Installer size: 978.43 MB


  Fixed issues NVIDIA lists for this driver:

  - World of Warcraft: Gaming stability improvements [5563205]

  - Apex Legends: Occasional visual corruption after extended gameplay [6239327]

  - Users may observe DLSS settings being grayed out in certain games after updating to display driver 615.47 [6262805]

  - Improved gaming stability in multi-monitor configurations when using V-SYNC with DLSS Frame Generation [6158481]

  - Resolved an issue that could cause jittering or ghosting in some DirectX 11 games when Smooth Motion is enabled
  [5937897]

  - Resolved an issue that could cause some games to crash when launched with Smooth Motion enabled [5466398]

  - [Ada] Resolves a frame pacing issue on certain monitors when G-SYNC is enabled [6226972]

  - Resolved an issue that prevented the EDID from being read on certain monitors causing them to be identified
  as "NVIDIA NV-Failsafe” [6005508]

  - Resolved an issue where certain monitors would not wake from sleep mode [5806798/5635230]

  - General stability improvements when the system fails to create a new allocation [5449920]


  Official driver page: https://www.nvidia.com/en-us/drivers/details/272766/

  Official release notes (PDF): https://us.download.nvidia.com/Windows/610.62/610.62-win10-win11-nsd-release-notes.pdf


  AUXSAYS note: this is official NVIDIA driver metadata, not community consensus. Game Ready and Studio drivers
  that share a version number are separate records.'
official_checksums_body: ''
official_checksums_capture_status: not-present
driver_family: NVIDIA Studio
driver_branch: R610
nvidia_download_id: '272766'
release_date_precision: day
source_origin: NVIDIA official
collection_method: public driver-lookup endpoint
collection_authorization: owner risk acceptance; NVIDIA permission not established
update_consensus_summary: 'INSUFFICIENT DATA: NVIDIA Studio Driver 610.62. One user report is matched to this exact
  update, and one report does not show a pattern. If it matches your setup, test before relying on this update.'
evidence_samples:
- source_name: NVIDIA GeForce forum (user reports)
  source_url: https://www.nvidia.com/en-us/geforce/forums/studio-drivers/39/590622/studio-driver-61692-broke-dp-output-on-my-4060/?comment=3625749
  source_title: Studio Driver 616.92 Broke DP Output on my 4060
  counted: true
  version_matched: '610.62'
  patch_version_matched: true
  issue: crash or driver reset in system stability
  outcome: high
evidence_sample_visible_limit: 5
accepted_report_sources:
- source_name: NVIDIA GeForce forum (user reports)
  source_type: nvidia forum comment
  source_url: https://www.nvidia.com/en-us/geforce/forums/studio-drivers/39/590622/studio-driver-61692-broke-dp-output-on-my-4060/?comment=3625749
  source_title: Studio Driver 616.92 Broke DP Output on my 4060
  source_date: '2026-09-18'
  version_matched: '610.62'
  patch_version_matched: true
  issue: crash or driver reset in system stability
  workflow_area: system stability
evidence_source_limitations:
- Too few reports for a firm verdict yet.
- Some community sources were unavailable during the last check; unavailable sources were not counted as reports.
---
