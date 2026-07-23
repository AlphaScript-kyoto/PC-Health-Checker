@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "TARGET="
for %%F in (PC-Chekkun-*-portable.exe) do set "TARGET=%%~fF"
if not defined TARGET (
  echo パソコンちぇっ君の portable exe が見つかりません。
  echo この bat と同じフォルダに PC-Chekkun-*-portable.exe を置いてください。
  pause
  exit /b 1
)
powershell -NoProfile -Command "Start-Process -FilePath '%TARGET%' -Verb RunAs"
