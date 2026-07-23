import { useEffect, useState } from 'react'
import { getRecommendations } from '../api'
import { statusJa } from '../lib/format'
import type { Recommendation } from '../types'

interface Props {
  showToast: (message: string) => void
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/\s+/g, '')
}

export function RecommendationsPage({ showToast }: Props) {
  const [items, setItems] = useState<Recommendation[]>([])
  const [scannedAt, setScannedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const data = await getRecommendations()
        if (cancelled) return
        setItems(data.recommendations || [])
        setScannedAt(data.scanned_at ?? null)
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err)
          showToast(`提案の取得に失敗: ${message}`)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [showToast])

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
        <h2>提案</h2>
        <p>
          交換・増設の候補検索リンクです。自動購入はしません。
          {scannedAt ? `（${new Date(scannedAt).toLocaleString('ja-JP')} 時点）` : ''}
        </p>
      </div>

      {items.length === 0 ? (
        <section className="panel">
          <p className="muted" style={{ margin: 0 }}>
            いま提案はありません。ディスクや容量に問題が出るとここに表示されます。
          </p>
        </section>
      ) : (
        items.map((rec) => (
          <section className="panel" key={`${rec.for_device_id}-${rec.query}`}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <h3 style={{ margin: 0 }}>{rec.for_model || rec.query}</h3>
              {rec.risk_level && (
                <span className={`status-pill ${statusClass(rec.risk_level)}`}>
                  {statusJa(rec.risk_level)}
                </span>
              )}
            </div>
            <p className="muted" style={{ marginTop: 8 }}>
              検索語: {rec.query}
            </p>
            {rec.price_band && (
              <p className="muted" style={{ marginTop: 4 }}>
                {rec.price_band}
              </p>
            )}
            {(rec.notes || []).length > 0 && (
              <ul className="muted" style={{ marginTop: 8, paddingLeft: 18 }}>
                {(rec.notes || []).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
            <div className="stack" style={{ marginTop: 12 }}>
              {(rec.candidates || []).map((link) => (
                <div className="list-row" key={link.url}>
                  <div>
                    <strong>{link.title}</strong>
                    <p className="muted" style={{ margin: '4px 0 0' }}>
                      {link.source}
                      {link.condition ? ` · ${link.condition}` : ''}
                      {link.price_hint ? ` · ${link.price_hint}` : ''}
                    </p>
                  </div>
                  <a className="btn ghost" href={link.url} target="_blank" rel="noreferrer">
                    開く
                  </a>
                </div>
              ))}
            </div>
            {rec.disclaimer && (
              <p className="muted" style={{ marginTop: 12 }}>
                {rec.disclaimer}
              </p>
            )}
          </section>
        ))
      )}
    </div>
  )
}
