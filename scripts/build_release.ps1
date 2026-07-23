# Build full portable release into release/
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> 1/4 Build UI + Electron"
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> 2/4 Build Python backend"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_backend.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> 3/4 Package portable exe"
npx --yes electron-builder --win portable
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> 4/4 Copy packaging files"
$Release = Join-Path $Root "release"
New-Item -ItemType Directory -Path $Release -Force | Out-Null
Copy-Item (Join-Path $Root "packaging\run_as_admin.bat") $Release -Force
Copy-Item (Join-Path $Root "packaging\readme.txt") $Release -Force

Write-Host ""
Write-Host "DONE"
Write-Host "ZIP this folder: $Release"
Get-ChildItem $Release | Format-Table Name, Length, LastWriteTime
