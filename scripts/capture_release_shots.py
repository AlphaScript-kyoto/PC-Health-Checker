"""Capture 1920x1080 release screenshots with polished demo content per tab."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
BASE = "http://127.0.0.1:8787/"

DEMO_JS = r"""
() => {
  const badge = (s, label) => `<span class="badge ${s}">${label}</span>`;

  // --- Home ---
  document.querySelector('#overall').innerHTML =
    `${badge('Watch', '注意')} <span>注意</span>`;
  document.querySelector('#heroHint').textContent =
    '様子を見た方がよい項目があります。';
  document.querySelector('#scannedAt').textContent =
    '最終スキャン 2026/7/16 17:30:00';
  document.querySelector('#inventory').innerHTML = `
    <div class="card">
      <div class="row"><span>ホスト</span><strong>GAMING-ASUSROG</strong></div>
      <div class="row"><span>CPU</span><strong>AMD Ryzen 9 9950X3D 16-Core Processor</strong></div>
      <div class="row"><span>GPU</span><strong>AMD Radeon RX 9070 XT（VRAM 16GB）</strong></div>
      <div class="row"><span>メモリ</span><strong>63.9 GB（使用 28.4%）<span class="mem-detail">DDR5 32GB×2 6000MHz</span></strong></div>
      <div class="row"><span>機種</span><strong>ASUS ROG CROSSHAIR X870E HERO</strong></div>
      <div class="row"><span>OS</span><strong>Microsoft Windows 11 Pro</strong></div>
    </div>`;
  document.querySelector('#issues').innerHTML = `
    <div class="card">
      <div class="row"><strong>C:</strong>${badge('Watch', '注意')}</div>
      <p class="muted">空き容量が 12.4%（248 GB / 2000 GB）です</p>
    </div>
    <div class="card">
      <div class="row"><strong>Samsung 990 PRO 2TB</strong>${badge('Watch', '注意')}</div>
      <ul class="reasons">
        <li>関連ボリューム空き 12.4%</li>
        <li>通電時間約 2.1 年（18420 h）</li>
      </ul>
    </div>
    <div class="card">
      <div class="row"><strong>WDC WD20EZRZ-00Z5HB0</strong>${badge('ReplaceSoon', '要交換')}</div>
      <ul class="reasons">
        <li>代替処理済セクタ: 3</li>
        <li>保留中セクタ: 8</li>
        <li>通電時間約 6.8 年（59547 h）</li>
      </ul>
    </div>`;
  document.querySelector('#alerts').innerHTML = `
    <div class="card">
      <div class="row"><strong>ディスク注意: Samsung 990 PRO 2TB</strong>${badge('Watch', '注意')}</div>
      <p class="muted">2026/7/16 17:30:00 — 関連ボリューム空き 12.4%</p>
    </div>
    <div class="card">
      <div class="row"><strong>容量不足: C:</strong>${badge('Watch', '注意')}</div>
      <p class="muted">2026/7/16 17:30:00 — C: の空き容量が 12.4%（248 GB）です</p>
    </div>
    <div class="card">
      <div class="row"><strong>定期スキャン完了</strong>${badge('OK', '正常')}</div>
      <p class="muted">2026/7/16 17:00:00 — 3 台のドライブを確認しました</p>
    </div>`;

  // --- Disks ---
  const elev = document.querySelector('#elevationBanner');
  if (elev) { elev.hidden = true; elev.innerHTML = ''; }
  document.querySelector('#disks').innerHTML = `
    <div class="card">
      <div class="disk-head">
        <div class="health-meter Good" title="SMART健康: 正常"><span class="meter-label">正常</span></div>
        <div>
          <div class="row" style="margin-bottom:6px"><strong style="font-size:16px">Samsung SSD 990 PRO 2TB</strong>${badge('OK', '正常')}</div>
          <div class="kv">
            <span>転送モード</span><strong>NVMe / SSD</strong>
            <span>容量</span><strong>1863 GB</strong>
            <span>シリアル</span><strong>S6Z2NX0R123456</strong>
            <span>ファームウェア</span><strong>4B2QGXA7</strong>
            <span>OS Health</span><strong>Healthy / OK</strong>
            <span>SMART</span><strong>合格（取得元: WMI）</strong>
            <span>通電時間</span><strong>18420 h（約 768 日 / 2.1 年）</strong>
            <span>電源投入回数</span><strong>842</strong>
            <span>ボリューム</span><strong>C: 空き 12.4% (248 GB / 2000 GB)</strong>
          </div>
        </div>
        <div class="temp-pill cool">38°C</div>
      </div>
      <div class="muted" style="margin-top:10px">温度・空き容量の簡易履歴</div>
      <div class="spark">${Array.from({length:16}, (_,i) => `<i title="${36+i%4}°C" style="height:${14+(i%5)*3}px"></i>`).join('')}</div>
      <div class="history">2026/7/16 17:30:00  正常  空き=12.4%  温度=38°C
2026/7/16 17:00:00  正常  空き=12.5%  温度=37°C
2026/7/16 16:30:00  正常  空き=12.6%  温度=39°C</div>
    </div>
    <div class="card">
      <div class="disk-head">
        <div class="health-meter Caution" title="SMART健康: 注意"><span class="meter-label">注意</span></div>
        <div>
          <div class="row" style="margin-bottom:6px"><strong style="font-size:16px">CT2000P3PSSD8</strong>${badge('Watch', '注意')}</div>
          <div class="kv">
            <span>転送モード</span><strong>NVMe / SSD</strong>
            <span>容量</span><strong>1863 GB</strong>
            <span>シリアル</span><strong>2334E6A12ABC</strong>
            <span>ファームウェア</span><strong>P9CR40A</strong>
            <span>OS Health</span><strong>Healthy / OK</strong>
            <span>SMART</span><strong>合格（取得元: WMI）</strong>
            <span>通電時間</span><strong>22140 h（約 922 日 / 2.5 年）</strong>
            <span>電源投入回数</span><strong>1102</strong>
            <span>ボリューム</span><strong>D: 空き 18.2% (364 GB / 2000 GB)</strong>
          </div>
        </div>
        <div class="temp-pill warm">51°C</div>
      </div>
      <ul class="reasons"><li>通電時間約 2.5 年（22140 h）</li><li>温度がやや高め（51°C）</li></ul>
      <div class="muted" style="margin-top:10px">温度・空き容量の簡易履歴</div>
      <div class="spark">${Array.from({length:16}, (_,i) => `<i title="${48+i%5}°C" style="height:${22+(i%4)*4}px"></i>`).join('')}</div>
      <div class="history">2026/7/16 17:30:00  注意  空き=18.2%  温度=51°C
2026/7/16 17:00:00  注意  空き=18.3%  温度=49°C</div>
    </div>
    <div class="card">
      <div class="disk-head">
        <div class="health-meter ReplaceSoon" title="SMART健康: 要交換"><span class="meter-label">要交換</span></div>
        <div>
          <div class="row" style="margin-bottom:6px"><strong style="font-size:16px">WDC WD20EZRZ-00Z5HB0</strong>${badge('ReplaceSoon', '要交換')}</div>
          <div class="kv">
            <span>転送モード</span><strong>SATA / HDD</strong>
            <span>容量</span><strong>1863 GB</strong>
            <span>シリアル</span><strong>WD-WCC4N7XXXXXX</strong>
            <span>ファームウェア</span><strong>80.00A80</strong>
            <span>OS Health</span><strong>Caution / OK</strong>
            <span>SMART</span><strong>注意（取得元: WMI）</strong>
            <span>通電時間</span><strong>59547 h（約 2481 日 / 6.8 年）</strong>
            <span>電源投入回数</span><strong>4821</strong>
            <span>ボリューム</span><strong>E: 空き 41.0% (763 GB / 1863 GB)</strong>
          </div>
        </div>
        <div class="temp-pill cool">34°C</div>
      </div>
      <ul class="reasons">
        <li>代替処理済セクタ: 3</li>
        <li>保留中セクタ: 8</li>
        <li>通電時間約 6.8 年（59547 h）</li>
      </ul>
      <div class="muted" style="margin-top:10px">温度・空き容量の簡易履歴</div>
      <div class="spark">${Array.from({length:16}, (_,i) => `<i title="${32+i%3}°C" style="height:${10+(i%3)*2}px"></i>`).join('')}</div>
      <div class="history">2026/7/16 17:30:00  要交換  空き=41.0%  温度=34°C
2026/7/16 17:00:00  要交換  空き=41.0%  温度=33°C</div>
    </div>`;

  // --- Recommendations ---
  document.querySelector('#recommendations').innerHTML = `
    <div class="card">
      <div class="row"><strong>WDC WD20EZRZ-00Z5HB0</strong>${badge('ReplaceSoon', '要交換')}</div>
      <p class="muted">検索語: SSD 2TB コスパ</p>
      <p>新品の目安 12,000〜28,000円 / 中古の目安 6,600〜22,400円（実売は変動。リンク先で確認）</p>
      <ul class="reasons">
        <li>現行: WDC WD20EZRZ-00Z5HB0（1863 GB / HDD）</li>
        <li>希望: SSD 2TB前後</li>
        <li>予算目安: 30,000円</li>
        <li>理由: 代替処理済セクタ: 3 / 保留中セクタ: 8 / 通電時間約 6.8 年</li>
      </ul>
      <div class="links">
        <a href="#" onclick="return false"><strong>価格.com</strong> — SSD 2TB 人気ランキング<br/><span class="muted">新品 / 相場の目安を確認</span></a>
        <a href="#" onclick="return false"><strong>Amazon</strong> — SSD 2TB 検索結果<br/><span class="muted">新品 / 出品価格を比較</span></a>
        <a href="#" onclick="return false"><strong>Mercari</strong> — SSD 2TB 中古<br/><span class="muted">中古 / 状態を確認してから</span></a>
      </div>
      <p class="muted">商品の自動購入機能はありません。リンク先で状態・保証・価格を必ず確認してください。</p>
    </div>
    <div class="card">
      <div class="row"><strong>Samsung SSD 990 PRO 2TB</strong>${badge('Watch', '注意')}</div>
      <p class="muted">検索語: M.2 SSD 4TB PCIe 4.0</p>
      <p>新品の目安 28,000〜55,000円（空き容量不足の増設候補）</p>
      <ul class="reasons">
        <li>現行: Samsung 990 PRO 2TB（C: 空き 12.4%）</li>
        <li>希望: M.2 SSD 4TB前後</li>
        <li>理由: 関連ボリューム空き 12.4%</li>
      </ul>
      <div class="links">
        <a href="#" onclick="return false"><strong>価格.com</strong> — M.2 SSD 4TB<br/><span class="muted">新品 / 相場の目安を確認</span></a>
        <a href="#" onclick="return false"><strong>Amazon</strong> — M.2 SSD 4TB<br/><span class="muted">新品 / 出品価格を比較</span></a>
      </div>
      <p class="muted">商品の自動購入機能はありません。リンク先で状態・保証・価格を必ず確認してください。</p>
    </div>`;

  // --- Prices: polish meta, collapse caveats, open first groups ---
  const caveats = document.querySelector('.price-caveats');
  if (caveats) caveats.open = false;
  const meta = document.querySelector('#priceMeta');
  if (meta) meta.textContent = 'カタログ 2026.07.3 / 最終価格取得 2026/7/16 16:12:31 / 追跡中 6 件';
  const overview = document.querySelector('#priceOverview');
  if (overview && !overview.querySelector('.price-card')) {
    const spark = (w=268,h=84) => {
      const pts = [42,44,41,46,48,47,49,51,50,52,51,53];
      const min=Math.min(...pts), max=Math.max(...pts);
      const line = pts.map((v,i) => {
        const x = 10 + i*((w-20)/(pts.length-1));
        const y = h-12 - ((v-min)/(max-min||1))*(h-24);
        return `${x},${y}`;
      }).join(' ');
      return `<div class="price-chart-wrap"><svg class="price-chart" viewBox="0 0 ${w} ${h}" width="100%" height="${h}"><polyline class="chart-line chart-kakaku" fill="none" stroke-width="2" points="${line}"/><polyline class="chart-line chart-amazon" fill="none" stroke-width="2" points="${line.split(' ').map((p,i)=>{const [x,y]=p.split(','); return `${x},${Number(y)+6+(i%3)}`;}).join(' ')}"/></svg>
      <div class="chart-legend"><span class="legend-kakaku">価格.com 最安</span><span class="legend-amazon">Amazon 新品平均</span></div></div>`;
    };
    const card = (name, brand, gen, cat, k, a) => `<article class="card price-card">
      <div class="price-card-head"><strong class="price-card-title">${name}</strong><span class="badge OK">${cat}</span></div>
      <p class="tiny price-card-sub">${brand} / ${gen}</p>
      <div class="price-dual">
        <div class="price-source"><span class="price-source-label legend-kakaku">価格.com 最安</span><div class="price-now">¥${k.toLocaleString('ja-JP')}</div></div>
        <div class="price-source"><span class="price-source-label legend-amazon">Amazon 新品平均</span><div class="price-now price-now-amazon">¥${a.toLocaleString('ja-JP')}</div></div>
      </div>
      ${spark()}
      <details class="keepa-fold"><summary class="keepa-summary">Keepa 過去価格グラフ（1年）</summary></details>
      <div class="price-card-links"><a href="#" onclick="return false">価格.com</a><a href="#" onclick="return false">Amazon</a></div>
    </article>`;
    overview.innerHTML = `
      <details class="price-overview-group" open>
        <summary><span class="price-overview-title">CPU</span><span class="fold-hint">2 件</span><span class="chevron" aria-hidden="true"></span></summary>
        <div class="price-overview-grid">
          ${card('Ryzen 9 9950X3D', 'AMD', 'Ryzen 9000', 'CPU', 92800, 99800)}
          ${card('Ryzen 7 9700X', 'AMD', 'Ryzen 9000', 'CPU', 42526, 49890)}
        </div>
      </details>
      <details class="price-overview-group" open>
        <summary><span class="price-overview-title">GPU</span><span class="fold-hint">2 件</span><span class="chevron" aria-hidden="true"></span></summary>
        <div class="price-overview-grid">
          ${card('Radeon RX 9070 XT', 'AMD', 'RX 9000', 'GPU', 102080, 109465)}
          ${card('Radeon RX 9060 XT', 'AMD', 'RX 9000', 'GPU', 69800, 75200)}
        </div>
      </details>
      <details class="price-overview-group">
        <summary><span class="price-overview-title">メモリ</span><span class="fold-hint">1 件</span><span class="chevron" aria-hidden="true"></span></summary>
        <div class="price-overview-grid">
          ${card('DDR5 32GB (16GBx2) 6000', '汎用', 'DDR5', 'メモリ', 14800, 16200)}
        </div>
      </details>`;
  } else {
    document.querySelectorAll('#priceOverview details.price-overview-group').forEach((d, i) => { d.open = i < 2; });
    document.querySelectorAll('#priceOverview details.keepa-fold').forEach((d) => { d.open = false; });
  }
  const catalog = document.querySelector('#priceCatalog');
  if (catalog) {
    catalog.style.display = 'none';
    const title = document.querySelector('#tab-prices .block-title');
    if (title) title.style.display = 'none';
  }

  // --- News ---
  document.querySelector('#news').innerHTML = `
    <article class="card news-card">
      <div class="news-thumb placeholder" aria-hidden="true"></div>
      <div class="news-body">
        <div class="news-meta"><span>4Gamer</span><span>2026/7/16 15:20:00</span></div>
        <h3><a href="#" onclick="return false">AMD、Ryzen 9000X3Dシリーズの最新ドライバ最適化を公開。ゲーミング性能がさらに向上</a></h3>
        <p>AMDは7月16日、Ryzen 9000X3D向けの最適化パッチを含むドライバを公開。特に高リフレッシュレート環境でのフレームタイム改善をうたう。</p>
      </div>
    </article>
    <article class="card news-card">
      <div class="news-thumb placeholder" aria-hidden="true"></div>
      <div class="news-body">
        <div class="news-meta"><span>PC Watch</span><span>2026/7/16 12:40:00</span></div>
        <h3><a href="#" onclick="return false">Radeon RX 9070 XTの実売価格が続落。国内ショップで10万円前後の製品も</a></h3>
        <p>RX 9000シリーズの流通が安定し、国内の実売価格がさらに下がってきた。4Kゲーム用途でも現実的な選択肢になりつつある。</p>
      </div>
    </article>
    <article class="card news-card">
      <div class="news-thumb placeholder" aria-hidden="true"></div>
      <div class="news-body">
        <div class="news-meta"><span>Akiba PC Hotline!</span><span>2026/7/15 19:10:00</span></div>
        <h3><a href="#" onclick="return false">PCIe 5.0対応の2TB M.2 SSDがセール。高速モデルが2万円台前半に</a></h3>
        <p>秋葉原各店でPCIe 5.0 SSDの特価販売が進行中。容量単価が下がったことで、ブート用からの移行も検討しやすい価格帯になってきた。</p>
      </div>
    </article>
    <article class="card news-card">
      <div class="news-thumb placeholder" aria-hidden="true"></div>
      <div class="news-body">
        <div class="news-meta"><span>Impress Watch</span><span>2026/7/15 10:05:00</span></div>
        <h3><a href="#" onclick="return false">DDR5メモリの価格動向。32GBキットが1.5万円前後まで落ち着き</a></h3>
        <p>6000MHz帯の32GBキットが安定供給。AMDプラットフォームとの組み合わせ需要も引き続き堅調だ。</p>
      </div>
    </article>`;

  // --- Settings ---
  const form = document.querySelector('#settingsForm');
  if (form) {
    const set = (name, value) => {
      const el = form.elements.namedItem(name);
      if (!el) return;
      if (el.type === 'checkbox') el.checked = !!value;
      else el.value = value;
    };
    set('notify_enabled', true);
    set('startup_enabled', true);
    set('capacity_warn_pct', 15);
    set('capacity_critical_pct', 8);
    set('budget_max_yen', 30000);
    set('daily_scan_time', '09:00');
    set('prefer_new_used', 'new');
    set('prefer_media', 'ssd');
    set('capacity_preference_tb', '2');
    set('priority', 'price');
  }
  const about = document.querySelector('#aboutBody');
  if (about) {
    about.innerHTML = `
      <p><strong>PC Health v0.2.2</strong></p>
      <p>作成: Alpha Script</p>
      <p>HP: <a href="https://alphascript-kyoto.github.io/as-homepage/" target="_blank" rel="noopener noreferrer">https://alphascript-kyoto.github.io/as-homepage/</a></p>
      <p>管理者権限: あり — SMART詳細・温度を取得中</p>
      <p class="muted">ローカル専用アプリです。データは PC 外に送信しません。</p>`;
  }
  return 'demo ready';
}
"""

TABS = [
    ("home", "01-home.png"),
    ("disks", "02-disks.png"),
    ("reco", "03-suggest.png"),
    ("prices", "04-prices.png"),
    ("news", "05-news.png"),
    ("settings", "06-settings.png"),
]


def switch_tab(page, tab: str) -> None:
    page.evaluate(
        """(tab) => {
          document.querySelectorAll('.nav-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
          document.querySelectorAll('.panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${tab}`));
          window.scrollTo(0, 0);
          const content = document.querySelector('.content');
          if (content) content.scrollTop = 0;
        }""",
        tab,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.goto(BASE, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        page.evaluate(DEMO_JS)
        page.wait_for_timeout(400)
        for tab, filename in TABS:
            switch_tab(page, tab)
            page.wait_for_timeout(350)
            path = OUT / filename
            page.screenshot(path=str(path), full_page=False)
            print(f"wrote {path}")
        browser.close()
    print("done")


if __name__ == "__main__":
    main()
