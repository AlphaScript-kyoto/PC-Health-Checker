import { useCallback, useEffect, useState } from 'react'
import { getAbout, postScan } from './api'
import { Toast } from './components/Toast'
import { DisksPage } from './pages/DisksPage'
import { HomePage } from './pages/HomePage'
import { NewsPage } from './pages/NewsPage'
import { PricesPage } from './pages/PricesPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { SettingsPage } from './pages/SettingsPage'
import { SpacePage } from './pages/SpacePage'
import type { TabId } from './types'
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
    void getAbout()
      .then((about) => setElevated(Boolean(about.elevated)))
      .catch(() => setElevated(true))
  }, [refreshKey])

  const runScan = async () => {
    if (scanning) return
    setScanning(true)
    showToast('スキャンを開始しました…')
    try {
      await postScan()
      setRefreshKey((k) => k + 1)
      showToast('スキャンが完了しました')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`スキャンに失敗しました: ${message}`)
    } finally {
      setScanning(false)
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
    showToast('管理者権限の確認画面を開いています…')
    try {
      await api.elevate()
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
            {!elevated && (
              <button
                type="button"
                className={`btn ghost ${elevating ? 'is-busy' : ''}`}
                onClick={() => void elevate()}
                disabled={elevating}
              >
                {elevating && <span className="btn-spinner" aria-hidden />}
                管理者として再起動
              </button>
            )}
            <button
              type="button"
              className={`btn primary ${scanning ? 'is-busy' : ''}`}
              onClick={() => void runScan()}
              disabled={scanning}
            >
              {scanning && <span className="btn-spinner" aria-hidden />}
              今すぐスキャン
            </button>
          </div>
        </header>

        <main className="page-area" key={`${tab}-${refreshKey}`}>
          {tab === 'home' && (
            <HomePage
              onOpenSpace={goSpace}
              onOpenRecommendations={goRecommendations}
              showToast={showToast}
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
        </main>
      </div>

      <Toast message={toast} />
    </div>
  )
}
