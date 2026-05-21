# AUXSAYS Local Playwright Capture

This is an MVP portable local capture agent for public patch-report pages that cloud runners may fail to fetch because of rate limits, browser challenges, or cloud-runner blocking.

It is a transport/operator package. Capture writes candidate page captures to JSONL. Promotion is delegated back to repo-owned deterministic scripts; the USB package does not decide consensus, score reports, edit generated records directly, write accepted evidence rows itself, or publish verdicts.

## Automation Doctrine Fit

AUXSAYS automation should gather, verify, score, summarize, and publish patch intelligence with minimal human intervention. This package covers the local gather transport for difficult public pages and provides one-command wrappers that call the repo-owned deterministic verifier/promoter.

Taylor should not manually review every captured source as the normal workflow. Manual review is only for calibration, debugging, and ambiguous fallback cases. Accepted evidence must still pass the repo verifier and normal consensus/writeback path.

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
  Run Capture Then Promote Dry Run.cmd
  Run Capture Then Promote WRITE.cmd
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

## Run Capture Then Promote

Safe dry-run path:

```text
D:\AUXSAYS_CAPTURE_PORTABLE\Run Capture Then Promote Dry Run.cmd
```

This runs capture, then calls:

```powershell
python auxsays/scripts/promote_local_playwright_captures.py --input "D:\AUXSAYS_CAPTURE_PORTABLE\app\outbox\captured-pages.jsonl" --product-id adobe-premiere-pro --dry-run
```

Dry-run prints rows read, listing cards found, accepted/rejected counts, unmatched versions, generated records that would update, and files that would change in write mode. It does not modify `consensus_evidence.yml`, `evidence_method_health.yml`, or generated records.

Explicit write path:

```text
D:\AUXSAYS_CAPTURE_PORTABLE\Run Capture Then Promote WRITE.cmd
```

The WRITE command requires typing:

```text
WRITE
```

before it calls the repo-owned promotion bridge in `--write` mode. Write mode appends accepted evidence through shared helpers and applies generated-record writeback through the existing repo pipeline. It does not move evidence rules into the USB capture agent.

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
D:\AUXSAYS_CAPTURE_PORTABLE\app\logs\operator-flow.log
D:\AUXSAYS_CAPTURE_PORTABLE\app\logs\operator-flow-meta.jsonl
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
