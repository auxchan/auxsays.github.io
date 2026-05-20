param(
  [string]$ConfigPath = "",
  [switch]$DryRun,
  [switch]$SelfTest,
  [int]$MaxPages = 0,
  [switch]$Headless,
  [switch]$ContinueOnBlock,
  [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"

$CollectorId = "local_browser_capture"
$SourceId = "blackmagic_forum"
$DefaultCaptureRoot = "C:\AUXSAYS_CAPTURE"
$Script:NextCdpId = 1

function Get-UtcTimestamp {
  return [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
}

function Get-FileTimestamp {
  return [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH-mm-ss-fffZ")
}

function Normalize-Text {
  param(
    [AllowNull()][string]$Value,
    [int]$MaxLength = 0
  )
  $text = [string]$Value
  $text = $text -replace [char]0x00a0, " "
  $text = $text -replace "`r`n", "`n"
  $text = $text -replace "[ `t`f`v]+", " "
  $text = $text -replace "(`n){3,}", "`n`n"
  $text = $text.Trim()
  if ($MaxLength -gt 0 -and $text.Length -gt $MaxLength) {
    return $text.Substring(0, $MaxLength).TrimEnd() + "..."
  }
  return $text
}

function Sanitize-PathSegment {
  param([string]$Value)
  $segment = ([string]$Value).Trim() -replace "[^A-Za-z0-9._-]+", "-"
  $segment = $segment.Trim("-")
  if (-not $segment) { return "capture" }
  return $segment
}

function Assert-DedicatedBrowserProfile {
  param([string]$ProfileDir)
  $normalized = ([string]$ProfileDir).ToLowerInvariant().Replace("/", "\")
  $blocked = @(
    "\appdata\local\google\chrome\user data",
    "\appdata\local\microsoft\edge\user data",
    "\appdata\local\bravesoftware\brave-browser\user data"
  )
  foreach ($marker in $blocked) {
    if ($normalized.Contains($marker)) {
      throw "browser_profile_dir appears to point at a personal browser profile; use a dedicated AUXSAYS capture profile"
    }
  }
  return $true
}

function Parse-QueryString {
  param([string]$Query)
  $pairs = @{}
  $q = ([string]$Query).TrimStart("?")
  if (-not $q) { return $pairs }
  foreach ($part in $q.Split("&")) {
    if (-not $part) { continue }
    $bits = $part.Split("=", 2)
    $key = [Uri]::UnescapeDataString($bits[0].Replace("+", " "))
    $value = ""
    if ($bits.Count -gt 1) {
      $value = [Uri]::UnescapeDataString($bits[1].Replace("+", " "))
    }
    $pairs[$key] = $value
  }
  return $pairs
}

function Canonical-SourceUrl {
  param([string]$Value)
  $base = [Uri]"https://forum.blackmagicdesign.com/"
  $uri = New-Object System.Uri($base, ([string]$Value).Trim())
  $scheme = $uri.Scheme.ToLowerInvariant()
  $hostName = $uri.Host.ToLowerInvariant()
  $path = $uri.AbsolutePath

  if ($hostName -eq "forum.blackmagicdesign.com" -and $path -match "/viewtopic\.php$") {
    $query = Parse-QueryString $uri.Query
    $parts = New-Object System.Collections.Generic.List[string]
    if ($query.ContainsKey("f")) {
      $parts.Add("f=$([Uri]::EscapeDataString($query["f"]))")
    }
    if ($query.ContainsKey("t")) {
      $parts.Add("t=$([Uri]::EscapeDataString($query["t"]))")
    } elseif ($query.ContainsKey("p")) {
      $parts.Add("p=$([Uri]::EscapeDataString($query["p"]))")
    }
    return "${scheme}://${hostName}${path}?$($parts -join "&")"
  }

  $queryPairs = Parse-QueryString $uri.Query
  foreach ($noise in @("sid", "hilit", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")) {
    if ($queryPairs.ContainsKey($noise)) {
      $queryPairs.Remove($noise)
    }
  }
  $orderedKeys = $queryPairs.Keys | Sort-Object
  $queryParts = @()
  foreach ($key in $orderedKeys) {
    $queryParts += "$([Uri]::EscapeDataString($key))=$([Uri]::EscapeDataString($queryPairs[$key]))"
  }
  $queryText = ""
  if ($queryParts.Count -gt 0) {
    $queryText = "?" + ($queryParts -join "&")
  }
  return "${scheme}://${hostName}${path}${queryText}"
}

function Host-MatchesAllowedDomain {
  param([string]$HostName, [string]$AllowedDomain)
  $hostValue = ([string]$HostName).ToLowerInvariant() -replace "^www\.", ""
  $allowed = ([string]$AllowedDomain).ToLowerInvariant() -replace "^https?://", "" -replace "^www\.", "" -replace "/.*$", ""
  return $hostValue -eq $allowed -or $hostValue.EndsWith(".$allowed")
}

function Is-AllowedSourceUrl {
  param([string]$Url, [object[]]$AllowedDomains)
  try {
    $uri = [Uri]$Url
    foreach ($domain in $AllowedDomains) {
      if (Host-MatchesAllowedDomain $uri.Host ([string]$domain)) {
        return $true
      }
    }
  } catch {
    return $false
  }
  return $false
}

function Build-SearchUrl {
  param([string]$Query)
  return "https://forum.blackmagicdesign.com/search.php?keywords=$([Uri]::EscapeDataString($Query))&terms=all&author=&sc=1&sf=all"
}

function Get-BlockReason {
  param([string]$Text)
  $lowered = ([string]$Text).ToLowerInvariant()
  if (-not $lowered.Trim()) { return "" }
  if ($lowered.Contains("window.gokuprops") -or $lowered.Contains("awswaf")) { return "aws_waf_challenge" }
  if ($lowered.Contains("captcha")) { return "captcha_challenge" }
  if ($lowered.Contains("verify you are human") -or $lowered.Contains("verification required")) { return "human_verification" }
  if ($lowered.Contains("checking your browser") -or $lowered.Contains("please enable javascript")) { return "browser_verification" }
  if ($lowered.Contains("access denied") -or $lowered.Contains("forbidden")) { return "access_denied" }
  return ""
}

function Validate-CaptureConfig {
  param([pscustomobject]$Config)
  foreach ($field in @("product_id", "target_version", "release_date", "watch_until", "query_variants", "allowed_source_domains")) {
    if (-not $Config.PSObject.Properties.Name.Contains($field)) {
      throw "config missing required field: $field"
    }
  }
  if (-not $Config.query_variants -or $Config.query_variants.Count -eq 0) {
    throw "config query_variants must be a non-empty array"
  }
  if (-not $Config.allowed_source_domains -or $Config.allowed_source_domains.Count -eq 0) {
    throw "config allowed_source_domains must be a non-empty array"
  }
  [DateTime]::Parse([string]$Config.release_date) | Out-Null
  [DateTime]::Parse([string]$Config.watch_until) | Out-Null
  if (-not (Is-AllowedSourceUrl "https://forum.blackmagicdesign.com/search.php" $Config.allowed_source_domains)) {
    throw "config allowed_source_domains must allow forum.blackmagicdesign.com for this collector"
  }
  return $true
}

function Get-RuntimeOptions {
  param([pscustomobject]$Config)
  $capture = $Config.capture
  $root = $DefaultCaptureRoot
  if ($capture -and $capture.output_root) { $root = [string]$capture.output_root }
  if ($OutputRoot) { $root = $OutputRoot }

  $profile = Join-Path $root "browser-profiles\blackmagic-forum"
  if ($capture -and $capture.browser_profile_dir) { $profile = [string]$capture.browser_profile_dir }

  $maxPagesValue = 20
  if ($capture -and $capture.max_pages_per_run) { $maxPagesValue = [int]$capture.max_pages_per_run }
  if ($MaxPages -gt 0) { $maxPagesValue = $MaxPages }

  $stopOnBlock = $true
  if ($capture -and $null -ne $capture.stop_on_block) { $stopOnBlock = [bool]$capture.stop_on_block }
  if ($ContinueOnBlock) { $stopOnBlock = $false }

  return [pscustomobject]@{
    output_root = $root
    browser_profile_dir = $profile
    headless = [bool]($Headless -or ($capture -and $capture.headless))
    max_pages_per_run = $maxPagesValue
    max_results_per_query = if ($capture -and $capture.max_results_per_query) { [int]$capture.max_results_per_query } else { 6 }
    delay_min_ms = if ($capture -and $capture.delay_min_ms) { [int]$capture.delay_min_ms } else { 5000 }
    delay_max_ms = if ($capture -and $capture.delay_max_ms) { [int]$capture.delay_max_ms } else { 12000 }
    navigation_timeout_ms = if ($capture -and $capture.navigation_timeout_ms) { [int]$capture.navigation_timeout_ms } else { 45000 }
    max_text_chars = if ($capture -and $capture.max_text_chars) { [int]$capture.max_text_chars } else { 12000 }
    stop_on_block = $stopOnBlock
  }
}

function Resolve-RunPaths {
  param([string]$ProductId, [string]$Root, [string]$ProfileDir)
  $productSegment = Sanitize-PathSegment $ProductId
  return [pscustomobject]@{
    output_dir = Join-Path $Root "outbox\$productSegment"
    log_dir = Join-Path $Root "logs\$productSegment"
    screenshot_dir = Join-Path $Root "screenshots\$productSegment"
    profile_dir = $ProfileDir
  }
}

function Ensure-RunDirs {
  param([pscustomobject]$Paths)
  foreach ($dir in @($Paths.output_dir, $Paths.log_dir, $Paths.screenshot_dir, $Paths.profile_dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
}

function Append-JsonLog {
  param([string]$LogFile, [hashtable]$Event)
  $payload = [ordered]@{ captured_at = Get-UtcTimestamp }
  foreach ($key in $Event.Keys) {
    $payload[$key] = $Event[$key]
  }
  Add-Content -LiteralPath $LogFile -Value ($payload | ConvertTo-Json -Compress -Depth 10) -Encoding UTF8
}

function New-CandidateRecord {
  param(
    [pscustomobject]$Config,
    [string]$QueryVariant,
    [string]$SourceUrl,
    [string]$ReportTitle = "",
    [string]$ForumCategory = "",
    [string]$SourceDate = "",
    [string]$ReportText = "",
    [string]$CaptureStatus = "captured",
    [string]$Notes = "",
    [int]$MaxTextChars = 12000
  )
  $allowedStatuses = @("captured", "blocked_or_verification", "no_readable_text", "failed", "skipped_duplicate", "dry_run")
  if ($allowedStatuses -notcontains $CaptureStatus) {
    throw "unsupported capture_status: $CaptureStatus"
  }
  return [ordered]@{
    collector_id = $CollectorId
    source_id = $SourceId
    product_id = [string]$Config.product_id
    target_version = [string]$Config.target_version
    query_variant_used = [string]$QueryVariant
    source_url = Canonical-SourceUrl $SourceUrl
    report_title = Normalize-Text $ReportTitle
    forum_category = Normalize-Text $ForumCategory
    source_date = Normalize-Text $SourceDate
    captured_at = Get-UtcTimestamp
    report_text = Normalize-Text $ReportText $MaxTextChars
    capture_status = $CaptureStatus
    notes = Normalize-Text $Notes
  }
}

function Serialize-JsonlRecord {
  param([System.Collections.IDictionary]$Record)
  foreach ($field in @("verdict", "decision", "evidence_state", "confidence", "counted", "sentiment", "severity")) {
    if ($Record.Contains($field)) {
      throw "candidate record contains forbidden evidence-decision field: $field"
    }
  }
  return ($Record | ConvertTo-Json -Compress -Depth 10)
}

function Load-ExistingSourceUrls {
  param([string]$OutputDir)
  $urls = New-Object "System.Collections.Generic.HashSet[string]"
  if (-not (Test-Path -LiteralPath $OutputDir)) {
    return $urls
  }
  Get-ChildItem -LiteralPath $OutputDir -Filter "*.jsonl" -File | ForEach-Object {
    Get-Content -LiteralPath $_.FullName | ForEach-Object {
      $line = $_.Trim()
      if (-not $line) { return }
      try {
        $parsed = $line | ConvertFrom-Json
        if ($parsed.source_url) {
          [void]$urls.Add((Canonical-SourceUrl ([string]$parsed.source_url)))
        }
      } catch {
      }
    }
  }
  return $urls
}

function Get-EdgePath {
  $candidates = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  $command = Get-Command msedge.exe -ErrorAction SilentlyContinue
  if ($command) { return $command.Source }
  throw "Microsoft Edge was not found. Install Edge or update Get-EdgePath in capture-edge.ps1."
}

function Get-FreeTcpPort {
  $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
  $listener.Start()
  $port = $listener.LocalEndpoint.Port
  $listener.Stop()
  return $port
}

function Start-EdgeForCapture {
  param([pscustomobject]$Runtime)
  $edgePath = Get-EdgePath
  $port = Get-FreeTcpPort
  New-Item -ItemType Directory -Force -Path $Runtime.browser_profile_dir | Out-Null
  $args = @(
    "--remote-debugging-port=$port",
    "--user-data-dir=$($Runtime.browser_profile_dir)",
    "--no-first-run",
    "--disable-default-apps",
    "--new-window",
    "about:blank"
  )
  if ($Runtime.headless) {
    $args += "--headless=new"
    $args += "--disable-gpu"
  }
  $process = Start-Process -FilePath $edgePath -ArgumentList $args -PassThru
  return [pscustomobject]@{ process = $process; port = $port }
}

function Wait-DevTools {
  param([int]$Port, [int]$TimeoutMs = 15000)
  $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
  $lastError = ""
  while ([DateTime]::UtcNow -lt $deadline) {
    try {
      $version = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 2
      if ($version.webSocketDebuggerUrl) { return $version }
    } catch {
      $lastError = $_.Exception.Message
      Start-Sleep -Milliseconds 250
    }
  }
  throw "Edge DevTools endpoint did not become available: $lastError"
}

function Get-PageWebSocketUrl {
  param([int]$Port)
  $tabs = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json/list" -TimeoutSec 5
  foreach ($tab in $tabs) {
    if ($tab.type -eq "page" -and $tab.webSocketDebuggerUrl) {
      return $tab.webSocketDebuggerUrl
    }
  }
  throw "Could not find an Edge page target for capture."
}

function Connect-Cdp {
  param([string]$WebSocketUrl)
  $socket = New-Object System.Net.WebSockets.ClientWebSocket
  $uri = [Uri]$WebSocketUrl
  $socket.ConnectAsync($uri, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
  return $socket
}

function Receive-CdpMessage {
  param([System.Net.WebSockets.ClientWebSocket]$Socket)
  $buffer = New-Object byte[] 1048576
  $stream = New-Object System.IO.MemoryStream
  do {
    $segment = New-Object System.ArraySegment[byte] -ArgumentList @(,$buffer)
    $result = $Socket.ReceiveAsync($segment, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
    if ($result.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) {
      throw "CDP websocket closed."
    }
    $stream.Write($buffer, 0, $result.Count)
  } while (-not $result.EndOfMessage)
  return [Text.Encoding]::UTF8.GetString($stream.ToArray())
}

function Invoke-CdpCommand {
  param(
    [System.Net.WebSockets.ClientWebSocket]$Socket,
    [string]$Method,
    [hashtable]$Params = @{}
  )
  $id = $Script:NextCdpId
  $Script:NextCdpId += 1
  $payload = @{ id = $id; method = $Method; params = $Params } | ConvertTo-Json -Compress -Depth 20
  $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
  $segment = New-Object System.ArraySegment[byte] -ArgumentList @(,$bytes)
  $Socket.SendAsync($segment, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
  while ($true) {
    $message = Receive-CdpMessage $Socket
    $parsed = $message | ConvertFrom-Json
    if ($parsed.id -eq $id) {
      if ($parsed.error) {
        throw "CDP $Method failed: $($parsed.error.message)"
      }
      return $parsed.result
    }
  }
}

function Invoke-Js {
  param([System.Net.WebSockets.ClientWebSocket]$Socket, [string]$Expression)
  $result = Invoke-CdpCommand $Socket "Runtime.evaluate" @{
    expression = $Expression
    returnByValue = $true
    awaitPromise = $true
  }
  if ($result.exceptionDetails) {
    throw "JavaScript evaluation failed."
  }
  return $result.result.value
}

function Wait-PageReady {
  param([System.Net.WebSockets.ClientWebSocket]$Socket, [int]$TimeoutMs)
  $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
  while ([DateTime]::UtcNow -lt $deadline) {
    try {
      $state = Invoke-Js $Socket "document.readyState"
      if ($state -eq "complete" -or $state -eq "interactive") {
        Start-Sleep -Milliseconds 1200
        return
      }
    } catch {
    }
    Start-Sleep -Milliseconds 350
  }
}

function Open-Page {
  param(
    [System.Net.WebSockets.ClientWebSocket]$Socket,
    [string]$Url,
    [pscustomobject]$Runtime
  )
  Invoke-CdpCommand $Socket "Page.navigate" @{ url = $Url } | Out-Null
  Wait-PageReady $Socket $Runtime.navigation_timeout_ms
}

function Inspect-PageForBlock {
  param([System.Net.WebSockets.ClientWebSocket]$Socket)
  $expression = @'
(() => {
  const text = (document.body && document.body.innerText || "").slice(0, 1000);
  const html = (document.documentElement && document.documentElement.outerHTML || "").slice(0, 4000);
  return { title: document.title || "", body_text: text, html };
})()
'@
  $value = Invoke-Js $Socket $expression
  $reason = Get-BlockReason "$($value.title)`n$($value.body_text)`n$($value.html)"
  return [pscustomobject]@{
    title = [string]$value.title
    body_text = [string]$value.body_text
    block_reason = $reason
  }
}

function Save-ProblemScreenshot {
  param(
    [System.Net.WebSockets.ClientWebSocket]$Socket,
    [string]$ScreenshotDir,
    [string]$Label
  )
  $safe = Sanitize-PathSegment $Label
  $path = Join-Path $ScreenshotDir "$(Get-FileTimestamp)-$safe.png"
  $shot = Invoke-CdpCommand $Socket "Page.captureScreenshot" @{ format = "png"; captureBeyondViewport = $true }
  [IO.File]::WriteAllBytes($path, [Convert]::FromBase64String([string]$shot.data))
  return $path
}

function Extract-ThreadLinks {
  param([System.Net.WebSockets.ClientWebSocket]$Socket, [object[]]$AllowedDomains)
  $expression = @'
(() => Array.from(document.querySelectorAll("a[href*='viewtopic.php']"))
  .map((anchor) => anchor.getAttribute("href"))
  .filter(Boolean)
  .map((href) => new URL(href, window.location.href).toString()))()
'@
  $rawLinks = Invoke-Js $Socket $expression
  $links = New-Object "System.Collections.Generic.List[string]"
  $seen = New-Object "System.Collections.Generic.HashSet[string]"
  foreach ($raw in $rawLinks) {
    $canonical = Canonical-SourceUrl ([string]$raw)
    if ((Is-AllowedSourceUrl $canonical $AllowedDomains) -and -not $seen.Contains($canonical)) {
      [void]$seen.Add($canonical)
      $links.Add($canonical)
    }
  }
  return $links
}

function Extract-ForumData {
  param([System.Net.WebSockets.ClientWebSocket]$Socket)
  $expression = @'
(() => {
  const clean = (value) => String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t\f\v]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  const firstText = (selectors) => {
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      const text = clean(element && element.textContent);
      if (text) return text;
    }
    return "";
  };
  const title = firstText([
    "h2.topic-title a",
    "h2.topic-title",
    ".topic-title a",
    "a.topictitle",
    "h1"
  ]) || clean(document.title).replace(/\s*-\s*Blackmagic Forum\s*$/i, "");
  const breadcrumbs = Array.from(document.querySelectorAll(".breadcrumbs a, .navlinks a, .crumb a"))
    .map((element) => clean(element.textContent))
    .filter(Boolean)
    .filter((text) => !/^(board index|blackmagic design|community forum)$/i.test(text));
  let sourceDate = "";
  const timeElement = document.querySelector("time[datetime]");
  if (timeElement) sourceDate = timeElement.getAttribute("datetime") || "";
  if (!sourceDate) {
    const dated = Array.from(document.querySelectorAll(".author, p.author, .postprofile"))
      .map((element) => clean(element.textContent))
      .find((text) => /\b(?:mon|tue|wed|thu|fri|sat|sun)\b|\b\d{4}\b/i.test(text));
    sourceDate = dated || "";
  }
  let postTexts = [];
  for (const selector of [".postbody .content", ".post .content", "article .content"]) {
    postTexts = Array.from(document.querySelectorAll(selector))
      .map((element) => clean(element.innerText || element.textContent))
      .filter((text) => text.length > 0);
    if (postTexts.length) break;
  }
  let reportText = postTexts.join("\n\n---\n\n");
  if (!reportText) reportText = clean((document.querySelector("main") || document.body || {}).innerText || "");
  return {
    report_title: title,
    forum_category: Array.from(new Set(breadcrumbs)).join(" > "),
    source_date: sourceDate,
    report_text: reportText
  };
})()
'@
  return Invoke-Js $Socket $expression
}

function Wait-BetweenPages {
  param([pscustomobject]$Runtime, [ref]$LastNavigationAt)
  if (-not $LastNavigationAt.Value) { return }
  $min = [Math]::Max(0, [int]$Runtime.delay_min_ms)
  $max = [Math]::Max($min, [int]$Runtime.delay_max_ms)
  $delay = Get-Random -Minimum $min -Maximum ($max + 1)
  $elapsed = ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()) - [int64]$LastNavigationAt.Value
  if ($elapsed -lt $delay) {
    Start-Sleep -Milliseconds ($delay - $elapsed)
  }
}

function Run-SelfTest {
  $config = [pscustomobject]@{
    product_id = "blackmagic-davinci"
    target_version = "21"
    release_date = "2026-04-14"
    watch_until = "2026-06-14"
    query_variants = @("DaVinci Resolve 21")
    allowed_source_domains = @("forum.blackmagicdesign.com")
  }
  Validate-CaptureConfig $config | Out-Null
  $record = New-CandidateRecord -Config $config -QueryVariant "DaVinci Resolve 21" -SourceUrl "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235117&sid=abc#p1" -ReportTitle "Example" -ReportText "Visible text." -CaptureStatus "captured"
  $line = Serialize-JsonlRecord $record
  $parsed = $line | ConvertFrom-Json
  if ($parsed.source_url -ne "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=235117") { throw "canonical URL self-test failed" }
  if ((Get-BlockReason "<script>window.gokuProps = {}</script>") -ne "aws_waf_challenge") { throw "block detection self-test failed" }
  Assert-DedicatedBrowserProfile "C:\AUXSAYS_CAPTURE\browser-profiles\blackmagic-forum" | Out-Null
  try {
    Assert-DedicatedBrowserProfile "C:\Users\someone\AppData\Local\Microsoft\Edge\User Data\Default" | Out-Null
    throw "personal profile self-test failed"
  } catch {
    if ($_.Exception.Message -notmatch "personal browser profile") { throw }
  }
  [pscustomobject]@{
    status = "passed"
    tests = 5
    sample_jsonl = $line
  } | ConvertTo-Json -Depth 10
}

function Run-Capture {
  if (-not $ConfigPath) {
    $ConfigPath = Join-Path $PSScriptRoot "configs\blackmagic-davinci.sample.json"
  }
  $resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
  $config = Get-Content -LiteralPath $resolvedConfig -Raw | ConvertFrom-Json
  Validate-CaptureConfig $config | Out-Null
  $runtime = Get-RuntimeOptions $config
  $paths = Resolve-RunPaths ([string]$config.product_id) $runtime.output_root $runtime.browser_profile_dir
  Assert-DedicatedBrowserProfile $paths.profile_dir | Out-Null

  $searchUrls = @($config.query_variants | ForEach-Object { Build-SearchUrl ([string]$_) })
  if ($DryRun) {
    [pscustomobject]@{
      mode = "dry_run"
      engine = "powershell_edge_cdp"
      config_path = $resolvedConfig
      product_id = [string]$config.product_id
      target_version = [string]$config.target_version
      release_date = [string]$config.release_date
      watch_until = [string]$config.watch_until
      allowed_source_domains = @($config.allowed_source_domains)
      search_urls = $searchUrls
      output_dir = $paths.output_dir
      log_dir = $paths.log_dir
      screenshot_dir = $paths.screenshot_dir
      browser_profile_dir = $paths.profile_dir
      max_pages_per_run = $runtime.max_pages_per_run
      note = "Dry run does not launch a browser and does not write candidate JSONL."
    } | ConvertTo-Json -Depth 10
    return
  }

  Ensure-RunDirs $paths
  $runId = Get-FileTimestamp
  $outputFile = Join-Path $paths.output_dir "$(Sanitize-PathSegment $config.product_id)-$runId.jsonl"
  $logFile = Join-Path $paths.log_dir "$(Sanitize-PathSegment $config.product_id)-$runId.log.jsonl"
  Append-JsonLog $logFile @{ event = "run_started"; engine = "powershell_edge_cdp"; output_file = $outputFile; profile_dir = $paths.profile_dir; max_pages_per_run = $runtime.max_pages_per_run }

  $seenUrls = Load-ExistingSourceUrls $paths.output_dir
  $edge = $null
  $socket = $null
  $pagesVisited = 0
  $recordsWritten = 0
  $duplicatesSkipped = 0
  $stoppedReason = $null
  $lastNavigationAt = $null

  function Append-Candidate {
    param([hashtable]$Args)
    $record = New-CandidateRecord @Args -Config $config -MaxTextChars $runtime.max_text_chars
    $key = Canonical-SourceUrl ([string]$record.source_url)
    if ($seenUrls.Contains($key)) {
      $script:duplicatesSkipped += 1
      Append-JsonLog $logFile @{ event = "candidate_skipped_duplicate"; source_url = $key }
      return
    }
    [void]$seenUrls.Add($key)
    $record.source_url = $key
    Add-Content -LiteralPath $outputFile -Value (Serialize-JsonlRecord $record) -Encoding UTF8
    $script:recordsWritten += 1
    Append-JsonLog $logFile @{ event = "candidate_written"; source_url = $key; capture_status = $record.capture_status }
  }

  function Safe-Open {
    param([string]$Url, [string]$Label)
    if ($script:pagesVisited -ge $runtime.max_pages_per_run) {
      return [pscustomobject]@{ status = "limit_reached"; reason = "max_pages_per_run_reached" }
    }
    Wait-BetweenPages $runtime ([ref]$script:lastNavigationAt)
    $script:lastNavigationAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $script:pagesVisited += 1
    Append-JsonLog $logFile @{ event = "page_opening"; page_number = $script:pagesVisited; source_url = $Url; label = $Label }
    try {
      Open-Page $socket $Url $runtime
      $pageState = Inspect-PageForBlock $socket
      if ($pageState.block_reason) {
        $shot = Save-ProblemScreenshot $socket $paths.screenshot_dir "blocked-$Label"
        return [pscustomobject]@{ status = "blocked_or_verification"; reason = $pageState.block_reason; page_title = $pageState.title; screenshot_path = $shot }
      }
      return [pscustomobject]@{ status = "ok" }
    } catch {
      $shot = ""
      try { $shot = Save-ProblemScreenshot $socket $paths.screenshot_dir "error-$Label" } catch {}
      return [pscustomobject]@{ status = "failed"; reason = $_.Exception.Message; screenshot_path = $shot }
    }
  }

  try {
    $edge = Start-EdgeForCapture $runtime
    Wait-DevTools $edge.port | Out-Null
    $wsUrl = Get-PageWebSocketUrl $edge.port
    $socket = Connect-Cdp $wsUrl
    Invoke-CdpCommand $socket "Page.enable" | Out-Null
    Invoke-CdpCommand $socket "Runtime.enable" | Out-Null

    foreach ($queryVariant in $config.query_variants) {
      $query = [string]$queryVariant
      $searchUrl = Build-SearchUrl $query
      $searchState = Safe-Open $searchUrl "search-$query"
      if ($searchState.status -eq "limit_reached") {
        $stoppedReason = $searchState.reason
        break
      }
      if ($searchState.status -eq "blocked_or_verification") {
        Append-Candidate @{
          QueryVariant = $query
          SourceUrl = $searchUrl
          ReportTitle = if ($searchState.page_title) { $searchState.page_title } else { "Blackmagic forum search blocked or verification page" }
          ReportText = ""
          CaptureStatus = "blocked_or_verification"
          Notes = "Search page blocked or verification shown: $($searchState.reason); screenshot=$($searchState.screenshot_path)"
        }
        $stoppedReason = "blocked_or_verification:$($searchState.reason)"
        if ($runtime.stop_on_block) { break }
        continue
      }
      if ($searchState.status -eq "failed") {
        Append-Candidate @{
          QueryVariant = $query
          SourceUrl = $searchUrl
          ReportTitle = "Blackmagic forum search failed"
          ReportText = ""
          CaptureStatus = "failed"
          Notes = "Search navigation failed: $($searchState.reason); screenshot=$($searchState.screenshot_path)"
        }
        continue
      }

      $links = Extract-ThreadLinks $socket $config.allowed_source_domains
      Append-JsonLog $logFile @{ event = "search_links_found"; query_variant_used = $query; link_count = $links.Count }

      $limit = [Math]::Min($links.Count, $runtime.max_results_per_query)
      for ($i = 0; $i -lt $limit; $i++) {
        $sourceUrl = [string]$links[$i]
        if ($seenUrls.Contains($sourceUrl)) {
          $duplicatesSkipped += 1
          Append-JsonLog $logFile @{ event = "thread_skipped_duplicate"; source_url = $sourceUrl }
          continue
        }
        $threadState = Safe-Open $sourceUrl "thread"
        if ($threadState.status -eq "limit_reached") {
          $stoppedReason = $threadState.reason
          break
        }
        if ($threadState.status -eq "blocked_or_verification") {
          Append-Candidate @{
            QueryVariant = $query
            SourceUrl = $sourceUrl
            ReportTitle = if ($threadState.page_title) { $threadState.page_title } else { "Blackmagic forum thread blocked or verification page" }
            ReportText = ""
            CaptureStatus = "blocked_or_verification"
            Notes = "Thread page blocked or verification shown: $($threadState.reason); screenshot=$($threadState.screenshot_path)"
          }
          $stoppedReason = "blocked_or_verification:$($threadState.reason)"
          if ($runtime.stop_on_block) { break }
          continue
        }
        if ($threadState.status -eq "failed") {
          Append-Candidate @{
            QueryVariant = $query
            SourceUrl = $sourceUrl
            ReportTitle = "Blackmagic forum thread failed"
            ReportText = ""
            CaptureStatus = "failed"
            Notes = "Thread navigation failed: $($threadState.reason); screenshot=$($threadState.screenshot_path)"
          }
          continue
        }
        $data = Extract-ForumData $socket
        $text = [string]$data.report_text
        Append-Candidate @{
          QueryVariant = $query
          SourceUrl = $sourceUrl
          ReportTitle = if ($data.report_title) { [string]$data.report_title } else { $sourceUrl }
          ForumCategory = [string]$data.forum_category
          SourceDate = [string]$data.source_date
          ReportText = $text
          CaptureStatus = if ($text) { "captured" } else { "no_readable_text" }
          Notes = if ($text) { "Captured visible public forum text only; validity is assessed downstream." } else { "Page loaded but no readable forum post text was extracted." }
        }
      }
      if ($stoppedReason) { break }
    }
  } finally {
    if ($socket) {
      try { $socket.Dispose() } catch {}
    }
    if ($edge -and $edge.process -and -not $edge.process.HasExited) {
      try { $edge.process.CloseMainWindow() | Out-Null } catch {}
    }
    Append-JsonLog $logFile @{ event = "run_finished"; pages_visited = $pagesVisited; records_written = $recordsWritten; duplicates_skipped = $duplicatesSkipped; stopped_reason = $stoppedReason }
  }

  [pscustomobject]@{
    mode = "capture"
    engine = "powershell_edge_cdp"
    product_id = [string]$config.product_id
    target_version = [string]$config.target_version
    pages_visited = $pagesVisited
    records_written = $recordsWritten
    duplicates_skipped = $duplicatesSkipped
    stopped_reason = $stoppedReason
    output_file = if ($recordsWritten -gt 0) { $outputFile } else { $null }
    log_file = $logFile
    screenshot_dir = $paths.screenshot_dir
  } | ConvertTo-Json -Depth 10
}

if ($SelfTest) {
  Run-SelfTest
} else {
  Run-Capture
}
