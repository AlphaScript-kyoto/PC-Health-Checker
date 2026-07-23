@echo off
cd /d "%~dp0"
if not exist "desktop\node_modules\electron\dist\electron.exe" (
  if not exist "desktop\node_modules\electron" (
    echo Installing Electron...
    pushd desktop
    call npm install
    popd
  )
)
start "" "%~dp0desktop\node_modules\electron\dist\electron.exe" "%~dp0desktop"
exit /b 0
