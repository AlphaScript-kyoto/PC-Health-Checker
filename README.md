# パソコンちぇっ君（Pasokon Chekkun）

ディスクの健全性（SMART）・空き容量・容量マップ・買い替え提案・価格ウォッチ・ニュースをひとつのデスクトップアプリで見守ります。  
旧称: PCの健康チェッカー  
制作者: [Alpha Script](https://alphascript-kyoto.github.io/as-homepage/)  
リポジトリ: https://github.com/AlphaScript-kyoto/PC-Health-Checker

**アプリ内からのファイル削除や商品の自動購入は行いません。**

## 使い方

### 必要環境

- Windows
- Node.js 18+
- Python 3.11+（推奨）
- （推奨）[smartmontools](https://www.smartmontools.org/) の `smartctl` … CrystalDiskInfo 相当の詳細取得に使います

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
SMART を正確に取るには、画面の **管理者として再起動** を使ってください。押すと少し準備（画面のビルド）のあと UAC が出ます。許可すると管理者ウィンドウが1つ開き、右上に **管理者で動作中**、ホームに **管理者権限あり** と表示されます。

起動後は自動で **健康診断** と **容量マップ作成** が並行して走ります。上部に進捗バーが2本（①健康診断 / ②容量マップ）並びます。

**管理者として再起動**すると開発サーバーではなく `dist`（ビルド済みUI）を開きます。進捗バーなど最新UIを管理者でも見るには、昇格前にビルドが走る仕様です。手元で古い画面のままなら一度アプリを終了し、`npm run build` のあと `npm run dev` → 管理者再起動、を試してください。

### 本番ビルド（UI）

```powershell
npm run build
npm start
```

ポータブル exe の再パッケージは、従来の PC Health と同様に PyInstaller + electron-builder で行います（`scripts/` 参照）。

## 画面

| タブ | 内容 |
|------|------|
| ホーム | 総合ステータス、在庫、アラート。起動時＆「今すぐスキャン」で健康診断＋容量マップを**並行**実行 |
| ディスク | CrystalDiskInfo 相当の識別情報（温度・転送モード・対応機能・使用時間など）と SMART 属性テーブル |
| 容量マップ | ツリーマップ・安全性ラベル・削除候補 |
| 提案 | 交換候補リンク（価格.com は SJIS エンコード） |
| 価格 | 追跡・カタログ（複数列）。追跡カードに **自前の価格推移グラフ** と **Keepa 1年グラフ**（ASIN取得後）。AMD マザボに X870 / X870E あり |
| ニュース | タブを開くたびに最新取得 |
| 設定 | 通知・スタートアップ・閾値・スキャン時刻 |

## ディスク詳細で見られる主な項目

スクショの CrystalDiskInfo に寄せた項目です（取得できる環境・権限・smartctl の有無で一部 `----` になることがあります）。

- モデル / 容量 / 健康状態 / 温度
- ファームウェア / シリアル番号（初期はマスク、表示ボタンあり）
- インターフェース / 転送モード（例: SATA/600）
- ドライブ文字 / 対応規格（ATA・SATA バージョン）
- 対応機能（S.M.A.R.T. / 48bit LBA / APM / AAM / NCQ / TRIM など）
- バッファサイズ / NVキャッシュ / 回転数
- 電源投入回数 / 使用時間
- S.M.A.R.T. 属性テーブル（ID・項目名・現在値・最悪値・しきい値・生の値）

## 各ファイルの役割

| パス | 役割 |
|------|------|
| `electron/main.ts` | ウィンドウ・トレイ・管理者昇格・Python 起動 |
| `electron/preload.ts` | 画面向け安全 API |
| `src/` | React UI（全タブ） |
| `src/pages/PricesPage.tsx` | 価格追跡・カタログ UI |
| `src/components/PriceCharts.tsx` | 価格推移グラフ / Keepa 埋め込み |
| `assets/icon.png` / `build/icon.ico` | アプリアイコン（ウィンドウ・トレイ・配布用） |
| `scripts/make_app_icon.py` | アイコン画像から PNG / ICO を再生成 |
| `backend/app/` | FastAPI・スキャン・DB・価格・ニュース |
| `backend/app/scanner.py` | 健康診断と容量マップの並行スキャン・二重進捗 |
| `backend/app/collectors/disks.py` | SMART / 識別情報の収集 |
| `backend/app/space_scan.py` | 容量マップ用フォルダ走査 |
| `requirements.txt` | Python 依存関係 |
| `package.json` | Node / Electron 依存関係 |

## データ保存場所

- 開発: `backend/app/data/`
- 配布想定: `%LOCALAPPDATA%\PCHealthChecker\data`
