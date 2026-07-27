import { useEffect, useState } from 'react'
import { getStatus } from '../api'
import { DiskDetailView } from '../components/DiskDetailView'
import { formatGb, formatPct } from '../lib/format'
import type { DiskInfo, StatusPayload, VolumeInfo } from '../types'

interface Props {
  onOpenSpace: (letter?: string | null) => void
  showToast: (message: string) => void
}

async function openDiskDetailWindow(deviceId: string, showToast: (m: string) => void) {
  const api = window.desktopApi
  if (api?.openDiskDetail) {
    try {
      const ok = await api.openDiskDetail(deviceId)
      if (!ok) showToast('詳細ウィンドウを開けませんでした')
      return
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`詳細ウィンドウの起動に失敗: ${message}`)
      return
    }
  }
  // Electron 以外（ブラウザ確認用）は別タブ
  const url = `${window.location.origin}${window.location.pathname}?view=disk&id=${encodeURIComponent(deviceId)}`
  window.open(url, `disk-${deviceId}`, 'width=980,height=780')
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
        <p>
          一覧は要約だけ。SMART の全項目は「詳細ウィンドウで開く」から CrystalDiskInfo 風に確認できます。
        </p>
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
              <DiskDetailView
                key={disk.device_id || disk.model}
                disk={disk}
                variant="card"
                onOpenSpace={onOpenSpace}
                onOpenWindow={() => {
                  const id = disk.device_id
                  if (!id) {
                    showToast('このディスクは詳細ウィンドウ用の ID がありません')
                    return
                  }
                  void openDiskDetailWindow(String(id), showToast)
                }}
              />
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
