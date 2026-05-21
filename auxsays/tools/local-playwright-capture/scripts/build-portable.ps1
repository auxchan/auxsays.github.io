param(
  [string]$OutputRoot = "D:\AUXSAYS_CAPTURE_PORTABLE",
  [string]$RepoPath = "C:\GITHUB PROJECTS\auxsays.github.io",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceRoot = Resolve-Path (Join-Path $ScriptDir "..")
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$RepoPath = [System.IO.Path]::GetFullPath($RepoPath)
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

$runCaptureThenPromoteDryRunCmd = @"
@echo off
setlocal
set "REPO_PATH=$RepoPath"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO_PATH%\auxsays\tools\local-playwright-capture\scripts\run-capture-and-promote.ps1" -RepoPath "%REPO_PATH%" -PortablePath "%~dp0" -ProductId "adobe-premiere-pro"
set AUXSAYS_EXIT=%ERRORLEVEL%
pause
endlocal & exit /b %AUXSAYS_EXIT%
"@

$runCaptureThenPromoteWriteCmd = @"
@echo off
setlocal
set "REPO_PATH=$RepoPath"
echo AUXSAYS WRITE mode will run capture, promote accepted rows, and modify repo evidence/generated files through the repo-owned verifier.
echo Type WRITE to continue. Anything else exits without writing.
set /p AUXSAYS_CONFIRM=Confirmation:
if not "%AUXSAYS_CONFIRM%"=="WRITE" (
  echo WRITE canceled. No repo files were modified.
  endlocal
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO_PATH%\auxsays\tools\local-playwright-capture\scripts\run-capture-and-promote.ps1" -RepoPath "%REPO_PATH%" -PortablePath "%~dp0" -ProductId "adobe-premiere-pro" -Write -ConfirmedWrite
set AUXSAYS_EXIT=%ERRORLEVEL%
pause
endlocal & exit /b %AUXSAYS_EXIT%
"@

Set-Content -LiteralPath (Join-Path $OutputRoot "Run Capture.cmd") -Value $runCaptureCmd -Encoding ASCII
Set-Content -LiteralPath (Join-Path $OutputRoot "Run Capture Once.cmd") -Value $runOnceCmd -Encoding ASCII
Set-Content -LiteralPath (Join-Path $OutputRoot "Run Capture Then Promote Dry Run.cmd") -Value $runCaptureThenPromoteDryRunCmd -Encoding ASCII
Set-Content -LiteralPath (Join-Path $OutputRoot "Run Capture Then Promote WRITE.cmd") -Value $runCaptureThenPromoteWriteCmd -Encoding ASCII

if ($SkipInstall) {
  Write-Host "Skipping npm/Chromium install because -SkipInstall was provided."
}
else {
  Push-Location $AppRoot
  try {
    $Env:PLAYWRIGHT_BROWSERS_PATH = "0"
    npm.cmd install
    npx.cmd playwright install chromium
  }
  finally {
    Pop-Location
  }
}

Write-Host "Portable package ready: $OutputRoot"
