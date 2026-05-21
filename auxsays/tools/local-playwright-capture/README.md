# AUXSAYS Local Playwright Capture

This is an MVP portable local capture agent for public patch-report pages that cloud runners may fail to fetch because of rate limits, browser challenges, or cloud-runner blocking.

It is a transport only. It writes candidate page captures to JSONL. It does not decide consensus, score reports, edit generated records, write accepted evidence rows, or publish verdicts.

## Automation Doctrine Fit

AUXSAYS automation should gather, verify, score, summarize, and publish patch intelligence with minimal human intervention. This tool covers only the local gather transport for difficult public pages. The next required step is a deterministic verifier/promoter that reads `outbox/captured-pages.jsonl`, confirms patch-specific evidence, scores it, and writes accepted evidence through repo-owned scripts.

Until that verifier exists, this MVP is intentionally incomplete as a full intelligence pipeline. Taylor should not manually review every captured source as the normal workflow; manual review is only for calibration, debugging, and ambiguous fallback cases.

## Guardrails

- Clear app/process name: `AUXSAYS Local Playwright Capture`.
- Does not auto-start.
- Does not persist after exit.
- Does not hide itself.
- Uses Playwright Chromium only.
- Does not read Chrome or Edge cookies, profiles, history, passwords, clipboard, screenshots, keystrokes, or unrelated browsing.
- Does not use proxies, CAPTCHA solving, stealth plugins, or anti-bot bypass packages.
- Opens only configured candidate URLs.
- Stops with `Ctrl+C`.
- Writes quiet local logs to the portable package.

## Portable Layout

Build output target:

```text
D:\AUXSAYS_CAPTURE_PORTABLE
```

Expected layout:

```text
D:\AUXSAYS_CAPTURE_PORTABLE\
  Run Capture.cmd
  Run Capture Once.cmd
  app\
    package.json
    capture-agent.mjs
    config\
      candidates.json
    outbox\
    logs\
    node_modules\
    node_modules\playwright-core\.local-browsers\
```

## Build

From the repo root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File auxsays\tools\local-playwright-capture\scripts\build-portable.ps1
```

The build script sets:

```powershell
$Env:PLAYWRIGHT_BROWSERS_PATH = "0"
```

Then runs inside the portable `app` folder:

```powershell
npm.cmd install
npx.cmd playwright install chromium
```

Do not install Playwright globally.

## Configure

Edit:

```text
D:\AUXSAYS_CAPTURE_PORTABLE\app\config\candidates.json
```

Candidate shape:

```json
{
  "source_url": "https://community.adobe.com/...",
  "source_name": "Adobe Community",
  "product_hint": "adobe-premiere-pro",
  "version_hint": "26.2"
}
```

## Run Once

Double-click:

```text
D:\AUXSAYS_CAPTURE_PORTABLE\Run Capture Once.cmd
```

Or from PowerShell:

```powershell
cd D:\AUXSAYS_CAPTURE_PORTABLE\app
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-capture.ps1
```

## Interval Mode

Double-click:

```text
D:\AUXSAYS_CAPTURE_PORTABLE\Run Capture.cmd
```

That runs every 360 minutes.

Or:

```powershell
cd D:\AUXSAYS_CAPTURE_PORTABLE\app
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-capture.ps1 -IntervalMinutes 360
```

## Output

Candidate captures:

```text
D:\AUXSAYS_CAPTURE_PORTABLE\app\outbox\captured-pages.jsonl
```

Logs:

```text
D:\AUXSAYS_CAPTURE_PORTABLE\app\logs\capture.log
D:\AUXSAYS_CAPTURE_PORTABLE\app\logs\capture-meta.jsonl
```

Each JSONL row includes:

- `source_url`
- `final_url`
- `source_name`
- `product_hint`
- `version_hint`
- `page_title`
- `visible_text`
- `captured_at`
- `capture_method: local_playwright`
- `capture_status: success / blocked / error`
- `error_reason` when applicable

## Tests

From this folder:

```powershell
node .\scripts\test-capture.mjs
```

The tests do not require opening a browser.
