@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "SILENT=0"
if /I "%~1"=="silent" set "SILENT=1"

where npm >nul 2>&1
if errorlevel 1 (
  if "%SILENT%"=="1" (
    msg * "npm が見つかりません。Node.js をインストールしてください。"
  ) else (
    echo [エラー] npm が見つかりません。
    echo Node.js をインストールしてから、もう一度実行してください。
    echo https://nodejs.org/
    pause
  )
  exit /b 1
)

if not exist "node_modules\" (
  if not "%SILENT%"=="1" echo 初回セットアップ: npm install を実行します...
  call npm install
  if errorlevel 1 (
    if "%SILENT%"=="1" (
      msg * "npm install に失敗しました。"
    ) else (
      echo [エラー] npm install に失敗しました。
      pause
    )
    exit /b 1
  )
)

if not "%SILENT%"=="1" (
  if not exist "backend\.venv\Scripts\python.exe" (
    echo [ヒント] Python 仮想環境がありません。
    echo README の初回セットアップ（python -m venv / pip install）を先に行ってください。
    echo.
  )
)

if not "%SILENT%"=="1" (
  echo 古い常駐プロセスがあれば終了します...
  echo （管理者で残っている場合は UAC 確認が出ることがあります）
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_dev_electron.ps1"
if errorlevel 1 (
  if not "%SILENT%"=="1" (
    echo.
    echo [注意] 古いプロセスを消しきれませんでした。
    echo 画面右下トレイの「パソコンちぇっ君」を右クリック →「終了」してから再実行してください。
    echo.
    pause
  )
)

set "LOGDIR=%LOCALAPPDATA%\PCHealthChecker"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
set "LOG=%LOGDIR%\dev-launch.log"

if "%SILENT%"=="1" (
  rem コンソールは出さない。ログだけ残す。
  call npm run dev > "%LOG%" 2>&1
) else (
  echo パソコンちぇっ君を起動しています（npm run dev）...
  echo このウィンドウを閉じると開発サーバーも止まります。
  echo 普段は run_app.vbs を使うと、この黒い画面は出ません。
  echo.
  call npm run dev
  set "EXITCODE=%ERRORLEVEL%"
  echo.
  echo アプリが終了しました。エラーが出ていたら上のメッセージを確認してください。
  echo ※ 「すでに起動しています」と出た場合は、トレイから終了して再実行してください。
  pause
  exit /b %EXITCODE%
)

exit /b %ERRORLEVEL%
