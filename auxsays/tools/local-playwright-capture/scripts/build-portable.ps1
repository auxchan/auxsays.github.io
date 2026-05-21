param(
  [string]$OutputRoot = "D:\AUXSAYS_CAPTURE_PORTABLE"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceRoot = Resolve-Path (Join-Path $ScriptDir "..")
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$AppRoot = Join-Path $OutputRoot "app"

Write-Host "Building AUXSAYS portable capture package at $OutputRoot"

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
New-Item -ItemType Directory -Force -Path $AppRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $AppRoot "config") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $AppRoot "outbox") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $AppRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $AppRoot "scripts") | Out-Null

Copy-Item -LiteralPath (Join-Path $SourceRoot "package.json") -Destination (Join-Path $AppRoot "package.json") -Force
Copy-Item -LiteralPath (Join-Path $SourceRoot "capture-agent.mjs") -Destination (Join-Path $AppRoot "capture-agent.mjs") -Force
Copy-Item -LiteralPath (Join-Path $SourceRoot "README.md") -Destination (Join-Path $AppRoot "README.md") -Force
Copy-Item -LiteralPath (Join-Path $SourceRoot "scripts\run-capture.ps1") -Destination (Join-Path $AppRoot "scripts\run-capture.ps1") -Force

$CandidatesPath = Join-Path $AppRoot "config\candidates.json"
if (-not (Test-Path -LiteralPath $CandidatesPath)) {
  Copy-Item -LiteralPath (Join-Path $SourceRoot "config\candidates.sample.json") -Destination $CandidatesPath -Force
}

$runCaptureCmd = @"
@echo off
setlocal
cd /d "%~dp0app"
set PLAYWRIGHT_BROWSERS_PATH=0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run-capture.ps1" -IntervalMinutes 360
endlocal
"@

$runOnceCmd = @"
@echo off
setlocal
cd /d "%~dp0app"
set PLAYWRIGHT_BROWSERS_PATH=0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run-capture.ps1"
endlocal
"@

Set-Content -LiteralPath (Join-Path $OutputRoot "Run Capture.cmd") -Value $runCaptureCmd -Encoding ASCII
Set-Content -LiteralPath (Join-Path $OutputRoot "Run Capture Once.cmd") -Value $runOnceCmd -Encoding ASCII

Push-Location $AppRoot
try {
  $Env:PLAYWRIGHT_BROWSERS_PATH = "0"
  npm.cmd install
  npx.cmd playwright install chromium
}
finally {
  Pop-Location
}

Write-Host "Portable package ready: $OutputRoot"
