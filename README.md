# PC Health

ローカル常駐アプリ（Electron）で、ディスク健全性・空き容量・構成を見守り、交換時に購入候補を提示、PCパーツニュースを一覧できます。**商品の自動購入機能はありません。**

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

- `release\PCHealth-0.2.4-portable.exe`

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
- **価格**: パーツを複数選択 → 週次で価格.com最安目安・Amazon新品平均を記録（Keepaグラフ付き）。世代更新でリスト外になったものは「残す/外す」を選択
- トレイ: ウィンドウ表示 / スキャン / 管理者として再起動 / 終了
- **システム状態（ヒーロー）はホームタブのみ**に表示されます
- **自動スキャン**: アプリ起動時に1回、その後は設定した**毎日の時刻**に実行（アプリが常駐している間）

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

- 商品の自動購入 / 高精度スクレイピング / クラウド送信

## 価格取得の既知の不具合・注意点

- Amazonへ短時間に連続アクセスすると一時ブロックされ、取得失敗になることがある（時間を置いて再更新で回復）
- 価格は検索結果ベースの参考値。検索語によっては別商品・アクセサリの価格が混ざる場合がある（外れ値は自動除外）
- Amazon価格は「検索上位の新品出品の平均」で、実際のカート価格と異なる場合がある
- Keepaグラフは検索結果先頭の商品を表示するため、意図と違う商品になる場合がある
- 価格.com・Amazonのページ構成変更で取得不能になる場合がある
