# Build Python backend with PyInstaller
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
  Write-Host "ERROR: backend\.venv not found"
  exit 1
}

Write-Host "==> Ensure PyInstaller"
& $VenvPython -m pip install --upgrade pip pyinstaller
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Entry = Join-Path $Root "scripts\backend_entry.py"
$Dist = Join-Path $Root "dist-backend"
$Work = Join-Path $Root "build-backend"
$BackendPath = Join-Path $Root "backend"

if (Test-Path $Dist) {
  Remove-Item $Dist -Recurse -Force
}
New-Item -ItemType Directory -Path $Dist -Force | Out-Null
New-Item -ItemType Directory -Path $Work -Force | Out-Null

Write-Host "==> Building backend (may take several minutes)"
& $VenvPython -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --name "pc-health-backend" `
  --distpath $Dist `
  --workpath $Work `
  --specpath $Work `
  --paths $BackendPath `
  --hidden-import "uvicorn.logging" `
  --hidden-import "uvicorn.loops" `
  --hidden-import "uvicorn.loops.auto" `
  --hidden-import "uvicorn.protocols" `
  --hidden-import "uvicorn.protocols.http" `
  --hidden-import "uvicorn.protocols.http.auto" `
  --hidden-import "uvicorn.protocols.websockets" `
  --hidden-import "uvicorn.protocols.websockets.auto" `
  --hidden-import "uvicorn.lifespan" `
  --hidden-import "uvicorn.lifespan.on" `
  --hidden-import "multipart" `
  --collect-submodules "uvicorn" `
  --collect-submodules "fastapi" `
  --collect-submodules "starlette" `
  --collect-all "pydantic" `
  --collect-all "httpx" `
  $Entry

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Exe = Join-Path $Dist "pc-health-backend\pc-health-backend.exe"
if (-not (Test-Path $Exe)) {
  Write-Host "ERROR: missing $Exe"
  exit 1
}

Write-Host "==> OK: $Exe"
