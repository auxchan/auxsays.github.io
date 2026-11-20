---
layout: aux-update
title: GeForce Game Ready Driver 617.42 official update breakdown
description: Official GeForce Game Ready Driver update record captured from NVIDIA for 617.42.
permalink: /updates/nvidia/nvidia-geforce-game-ready/617-42/
update_entry: true
company_id: nvidia
product_id: nvidia-geforce-game-ready
update_brand_id: nvidia-geforce-game-ready
update_product: GeForce Game Ready Driver
update_category: Hardware / Drivers
update_type: official-source
update_source_name: NVIDIA
update_source_url: https://www.nvidia.com/en-us/drivers/details/280103/
update_download_url: https://www.nvidia.com/en-us/drivers/details/280103/
update_version: '617.42'
update_logo_text: GRD
update_published_at: '2026-10-06T00:00:00Z'
update_last_checked: '2026-11-19T23:17:53Z'
source_last_checked: '2026-11-19T23:17:53Z'
official_body_last_checked: '2026-11-19T23:17:53Z'
record_last_updated: '2026-11-20T22:10:12.261155Z'
patch_file_size: 990.85 MB
patch_file_size_note: Installer size as NVIDIA lists it for the Windows desktop DCH package.
patch_file_size_status: captured
update_status: current
update_feed_title: GeForce Game Ready Driver 617.42
update_detail_title: GeForce Game Ready Driver 617.42
update_consensus_label: Negative
update_report_count: 1
update_consensus_confidence: Low
quick_verdict: GeForce Game Ready Driver 617.42 has an official AUXSAYS record. Confirmed patch-specific consensus
  is deferred until the consensus refresh pipeline is active.
official_summary: NVIDIA published GeForce Game Ready Driver 617.42 on 2026-10-06.
release_summary: NVIDIA lists GeForce Game Ready Driver 617.42 (branch R615) for Windows desktop, released 2026-10-06.
consensus_report: '1 user report found for GeForce Game Ready Driver 617.42. Current reports mention black screen
  or display loss. Too few reports for a firm verdict yet. Sources represented: NVIDIA GeForce forum (user reports).'
evidence_state: pilot_sample
evidence_state_label: Verified reports
intelligence_stage: pilot
official_source_captured: true
confirmed_patch_specific_report_count: 1
evidence_last_checked: '2026-11-20T21:29:41Z'
known_issues_present: null
consensus_collection_status: pilot_initial_sample
consensus_match_policy: confirmed_patch_specific_reports_v1
consensus_match_policy_label: Confirmed patch-specific reports only
consensus_report_count_label: user reports found
consensus_report_weighting: equal_per_confirmed_report
consensus_low_context_policy: excluded
complaint_themes: []
status_events:
- at: '2026-10-06T00:00:00Z'
  label: Published
  note: Official source entry detected.
- at: '2026-11-19T23:18:12Z'
  label: Insufficient data
  note: AUXSAYS official-ingestion record initialized.
- at: '2026-11-20T22:10:12.261155Z'
  label: User reports found
  note: User report count updated to 1.
official_patch_notes_source_type: download_portal
primary_official_source: https://www.nvidia.com/en-us/geforce/drivers/
fallback_official_sources: []
official_patch_notes_capture_status: captured-from-official-nvidia-driver-listing
official_patch_notes_source_url: https://www.nvidia.com/en-us/drivers/details/280103/
official_note_status: official_source_captured
official_note_label: Official driver listing
official_source_type: download_portal
official_source_classification_note: NVIDIA's driver listing is treated as an official download-portal source. It
  confirms the driver family, version, branch and release date; community evidence remains separate.
official_sources:
- label: NVIDIA driver page
  url: https://www.nvidia.com/en-us/drivers/details/280103/
  source_type: download_portal
  trust_level: official
  extraction_status: version_metadata_captured
- label: NVIDIA release notes (PDF)
  url: https://us.download.nvidia.com/Windows/617.42/617.42-win11-win10-release-notes.pdf
  source_type: release_notes
  trust_level: official
  extraction_status: linked_not_captured
official_source_attempts:
- at: '2026-11-19T23:17:53Z'
  url: https://www.nvidia.com/en-us/drivers/details/280103/
  status: captured-from-official-nvidia-driver-listing
  body_captured: true
  checksums_captured: false
official_patch_notes_body: 'NVIDIA driver listing: GeForce Game Ready Driver 617.42


  - Driver family: GeForce Game Ready (as named by NVIDIA)

  - Driver branch: R615

  - Release date: 2026-10-06 (NVIDIA lists the date only, no time of day)

  - WHQL: certified

  - Package: desktop, DCH, for Windows 10 64-bit, Windows 11

  - Installer size: 990.85 MB

  - NVIDIA lists it as Game Ready for: Call of Duty: Modern Warfare 4


  Fixed issues NVIDIA lists for this driver:

  - Assassin''s Creed Shadows may crash to desktop after extended gameplay after updating to driver 616.56 [6685219]


  Official driver page: https://www.nvidia.com/en-us/drivers/details/280103/

  Official release notes (PDF): https://us.download.nvidia.com/Windows/617.42/617.42-win11-win10-release-notes.pdf


  AUXSAYS note: this is official NVIDIA driver metadata, not community consensus. Game Ready and Studio drivers
  that share a version number are separate records.'
official_checksums_body: ''
official_checksums_capture_status: not-present
driver_family: GeForce Game Ready
driver_branch: R615
nvidia_download_id: '280103'
release_date_precision: day
source_origin: NVIDIA official
collection_method: public driver-lookup endpoint
collection_authorization: owner risk acceptance; NVIDIA permission not established
update_consensus_summary: 'INSUFFICIENT DATA: GeForce Game Ready Driver 617.42. One user report is matched to this
  exact update, and one report does not show a pattern. If it matches your setup, test before relying on this update.'
evidence_samples:
- source_name: NVIDIA GeForce forum (user reports)
  source_url: https://www.nvidia.com/en-us/geforce/forums/game-ready-drivers/13/591981/geforce-grd-62101-feedback-thread-released-102126/?comment=3633156
  source_title: GeForce GRD 621.01 Feedback Thread (Released 10/21/26)
  counted: true
  version_matched: '617.42'
  patch_version_matched: true
  issue: black screen or display loss in display output
  outcome: high
evidence_sample_visible_limit: 5
accepted_report_sources:
- source_name: NVIDIA GeForce forum (user reports)
  source_type: nvidia forum comment
  source_url: https://www.nvidia.com/en-us/geforce/forums/game-ready-drivers/13/591981/geforce-grd-62101-feedback-thread-released-102126/?comment=3633156
  source_title: GeForce GRD 621.01 Feedback Thread (Released 10/21/26)
  source_date: '2026-11-09'
  version_matched: '617.42'
  patch_version_matched: true
  issue: black screen or display loss in display output
  workflow_area: display output
evidence_source_limitations:
- Too few reports for a firm verdict yet.
---
