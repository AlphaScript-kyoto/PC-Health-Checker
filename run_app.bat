@echo off
chcp 65001 >nul
cd /d "%~dp0"

where npm >nul 2>&1
if errorlevel 1 (
  echo [エラー] npm が見つかりません。
  echo Node.js をインストールしてから、もう一度実行してください。
  echo https://nodejs.org/
  pause
  exit /b 1
)

if not exist "node_modules\" (
  echo 初回セットアップ: npm install を実行します...
  call npm install
  if errorlevel 1 (
    echo [エラー] npm install に失敗しました。
    pause
    exit /b 1
  )
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ヒント] Python 仮想環境がありません。
  echo README の初回セットアップ（python -m venv / pip install）を先に行ってください。
  echo.
)

echo パソコンちぇっ君を起動しています（npm run dev）...
echo このウィンドウは閉じないでください。終了するときは Ctrl+C か、トレイから終了してください。
echo.
call npm run dev
echo.
echo アプリが終了しました。エラーが出ていたら上のメッセージを確認してください。
pause
exit /b %errorlevel%
