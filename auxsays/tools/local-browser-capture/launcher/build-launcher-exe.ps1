$ErrorActionPreference = "Stop"

$launcherRoot = $PSScriptRoot
$sourcePath = Join-Path $launcherRoot "AuxsaysCaptureLauncher.cs"
$outputPath = Join-Path $launcherRoot "AuxsaysCaptureLauncher.exe"

$compilerCandidates = @(
  "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
  "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe",
  "$env:WINDIR\Microsoft.NET\Framework64\v3.5\csc.exe",
  "$env:WINDIR\Microsoft.NET\Framework\v3.5\csc.exe"
)

$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) {
  throw "Could not find csc.exe. Use AuxsaysCaptureLauncher.cmd instead, or install .NET Framework developer tools."
}

& $compiler /nologo /target:winexe /out:$outputPath /reference:System.Windows.Forms.dll /reference:System.Drawing.dll $sourcePath
if ($LASTEXITCODE -ne 0) {
  throw "Launcher EXE build failed with exit code $LASTEXITCODE"
}

Write-Host "Built $outputPath"
