# PCの健康チェッカー（PC Health Checker）

ディスクの健全性（SMART）・空き容量・容量マップ・買い替え提案・価格ウォッチ・ニュースをひとつのデスクトップアプリで見守ります。  
制作者: [Alpha Script](https://alphascript-kyoto.github.io/as-homepage/)  
リポジトリ: https://github.com/AlphaScript-kyoto/PC-Health-Checker

**アプリ内からのファイル削除や商品の自動購入は行いません。**

## 使い方

### 必要環境

- Windows
- Node.js 18+
- Python 3.11+（推奨）

### 初回セットアップ

```powershell
cd "C:\Users\akimi\Desktop\programming\pc-health-checker"

python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

npm install
```

### 開発起動

```powershell
npm run dev
```

Electron が開き、Python バックエンド（`http://127.0.0.1:8787`）も自動起動します。  
SMART を正確に取るには、画面の **管理者として再起動** を使ってください。UAC で許可すると、新しい管理者ウィンドウが古い非管理者プロセスを終了させ、ウィンドウは1つだけ残ります。右上に **管理者で動作中**、ホームに **管理者権限あり** と表示されます。

### 本番ビルド（UI）

```powershell
npm run build
npm start
```

ポータブル exe の再パッケージは、従来の PC Health と同様に PyInstaller + electron-builder で行います（`scripts/` 参照）。

## 画面

| タブ | 内容 |
|------|------|
| ホーム | 総合ステータス、在庫、アラート、導線 |
| ディスク | SMART / 空き |
| 容量マップ | ツリーマップ・安全性ラベル・削除候補 |
| 提案 | 交換候補リンク |
| 価格 | パーツ価格追跡 |
| ニュース | PC パーツニュース |
| 設定 | 通知・スタートアップ・閾値・スキャン時刻 |

## 各ファイルの役割

| パス | 役割 |
|------|------|
| `electron/main.ts` | ウィンドウ・トレイ・管理者昇格・Python 起動 |
| `electron/preload.ts` | 画面向け安全 API |
| `src/` | React UI（全タブ） |
| `assets/icon.png` / `build/icon.ico` | アプリアイコン（ウィンドウ・トレイ・配布用） |
| `scripts/make_app_icon.py` | アイコン画像から PNG / ICO を再生成 |
| `backend/app/` | FastAPI・スキャン・DB・価格・ニュース |
| `backend/app/space_scan.py` | 容量マップ用フォルダ走査 |
| `requirements.txt` | Python 依存関係 |
| `package.json` | Node / Electron 依存関係 |

## データ保存場所

- 開発: `backend/app/data/`
- 配布想定: `%LOCALAPPDATA%\PCHealthChecker\data`
