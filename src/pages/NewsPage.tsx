import { useEffect, useState } from 'react'
import { getNews } from '../api'
import type { NewsItem, NewsPayload } from '../types'

interface Props {
  showToast: (message: string) => void
}

export function NewsPage({ showToast }: Props) {
  const [data, setData] = useState<NewsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = async (force = false) => {
    if (force) setRefreshing(true)
    else setLoading(true)
    try {
      const payload = await getNews(force)
      setData(payload)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`ニュースの取得に失敗: ${message}`)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    void load(true)
  }, [])

  const items: NewsItem[] = data?.items || []

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
        <h2>ニュース</h2>
        <p>PCパーツ関連の最新情報を集めます。</p>
      </div>

      <section
        className="panel"
        style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}
      >
        <p className="muted" style={{ margin: 0 }}>
          {items.length} 件
        </p>
        <button
          type="button"
          className="btn ghost"
          disabled={refreshing}
          onClick={() => void load(true)}
        >
          {refreshing && <span className="btn-spinner" aria-hidden />}
          再読み込み
        </button>
      </section>

      {items.length === 0 ? (
        <section className="panel">
          <p className="muted" style={{ margin: 0 }}>
            表示できるニュースがありません。
          </p>
        </section>
      ) : (
        <div className="news-grid">
          {items.map((item) => (
            <a
              key={item.url || item.id || item.title}
              className="news-card"
              href={item.url}
              target="_blank"
              rel="noreferrer"
            >
              {item.image_url || item.image ? (
                <img src={item.image_url || item.image} alt="" loading="lazy" />
              ) : null}
              <h3>{item.title}</h3>
              <p className="muted" style={{ margin: 0 }}>
                {item.source || 'ニュース'}
                {item.published_at || item.published
                  ? ` · ${new Date(String(item.published_at || item.published)).toLocaleDateString('ja-JP')}`
                  : ''}
              </p>
              {item.summary && (
                <p className="muted" style={{ margin: 0 }}>
                  {item.summary}
                </p>
              )}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
