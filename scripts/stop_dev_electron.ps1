# Stop leftover PC Chekkun Electron so npm run dev can start.
param(
  [switch]$ForceElevated
)

$ErrorActionPreference = 'SilentlyContinue'

function Test-IsAdmin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-IsChekkunProcess($proc) {
  $ep = [string]$proc.ExecutablePath
  $cl = [string]$proc.CommandLine
  $blob = "$ep $cl"
  if ($blob -like '*pc-health-checker*') { return $true }
  if ($blob -like '*PCHealthChecker*') { return $true }
  if ($blob -like '*PC-Chekkun*') { return $true }
  return $false
}

function Get-TargetElectron {
  @(Get-CimInstance Win32_Process -Filter "Name = 'electron.exe'" | Where-Object { Test-IsChekkunProcess $_ })
}

function Stop-Targets {
  $denied = $false
  $killed = 0
  foreach ($p in Get-TargetElectron) {
    try {
      Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
      $killed++
      continue
    } catch {
      $denied = $true
    }
    & taskkill.exe /F /PID $p.ProcessId /T 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      $killed++
    } else {
      $denied = $true
    }
  }
  return @{ Killed = $killed; Denied = $denied }
}

$result = Stop-Targets
Start-Sleep -Milliseconds 400

$lockfile = Join-Path $env:LOCALAPPDATA 'PCHealthChecker\lockfile'
$opaque = @(
  Get-CimInstance Win32_Process -Filter "Name = 'electron.exe'" |
    Where-Object { (-not [string]$_.ExecutablePath) -and (-not [string]$_.CommandLine) }
)

$needElevate = $false
if (-not (Test-IsAdmin) -and -not $ForceElevated) {
  if ($result.Denied) { $needElevate = $true }
  if (($opaque.Count -gt 0) -and (Test-Path $lockfile)) { $needElevate = $true }
}

if ($needElevate) {
  Write-Host 'Admin leftover detected. Showing UAC prompt...'
  $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -ForceElevated"
  try {
    $p = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arg -Wait -PassThru
    exit $p.ExitCode
  } catch {
    Write-Host 'UAC cancelled. Quit from tray icon first.'
    exit 2
  }
}

if ($ForceElevated) {
  Stop-Targets | Out-Null
  Start-Sleep -Milliseconds 400
}

$left = Get-TargetElectron
if ($left.Count -gt 0) {
  Write-Host 'Could not stop Chekkun Electron. Quit from tray.'
  exit 1
}

Write-Host 'OK'
exit 0
