import { useCallback, useEffect, useState } from 'react'
import { getAbout, getScanProgress, postScan } from './api'
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

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => {
      setToast((current) => (current === message ? null : current))
    }, 2200)
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
          // Electron 外では about API にフォールバック
          void getAbout()
            .then((about) => setElevated(Boolean(about.elevated)))
            .catch(() => setElevated(true))
        })
    }
    refreshAdmin()
    window.addEventListener('focus', refreshAdmin)
    return () => window.removeEventListener('focus', refreshAdmin)
  }, [refreshKey])

  const runScan = async () => {
    if (scanning) return
    setScanning(true)
    setScanProgress({
      running: true,
      phase: 'queued',
      percent: 1,
      message: 'スキャンを準備中…',
    })
    showToast('スキャンを開始しました…')
    try {
      await postScan()
      // 進捗をポーリング（SMART 取得などで数十秒かかることがある）
      for (;;) {
        await new Promise((r) => window.setTimeout(r, 400))
        const progress = await getScanProgress()
        setScanProgress(progress)
        if (!progress.running) {
          if (progress.error) {
            showToast(`スキャンに失敗しました: ${progress.error}`)
          } else {
            setRefreshKey((k) => k + 1)
            showToast('スキャンが完了しました')
          }
          break
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`スキャンに失敗しました: ${message}`)
      setScanProgress({
        running: false,
        phase: 'error',
        percent: 0,
        message: 'スキャンに失敗しました',
        error: message,
      })
    } finally {
      setScanning(false)
      window.setTimeout(() => {
        setScanProgress((current) => (current?.running ? current : null))
      }, 1800)
    }
  }

  const elevate = async () => {
    if (elevating) return
    const api = window.desktopApi
    if (!api?.elevate) {
      showToast('管理者昇格は Electron 起動時のみ利用できます')
      return
    }
    setElevating(true)
    showToast('画面を準備してから、管理者で開き直します…')
    try {
      const ok = await api.elevate()
      if (ok) {
        showToast('管理者として開き直します…')
      } else {
        showToast('管理者での再起動をキャンセルしたか、起動に失敗しました')
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
          <p className="side-brand-mark">PCの健康チェッカー</p>
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
            <h1>PCの健康チェッカー</h1>
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
            <button
              type="button"
              className={`btn primary ${scanning ? 'is-busy' : ''}`}
              onClick={() => void runScan()}
              disabled={scanning}
            >
              {scanning && <span className="btn-spinner" aria-hidden />}
              {scanning
                ? `スキャン中 ${Math.round(scanProgress?.percent ?? 0)}%`
                : '今すぐスキャン'}
            </button>
          </div>
        </header>

        {scanProgress && (scanning || scanProgress.message) && (
          <div className={`scan-banner ${scanProgress.error ? 'is-error' : ''} ${!scanning && !scanProgress.error ? 'is-done' : ''}`}>
            <div className="scan-banner-text">
              <strong>{scanning ? 'スキャン実行中' : scanProgress.error ? 'スキャン失敗' : 'スキャン完了'}</strong>
              <span>{scanProgress.message || '処理しています…'}</span>
            </div>
            <div className="progress-block" style={{ marginTop: 0, flex: 1, minWidth: 160 }}>
              <div className="progress-track" aria-hidden>
                <i style={{ width: `${Math.max(4, scanProgress.percent ?? 0)}%` }} />
              </div>
              <p className="muted" style={{ margin: '6px 0 0', fontSize: 12 }}>
                {Math.round(scanProgress.percent ?? 0)}%
              </p>
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
