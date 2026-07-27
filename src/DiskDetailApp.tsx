import { useEffect, useState } from 'react'
import { getStatus } from './api'
import { DiskDetailView } from './components/DiskDetailView'
import type { DiskInfo } from './types'
import './App.css'

interface Props {
  deviceId: string
}

export function DiskDetailApp({ deviceId }: Props) {
  const [disk, setDisk] = useState<DiskInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const status = await getStatus()
        const found =
          (status.disks || []).find((d) => String(d.device_id) === String(deviceId)) || null
        if (!cancelled) {
          setDisk(found)
          setError(found ? null : '指定のディスクが見つかりません。メイン画面で再スキャンしてください。')
          if (found?.model) {
            document.title = `${found.model} — パソコンちぇっ君`
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [deviceId])

  if (loading) {
    return (
      <div className="disk-detail-shell">
        <div className="panel muted">読み込み中…</div>
      </div>
    )
  }

  if (error || !disk) {
    return (
      <div className="disk-detail-shell">
        <div className="panel">
          <h2>ディスク詳細</h2>
          <p className="muted">{error || 'ディスク情報がありません。'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="disk-detail-shell">
      <header className="disk-detail-top">
        <div>
          <p className="disk-detail-brand">パソコンちぇっ君 / ディスク詳細</p>
        </div>
        <button type="button" className="btn ghost" onClick={() => window.close()}>
          閉じる
        </button>
      </header>
      <DiskDetailView disk={disk} variant="window" />
    </div>
  )
}
