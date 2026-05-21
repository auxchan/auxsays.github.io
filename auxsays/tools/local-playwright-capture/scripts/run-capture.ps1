param(
  [int]$MaxUrls = 10,
  [int]$TimeoutMs = 30000,
  [int]$IntervalMinutes = 0,
  [switch]$Headed,
  [switch]$DryRun,
  [switch]$AllowLocalhostTest
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppRoot = Resolve-Path (Join-Path $ScriptDir "..")

Push-Location $AppRoot
try {
  $Env:PLAYWRIGHT_BROWSERS_PATH = "0"
  $argsList = @(
    "capture-agent.mjs",
    "--config", "config\candidates.json",
    "--outbox", "outbox\captured-pages.jsonl",
    "--log-file", "logs\capture.log",
    "--meta-log", "logs\capture-meta.jsonl",
    "--max-urls", $MaxUrls,
    "--timeout-ms", $TimeoutMs
  )

  if ($IntervalMinutes -gt 0) {
    $argsList += @("--interval-minutes", $IntervalMinutes)
  }
  if ($Headed) {
    $argsList += "--headed"
  }
  if ($DryRun) {
    $argsList += "--dry-run"
  }
  if ($AllowLocalhostTest) {
    $argsList += "--allow-localhost-test"
  }

  node.exe @argsList
}
finally {
  Pop-Location
}
