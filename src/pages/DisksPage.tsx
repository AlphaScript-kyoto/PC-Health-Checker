import { useEffect, useState } from 'react'
import { getStatus } from '../api'
import { formatGb, formatPct, statusJa } from '../lib/format'
import type { DiskInfo, StatusPayload, VolumeInfo } from '../types'

interface Props {
  onOpenSpace: (letter?: string | null) => void
  showToast: (message: string) => void
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/\s+/g, '')
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
        <p>SMART と空き容量を確認し、必要なら容量マップへ進めます。</p>
      </div>

      <section className="panel">
        <h3>物理ディスク</h3>
        {disks.length === 0 ? (
          <p className="muted" style={{ marginTop: 10 }}>
            ディスク情報がありません。上部の「今すぐスキャン」を試してください。
          </p>
        ) : (
          <div className="stack" style={{ marginTop: 8 }}>
            {disks.map((disk: DiskInfo) => (
              <div className="list-row" key={disk.device_id || disk.model}>
                <div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <strong>{disk.model || '不明なディスク'}</strong>
                    <span className={`status-pill ${statusClass(String(disk.risk_level || 'Unknown'))}`}>
                      {statusJa(String(disk.risk_level || 'Unknown'))}
                    </span>
                  </div>
                  <p className="muted" style={{ margin: '6px 0 0' }}>
                    {disk.media_type || 'メディア不明'}
                    {disk.size_gb != null ? ` / ${formatGb(disk.size_gb)}` : ''}
                    {disk.health_status ? ` / OS状態: ${disk.health_status}` : ''}
                    {disk.smart?.overall ? ` / SMART: ${disk.smart.overall}` : ''}
                    {disk.free_pct != null ? ` / 関連空き ${formatPct(disk.free_pct)}` : ''}
                  </p>
                  {(disk.reasons || []).length > 0 && (
                    <p className="muted" style={{ margin: '4px 0 0' }}>
                      {(disk.reasons || []).slice(0, 3).join(' / ')}
                    </p>
                  )}
                </div>
                <div className="stack" style={{ alignItems: 'flex-end' }}>
                  {(disk.volumes || [])
                    .map((v) => v.letter)
                    .filter(Boolean)
                    .map((letter) => (
                      <button
                        key={letter}
                        type="button"
                        className="btn ghost"
                        onClick={() => onOpenSpace(letter)}
                      >
                        {letter} 容量マップ
                      </button>
                    ))}
                </div>
              </div>
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
                  <button
                    type="button"
                    className="btn ghost"
                    onClick={() => onOpenSpace(vol.letter)}
                  >
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
