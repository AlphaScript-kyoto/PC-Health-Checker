# PC Health Monitor — スタートアップ登録（コンソールなし）
param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$AppName = "PC Health"
$Root = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $Root "run_app.vbs"
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$ShortcutPath = Join-Path $StartupDir "$AppName.lnk"

if ($Remove) {
    if (Test-Path $ShortcutPath) {
        Remove-Item $ShortcutPath -Force
        Write-Host "Removed: $ShortcutPath"
    } else {
        Write-Host "Shortcut not found."
    }
    exit 0
}

if (-not (Test-Path $Launcher)) {
    throw "Launcher not found: $Launcher"
}

$wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($ShortcutPath)
$sc.TargetPath = $wscript
$sc.Arguments = "//nologo `"$Launcher`""
$sc.WorkingDirectory = $Root
$sc.WindowStyle = 7
$sc.Description = $AppName
$sc.Save()

Write-Host "Installed: $ShortcutPath"
