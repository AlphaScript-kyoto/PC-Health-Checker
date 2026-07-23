@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "TARGET="
for %%F in (PCHealth-*-portable.exe) do set "TARGET=%%~fF"
if not defined TARGET (
  echo PCHealth の portable exe が見つかりません。
  echo この bat と同じフォルダに exe を置いてください。
  pause
  exit /b 1
)

echo 管理者権限で起動します: %TARGET%
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath '%TARGET%' -Verb RunAs"
exit /b 0
