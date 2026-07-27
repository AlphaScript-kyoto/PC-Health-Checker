import { useState, type ReactNode } from 'react'
import { statusJa } from '../lib/format'
import type { DiskInfo, DiskSmartInfo, SmartAttributeRow } from '../types'

function statusClass(status: string): string {
  return status.toLowerCase().replace(/\s+/g, '')
}

export function dash(value: unknown): string {
  if (value === null || value === undefined || value === '') return '----'
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    for (const key of ['name', 'string', 'ascii', 'value', 'label']) {
      if (obj[key] != null && obj[key] !== '') return String(obj[key])
    }
    return '----'
  }
  return String(value)
}

function maskSerial(serial?: string | null): string {
  if (!serial) return '----'
  if (serial.length <= 4) return '*'.repeat(serial.length)
  return '*'.repeat(Math.max(8, serial.length - 4)) + serial.slice(-4)
}

function formatPoh(smart?: DiskSmartInfo): string {
  if (smart?.power_on_hours == null) return '----'
  const h = smart.power_on_hours
  const days = smart.power_on_days ?? Math.round(h / 24)
  const years = smart.power_on_years ?? Math.round((h / 24 / 365) * 10) / 10
  return `${h} 時間（約 ${days} 日 / ${years} 年）`
}

function healthMeterJa(meter?: string, risk?: string): string {
  const m = (meter || '').toLowerCase()
  if (m === 'good') return '正常'
  if (m === 'caution') return '注意'
  if (m === 'bad') return '異常'
  return statusJa(String(risk || 'Unknown'))
}

function attrStatusClass(status?: string): string {
  const s = (status || 'OK').toUpperCase()
  if (s === 'FAIL' || s === 'BAD') return 'is-bad'
  if (s === 'WARN' || s === 'CAUTION') return 'is-warn'
  return 'is-ok'
}

function formatAttrId(row: SmartAttributeRow): string {
  if (row.id == null) return '—'
  const raw = String(row.id)
  if (/^\d+$/.test(raw)) return Number(raw).toString(16).toUpperCase().padStart(2, '0')
  return raw
}

export function buildDiskInfoRows(
  disk: DiskInfo,
  smart: DiskSmartInfo,
  opts: { showSerial: boolean },
): Array<[string, string]> {
  const letters = (disk.volumes || [])
    .map((v) => v.letter)
    .filter(Boolean)
    .join(' ')
  return [
    ['ファームウェア', dash(disk.firmware || smart.firmware)],
    [
      'シリアル番号',
      opts.showSerial ? dash(disk.serial || smart.serial) : maskSerial(disk.serial || smart.serial),
    ],
    ['インターフェース', dash(disk.interface || smart.interface || disk.interface_type || disk.bus_type)],
    ['転送モード', dash(disk.transfer_mode || smart.transfer_mode)],
    ['ドライブ文字', letters || '----'],
    [
      '対応規格',
      [disk.ata_standard || smart.ata_standard, disk.sata_version || smart.sata_version]
        .filter(Boolean)
        .join(' | ') || '----',
    ],
    [
      '対応機能',
      dash(disk.features_text || smart.features_text || (disk.features || smart.features)?.join(', ')),
    ],
    [
      'バッファサイズ',
      (() => {
        const kb = disk.buffer_size_kb ?? smart.buffer_size_kb
        if (kb == null) return '----'
        const src = disk.buffer_size_source || smart.buffer_size_source
        return src === 'model_db' ? `${kb} KB（公称値）` : `${kb} KB`
      })(),
    ],
    ['NVキャッシュ', dash(disk.nv_cache_size || smart.nv_cache_size)],
    [
      '回転数',
      dash(
        disk.rotation_label ||
          smart.rotation_label ||
          (disk.rotation_rate != null ? `${disk.rotation_rate} rpm` : null),
      ),
    ],
    [
      '総書込み量（ホスト）',
      smart.host_writes_gb != null ? `${smart.host_writes_gb} GB` : '----',
    ],
    ['電源投入回数', smart.power_cycles != null ? `${smart.power_cycles} 回` : '----'],
    ['使用時間', formatPoh(smart)],
  ]
}

export function SmartAttributeTable({ table }: { table: SmartAttributeRow[] }) {
  if (table.length === 0) {
    return (
      <p className="muted" style={{ marginTop: 10 }}>
        属性テーブルなし（smartctl 未導入、または権限不足の可能性）
      </p>
    )
  }
  return (
    <div className="smart-table-wrap smart-table-wrap-fill">
      <table className="smart-table">
        <thead>
          <tr>
            <th></th>
            <th>ID</th>
            <th>項目名</th>
            <th>現在値</th>
            <th>最悪値</th>
            <th>しきい値</th>
            <th>生の値</th>
          </tr>
        </thead>
        <tbody>
          {table.map((row, idx) => {
            const id = formatAttrId(row)
            return (
              <tr key={`${id}-${row.name || idx}`} className={attrStatusClass(row.status)}>
                <td>
                  <span className={`smart-dot ${attrStatusClass(row.status)}`} title={row.status || 'OK'} />
                </td>
                <td>{id}</td>
                <td>{row.label_ja || row.name || '—'}</td>
                <td>{row.current ?? '—'}</td>
                <td>{row.worst ?? '—'}</td>
                <td>{row.threshold ?? '—'}</td>
                <td className="smart-raw">{row.raw ?? '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

interface DiskDetailViewProps {
  disk: DiskInfo
  variant?: 'card' | 'window'
  onOpenSpace?: (letter?: string | null) => void
  onOpenWindow?: () => void
  footer?: ReactNode
}

export function DiskDetailView({
  disk,
  variant = 'card',
  onOpenSpace,
  onOpenWindow,
  footer,
}: DiskDetailViewProps) {
  const [showSerial, setShowSerial] = useState(false)
  const smart = disk.smart || {}
  const table = smart.attribute_table || []
  const temp = smart.temperature_c
  const meter = healthMeterJa(smart.health_meter, disk.risk_level)
  const meterClass = statusClass(String(disk.risk_level || smart.health_meter || 'Unknown'))
  const rows = buildDiskInfoRows(disk, smart, { showSerial })
  const isWindow = variant === 'window'

  return (
    <article className={`disk-crystal ${isWindow ? 'disk-crystal-window' : ''}`}>
      <header className="disk-crystal-head">
        <div className={`disk-health-badge ${meterClass}`} title={`SMART: ${dash(smart.overall)}`}>
          <span>健康状態</span>
          <strong>{meter}</strong>
        </div>
        <div className="disk-crystal-title">
          <h4>
            {disk.model || '不明なディスク'}
            {disk.size_gb != null ? ` ${disk.size_gb} GB` : ''}
          </h4>
          <p className="muted">
            {dash(disk.media_type) !== '----' ? dash(disk.media_type) : 'メディア不明'}
            {dash(disk.form_factor || smart.form_factor) !== '----'
              ? ` / ${dash(disk.form_factor || smart.form_factor)}`
              : ''}
            {disk.health_status ? ` / OS: ${disk.health_status}` : ''}
            {smart.source ? ` / 取得元: ${smart.source}` : ''}
          </p>
        </div>
        <div className={`disk-temp-pill ${temp != null && temp >= 50 ? 'is-hot' : ''}`}>
          {temp != null ? `${temp} °C` : '-- °C'}
        </div>
      </header>

      <dl className="disk-kv-grid">
        {rows.map(([label, value]) => (
          <div key={label} className="disk-kv">
            <dt>{label}</dt>
            <dd>
              {label === 'シリアル番号' ? (
                <span className="disk-serial-row">
                  <code>{value}</code>
                  {(disk.serial || smart.serial) && (
                    <button
                      type="button"
                      className="btn ghost"
                      style={{ padding: '2px 8px', fontSize: 11 }}
                      onClick={() => setShowSerial((v) => !v)}
                    >
                      {showSerial ? '隠す' : '表示'}
                    </button>
                  )}
                </span>
              ) : (
                value
              )}
            </dd>
          </div>
        ))}
      </dl>

      {(disk.reasons || []).length > 0 && (
        <ul className="disk-reasons">
          {(disk.reasons || []).map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      {smart.note && <p className="muted disk-note">{smart.note}</p>}

      {isWindow ? (
        <section className="smart-window-section">
          <h3>S.M.A.R.T. 情報（{table.length} 件）</h3>
          <SmartAttributeTable table={table} />
        </section>
      ) : (
        <div className="disk-crystal-actions">
          {onOpenWindow && (
            <button type="button" className="btn primary" onClick={onOpenWindow}>
              詳細ウィンドウで開く
            </button>
          )}
          {(disk.volumes || [])
            .map((v) => v.letter)
            .filter(Boolean)
            .map((letter) => (
              <button
                key={letter}
                type="button"
                className="btn ghost"
                onClick={() => onOpenSpace?.(letter)}
              >
                {letter}:のマッピングを作成
              </button>
            ))}
        </div>
      )}

      {footer}
    </article>
  )
}
