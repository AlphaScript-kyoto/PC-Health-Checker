import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ApiError,
  getDrives,
  getSpaceProgress,
  getSpaceResult,
  postSpaceScan,
} from '../api'
import { Treemap } from '../components/Treemap'
import { formatBytes, formatDuration, safetyLabel } from '../lib/format'
import type { DirNode, DriveInfo, ScanProgress, SpaceScanResult } from '../types'

interface Props {
  initialDrive?: string | null
  showToast: (message: string) => void
}

type Phase = 'idle' | 'scanning' | 'done' | 'error' | 'unavailable'

function normalizeLetter(value: string | null | undefined): string {
  return String(value || '')
    .replace(':', '')
    .trim()
    .toUpperCase()
}

export function SpacePage({ initialDrive, showToast }: Props) {
  const [drives, setDrives] = useState<DriveInfo[]>([])
  const [selectedDrive, setSelectedDrive] = useState<DriveInfo | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [progress, setProgress] = useState<ScanProgress | null>(null)
  const [result, setResult] = useState<SpaceScanResult | null>(null)
  const [selected, setSelected] = useState<DirNode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [apiMissing, setApiMissing] = useState(false)
  const pollRef = useRef<number | null>(null)

  const stopPolling = () => {
    if (pollRef.current != null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const list = await getDrives()
        if (cancelled) return
        setDrives(list)
        const want = normalizeLetter(initialDrive)
        const preferred =
          list.find((d) => d.letter === want) ||
          list.find((d) => d.letter === 'C') ||
          list[0] ||
          null
        setSelectedDrive(preferred)
        setApiMissing(false)
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
          setApiMissing(true)
          setPhase('unavailable')
          setError('容量マップ API がまだバックエンドにありません。後ほど利用できます。')
        } else {
          const message = err instanceof Error ? err.message : String(err)
          setError(message)
          setPhase('error')
          showToast(`ドライブ一覧の取得に失敗: ${message}`)
        }
      }
    })()
    return () => {
      cancelled = true
      stopPolling()
    }
  }, [initialDrive, showToast])

  useEffect(() => {
    if (!initialDrive || drives.length === 0) return
    const want = normalizeLetter(initialDrive)
    const found = drives.find((d) => d.letter === want)
    if (found) setSelectedDrive(found)
  }, [drives, initialDrive])

  const startScan = async () => {
    if (!selectedDrive || phase === 'scanning' || apiMissing) return
    setError(null)
    setResult(null)
    setSelected(null)
    setPhase('scanning')
    setProgress({
      scannedFiles: 0,
      scannedDirs: 0,
      currentPath: selectedDrive.rootPath,
      bytesSeen: 0,
      percent: 0,
    })
    showToast(`${selectedDrive.letter}: のスキャンを開始しました`)

    try {
      await postSpaceScan(selectedDrive.rootPath)
    } catch (err) {
      stopPolling()
      if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
        setApiMissing(true)
        setPhase('unavailable')
        setError('容量マップ API がまだバックエンドにありません。')
        showToast('容量スキャン API が未実装です')
        return
      }
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
      setPhase('error')
      showToast(`スキャン開始に失敗: ${message}`)
      return
    }

    stopPolling()
    pollRef.current = window.setInterval(() => {
      void (async () => {
        try {
          const prog = await getSpaceProgress()
          if (prog) setProgress(prog)

          const done = await getSpaceResult()
          if (done && done.root) {
            stopPolling()
            setResult(done)
            setSelected(done.root)
            setPhase('done')
            setProgress(null)
            showToast('容量スキャンが完了しました')
          }
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) {
            return
          }
          stopPolling()
          const message = err instanceof Error ? err.message : String(err)
          setError(message)
          setPhase('error')
        }
      })()
    }, 800)
  }

  const openPath = async (targetPath: string) => {
    const api = window.desktopApi
    if (!api?.openPath) {
      showToast('エクスプローラー連携は Electron 起動時のみ利用できます')
      return
    }
    showToast('エクスプローラーで開いています…')
    await api.openPath(targetPath)
  }

  const rootLabel = selectedDrive ? `${selectedDrive.letter}:` : 'ドライブ'
  const usedRatio = useMemo(() => {
    const disk = result?.disk || selectedDrive
    if (!disk || !disk.totalBytes) return 0
    return Math.min(100, (disk.usedBytes / disk.totalBytes) * 100)
  }, [result, selectedDrive])

  return (
    <div className="page">
      <div className="page-head">
        <h2>容量マップ</h2>
        <p>ドライブの中身を色分けして、削除候補を見つけやすくします（削除はしません）。</p>
      </div>

      {apiMissing || phase === 'unavailable' ? (
        <section className="panel">
          <h3>準備中の機能です</h3>
          <p className="muted" style={{ marginTop: 8 }}>
            {error ||
              'バックエンドに /api/drives と /api/space/* が追加されると、ここで容量マップが使えます。'}
          </p>
        </section>
      ) : (
        <>
          <section className="panel">
            <div style={{ marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>ドライブを選択</h3>
              <p className="muted" style={{ margin: '4px 0 0' }}>
                スキャンしたいドライブを選んでから開始してください。
              </p>
            </div>
            {drives.length === 0 ? (
              <p className="muted">接続ドライブが見つかりませんでした。</p>
            ) : (
              <div className="drive-grid">
                {drives.map((drive) => {
                  const active = selectedDrive?.letter === drive.letter
                  return (
                    <button
                      key={drive.letter}
                      type="button"
                      className={`drive-card ${active ? 'is-active' : ''}`}
                      disabled={phase === 'scanning'}
                      onClick={() => {
                        setSelectedDrive(drive)
                        if (result && result.rootPath !== drive.rootPath) {
                          setResult(null)
                          setSelected(null)
                          setPhase('idle')
                        }
                      }}
                    >
                      <strong>{drive.letter}:</strong>
                      <span>{drive.label || 'ローカルディスク'}</span>
                      <span>
                        空き {formatBytes(drive.freeBytes)} / {formatBytes(drive.totalBytes)}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn primary"
                disabled={!selectedDrive || phase === 'scanning'}
                onClick={() => void startScan()}
              >
                {phase === 'scanning' && <span className="btn-spinner" aria-hidden />}
                {selectedDrive ? `${selectedDrive.letter}: をスキャン` : 'スキャン'}
              </button>
            </div>

            {(selectedDrive || result) && (
              <div className="progress-block">
                <div
                  className="muted"
                  style={{ display: 'flex', justifyContent: 'space-between' }}
                >
                  <span>使用量</span>
                  <strong style={{ color: 'var(--ink)', fontFamily: 'var(--display)', fontSize: 22 }}>
                    {usedRatio.toFixed(1)}%
                  </strong>
                </div>
                <div className="progress-track" style={{ marginTop: 8 }}>
                  <i style={{ width: `${usedRatio}%` }} />
                </div>
              </div>
            )}

            {phase === 'scanning' && progress && (
              <p className="muted" style={{ marginTop: 10 }}>
                スキャン中… ファイル {progress.scannedFiles.toLocaleString('ja-JP')} / フォルダ{' '}
                {progress.scannedDirs.toLocaleString('ja-JP')}
                {progress.currentPath ? ` / ${progress.currentPath}` : ''}
              </p>
            )}

            {error && phase === 'error' && (
              <p className="muted" style={{ marginTop: 10, color: 'var(--danger)' }}>
                {error}
              </p>
            )}
          </section>

          {result && (
            <div className="space-layout">
              <Treemap
                root={result.root}
                rootLabel={rootLabel}
                selectedPath={selected?.path ?? null}
                onSelect={setSelected}
              />
              <section className="panel stack">
                <div>
                  <h3>選択中</h3>
                  {selected ? (
                    <>
                      <strong>{selected.name}</strong>
                      <p className="muted" style={{ margin: '6px 0 0' }}>
                        {formatBytes(selected.size)} / {safetyLabel(selected.safety)}
                      </p>
                      <p className="muted" style={{ margin: '6px 0 0' }}>
                        {selected.reason}
                      </p>
                      <button
                        type="button"
                        className="btn ghost"
                        style={{ marginTop: 10 }}
                        onClick={() => void openPath(selected.path)}
                      >
                        エクスプローラーで開く
                      </button>
                    </>
                  ) : (
                    <p className="muted">マップ上の項目をクリックしてください。</p>
                  )}
                </div>

                <div>
                  <h3>削除候補</h3>
                  <p className="muted" style={{ marginTop: 4 }}>
                    比較的安全そうな大きめフォルダです。自分で確認してから操作してください。
                  </p>
                  <div className="candidate-list" style={{ marginTop: 10 }}>
                    {(result.candidates || []).slice(0, 12).map((node) => (
                      <div className="candidate-item" key={node.path}>
                        <div>
                          <strong>{node.name}</strong>
                          <span>
                            {formatBytes(node.size)} · {safetyLabel(node.safety)}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="btn ghost"
                          onClick={() => void openPath(node.path)}
                        >
                          開く
                        </button>
                      </div>
                    ))}
                    {(result.candidates || []).length === 0 && (
                      <p className="muted">候補は見つかりませんでした。</p>
                    )}
                  </div>
                  <p className="muted" style={{ marginTop: 12 }}>
                    所要時間 {formatDuration(result.durationMs)} / スキップ{' '}
                    {result.skippedCount.toLocaleString('ja-JP')} 件
                  </p>
                </div>
              </section>
            </div>
          )}
        </>
      )}
    </div>
  )
}
