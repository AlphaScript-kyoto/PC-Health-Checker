import { useEffect, useState } from 'react'
import { getAbout, getAlerts, getStatus } from '../api'
import { formatGb, formatPct, statusJa } from '../lib/format'
import type { AboutInfo, AlertItem, StatusPayload } from '../types'

interface Props {
  onOpenSpace: (letter?: string | null) => void
  onOpenRecommendations: () => void
  showToast: (message: string) => void
  /** Electron プロセス側の管理者判定（バックエンドより優先） */
  processElevated?: boolean
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/\s+/g, '')
}

export function HomePage({
  onOpenSpace,
  onOpenRecommendations,
  showToast,
  processElevated,
}: Props) {
  const [status, setStatus] = useState<StatusPayload | null>(null)
  const [about, setAbout] = useState<AboutInfo | null>(null)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const [st, ab, al] = await Promise.all([getStatus(), getAbout(), getAlerts()])
        if (cancelled) return
        setStatus(st)
        setAbout(ab)
        setAlerts(al.slice(0, 8))
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err)
          showToast(`ホーム情報の取得に失敗: ${message}`)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [showToast])

  const overall = status?.overall_status || 'Unknown'
  const inventory = status?.inventory || {}
  const volumeIssues = status?.volume_issues || []
  const smartBad =
    (status?.disks || []).some((d) =>
      ['Watch', 'ReplaceSoon', 'Critical'].includes(String(d.risk_level || '')),
    ) || (status?.replacement_targets || []).length > 0

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
        <h2>ホーム</h2>
        <p>いまのPCの健康状態をまとめて確認できます。</p>
      </div>

      <div className="grid-2">
        <section className="panel">
          <h3>総合ステータス</h3>
          <div className="stack" style={{ marginTop: 12 }}>
            <span className={`status-pill ${statusClass(String(overall))}`}>
              {statusJa(String(overall))}
            </span>
            <p className="muted" style={{ margin: 0 }}>
              {status?.scanned_at
                ? `最終スキャン: ${new Date(status.scanned_at).toLocaleString('ja-JP')}`
                : status?.message || 'まだスキャンされていません'}
            </p>
            {about && (
              <p className="muted" style={{ margin: 0 }}>
                {about.name} v{about.version}
                {(processElevated ?? about.elevated)
                  ? ' / 管理者権限あり'
                  : ' / 管理者権限なし'}
                {about.smartctl_available ? ' / smartctl 利用可' : ''}
              </p>
            )}
          </div>
        </section>

        <section className="panel">
          <h3>インベントリ</h3>
          <div className="stack" style={{ marginTop: 8 }}>
            <div className="list-row">
              <span>CPU</span>
              <strong>{String(inventory.cpu || '—')}</strong>
            </div>
            <div className="list-row">
              <span>メモリ</span>
              <strong>
                {inventory.memory_summary
                  ? String(inventory.memory_summary)
                  : inventory.ram_gb
                    ? `${inventory.ram_gb} GB`
                    : '—'}
              </strong>
            </div>
            <div className="list-row">
              <span>OS</span>
              <strong>{String(inventory.os || '—')}</strong>
            </div>
            <div className="list-row">
              <span>ホスト名</span>
              <strong>{String(inventory.hostname || '—')}</strong>
            </div>
          </div>
        </section>
      </div>

      {(volumeIssues.length > 0 || smartBad) && (
        <section className="panel">
          <h3>すぐに確認したいこと</h3>
          <div className="stack" style={{ marginTop: 10 }}>
            {volumeIssues.map((issue) => (
              <div className="list-row" key={`${issue.letter}-${issue.free_pct}`}>
                <div>
                  <strong>容量不足: {issue.letter}</strong>
                  <p className="muted" style={{ margin: '4px 0 0' }}>
                    空き {formatPct(issue.free_pct)}（{formatGb(issue.free_gb)}）
                  </p>
                </div>
                <button type="button" className="linkish" onClick={() => onOpenSpace(issue.letter)}>
                  容量マップへ
                </button>
              </div>
            ))}
            {smartBad && (
              <div className="list-row">
                <div>
                  <strong>ディスクの健全性に注意があります</strong>
                  <p className="muted" style={{ margin: '4px 0 0' }}>
                    SMART や摩耗、通電時間などから交換・対策の提案があります。
                  </p>
                </div>
                <button type="button" className="linkish" onClick={onOpenRecommendations}>
                  提案へ
                </button>
              </div>
            )}
          </div>
        </section>
      )}

      <section className="panel">
        <h3>最近のアラート</h3>
        {alerts.length === 0 ? (
          <p className="muted" style={{ marginTop: 10 }}>
            まだアラートはありません。
          </p>
        ) : (
          <div className="stack" style={{ marginTop: 8 }}>
            {alerts.map((alert, index) => (
              <div className="list-row" key={`${alert.id ?? index}-${alert.title}`}>
                <div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className={`status-pill ${statusClass(alert.level)}`}>
                      {statusJa(alert.level)}
                    </span>
                    <strong>{alert.title}</strong>
                  </div>
                  <p className="muted" style={{ margin: '6px 0 0' }}>
                    {alert.message}
                  </p>
                </div>
                {alert.kind === 'capacity' && (
                  <button
                    type="button"
                    className="linkish"
                    onClick={() => {
                      const match = alert.title.match(/([A-Z]):/i)
                      onOpenSpace(match?.[1] || null)
                    }}
                  >
                    容量マップ
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
