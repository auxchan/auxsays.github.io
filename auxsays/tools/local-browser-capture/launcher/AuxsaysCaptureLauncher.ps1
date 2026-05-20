param(
  [string]$ConfigPath
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$launcherRoot = $PSScriptRoot
$toolRoot = (Resolve-Path (Join-Path $launcherRoot "..")).Path
$auxsaysRoot = (Resolve-Path (Join-Path $toolRoot "..\..")).Path
$edgeCaptureScript = Join-Path $toolRoot "capture-edge.ps1"
$defaultConfig = Join-Path $toolRoot "configs\blackmagic-davinci.sample.json"
$readmePath = Join-Path $toolRoot "README.md"
$defaultOutputRoot = "C:\AUXSAYS_CAPTURE"

if (-not $ConfigPath) {
  $ConfigPath = $defaultConfig
}

function Quote-ProcessArg {
  param([string]$Value)
  if ($null -eq $Value) {
    return '""'
  }
  if ($Value -notmatch '[\s"]') {
    return $Value
  }
  return '"' + ($Value -replace '"', '\"') + '"'
}

function Invoke-CapturedProcess {
  param(
    [string]$FileName,
    [string[]]$Arguments,
    [string]$WorkingDirectory
  )

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FileName
  $psi.Arguments = (($Arguments | ForEach-Object { Quote-ProcessArg $_ }) -join " ")
  $psi.WorkingDirectory = $WorkingDirectory
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $psi
  [void]$process.Start()
  $stdout = $process.StandardOutput.ReadToEnd()
  $stderr = $process.StandardError.ReadToEnd()
  $process.WaitForExit()

  return [pscustomobject]@{
    ExitCode = $process.ExitCode
    StdOut = $stdout
    StdErr = $stderr
    Command = "$FileName $($psi.Arguments)"
  }
}

function New-Label {
  param([string]$Text, [int]$X, [int]$Y, [int]$Width = 120)
  $label = New-Object System.Windows.Forms.Label
  $label.Text = $Text
  $label.Location = New-Object System.Drawing.Point($X, $Y)
  $label.Size = New-Object System.Drawing.Size($Width, 22)
  $label.TextAlign = [System.Drawing.ContentAlignment]::MiddleLeft
  return $label
}

function New-Button {
  param([string]$Text, [int]$X, [int]$Y, [int]$Width = 130)
  $button = New-Object System.Windows.Forms.Button
  $button.Text = $Text
  $button.Location = New-Object System.Drawing.Point($X, $Y)
  $button.Size = New-Object System.Drawing.Size($Width, 34)
  return $button
}

function Resolve-OutputPath {
  param([string]$Kind)
  $root = $outputRootBox.Text.Trim()
  if (-not $root) {
    $root = $defaultOutputRoot
  }
  $product = "blackmagic-davinci"
  switch ($Kind) {
    "logs" { return Join-Path $root "logs\$product" }
    "screenshots" { return Join-Path $root "screenshots\$product" }
    default { return Join-Path $root "outbox\$product" }
  }
}

function Append-Output {
  param([string]$Text)
  $outputBox.AppendText($Text)
  if (-not $Text.EndsWith("`n")) {
    $outputBox.AppendText("`r`n")
  }
}

function Set-Running {
  param([bool]$Running)
  foreach ($button in $actionButtons) {
    $button.Enabled = -not $Running
  }
  $statusLabel.Text = if ($Running) { "Running..." } else { "Ready" }
}

function Build-CaptureArgs {
  param([bool]$DryRun)

  $config = $configBox.Text.Trim()
  if (-not $config) {
    throw "Choose a config file first."
  }
  if (-not (Test-Path -LiteralPath $config)) {
    throw "Config file does not exist: $config"
  }

  $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $edgeCaptureScript, "-ConfigPath", $config)
  if ($DryRun) {
    $args += "-DryRun"
  }
  $args += @("-MaxPages", [string][int]$maxPagesBox.Value)
  if ($headlessBox.Checked) {
    $args += "-Headless"
  }
  if ($continueOnBlockBox.Checked) {
    $args += "-ContinueOnBlock"
  }
  if ($outputRootBox.Text.Trim()) {
    $args += @("-OutputRoot", $outputRootBox.Text.Trim())
  }
  return $args
}

function Run-BackgroundCommand {
  param(
    [string]$Title,
    [scriptblock]$Work
  )

  Set-Running $true
  Append-Output ""
  Append-Output "== $Title =="

  $worker = New-Object System.ComponentModel.BackgroundWorker
  $worker.DoWork += {
    param($sender, $eventArgs)
    $eventArgs.Result = & $Work
  }
  $worker.RunWorkerCompleted += {
    param($sender, $eventArgs)
    try {
      if ($eventArgs.Error) {
        Append-Output "ERROR: $($eventArgs.Error.Message)"
      } else {
        $result = $eventArgs.Result
        Append-Output "Command:"
        Append-Output $result.Command
        if ($result.StdOut) {
          Append-Output ""
          Append-Output $result.StdOut.TrimEnd()
        }
        if ($result.StdErr) {
          Append-Output ""
          Append-Output $result.StdErr.TrimEnd()
        }
        Append-Output ""
        Append-Output "Exit code: $($result.ExitCode)"
      }
    } finally {
      Set-Running $false
    }
  }
  $worker.RunWorkerAsync()
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "AUXSAYS Local Browser Capture"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(920, 690)
$form.MinimumSize = New-Object System.Drawing.Size(820, 600)

$title = New-Object System.Windows.Forms.Label
$title.Text = "AUXSAYS Blackmagic Forum Capture"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(16, 14)
$title.Size = New-Object System.Drawing.Size(520, 32)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "Reads public forum pages at low rate with Microsoft Edge and writes JSONL candidates. No Node install is needed for this launcher."
$subtitle.Location = New-Object System.Drawing.Point(18, 48)
$subtitle.Size = New-Object System.Drawing.Size(850, 24)
$form.Controls.Add($subtitle)

$form.Controls.Add((New-Label "Config file" 18 88 110))
$configBox = New-Object System.Windows.Forms.TextBox
$configBox.Location = New-Object System.Drawing.Point(130, 88)
$configBox.Size = New-Object System.Drawing.Size(610, 24)
$configBox.Text = $ConfigPath
$form.Controls.Add($configBox)

$browseButton = New-Button "Browse..." 752 84 110
$browseButton.Add_Click({
  $dialog = New-Object System.Windows.Forms.OpenFileDialog
  $dialog.Filter = "JSON config (*.json)|*.json|All files (*.*)|*.*"
  $dialog.InitialDirectory = Join-Path $toolRoot "configs"
  if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    $configBox.Text = $dialog.FileName
  }
})
$form.Controls.Add($browseButton)

$form.Controls.Add((New-Label "Output root" 18 122 110))
$outputRootBox = New-Object System.Windows.Forms.TextBox
$outputRootBox.Location = New-Object System.Drawing.Point(130, 122)
$outputRootBox.Size = New-Object System.Drawing.Size(300, 24)
$outputRootBox.Text = $defaultOutputRoot
$form.Controls.Add($outputRootBox)

$form.Controls.Add((New-Label "Max pages" 452 122 85))
$maxPagesBox = New-Object System.Windows.Forms.NumericUpDown
$maxPagesBox.Location = New-Object System.Drawing.Point(535, 122)
$maxPagesBox.Size = New-Object System.Drawing.Size(72, 24)
$maxPagesBox.Minimum = 1
$maxPagesBox.Maximum = 200
$maxPagesBox.Value = 20
$form.Controls.Add($maxPagesBox)

$form.Controls.Add((New-Label "Browser" 625 122 70))
$browserChannelBox = New-Object System.Windows.Forms.ComboBox
$browserChannelBox.Location = New-Object System.Drawing.Point(690, 122)
$browserChannelBox.Size = New-Object System.Drawing.Size(120, 24)
$browserChannelBox.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
[void]$browserChannelBox.Items.Add("msedge")
[void]$browserChannelBox.Items.Add("chrome")
[void]$browserChannelBox.Items.Add("chromium")
$browserChannelBox.SelectedItem = "msedge"
$browserChannelBox.Enabled = $false
$form.Controls.Add($browserChannelBox)

$headlessBox = New-Object System.Windows.Forms.CheckBox
$headlessBox.Text = "Headless"
$headlessBox.Location = New-Object System.Drawing.Point(130, 156)
$headlessBox.Size = New-Object System.Drawing.Size(100, 24)
$form.Controls.Add($headlessBox)

$continueOnBlockBox = New-Object System.Windows.Forms.CheckBox
$continueOnBlockBox.Text = "Continue if block/verification is shown"
$continueOnBlockBox.Location = New-Object System.Drawing.Point(240, 156)
$continueOnBlockBox.Size = New-Object System.Drawing.Size(260, 24)
$continueOnBlockBox.Checked = $false
$form.Controls.Add($continueOnBlockBox)

$dryRunButton = New-Button "Dry Run" 18 198 120
$captureButton = New-Button "Start Capture" 148 198 130
$testButton = New-Button "Self Check" 288 198 120
$installButton = New-Button "Open Screenshots" 418 198 150
$openOutputButton = New-Button "Open Output" 578 198 120
$openLogsButton = New-Button "Open Logs" 708 198 110
$readmeButton = New-Button "README" 828 198 70

$actionButtons = @($dryRunButton, $captureButton, $testButton, $installButton, $openOutputButton, $openLogsButton, $readmeButton, $browseButton)

$dryRunButton.Add_Click({
  Run-BackgroundCommand "Dry run" {
    Invoke-CapturedProcess -FileName "powershell.exe" -Arguments (Build-CaptureArgs -DryRun $true) -WorkingDirectory $auxsaysRoot
  }
})

$captureButton.Add_Click({
  $answer = [System.Windows.Forms.MessageBox]::Show(
    "This will open a dedicated browser profile and read public Blackmagic forum pages. It will stop if verification or a block page is detected. Continue?",
    "Start capture",
    [System.Windows.Forms.MessageBoxButtons]::OKCancel,
    [System.Windows.Forms.MessageBoxIcon]::Information
  )
  if ($answer -ne [System.Windows.Forms.DialogResult]::OK) {
    return
  }
  Run-BackgroundCommand "Capture" {
    Invoke-CapturedProcess -FileName "powershell.exe" -Arguments (Build-CaptureArgs -DryRun $false) -WorkingDirectory $auxsaysRoot
  }
})

$testButton.Add_Click({
  Run-BackgroundCommand "PowerShell Edge capture self check" {
    Invoke-CapturedProcess -FileName "powershell.exe" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $edgeCaptureScript, "-SelfTest") -WorkingDirectory $auxsaysRoot
  }
})

$installButton.Add_Click({
  $path = Resolve-OutputPath "screenshots"
  [System.IO.Directory]::CreateDirectory($path) | Out-Null
  Start-Process -FilePath $path
})

$openOutputButton.Add_Click({
  $path = Resolve-OutputPath "outbox"
  [System.IO.Directory]::CreateDirectory($path) | Out-Null
  Start-Process -FilePath $path
})

$openLogsButton.Add_Click({
  $path = Resolve-OutputPath "logs"
  [System.IO.Directory]::CreateDirectory($path) | Out-Null
  Start-Process -FilePath $path
})

$readmeButton.Add_Click({
  Start-Process -FilePath $readmePath
})

$form.Controls.AddRange(@($dryRunButton, $captureButton, $testButton, $installButton, $openOutputButton, $openLogsButton, $readmeButton))

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Ready"
$statusLabel.Location = New-Object System.Drawing.Point(18, 242)
$statusLabel.Size = New-Object System.Drawing.Size(850, 22)
$form.Controls.Add($statusLabel)

$outputBox = New-Object System.Windows.Forms.TextBox
$outputBox.Location = New-Object System.Drawing.Point(18, 270)
$outputBox.Size = New-Object System.Drawing.Size(850, 350)
$outputBox.Multiline = $true
$outputBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Both
$outputBox.WordWrap = $false
$outputBox.ReadOnly = $true
$outputBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$form.Controls.Add($outputBox)

Append-Output "Ready. Start with Dry Run, then Start Capture."
Append-Output "Output folder: C:\AUXSAYS_CAPTURE\outbox\blackmagic-davinci"
Append-Output "This launcher uses Microsoft Edge with the dedicated capture profile configured in the JSON file."

[void]$form.ShowDialog()
