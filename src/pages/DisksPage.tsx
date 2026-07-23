import { useEffect, useState } from 'react'
import { getStatus } from '../api'
import { formatGb, formatPct, statusJa } from '../lib/format'
import type { DiskInfo, DiskSmartInfo, SmartAttributeRow, StatusPayload, VolumeInfo } from '../types'

interface Props {
  onOpenSpace: (letter?: string | null) => void
  showToast: (message: string) => void
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/\s+/g, '')
}

function dash(value: unknown): string {
  if (value === null || value === undefined || value === '') return '----'
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

function DiskCard({
  disk,
  onOpenSpace,
}: {
  disk: DiskInfo
  onOpenSpace: (letter?: string | null) => void
}) {
  const [showSerial, setShowSerial] = useState(false)
  const smart = disk.smart || {}
  const table = smart.attribute_table || []
  const temp = smart.temperature_c
  const letters = (disk.volumes || [])
    .map((v) => v.letter)
    .filter(Boolean)
    .join(' ')
  const meter = healthMeterJa(smart.health_meter, disk.risk_level)
  const meterClass = statusClass(String(disk.risk_level || smart.health_meter || 'Unknown'))

  const rows: Array<[string, string]> = [
    ['ファームウェア', dash(disk.firmware || smart.firmware)],
    [
      'シリアル番号',
      showSerial ? dash(disk.serial || smart.serial) : maskSerial(disk.serial || smart.serial),
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
    ['対応機能', dash(disk.features_text || smart.features_text || (disk.features || smart.features)?.join(', '))],
    [
      'バッファサイズ',
      disk.buffer_size_kb != null || smart.buffer_size_kb != null
        ? `${disk.buffer_size_kb ?? smart.buffer_size_kb} KB`
        : '----',
    ],
    ['NVキャッシュ', dash(disk.nv_cache_size || smart.nv_cache_size)],
    ['回転数', dash(disk.rotation_label || smart.rotation_label || (disk.rotation_rate != null ? `${disk.rotation_rate} rpm` : null))],
    ['電源投入回数', smart.power_cycles != null ? `${smart.power_cycles} 回` : '----'],
    ['使用時間', formatPoh(smart)],
  ]

  return (
    <article className="disk-crystal">
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
            {disk.media_type || 'メディア不明'}
            {disk.form_factor || smart.form_factor ? ` / ${disk.form_factor || smart.form_factor}` : ''}
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

      <details className="smart-details">
        <summary>S.M.A.R.T. 情報（{table.length} 件）</summary>
        {table.length === 0 ? (
          <p className="muted" style={{ marginTop: 10 }}>
            属性テーブルなし（smartctl 未導入、または権限不足の可能性）
          </p>
        ) : (
          <div className="smart-table-wrap">
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
                {table.map((row: SmartAttributeRow, idx: number) => {
                  const id =
                    row.id != null
                      ? String(row.id).match(/^\d+$/)
                        ? Number(row.id).toString(16).toUpperCase().padStart(2, '0')
                        : String(row.id)
                      : '—'
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
        )}
      </details>

      <div className="disk-crystal-actions">
        {(disk.volumes || [])
          .map((v) => v.letter)
          .filter(Boolean)
          .map((letter) => (
            <button key={letter} type="button" className="btn ghost" onClick={() => onOpenSpace(letter)}>
              {letter}:のマッピングを作成
            </button>
          ))}
      </div>
    </article>
  )
}

export function DisksPage({ onOpenSpace, showToast }: Props) {
  const [status, setStatus] = useState<StatusPayload | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const st = await getStatus()
        if (!cancelled) setStatus(st)
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err)
          showToast(`ディスク情報の取得に失敗: ${message}`)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [showToast])

  const disks = status?.disks || []
  const volumes = status?.volumes || []

  if (loading) {
    return (
      <div className="page">
        <div className="panel muted">読み込み中…</div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>ディスク</h2>
        <p>CrystalDiskInfo 相当の識別情報と S.M.A.R.T. 属性を確認できます。</p>
      </div>

      <section className="panel">
        <h3>物理ディスク</h3>
        {disks.length === 0 ? (
          <p className="muted" style={{ marginTop: 10 }}>
            ディスク情報がありません。上部の「今すぐスキャン」を試してください。
          </p>
        ) : (
          <div className="stack" style={{ marginTop: 12, gap: 16 }}>
            {disks.map((disk: DiskInfo) => (
              <DiskCard key={disk.device_id || disk.model} disk={disk} onOpenSpace={onOpenSpace} />
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h3>ボリューム（空き容量）</h3>
        {volumes.length === 0 ? (
          <p className="muted" style={{ marginTop: 10 }}>
            ボリューム情報がありません。
          </p>
        ) : (
          <div className="stack" style={{ marginTop: 8 }}>
            {volumes.map((vol: VolumeInfo) => (
              <div className="list-row" key={vol.letter || vol.label}>
                <div>
                  <strong>
                    {vol.letter || '?'} {vol.label ? `（${vol.label}）` : ''}
                  </strong>
                  <p className="muted" style={{ margin: '6px 0 0' }}>
                    空き {formatGb(vol.free_gb)} / 全体 {formatGb(vol.size_gb)}（
                    {formatPct(vol.free_pct)}）
                    {vol.file_system ? ` / ${vol.file_system}` : ''}
                  </p>
                </div>
                {vol.letter && (
                  <button type="button" className="btn ghost" onClick={() => onOpenSpace(vol.letter)}>
                    容量マップを開く
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
