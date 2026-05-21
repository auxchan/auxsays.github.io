param(
  [string]$RepoPath = "C:\GITHUB PROJECTS\auxsays.github.io",
  [string]$PortablePath = "D:\AUXSAYS_CAPTURE_PORTABLE",
  [string]$ProductId = "adobe-premiere-pro",
  [switch]$Write,
  [int]$MaxRows = 0,
  [switch]$SkipCapture,
  [switch]$ConfirmedWrite
)

$ErrorActionPreference = "Stop"

function Get-UtcIsoTimestamp {
  return (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

function Join-ProcessArguments {
  param([string[]]$Arguments)
  $quoted = foreach ($arg in $Arguments) {
    $text = [string]$arg
    if ($text -eq "") {
      '""'
    }
    elseif ($text -match '[\s"]') {
      '"' + ($text -replace '"', '\"') + '"'
    }
    else {
      $text
    }
  }
  return ($quoted -join " ")
}

function Write-OperatorLine {
  param([string]$Message)
  $line = "$(Get-UtcIsoTimestamp) $Message"
  Add-Content -LiteralPath $script:OperatorLogPath -Value $line -Encoding UTF8
  Write-Host $Message
}

function Write-OperatorMeta {
  param([hashtable]$Data)
  $row = [ordered]@{
    captured_at = Get-UtcIsoTimestamp
    app_name = "AUXSAYS Local Capture Operator"
  }
  foreach ($key in $Data.Keys) {
    $row[$key] = $Data[$key]
  }
  Add-Content -LiteralPath $script:OperatorMetaPath -Value ($row | ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}

function Invoke-LoggedProcess {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory
  )
  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = $FilePath
  $startInfo.Arguments = Join-ProcessArguments -Arguments $Arguments
  if ($WorkingDirectory) {
    $startInfo.WorkingDirectory = $WorkingDirectory
  }
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.CreateNoWindow = $true

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $startInfo
  [void]$process.Start()
  $stdout = $process.StandardOutput.ReadToEnd()
  $stderr = $process.StandardError.ReadToEnd()
  $process.WaitForExit()

  foreach ($line in ($stdout -split "`r?`n")) {
    if ($line.Trim()) {
      Add-Content -LiteralPath $script:OperatorLogPath -Value "$(Get-UtcIsoTimestamp) stdout: $line" -Encoding UTF8
    }
  }
  foreach ($line in ($stderr -split "`r?`n")) {
    if ($line.Trim()) {
      Add-Content -LiteralPath $script:OperatorLogPath -Value "$(Get-UtcIsoTimestamp) stderr: $line" -Encoding UTF8
    }
  }

  return [pscustomobject]@{
    ExitCode = $process.ExitCode
    Stdout = $stdout
    Stderr = $stderr
  }
}

function Find-PythonCommand {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return [pscustomobject]@{ FilePath = $python.Source; PrefixArgs = @() }
  }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    return [pscustomobject]@{ FilePath = $py.Source; PrefixArgs = @("-3") }
  }
  return $null
}

function Parse-PromotionSummary {
  param([string]$Text)
  $trimmed = $Text.Trim()
  if (-not $trimmed) {
    return $null
  }
  $start = $trimmed.IndexOf("{")
  $end = $trimmed.LastIndexOf("}")
  if ($start -lt 0 -or $end -lt $start) {
    return $null
  }
  $json = $trimmed.Substring($start, $end - $start + 1)
  try {
    return $json | ConvertFrom-Json
  }
  catch {
    return $null
  }
}

function Show-PromotionSummary {
  param([object]$Summary, [bool]$IsWrite)
  if (-not $Summary) {
    Write-OperatorLine "Promotion summary could not be parsed; see operator-flow.log for raw output."
    return
  }

  $wouldUpdate = @()
  if ($Summary.accepted) {
    $generatedVersions = @($Summary.generated_record_versions)
    foreach ($row in @($Summary.accepted)) {
      if ($generatedVersions -contains $row.update_version -and $wouldUpdate -notcontains $row.update_version) {
        $wouldUpdate += $row.update_version
      }
    }
  }
  if ($IsWrite -and $Summary.generated_records_updated -eq $true) {
    $wouldUpdate = @("updated")
  }

  Write-Host ""
  Write-Host "AUXSAYS local capture promotion summary"
  Write-Host "---------------------------------------"
  Write-Host ("Rows read: {0}" -f $Summary.rows_read)
  Write-Host ("Listing cards found: {0}" -f $Summary.listing_cards_found)
  Write-Host ("Accepted: {0}" -f $Summary.accepted_count)
  Write-Host ("Rejected: {0}" -f $Summary.rejected_count)
  Write-Host ("Unmatched versions: {0}" -f (($Summary.unmatched_versions -join ", ") -replace "^$", "none"))
  Write-Host ("Generated records that would update: {0}" -f (($wouldUpdate -join ", ") -replace "^$", "none"))
  Write-Host "Files that would change in write mode:"
  foreach ($path in @($Summary.output_files_that_would_change)) {
    Write-Host ("  {0}" -f $path)
  }
}

$RepoPath = [System.IO.Path]::GetFullPath($RepoPath)
$PortablePath = [System.IO.Path]::GetFullPath($PortablePath)
$AppRoot = Join-Path $PortablePath "app"
$LogDir = Join-Path $AppRoot "logs"
$CaptureOutputPath = Join-Path $AppRoot "outbox\captured-pages.jsonl"
$CaptureScriptPath = Join-Path $AppRoot "scripts\run-capture.ps1"
$PromotionScriptPath = Join-Path $RepoPath "auxsays\scripts\promote_local_playwright_captures.py"
$script:OperatorLogPath = Join-Path $LogDir "operator-flow.log"
$script:OperatorMetaPath = Join-Path $LogDir "operator-flow-meta.jsonl"

if (-not (Test-Path -LiteralPath $RepoPath -PathType Container)) {
  throw "RepoPath does not exist: $RepoPath"
}
if (-not (Test-Path -LiteralPath $PortablePath -PathType Container)) {
  throw "PortablePath does not exist: $PortablePath"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $CaptureOutputPath) | Out-Null

if ($Write -and -not $ConfirmedWrite) {
  Write-Host "WRITE mode will modify repo evidence/generated files through the deterministic promotion bridge."
  Write-Host "Type WRITE to continue."
  $confirmation = Read-Host "Confirmation"
  if ($confirmation -ne "WRITE") {
    Write-OperatorLine "WRITE mode canceled by user."
    Write-OperatorMeta @{
      status = "canceled"
      mode = "write"
      reason = "confirmation_not_matched"
      repo_path = $RepoPath
      portable_path = $PortablePath
      product_id = $ProductId
    }
    exit 2
  }
}

Write-OperatorLine "Starting AUXSAYS local capture operator flow."
Write-OperatorLine "RepoPath: $RepoPath"
Write-OperatorLine "PortablePath: $PortablePath"
Write-OperatorLine "Mode: $(if ($Write) { 'write' } else { 'dry-run' })"

try {
  if (-not $SkipCapture) {
    if (-not (Test-Path -LiteralPath $CaptureScriptPath -PathType Leaf)) {
      throw "Capture script not found in portable package: $CaptureScriptPath"
    }
    $captureArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $CaptureScriptPath)
    if ($MaxRows -gt 0) {
      $captureArgs += @("-MaxUrls", [string]$MaxRows)
    }
    Write-OperatorLine "Running portable capture."
    $captureResult = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $captureArgs -WorkingDirectory $AppRoot
    if ($captureResult.ExitCode -ne 0) {
      throw "Capture failed with exit code $($captureResult.ExitCode)."
    }
  }
  else {
    Write-OperatorLine "Skipping capture; using existing captured-pages.jsonl."
  }

  if (-not (Test-Path -LiteralPath $CaptureOutputPath -PathType Leaf)) {
    throw "Captured output JSONL was not found: $CaptureOutputPath"
  }

  $python = Find-PythonCommand
  if (-not $python) {
    throw "Python was not found. Install or expose python/py on PATH, then rerun. This script will not install Python."
  }
  if (-not (Test-Path -LiteralPath $PromotionScriptPath -PathType Leaf)) {
    throw "Promotion bridge not found: $PromotionScriptPath"
  }

  $promotionArgs = @($python.PrefixArgs) + @(
    $PromotionScriptPath,
    "--input", $CaptureOutputPath,
    "--product-id", $ProductId
  )
  if ($MaxRows -gt 0) {
    $promotionArgs += @("--max-rows", [string]$MaxRows)
  }
  if ($Write) {
    $promotionArgs += "--write"
  }
  else {
    $promotionArgs += "--dry-run"
  }

  Write-OperatorLine "Running repo-owned deterministic promotion bridge."
  $promotionResult = Invoke-LoggedProcess -FilePath $python.FilePath -Arguments $promotionArgs -WorkingDirectory $RepoPath
  if ($promotionResult.Stdout.Trim()) {
    Write-Host $promotionResult.Stdout.Trim()
  }
  if ($promotionResult.Stderr.Trim()) {
    Write-Host $promotionResult.Stderr.Trim()
  }
  if ($promotionResult.ExitCode -ne 0) {
    throw "Promotion failed with exit code $($promotionResult.ExitCode)."
  }

  $summary = Parse-PromotionSummary -Text $promotionResult.Stdout
  Show-PromotionSummary -Summary $summary -IsWrite ([bool]$Write)

  if ($Write) {
    Write-Host ""
    Write-Host "GitHub Desktop checklist"
    Write-Host "------------------------"
    Write-Host "Expected changed files may include consensus_evidence.yml, evidence_method_health.yml, and generated patch records."
    Write-Host "Do not commit D:\ output, logs, node_modules, browser binaries, pycache, or state files unless intentionally changed."
  }

  $meta = @{
    status = "success"
    mode = if ($Write) { "write" } else { "dry-run" }
    repo_path = $RepoPath
    portable_path = $PortablePath
    product_id = $ProductId
    skip_capture = [bool]$SkipCapture
    max_rows = if ($MaxRows -gt 0) { $MaxRows } else { $null }
  }
  if ($summary) {
    $meta["rows_read"] = $summary.rows_read
    $meta["listing_cards_found"] = $summary.listing_cards_found
    $meta["accepted_count"] = $summary.accepted_count
    $meta["rejected_count"] = $summary.rejected_count
    $meta["unmatched_version_count"] = $summary.unmatched_version_count
  }
  Write-OperatorMeta $meta
  Write-OperatorLine "Operator flow completed successfully."
}
catch {
  Write-OperatorLine "Operator flow failed: $($_.Exception.Message)"
  Write-OperatorMeta @{
    status = "error"
    mode = if ($Write) { "write" } else { "dry-run" }
    repo_path = $RepoPath
    portable_path = $PortablePath
    product_id = $ProductId
    error_reason = $_.Exception.Message
  }
  throw
}
