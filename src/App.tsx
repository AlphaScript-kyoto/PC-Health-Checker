import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getAbout,
  getScanProgress,
  getStatus,
  postScan,
  postScanPause,
  postScanRestart,
  postScanResume,
} from './api'
import { PageErrorBoundary } from './components/PageErrorBoundary'
import { Toast } from './components/Toast'
import { DisksPage } from './pages/DisksPage'
import { HomePage } from './pages/HomePage'
import { NewsPage } from './pages/NewsPage'
import { PricesPage } from './pages/PricesPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { SettingsPage } from './pages/SettingsPage'
import { SpacePage } from './pages/SpacePage'
import type { ScanProgressInfo, TabId } from './types'
import './App.css'

const TABS: { id: TabId; label: string }[] = [
  { id: 'home', label: 'ホーム' },
  { id: 'disks', label: 'ディスク' },
  { id: 'space', label: '容量マップ' },
  { id: 'recommendations', label: '提案' },
  { id: 'prices', label: '価格' },
  { id: 'news', label: 'ニュース' },
  { id: 'settings', label: '設定' },
]

export default function App() {
  const [tab, setTab] = useState<TabId>('home')
  const [deepLinkDrive, setDeepLinkDrive] = useState<string | null>(null)
  const [elevated, setElevated] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [scanProgress, setScanProgress] = useState<ScanProgressInfo | null>(null)
  const [elevating, setElevating] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [lastScannedAt, setLastScannedAt] = useState<string | null>(null)
  const autoScanStarted = useRef(false)
  const lastSeenScanAt = useRef<string | null>(null)
  const watchingBackground = useRef(false)
  const scanSession = useRef(0)

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => {
      setToast((current) => (current === message ? null : current))
    }, 2200)
  }, [])

  const refreshLastScan = useCallback(async () => {
    try {
      const status = await getStatus()
      const at = status.scanned_at || null
      setLastScannedAt(at)
      if (at && !lastSeenScanAt.current) {
        lastSeenScanAt.current = at
      }
      return at
    } catch {
      return null
    }
  }, [])

  const goSpace = useCallback((letter?: string | null) => {
    if (letter) {
      const normalized = letter.replace(':', '').toUpperCase()
      setDeepLinkDrive(normalized)
    }
    setTab('space')
  }, [])

  const goRecommendations = useCallback(() => {
    setTab('recommendations')
  }, [])

  useEffect(() => {
    const refreshAdmin = () => {
      void window.desktopApi?.isAdmin()
        .then((admin) => setElevated(Boolean(admin)))
        .catch(() => {
          void getAbout()
            .then((about) => setElevated(Boolean(about.elevated)))
            .catch(() => setElevated(true))
        })
    }
    refreshAdmin()
    void refreshLastScan()
    window.addEventListener('focus', refreshAdmin)
    return () => window.removeEventListener('focus', refreshAdmin)
  }, [refreshKey, refreshLastScan])

  const monitorScan = useCallback(
    async (session: number) => {
      try {
        for (;;) {
          await new Promise((r) => window.setTimeout(r, 400))
          if (session !== scanSession.current) return
          const progress = await getScanProgress()
          if (session !== scanSession.current) return
          setScanProgress(progress)
          if (!progress.running) {
            if (progress.error) {
              showToast(`スキャンに失敗しました: ${progress.error}`)
            } else if (progress.phase !== 'cancelled') {
              setRefreshKey((k) => k + 1)
              await refreshLastScan()
              showToast('スキャンが完了しました')
            }
            break
          }
        }
      } finally {
        if (session !== scanSession.current) return
        setScanning(false)
        window.setTimeout(() => {
          setScanProgress((current) => (current?.running ? current : null))
        }, 1800)
      }
    },
    [refreshLastScan, showToast],
  )

  const runScan = useCallback(async () => {
    if (scanning) return
    const session = ++scanSession.current
    setScanning(true)
    setScanProgress({
      running: true,
      phase: 'queued',
      percent: 1,
      message: 'スキャンを準備中…',
    })
    showToast('スキャンを開始しました…')
    try {
      const response = await postScan()
      if (response.ok === false) throw new Error(response.message || 'スキャンを開始できませんでした')
      await monitorScan(session)
    } catch (err) {
      if (session !== scanSession.current) return
      const message = err instanceof Error ? err.message : String(err)
      showToast(`スキャンに失敗しました: ${message}`)
      setScanning(false)
      setScanProgress({
        running: false,
        phase: 'error',
        percent: 0,
        message: 'スキャンに失敗しました',
        error: message,
      })
    }
  }, [monitorScan, scanning, showToast])

  const pauseScan = useCallback(async () => {
    try {
      const response = await postScanPause()
      if (response.ok === false) throw new Error(response.message || 'スキャンを中断できませんでした')
      const progress = await getScanProgress()
      setScanProgress(progress)
      showToast('スキャンを中断しました')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`スキャンの中断に失敗: ${message}`)
    }
  }, [showToast])

  const resumeScan = useCallback(async () => {
    try {
      const response = await postScanResume()
      if (response.ok === false) throw new Error(response.message || 'スキャンを再開できませんでした')
      const progress = await getScanProgress()
      setScanProgress(progress)
      showToast('スキャンを再開しました')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`スキャンの再開に失敗: ${message}`)
    }
  }, [showToast])

  const restartScan = useCallback(async () => {
    const session = ++scanSession.current
    setScanning(true)
    setScanProgress({
      running: true,
      phase: 'queued',
      percent: 1,
      message: '前の処理を停止して、最初から準備中…',
    })
    try {
      const response = await postScanRestart()
      if (response.ok === false) throw new Error(response.message || 'スキャンをやり直せませんでした')
      showToast('最初からスキャンを開始しました')
      await monitorScan(session)
    } catch (err) {
      if (session !== scanSession.current) return
      const message = err instanceof Error ? err.message : String(err)
      setScanning(false)
      setScanProgress({
        running: false,
        phase: 'error',
        percent: 0,
        message: '再スキャンを開始できませんでした',
        error: message,
      })
      showToast(`再スキャンの開始に失敗: ${message}`)
    }
  }, [monitorScan, showToast])

  // 起動時は必ず健康診断スキャンを実行
  useEffect(() => {
    if (autoScanStarted.current) return
    autoScanStarted.current = true
    const timer = window.setTimeout(() => {
      void runScan()
    }, 1200)
    return () => window.clearTimeout(timer)
  }, [runScan])

  // バックエンドの毎日スキャンなど、UI外で走った結果を取り込む
  useEffect(() => {
    let cancelled = false

    const tick = async () => {
      if (cancelled || scanning || watchingBackground.current) return
      try {
        const progress = await getScanProgress()
        if (cancelled) return

        if (progress.running) {
          const session = ++scanSession.current
          watchingBackground.current = true
          setScanning(true)
          setScanProgress(progress)
          showToast('自動スキャンを検知しました…')
          try {
            for (;;) {
              if (cancelled || session !== scanSession.current) break
              await new Promise((r) => window.setTimeout(r, 500))
              const next = await getScanProgress()
              if (cancelled || session !== scanSession.current) break
              setScanProgress(next)
              if (!next.running) {
                if (next.error) {
                  showToast(`自動スキャンに失敗しました: ${next.error}`)
                } else {
                  const at = await refreshLastScan()
                  if (at) lastSeenScanAt.current = at
                  setRefreshKey((k) => k + 1)
                  showToast('自動スキャンが完了しました')
                }
                break
              }
            }
          } finally {
            watchingBackground.current = false
            if (session === scanSession.current) {
              setScanning(false)
              window.setTimeout(() => {
                setScanProgress((current) => (current?.running ? current : null))
              }, 1800)
            }
          }
          return
        }

        const status = await getStatus()
        if (cancelled) return
        const at = status.scanned_at || null
        if (at && lastSeenScanAt.current && at !== lastSeenScanAt.current) {
          lastSeenScanAt.current = at
          setLastScannedAt(at)
          setRefreshKey((k) => k + 1)
          showToast('自動スキャンの結果を反映しました')
        } else if (at && !lastSeenScanAt.current) {
          lastSeenScanAt.current = at
          setLastScannedAt(at)
        }
      } catch {
        // ignore
      }
    }

    const id = window.setInterval(() => {
      void tick()
    }, 10000)
    void tick()
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [scanning, showToast, refreshLastScan])

  const elevate = async () => {
    if (elevating) return
    const api = window.desktopApi
    if (!api?.elevate) {
      showToast('管理者昇格は Electron 起動時のみ利用できます')
      return
    }
    setElevating(true)
    const wasElevated = elevated
    showToast(
      wasElevated
        ? '画面を最新の内容に更新しています…'
        : '画面を準備してから、管理者で開き直します…',
    )
    try {
      const ok = await api.elevate()
      if (ok) {
        showToast(
          wasElevated
            ? '画面を更新しました。ディスク表示を確認してみてください'
            : '管理者として開き直します…',
        )
      } else {
        showToast(
          wasElevated
            ? '画面の更新に失敗しました'
            : '管理者での再起動をキャンセルしたか、起動に失敗しました',
        )
      }
    } catch {
      showToast('管理者昇格に失敗しました')
    } finally {
      setElevating(false)
    }
  }

  return (
    <div className="shell">
      <aside className="side-nav">
        <div className="side-brand">
          <p className="side-brand-mark">パソコンちぇっ君</p>
          <p className="side-brand-sub">ディスクと容量を、やさしく見守る</p>
        </div>
        <nav className="nav-list" aria-label="メインメニュー">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${tab === item.id ? 'is-active' : ''}`}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <div className="main-column">
        <header className="top-bar">
          <div className="top-bar-brand">
            <h1>パソコンちぇっ君</h1>
            <p>ローカルだけで動く、PCの健康診断</p>
          </div>
          <div className="top-bar-actions">
            {elevated ? (
              <span className="admin-pill" title="管理者権限で動作中です">
                管理者で動作中
              </span>
            ) : (
              <button
                type="button"
                className={`btn ghost ${elevating ? 'is-busy' : ''}`}
                onClick={() => void elevate()}
                disabled={elevating}
              >
                {elevating && <span className="btn-spinner" aria-hidden />}
                {elevating ? '準備中…' : '管理者として再起動'}
              </button>
            )}
            <div className="scan-action">
              {!scanning ? (
                <button type="button" className="btn primary" onClick={() => void runScan()}>
                  今すぐスキャン
                </button>
              ) : scanProgress?.phase === 'paused' ? (
                <button type="button" className="btn primary" onClick={() => void resumeScan()}>
                  スキャンを再開
                </button>
              ) : (
                <button type="button" className="btn danger" onClick={() => void pauseScan()}>
                  スキャンを中断
                </button>
              )}
              {scanning && (
                <button type="button" className="btn ghost" onClick={() => void restartScan()}>
                  最初からスキャン
                </button>
              )}
              <p className="scan-last">
                {lastScannedAt
                  ? `最終スキャン: ${new Date(lastScannedAt).toLocaleString('ja-JP')}`
                  : '最終スキャン: まだありません'}
              </p>
            </div>
          </div>
        </header>

        {scanProgress && (scanning || scanProgress.message) && (
          <div
            className={`scan-banner scan-banner-dual ${scanProgress.error ? 'is-error' : ''} ${!scanning && !scanProgress.error ? 'is-done' : ''}`}
          >
            <div className="scan-banner-head">
              <strong>
                {scanProgress.phase === 'paused'
                  ? 'スキャン中断中'
                  : scanning
                    ? '並行スキャン実行中'
                    : scanProgress.error
                      ? 'スキャン失敗'
                      : 'スキャン完了'}
              </strong>
              <span className="scan-banner-overall">
                全体 {Math.round(scanProgress.percent ?? 0)}%
              </span>
            </div>
            <div className="scan-dual-bars">
              <div className="scan-bar-card">
                <div className="scan-bar-label">
                  <span>① 健康診断（SMART）</span>
                  <span>
                    {Math.round(
                      scanProgress.health?.percent ??
                        (scanning && scanProgress.phase !== 'space_map' && scanProgress.phase !== 'done'
                          ? scanProgress.percent ?? 0
                          : scanning
                            ? 0
                            : 100),
                    )}
                    %
                  </span>
                </div>
                <div className="progress-track" aria-label="健康診断の進捗">
                  <i
                    style={{
                      width: `${Math.max(
                        4,
                        scanProgress.health?.percent ??
                          (scanning && scanProgress.phase !== 'space_map' && scanProgress.phase !== 'done'
                            ? scanProgress.percent ?? 8
                            : scanning
                              ? 4
                              : 100),
                      )}%`,
                    }}
                  />
                </div>
                <p className="muted scan-bar-msg">
                  {scanProgress.health?.message ||
                    (scanning ? '健康診断を処理中…' : '完了')}
                </p>
              </div>
              <div className="scan-bar-card">
                <div className="scan-bar-label">
                  <span>② 容量マップ</span>
                  <span>{Math.round(scanProgress.mapping?.percent ?? 0)}%</span>
                </div>
                <div className="progress-track is-map" aria-label="容量マップの進捗">
                  <i
                    style={{
                      width: `${Math.max(4, scanProgress.mapping?.percent ?? (scanning ? 4 : 100))}%`,
                    }}
                  />
                </div>
                <p className="muted scan-bar-msg">
                  {scanProgress.mapping?.message ||
                    (scanning ? '容量マップを処理中…' : '完了')}
                </p>
              </div>
            </div>
          </div>
        )}

        <main className="page-area" key={`${tab}-${refreshKey}`}>
          <PageErrorBoundary
            fallbackTitle="画面の表示に失敗しました"
            onRetry={() => setRefreshKey((k) => k + 1)}
          >
            {tab === 'home' && (
              <HomePage
                onOpenSpace={goSpace}
                onOpenRecommendations={goRecommendations}
                showToast={showToast}
                processElevated={elevated}
              />
            )}
            {tab === 'disks' && <DisksPage onOpenSpace={goSpace} showToast={showToast} />}
            {tab === 'space' && (
              <SpacePage initialDrive={deepLinkDrive} showToast={showToast} />
            )}
            {tab === 'recommendations' && <RecommendationsPage showToast={showToast} />}
            {tab === 'prices' && <PricesPage showToast={showToast} />}
            {tab === 'news' && <NewsPage showToast={showToast} />}
            {tab === 'settings' && <SettingsPage showToast={showToast} />}
          </PageErrorBoundary>
        </main>
      </div>

      <Toast message={toast} />
    </div>
  )
}
