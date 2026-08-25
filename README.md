# パソコンちぇっ君（Pasokon Chekkun）

**バージョン 0.3.0**

ディスクの健全性（SMART）・空き容量・容量マップ・買い替え提案・価格ウォッチ・ニュースをひとつのデスクトップアプリで見守ります。  
旧称: PCの健康チェッカー  
制作者: [Alpha Script](https://alphascript-kyoto.github.io/as-homepage/)  
リポジトリ: https://github.com/AlphaScript-kyoto/PC-Health-Checker

**アプリ内からのファイル削除や商品の自動購入は行いません。**

## 0.3.0 の主な変更

- ディスク詳細を CrystalDiskInfo 風の**別ウィンドウ**で表示（上段2列・温度は右上）
- SMART から**総書込み量（ホスト）**、バッファサイズ（IDENTIFY／モデル公称値）を表示
- HDD／SSD の回転数誤判定を修正
- 健康バッジの**文言と色を一致**（通電年数などの「注意」を正しく表示）
- 管理者起動でも最新 UI を取り込みやすく改善（再起動時の再ビルド／再読込）
- **毎日の自動スキャン**結果を画面に反映（進捗・最終スキャン時刻・通知）
- 全体スキャンと容量マップ単独スキャンを**中断・再開・最初から再スキャン**できる操作ボタンを追加
- 開発用ランチャー（`run_app.vbs` / `run_app.bat`）を現行構成に合わせて修正
- **修正:** 自動スキャン／全体スキャン中、容量マップの進捗バーがドライブ開始直後で止まりっぱなしになる問題（ドライブ内部の走査量に応じてバーが進むように改善）
- **修正:** HDD で健康診断と容量マップを同時実行すると極端に遅くなる問題（順次実行に変更）。WinSxS など巨大システム領域の詳細走査を省略し、進捗にファイル数も表示

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

または、プロジェクト直下のランチャーでも起動できます。

- `run_app.vbs` … おすすめ。コンソールを出さずに起動（`npm run dev` は裏で動作）
- `run_app.bat` … ログ付きでコンソール表示（トラブル時向け）
- `run_as_admin.bat` … 管理者として同じ開発起動（UAC あり）

※ アプリはトレイ常駐します。すでに動いていると新しい起動は案内を出して終わります。  
`run_app.bat` / `vbs` は起動前に古い Electron を終了します。手動ならトレイ右クリック → **終了**。

※ 裏で動いている開発サーバーのログは `%LOCALAPPDATA%\PCHealthChecker\dev-launch.log` に残ります。

Electron が開き、Python バックエンド（`http://127.0.0.1:8787`）も自動起動します。  
SMART を正確に取るには、画面の **管理者として再起動** を使ってください。押すと少し準備（画面のビルド）のあと UAC が出ます。許可すると管理者ウィンドウが1つ開き、右上に **管理者で動作中**、ホームに **管理者権限あり** と表示されます。

起動後は自動で **健康診断** のあと **容量マップ作成** が順に走ります（HDD で同時実行すると遅くなるため）。上部に進捗バーが2本（①健康診断 / ②容量マップ）並びます。

スキャン中は右上の **スキャンを中断** で一時停止できます。続きから動かすときは **スキャンを再開**、進捗を破棄してやり直すときは **最初からスキャン** を押してください。

**管理者として再起動**について:

- まだ管理者でない → UI を `dist` に書き出してから管理者で開き直します
- **すでに管理者** → 最新UIをビルドし直して画面を読み直します
- Vite に繋がるときは最新の開発サーバーを優先します

うまく反映されないときは、トレイから一度「終了」して `run_app.vbs` → 管理者再起動、を試してください。

**配布用の `release\run_as_admin.bat`** は別物で、横の `PC-Chekkun-*-portable.exe` を管理者起動します（開発用ランチャーではありません）。

### 本番ビルド（UI）

```powershell
npm run build
npm start
```

### リリース版（ポータブル exe）

```powershell
npm run release
```

完了すると `release` フォルダに次が並びます。

- `PC-Chekkun-*-portable.exe` … 本体
- `run_as_admin.bat` … 管理者起動用
- `readme.txt` … 使い方

**ZIP にするのは次の3ファイルだけ**です（`.icon-ico` / `win-unpacked` / `builder-debug.yml` は入れない）。

```
release/
  PC-Chekkun-0.3.0-portable.exe
  run_as_admin.bat
  readme.txt
```

※ 初回は PyInstaller の導入とバックエンド固めで数分〜十数分かかります。

## 画面

| タブ | 内容 |
|------|------|
| ホーム | 総合ステータス、在庫、アラート。起動時＆「今すぐスキャン」で健康診断＋容量マップを**並行**実行 |
| ディスク | CrystalDiskInfo 相当の識別情報。SMART 全項目は **詳細ウィンドウ**（上段2列・コンパクト）で確認 |
| 容量マップ | ツリーマップ・安全性ラベル・削除候補。長いスキャンは中断・再開でき、必要なら最初からやり直せます |
| 提案 | 交換候補リンク（価格.com は SJIS エンコード） |
| 価格 | 追跡・カタログ（複数列）。追跡カードに **自前の価格推移グラフ** と **Keepa 1年グラフ**（ASIN取得後）。AMD マザボに X870 / X870E あり |
| ニュース | タブを開くたびに最新取得 |
| 設定 | 通知・スタートアップ・閾値・**毎日の自動スキャン時刻**（アプリ常駐中に実行。画面も約10秒ごとに結果を取り込みます） |

## ディスク詳細で見られる主な項目

スクショの CrystalDiskInfo に寄せた項目です（取得できる環境・権限・smartctl の有無で一部 `----` になることがあります）。

- モデル / 容量 / 健康状態 / 温度
- ファームウェア / シリアル番号（初期はマスク、表示ボタンあり）
- インターフェース / 転送モード（例: SATA/600）
- ドライブ文字 / 対応規格（ATA・SATA バージョン）
- 対応機能（S.M.A.R.T. / 48bit LBA / APM / AAM / NCQ / TRIM など）
- バッファサイズ / NVキャッシュ / 回転数  
  （バッファは SMART 属性ではなく ATA IDENTIFY の旧項目。取れないときはモデル公称値を補完し、`8192 KB（公称値）` と表示します）
- 総書込み量（ホスト） / 電源投入回数 / 使用時間
- S.M.A.R.T. 属性テーブル（ID・項目名・現在値・最悪値・しきい値・生の値）

## 各ファイルの役割

| パス | 役割 |
|------|------|
| `electron/main.ts` | ウィンドウ・トレイ・管理者昇格・Python 起動 |
| `electron/preload.ts` | 画面向け安全 API |
| `src/` | React UI（全タブ） |
| `src/pages/SpacePage.tsx` | 容量マップ画面とスキャンの開始・中断・再開・再スキャン操作 |
| `src/components/DiskDetailView.tsx` | ディスク詳細（一覧カード／詳細ウィンドウ共通） |
| `src/pages/PricesPage.tsx` | 価格追跡・カタログ UI |
| `src/components/PriceCharts.tsx` | 価格推移グラフ / Keepa 埋め込み |
| `assets/icon.png` / `build/icon.ico` | アプリアイコン（ウィンドウ・トレイ・配布用） |
| `scripts/build_backend.ps1` | Python バックエンドを PyInstaller で固める |
| `scripts/build_release.ps1` | UI + バックエンド + portable exe を一括作成 |
| `packaging/` | 配布同梱の readme / 管理者起動 bat |
| `release/` | **配布用の完成物（ここを ZIP する）** |
| `backend/app/` | FastAPI・スキャン・DB・価格・ニュース |
| `backend/app/scanner.py` | 健康診断と容量マップの並行スキャン・二重進捗 |
| `backend/app/main.py` | API 起動・毎日自動スキャンのスケジューラ |
| `backend/app/collectors/disks.py` | SMART / 識別情報の収集 |
| `backend/app/space_scan.py` | 容量マップ用フォルダ走査 |
| `requirements.txt` | Python 依存関係 |
| `package.json` | Node / Electron 依存関係 |

## データ保存場所

- 開発: `backend/app/data/`
- 配布想定: `%LOCALAPPDATA%\PCHealthChecker\data`
