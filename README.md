# PC Health

ローカル常駐アプリ（Electron）で、ディスク健全性・空き容量・構成を見守り、交換時に購入候補を提示、PCパーツニュースを一覧できます。**自動購入はしません。**

制作者: [Alpha Script](https://alphascript-kyoto.github.io/as-homepage/)

## 起動（開発）

1. 初回だけ（未セットアップなら）:

```powershell
cd "C:\Users\akimi\Desktop\programming\my pc"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd desktop
npm install
cd ..
```

2. **`run_app.bat`** をダブルクリック  
   - ウィンドウを閉じてもトレイ常駐

SMARTを正しく取るには **`run_as_admin.bat`**

## 配布パッケージ

ポータブル実行ファイル（インストール不要）:

- `release\PCHealth-0.2.0-portable.exe`

受け取った側は exe をダブルクリックするだけです。データは `%LOCALAPPDATA%\PCHealth\data` に保存されます。

### 再ビルド手順

```powershell
cd "C:\Users\akimi\Desktop\programming\my pc"
# 1) Python バックエンド
$ui = (Resolve-Path "app\ui").Path
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --noconsole --name pc-health-backend --paths . --add-data "$ui;app/ui" --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on --collect-all uvicorn --collect-all fastapi --collect-all starlette --collect-submodules app scripts/backend_entry.py --distpath dist-backend --workpath build-backend --specpath build-backend

# 2) Electron ポータブル
cd desktop
npm run dist
```

成果物: `release\PCHealth-<version>-portable.exe`

## 使い方

- 左ナビ: ホーム / ディスク / 提案 / **価格** / ニュース / 設定
- **価格**: パーツを複数選択 → 週次で価格.com最安を記録。世代更新でリスト外になったものは「残す/外す」を選択
- トレイ: ウィンドウ表示 / スキャン / 終了
- **システム状態（ヒーロー）はホームタブのみ**に表示されます

## スタートアップ

**設定 → Windows起動時に起動**、または:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_startup.ps1
```

## 技術構成

- UI: Electron（ライト UI）
- 監視: Python（FastAPI / WMI SMART / トースト）
- ニュース: 公開 RSS + 記事の og:image サムネイル
- データ: ローカル SQLite（開発時 `app/data/`、配布版は `%LOCALAPPDATA%\PCHealth\data`）

## 任意: smartctl

`winget install smartmontools.smartmontools`

## やらないこと

- 自動購入 / 高精度スクレイピング / クラウド送信
