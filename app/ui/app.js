const $ = (sel) => document.querySelector(sel);

const RISK_JA = {
  OK: "正常",
  Watch: "注意",
  ReplaceSoon: "要交換",
  Critical: "危険",
  Unknown: "不明",
};

const METER_JA = {
  Good: "正常",
  Caution: "注意",
  Bad: "異常",
  Unknown: "不明",
};

function statusJa(status) {
  return RISK_JA[status] || METER_JA[status] || status || "不明";
}

function badge(status) {
  const s = status || "Unknown";
  return `<span class="badge ${s}">${statusJa(s)}</span>`;
}

/** Circle shows app judgment (risk), colored by severity. */
function diskMeterClass(risk) {
  const map = {
    OK: "Good",
    Watch: "Caution",
    ReplaceSoon: "ReplaceSoon",
    Critical: "Bad",
    Unknown: "Unknown",
  };
  return map[risk] || "Unknown";
}

function fmtTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("ja-JP");
  } catch {
    return iso;
  }
}

function fmtYen(v) {
  if (v == null || v === "") return "—";
  return `¥${Number(v).toLocaleString()}`;
}

const PRICE_CATEGORY_JA = {
  cpu: "CPU",
  gpu: "GPU",
  hdd: "HDD",
  sata_ssd: "SATA SSD",
  m2_ssd: "M.2 SSD",
  memory: "メモリ",
  motherboard: "マザーボード",
};

function renderDualPriceChart(kakakuHist, amazonHist, width = 268, height = 84) {
  const series = [
    { key: "kakaku", hist: kakakuHist || [], cls: "chart-kakaku" },
    { key: "amazon", hist: amazonHist || [], cls: "chart-amazon" },
  ];
  const points = [];
  for (const s of series) {
    for (const h of s.hist) {
      if (h.price_yen == null) continue;
      const t = new Date(h.fetched_at).getTime();
      if (!Number.isFinite(t)) continue;
      points.push({ t, y: h.price_yen, key: s.key });
    }
  }
  if (!points.length) {
    return `<div class="price-chart-empty">「今すぐ価格更新」で履歴が溜まるとグラフ表示</div>`;
  }
  const minT = Math.min(...points.map((p) => p.t));
  const maxT = Math.max(...points.map((p) => p.t));
  const prices = points.map((p) => p.y);
  const minY = Math.min(...prices);
  const maxY = Math.max(...prices);
  const pad = { l: 4, r: 4, t: 10, b: 16 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const xOf = (t) => pad.l + (maxT === minT ? iw / 2 : ((t - minT) / (maxT - minT)) * iw);
  const yOf = (y) => pad.t + ih - (maxY === minY ? ih / 2 : ((y - minY) / (maxY - minY)) * ih);

  const paths = series
    .map((s) => {
      const pts = (s.hist || []).filter((h) => h.price_yen != null);
      if (!pts.length) return "";
      const d = pts
        .map((h, i) => {
          const x = xOf(new Date(h.fetched_at).getTime());
          const y = yOf(h.price_yen);
          return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");
      return `<path d="${d}" class="chart-line ${s.cls}" fill="none" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
    })
    .join("");

  return `<div class="price-chart-wrap">
    <svg class="price-chart" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="価格推移グラフ">
      <text x="${pad.l}" y="${height - 3}" class="chart-label">${fmtYen(minY)}</text>
      <text x="${width - pad.r}" y="${pad.t + 8}" class="chart-label chart-label-end" text-anchor="end">${fmtYen(maxY)}</text>
      ${paths}
    </svg>
    <div class="chart-legend">
      <span class="legend-kakaku">価格.com 最安</span>
      <span class="legend-amazon">Amazon 新品平均</span>
    </div>
  </div>`;
}

function renderKeepaSection(p) {
  if (!p.keepa_graph_url) return "";
  return `<details class="keepa-fold">
    <summary class="keepa-summary">Keepa 過去価格グラフ（1年）</summary>
    <a href="${escapeHtml(p.keepa_product_url)}" target="_blank" rel="noopener noreferrer" title="Keepaで詳細を見る">
      <img class="keepa-chart" loading="lazy" src="${escapeHtml(p.keepa_graph_url)}" alt="Keepa価格推移グラフ"
        onerror="this.parentElement.parentElement.classList.add('keepa-error')" />
    </a>
    <p class="tiny keepa-note">グラフ提供: keepa.com（Amazon新品/本体価格・過去365日）</p>
  </details>`;
}

function renderPriceOverviewCard(p) {
  const kYen = p.latest_kakaku?.price_yen ?? p.latest_price?.price_yen;
  const aYen = p.latest_amazon?.price_yen;
  const chart = renderDualPriceChart(p.kakaku_history, p.amazon_history);
  return `<article class="card price-card">
    <div class="price-card-head">
      <strong class="price-card-title">${escapeHtml(p.name)}</strong>
      <span class="badge tag">${escapeHtml(PRICE_CATEGORY_JA[p.category] || p.category || "")}</span>
    </div>
    <p class="tiny price-card-sub">${escapeHtml(p.brand || "")} / ${escapeHtml(p.generation || "")}${p.keep_legacy ? " / 旧世代キープ" : ""}</p>
    <div class="price-dual">
      <div class="price-source">
        <span class="price-source-label legend-kakaku">価格.com 最安</span>
        <div class="price-now">${fmtYen(kYen)}</div>
      </div>
      <div class="price-source">
        <span class="price-source-label legend-amazon">Amazon 新品平均</span>
        <div class="price-now price-now-amazon">${fmtYen(aYen)}</div>
      </div>
    </div>
    ${chart}
    ${renderKeepaSection(p)}
    <div class="price-card-links">
      <a href="${escapeHtml(p.kakaku_url)}" target="_blank" rel="noopener noreferrer">価格.com</a>
      <a href="${escapeHtml(p.amazon_url)}" target="_blank" rel="noopener noreferrer">Amazon</a>
    </div>
  </article>`;
}

function groupOverviewByCategory(overview) {
  const order = ["cpu", "gpu", "motherboard", "memory", "m2_ssd", "sata_ssd", "hdd"];
  const map = {};
  for (const p of overview) {
    const cat = p.category || "other";
    if (!map[cat]) map[cat] = [];
    map[cat].push(p);
  }
  const keys = [
    ...order.filter((k) => map[k]),
    ...Object.keys(map).filter((k) => !order.includes(k)),
  ];
  return keys.map((cat) => ({
    category: cat,
    label: PRICE_CATEGORY_JA[cat] || cat,
    items: map[cat],
  }));
}

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

function renderInventory(inv) {
  if (!inv) {
    $("#inventory").innerHTML = "<p class='muted'>データなし</p>";
    return;
  }
  const memDetail = inv.memory_summary
    ? `<span class="mem-detail">${escapeHtml(inv.memory_summary)}</span>`
    : "";
  $("#inventory").innerHTML = `
    <div class="card">
      <div class="row"><span>ホスト</span><strong>${escapeHtml(inv.hostname || "-")}</strong></div>
      <div class="row"><span>CPU</span><strong>${escapeHtml(inv.cpu_name || "-")}</strong></div>
      ${inv.gpu_summary ? `<div class="row"><span>GPU</span><strong>${escapeHtml(inv.gpu_summary)}</strong></div>` : ""}
      <div class="row"><span>メモリ</span><strong>${escapeHtml(String(inv.total_memory_gb ?? "-"))} GB（使用 ${escapeHtml(String(inv.memory_used_pct ?? "-"))}%）${memDetail}</strong></div>
      <div class="row"><span>機種</span><strong>${escapeHtml(`${inv.manufacturer || ""} ${inv.model || ""}`.trim() || "-")}</strong></div>
      <div class="row"><span>OS</span><strong>${escapeHtml(inv.os_caption || inv.platform || "-")}</strong></div>
    </div>`;
}

function renderIssues(data) {
  const items = [];
  for (const v of data.volume_issues || []) {
    items.push(`<div class="card"><div class="row"><strong>${escapeHtml(v.letter || "")}</strong>${badge(v.risk_level)}</div><p class="muted">${escapeHtml(v.reason || "")}</p></div>`);
  }
  for (const d of data.disks || []) {
    if (d.risk_level && d.risk_level !== "OK") {
      items.push(`<div class="card"><div class="row"><strong>${escapeHtml(d.model || "")}</strong>${badge(d.risk_level)}</div>
        <ul class="reasons">${(d.reasons || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul></div>`);
    }
  }
  $("#issues").innerHTML = items.length ? items.join("") : "<div class='card'><p class='muted'>現時点で要注意項目はありません。</p></div>";
}

function tempClass(t) {
  if (t == null) return "";
  if (t >= 60) return "hot";
  if (t >= 50) return "warm";
  return "cool";
}

function healthMeterLabel(meter) {
  return METER_JA[meter] || meter || "不明";
}

function smartOverallJa(overall) {
  const map = {
    PASSED: "合格",
    FAILED: "不合格",
    CAUTION: "注意",
  };
  const u = (overall || "").toUpperCase();
  return map[u] || overall || "-";
}

function sourceJa(src) {
  const map = {
    wmi: "WMI",
    smartctl: "smartctl",
    storage_reliability: "Windows信頼性",
    none: "未取得",
  };
  return map[src] || src || "未取得";
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderSmartTable(table) {
  if (!table?.length) {
    return `<p class="muted">属性テーブルなし（smartctl 未導入、または非対応ディスクの可能性）</p>`;
  }
  const body = table
    .map((r) => {
      const st = r.status || "OK";
      return `<tr class="status-${st}">
        <td>${escapeHtml(r.id || "-")}</td>
        <td>${escapeHtml(r.label_ja || r.name || "-")}</td>
        <td>${escapeHtml(r.name || "-")}</td>
        <td>${r.current ?? "-"}</td>
        <td>${r.worst ?? "-"}</td>
        <td>${r.threshold ?? "-"}</td>
        <td>${escapeHtml(r.raw ?? "-")}</td>
        <td class="st-${st}">${st}</td>
      </tr>`;
    })
    .join("");
  return `<div class="smart-table-wrap"><table class="smart-table">
    <thead><tr>
      <th>ID</th><th>項目（日本語）</th><th>Name</th>
      <th>Current</th><th>Worst</th><th>Thresh</th><th>Raw</th><th>状態</th>
    </tr></thead>
    <tbody>${body}</tbody>
  </table></div>`;
}

function renderDisks(disks, meta = {}) {
  const banner = $("#elevationBanner");
  if (banner) {
    const needs =
      meta.elevated === false &&
      (disks || []).some((d) => d.smart?.source === "none" || d.smart?.needs_elevation);
    if (needs) {
      banner.hidden = false;
      banner.innerHTML =
        "温度・通電時間などの SMART 詳細には<strong>管理者権限</strong>が必要です。" +
        ' トレイの「管理者として再起動」、または <a href="pchealth://elevate">ここをクリック</a> / 同梱の run_as_admin.bat で昇格起動してください。';
    } else {
      banner.hidden = true;
      banner.innerHTML = "";
    }
  }
  if (!disks?.length) {
    $("#disks").innerHTML = "<p class='muted'>ディスク情報なし</p>";
    return;
  }
  $("#disks").innerHTML = disks
    .map((d) => {
      const smart = d.smart || {};
      const meter = smart.health_meter || "Unknown";
      const temp = smart.temperature_c;
      const vols = (d.volumes || [])
        .map((v) => `${v.letter} 空き ${v.free_pct}% (${v.free_gb} GB / ${v.size_gb} GB)`)
        .join(" · ");
      const poh =
        smart.power_on_hours != null
          ? `${smart.power_on_hours} h（約 ${smart.power_on_days ?? "-"} 日 / ${smart.power_on_years ?? "-"} 年）`
          : "-";
      return `<div class="card" data-device="${d.device_id}">
        <div class="disk-head">
          <div class="health-meter ${diskMeterClass(d.risk_level)}" title="SMART健康: ${healthMeterLabel(meter)}">
            <span class="meter-label">${statusJa(d.risk_level)}</span>
          </div>
          <div>
            <div class="row" style="margin-bottom:6px"><strong style="font-size:16px">${escapeHtml(d.model)}</strong>${badge(d.risk_level)}</div>
            <div class="kv">
              <span>転送モード</span><strong>${escapeHtml(d.bus_type || "-")} / ${escapeHtml(d.media_type || "-")}</strong>
              <span>容量</span><strong>${d.size_gb ?? "-"} GB</strong>
              <span>シリアル</span><strong>${escapeHtml(smart.serial || d.serial || "-")}</strong>
              <span>ファームウェア</span><strong>${escapeHtml(smart.firmware || d.firmware || "-")}</strong>
              <span>OS Health</span><strong>${escapeHtml(d.health_status || "-")} / ${escapeHtml(d.operational_status || "-")}</strong>
              <span>SMART</span><strong>${escapeHtml(smartOverallJa(smart.overall))}（取得元: ${escapeHtml(sourceJa(smart.source))}）</strong>
              <span>通電時間</span><strong>${escapeHtml(poh)}</strong>
              <span>電源投入回数</span><strong>${smart.power_cycles ?? "-"}</strong>
              ${vols ? `<span>ボリューム</span><strong>${escapeHtml(vols)}</strong>` : ""}
            </div>
          </div>
          <div class="temp-pill ${tempClass(temp)}">${temp != null ? `${temp}°C` : "--°C"}</div>
        </div>
        ${(d.reasons || []).length ? `<ul class="reasons">${d.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>` : ""}
        ${smart.note ? `<p class="tiny">${escapeHtml(smart.note)}</p>` : ""}
        ${smart.source === "none" ? `<p class="tiny">ヒント: 管理者で起動すると WMI SMART が取りやすくなります。smartctl もあるとさらに詳細です。</p>` : ""}
        <details class="smart-details">
          <summary>SMART属性テーブルを開く（${(smart.attribute_table || []).length} 件）</summary>
          ${renderSmartTable(smart.attribute_table)}
        </details>
        <div class="muted" style="margin-top:10px">温度・空き容量の簡易履歴</div>
        <div class="spark" id="spark-${d.device_id}"></div>
        <div class="history" id="hist-${d.device_id}">履歴を読み込み中…</div>
      </div>`;
    })
    .join("");

  for (const d of disks) {
    loadHistory(d.device_id);
  }
}

async function loadHistory(deviceId) {
  const el = document.getElementById(`hist-${deviceId}`);
  const spark = document.getElementById(`spark-${deviceId}`);
  if (!el) return;
  try {
    const rows = await api(`/api/disks/${encodeURIComponent(deviceId)}/history`);
    if (!rows.length) {
      el.textContent = "履歴はまだありません。";
      if (spark) spark.innerHTML = "";
      return;
    }
    el.textContent = rows
      .slice(-12)
      .map((r) => {
        const t = r.smart?.temperature_c;
        return `${fmtTime(r.created_at)}  ${statusJa(r.risk_level)}  空き=${r.free_pct ?? "-"}%  温度=${t ?? "-"}°C`;
      })
      .join("\n");
    if (spark) {
      const temps = rows.slice(-24).map((r) => r.smart?.temperature_c).filter((v) => v != null);
      if (!temps.length) {
        spark.innerHTML = "<span class='muted' style='font-size:12px'>温度履歴なし</span>";
      } else {
        const max = Math.max(...temps, 1);
        spark.innerHTML = temps
          .map((t) => `<i title="${t}°C" style="height:${Math.max(4, Math.round((t / max) * 36))}px"></i>`)
          .join("");
      }
    }
  } catch {
    el.textContent = "履歴の取得に失敗しました。";
  }
}

function renderRecommendations(list) {
  if (!list?.length) {
    $("#recommendations").innerHTML =
      "<div class='card'><p class='muted'>現在、交換提案はありません。「注意 / 要交換 / 危険」が出るとここに候補が出ます。</p></div>";
    return;
  }
  $("#recommendations").innerHTML = list
    .map((r) => {
      const links = (r.candidates || [])
        .map(
          (c) =>
            `<a href="${escapeHtml(c.url || "#")}" target="_blank" rel="noopener noreferrer"><strong>${escapeHtml(c.source || "")}</strong> — ${escapeHtml(c.title || "")}<br/><span class="muted">${escapeHtml(c.condition || "")} / ${escapeHtml(c.price_hint || "")}</span></a>`
        )
        .join("");
      return `<div class="card">
        <div class="row"><strong>${escapeHtml(r.for_model || "対象不明")}</strong>${badge(r.risk_level)}</div>
        <p class="muted">検索語: ${escapeHtml(r.query || "")}</p>
        <p>${escapeHtml(r.price_band || "")}</p>
        <ul class="reasons">${(r.notes || []).map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>
        <div class="links">${links}</div>
        <p class="muted">${escapeHtml(r.disclaimer || "")}</p>
      </div>`;
    })
    .join("");
}

async function renderAlerts() {
  try {
    const alerts = await api("/api/alerts");
    if (!alerts.length) {
      $("#alerts").innerHTML = "<div class='card'><p class='muted'>アラート履歴はまだありません。</p></div>";
      return;
    }
    $("#alerts").innerHTML = alerts
      .slice(0, 12)
      .map(
        (a) => `<div class="card"><div class="row"><strong>${escapeHtml(a.title || "")}</strong>${badge(a.level)}</div>
        <p class="muted">${escapeHtml(fmtTime(a.created_at))} — ${escapeHtml(a.message || "")}</p></div>`
      )
      .join("");
  } catch {
    $("#alerts").innerHTML = "<p class='muted'>アラート取得失敗</p>";
  }
}

const CAPACITY_OPTIONS = [0.5, 1, 2, 4, 8, 16];

function nearestCapacityOption(tb) {
  const n = Number(tb);
  if (!Number.isFinite(n)) return "2";
  let best = CAPACITY_OPTIONS[0];
  let bestDiff = Math.abs(n - best);
  for (const opt of CAPACITY_OPTIONS) {
    const d = Math.abs(n - opt);
    if (d < bestDiff) {
      best = opt;
      bestDiff = d;
    }
  }
  return String(best);
}

function fillSettings(s) {
  const form = $("#settingsForm");
  for (const [k, v] of Object.entries(s)) {
    const el = form.elements.namedItem(k);
    if (!el) continue;
    if (el.type === "checkbox") el.checked = Boolean(v);
    else if (k === "capacity_preference_tb") el.value = nearestCapacityOption(v);
    else if (k === "daily_scan_time") {
      const raw = String(v || "09:00");
      const m = raw.match(/^(\d{1,2}):(\d{2})/);
      el.value = m ? `${String(Number(m[1])).padStart(2, "0")}:${m[2]}` : "09:00";
    } else el.value = v;
  }
}

async function renderNews(force = false) {
  const el = $("#news");
  if (!el) return;
  el.innerHTML = "<div class='card'><p class='tiny'>ニュースを読み込み中…</p></div>";
  try {
    const data = await api(`/api/news${force ? "?force=true" : ""}`);
    const items = data.items || [];
    if (!items.length) {
      const errs = (data.errors || []).join(" / ");
      el.innerHTML = `<div class="card"><p class="tiny">ニュースを取得できませんでした。${errs ? `<br/>${escapeHtml(errs)}` : ""}</p></div>`;
      return;
    }
    el.innerHTML = items
      .map((n) => {
        let when = n.published || "";
        if (n.published_ts) {
          try {
            when = new Date(n.published_ts * 1000).toLocaleString("ja-JP");
          } catch {}
        }
        const img = n.image
          ? `<a class="news-thumb" href="${escapeHtml(n.url)}" target="_blank" rel="noopener noreferrer"><img src="${escapeHtml(n.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" /></a>`
          : `<div class="news-thumb placeholder" aria-hidden="true"></div>`;
        return `<article class="card news-card">
          ${img}
          <div class="news-body">
            <div class="news-meta"><span>${escapeHtml(n.source || "")}</span><span>${escapeHtml(when)}</span></div>
            <h3><a href="${escapeHtml(n.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(n.title)}</a></h3>
            ${n.summary ? `<p>${escapeHtml(n.summary)}</p>` : ""}
          </div>
        </article>`;
      })
      .join("");
  } catch (e) {
    el.innerHTML = `<div class="card"><p class="tiny">取得エラー: ${escapeHtml(e.message || e)}</p></div>`;
  }
}

async function loadAll() {
  const data = await api("/api/status");
  $("#overall").innerHTML = `${badge(data.overall_status)} <span>${statusJa(data.overall_status)}</span>`;
  const hint = {
    OK: "いまのところ大きな問題は見当たりません。",
    Watch: "様子を見た方がよい項目があります。",
    ReplaceSoon: "交換を検討した方がよいドライブがあります。",
    Critical: "すぐに確認・バックアップを検討してください。",
  };
  const heroHint = $("#heroHint");
  if (heroHint) heroHint.textContent = hint[data.overall_status] || "ディスクと空き容量を見守っています。";
  $("#scannedAt").textContent = data.scanned_at
    ? `最終スキャン ${fmtTime(data.scanned_at)}`
    : data.message || "";
  renderInventory(data.inventory);
  renderIssues(data);
  renderDisks(data.disks || [], {
    elevated: data.elevated,
    smartctl_available: data.smartctl_available,
  });
  renderRecommendations(data.recommendations || []);
  await renderAlerts();
  // Prefetch news quietly (cached)
  renderNews(false);
}

async function renderPrices() {
  const catalogEl = $("#priceCatalog");
  const overviewEl = $("#priceOverview");
  const orphanEl = $("#orphanBox");
  const metaEl = $("#priceMeta");
  if (!catalogEl) return;
  try {
    const state = await api("/api/prices");
    const tracked = new Set(state.tracked_ids || []);
    (state.legacy_items || []).forEach((x) => tracked.add(x.id));

    if (metaEl) {
      const last = state.last_price_fetch ? fmtTime(state.last_price_fetch) : "未取得";
      metaEl.textContent = `カタログ ${state.catalog_version} / 最終価格取得 ${last}`;
    }

    // Orphans dialog
    if (orphanEl) {
      const orphans = state.orphans || [];
      if (!orphans.length) {
        orphanEl.hidden = true;
        orphanEl.innerHTML = "";
      } else {
        orphanEl.hidden = false;
        orphanEl.innerHTML = `<h3>世代更新でリスト外になったパーツ</h3>
          <p class="tiny">残す（キープ）か、トラッキングから外すか選んでください。</p>
          ${orphans
            .map(
              (o) => `<div class="orphan-item" data-id="${escapeHtml(o.id)}">
              <div><strong>${escapeHtml(o.name)}</strong><span class="gen">${escapeHtml(o.generation || "")}</span></div>
              <div class="btns">
                <button type="button" class="btn-ghost" data-act="keep">残す</button>
                <button type="button" class="btn-ghost" data-act="drop">外す</button>
              </div>
            </div>`
            )
            .join("")}
          <button type="button" id="btnOrphanApply" class="btn-primary" style="margin-top:12px">決定を反映</button>`;
        const decisions = {};
        orphanEl.querySelectorAll(".orphan-item").forEach((row) => {
          row.querySelectorAll("button[data-act]").forEach((btn) => {
            btn.addEventListener("click", () => {
              decisions[row.dataset.id] = btn.dataset.act;
              row.querySelectorAll("button[data-act]").forEach((b) => (b.style.outline = ""));
              btn.style.outline = "2px solid #0071e3";
            });
          });
        });
        const apply = $("#btnOrphanApply");
        if (apply) {
          apply.onclick = async () => {
            await api("/api/prices/orphans", {
              method: "POST",
              body: JSON.stringify({ decisions }),
            });
            await renderPrices();
          };
        }
      }
    }

    // Overview of tracked prices (grid + collapsible by category)
    const overview = state.overview || [];
    if (!overview.length) {
      overviewEl.innerHTML = `<div class="card"><p class="tiny">まだトラッキング対象がありません。下のリストから複数選択して保存してください。</p></div>`;
      overviewEl.className = "price-overview";
    } else {
      overviewEl.className = "price-overview";
      const groups = groupOverviewByCategory(overview);
      overviewEl.innerHTML = groups
        .map(
          (g, gi) => `<details class="price-overview-group"${gi === 0 ? " open" : ""}>
          <summary class="price-overview-summary">
            <h3>${escapeHtml(g.label)}</h3>
            <span class="fold-hint">${g.items.length} 件</span>
            <span class="chevron" aria-hidden="true"></span>
          </summary>
          <div class="price-overview-grid">${g.items.map((p) => renderPriceOverviewCard(p)).join("")}</div>
        </details>`
        )
        .join("");
    }

    // Catalog multi-select (category → brand, both collapsible)
    catalogEl.innerHTML = (state.groups || [])
      .map((g) => {
        const brandBlocks = (g.brands || [{ brand: "", label: "", items: g.items || [] }])
          .map((b, bi) => {
            const checks = (b.items || [])
              .map((it) => {
                const checked = tracked.has(it.id) ? "checked" : "";
                return `<label><input type="checkbox" name="part" value="${escapeHtml(it.id)}" ${checked} />
                  <span><strong>${escapeHtml(it.name)}</strong><span class="gen">${escapeHtml(it.generation)} · ${escapeHtml(it.tier || "")}</span></span></label>`;
              })
              .join("");
            const brandName = b.label || b.brand || "その他";
            const openAttr = bi === 0 ? " open" : "";
            return `<details class="price-brand"${openAttr}>
              <summary class="price-brand-summary">
                <span class="price-brand-name">${escapeHtml(brandName)}</span>
                <span class="fold-hint">${(b.items || []).length} 件</span>
                <span class="chevron" aria-hidden="true"></span>
              </summary>
              <div class="price-checks">${checks}</div>
            </details>`;
          })
          .join("");
        return `<details class="price-group"${g === (state.groups || [])[0] ? " open" : ""}>
          <summary class="price-group-summary">
            <h3>${escapeHtml(g.label)}</h3>
            <span class="fold-hint">クリックで開閉</span>
            <span class="chevron" aria-hidden="true"></span>
          </summary>
          <div class="price-group-body">${brandBlocks}</div>
        </details>`;
      })
      .join("");

    // Legacy keep section
    if ((state.legacy_items || []).length) {
      catalogEl.innerHTML += `<details class="price-group" open>
        <summary class="price-group-summary">
          <h3>旧世代キープ中</h3>
          <span class="fold-hint">クリックで開閉</span>
          <span class="chevron" aria-hidden="true"></span>
        </summary>
        <div class="price-group-body"><div class="price-checks">${(
        state.legacy_items || []
      )
        .map(
          (it) =>
            `<label><input type="checkbox" name="part" value="${escapeHtml(it.id)}" checked />
            <span><strong>${escapeHtml(it.name)}</strong><span class="gen">リスト外だが継続トラッキング</span></span></label>`
        )
        .join("")}</div></div>
      </details>`;
    }
  } catch (e) {
    overviewEl.innerHTML = `<div class="card"><p class="tiny">読み込み失敗: ${escapeHtml(e.message || e)}</p></div>`;
  }
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "news") renderNews(false);
    if (btn.dataset.tab === "prices") renderPrices();
  });
});

$("#btnScan").addEventListener("click", async () => {
  $("#btnScan").disabled = true;
  $("#btnScan").textContent = "スキャン中…";
  try {
    await api("/api/scan", { method: "POST" });
    await loadAll();
  } catch (e) {
    alert("スキャン失敗: " + e.message);
  } finally {
    $("#btnScan").disabled = false;
    $("#btnScan").textContent = "今すぐスキャン";
  }
});

const btnNews = $("#btnNewsRefresh");
if (btnNews) {
  btnNews.addEventListener("click", async () => {
    btnNews.disabled = true;
    btnNews.textContent = "取得中…";
    try {
      await renderNews(true);
    } finally {
      btnNews.disabled = false;
      btnNews.textContent = "最新を取得";
    }
  });
}

const btnPriceSave = $("#btnPriceSave");
if (btnPriceSave) {
  btnPriceSave.addEventListener("click", async () => {
    const ids = [...document.querySelectorAll('#priceCatalog input[name="part"]:checked')].map(
      (el) => el.value
    );
    btnPriceSave.disabled = true;
    try {
      await api("/api/prices/tracked", { method: "PUT", body: JSON.stringify({ ids }) });
      await renderPrices();
    } catch (e) {
      alert("保存失敗: " + e.message);
    } finally {
      btnPriceSave.disabled = false;
    }
  });
}

const btnPriceRefresh = $("#btnPriceRefresh");
if (btnPriceRefresh) {
  btnPriceRefresh.addEventListener("click", async () => {
    btnPriceRefresh.disabled = true;
    btnPriceRefresh.textContent = "更新中…";
    try {
      await api("/api/prices/refresh?force=true", { method: "POST" });
      await renderPrices();
    } catch (e) {
      alert("価格更新失敗: " + e.message);
    } finally {
      btnPriceRefresh.disabled = false;
      btnPriceRefresh.textContent = "今すぐ価格更新";
    }
  });
}

$("#settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const body = {
    notify_enabled: form.notify_enabled.checked,
    capacity_warn_pct: Number(form.capacity_warn_pct.value),
    capacity_critical_pct: Number(form.capacity_critical_pct.value),
    budget_max_yen: Number(form.budget_max_yen.value),
    prefer_new_used: form.prefer_new_used.value,
    prefer_media: form.prefer_media.value,
    capacity_preference_tb: Number(form.capacity_preference_tb.value),
    priority: form.priority.value,
    daily_scan_time: form.daily_scan_time.value,
    startup_enabled: form.startup_enabled.checked,
  };
  try {
    const saved = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
    fillSettings(saved);
    $("#settingsMsg").textContent = "保存しました。起動時に1回スキャンし、以降は毎日この時刻に自動スキャンします（アプリ常駐中）。";
  } catch (err) {
    $("#settingsMsg").textContent = "保存失敗: " + err.message;
  }
});

(async () => {
  try {
    const settings = await api("/api/settings");
    fillSettings(settings);
    await loadAll();
    try {
      const about = await api("/api/about");
      const el = $("#aboutBody");
      if (el) {
          const elev = about.elevated
            ? "管理者権限: あり（SMART詳細を取得できます）"
            : "管理者権限: なし — 温度などはトレイの「管理者として再起動」が必要です";
          el.innerHTML = `
          <p><strong>${escapeHtml(about.name)}</strong> v${escapeHtml(about.version)}</p>
          <p>作成: ${escapeHtml(about.author || "—")}</p>
          ${about.homepage ? `<p>HP: <a href="${escapeHtml(about.homepage)}" target="_blank" rel="noopener noreferrer">${escapeHtml(about.homepage)}</a></p>` : ""}
          ${about.contact ? `<p>連絡先: ${escapeHtml(about.contact)}</p>` : ""}
          <p style="margin-top:8px">${escapeHtml(elev)}</p>
          ${
            about.elevated
              ? ""
              : `<p><a href="pchealth://elevate">管理者として再起動</a></p>`
          }
          <p style="margin-top:8px">ローカル専用アプリです。データは PC 外に送信しません。</p>`;
      }
    } catch {}
  } catch (e) {
    $("#overall").textContent = "接続エラー";
    $("#scannedAt").textContent = String(e.message || e);
  }
})();
