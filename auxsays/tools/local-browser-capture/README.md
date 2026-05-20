# AUXSAYS Local Browser Capture

This is a local Windows capture tool for public Blackmagic Design forum pages related to DaVinci Resolve patch versions.

It captures visible page text into JSONL candidate records. It does not decide what counts as valid evidence, does not write verdicts, and does not edit generated AUXSAYS pages or `consensus_evidence.yml`.

## Guardrails

- Uses a dedicated browser profile under `C:\AUXSAYS_CAPTURE\browser-profiles\`.
- Rejects obvious personal Chrome, Edge, or Brave profile paths if `browser_profile_dir` is overridden.
- Reads public pages only.
- Does not log in, post, click engagement controls, harvest cookies, use proxies, or attempt to bypass CAPTCHA, Cloudflare, AWS WAF, or other verification.
- Runs at a low rate with delays between pages.
- Stops by default when a block or verification page is detected.
- Saves screenshots only for error, block, or verification pages.
- Deduplicates by canonical `source_url`, including records already present in the output folder.

## Setup

For the Windows launcher path, no Node.js or npm install is required.

Requirements:

- Windows PowerShell
- Microsoft Edge
- public internet access from Edge

## Windows Launcher

Double-click:

```text
tools\local-browser-capture\launcher\AuxsaysCaptureLauncher.exe
```

Fallback double-click launcher:

```text
tools\local-browser-capture\launcher\AuxsaysCaptureLauncher.cmd
```

The launcher can:

- run a dry run
- start capture
- run a self-check
- open the output, log, and screenshot folders

If the `.exe` needs to be rebuilt:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/local-browser-capture/launcher/build-launcher-exe.ps1
```

The `.exe` is a small Windows launcher for the PowerShell UI. The default capture logic is in `capture-edge.ps1` and drives Microsoft Edge through its local developer protocol with a dedicated AUXSAYS profile.

## Dry Run

Dry run validates the config and prints the planned search URLs and output paths. It does not launch a browser and does not write candidate JSONL.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/local-browser-capture/capture-edge.ps1 -ConfigPath tools/local-browser-capture/configs/blackmagic-davinci.sample.json -DryRun
```

## Capture

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/local-browser-capture/capture-edge.ps1 -ConfigPath tools/local-browser-capture/configs/blackmagic-davinci.sample.json
```

Useful overrides:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/local-browser-capture/capture-edge.ps1 -ConfigPath tools/local-browser-capture/configs/blackmagic-davinci.sample.json -MaxPages 10
powershell -NoProfile -ExecutionPolicy Bypass -File tools/local-browser-capture/capture-edge.ps1 -ConfigPath tools/local-browser-capture/configs/blackmagic-davinci.sample.json -Headless
```

Output is written to:

```text
C:\AUXSAYS_CAPTURE\outbox\blackmagic-davinci\
```

Logs are written to:

```text
C:\AUXSAYS_CAPTURE\logs\blackmagic-davinci\
```

Error and block screenshots are written to:

```text
C:\AUXSAYS_CAPTURE\screenshots\blackmagic-davinci\
```

## Config

The config must include:

- `product_id`
- `target_version`
- `release_date`
- `watch_until`
- `query_variants`
- `allowed_source_domains`

The initial sample target is `blackmagic-davinci` version `21`, with Blackmagic forum searches for crash, export, render, audio, and GPU terms.

Only domains listed in `allowed_source_domains` are captured. The sample allows only:

```json
["forum.blackmagicdesign.com"]
```

## JSONL Shape

Each line is one candidate record with these fields:

- `collector_id`
- `source_id`
- `product_id`
- `target_version`
- `query_variant_used`
- `source_url`
- `report_title`
- `forum_category`
- `source_date`
- `captured_at`
- `report_text`
- `capture_status`
- `notes`

Supported `capture_status` values:

- `captured`
- `blocked_or_verification`
- `no_readable_text`
- `failed`
- `skipped_duplicate`
- `dry_run`

See `samples/blackmagic-davinci.sample.jsonl` for a formatting example. The sample is not evidence.

## Tests

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/local-browser-capture/capture-edge.ps1 -SelfTest
```

The self-check covers JSONL serialization, config validation, allowed-domain checks, block detection, and personal-profile rejection. It does not open a browser or touch `C:\AUXSAYS_CAPTURE`.

## Optional Node/Playwright Runner

The older Node/Playwright runner remains available in `capture.mjs` for developer use, but the Windows launcher does not require it.
