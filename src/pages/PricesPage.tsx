import { useEffect, useMemo, useState } from 'react'
import { getPrices, postOrphans, postPriceRefresh, putTracked } from '../api'
import { formatYen } from '../lib/format'
import type { PriceCatalogGroup, PricePart, PricesPayload } from '../types'

interface Props {
  showToast: (message: string) => void
}

function asCatalogGroups(groups: PricesPayload['groups']): PriceCatalogGroup[] {
  if (!groups) return []
  if (Array.isArray(groups)) return groups
  return Object.entries(groups).map(([category, items]) => ({
    category,
    label: category,
    items: Array.isArray(items) ? items : [],
    brands: [
      {
        brand: 'すべて',
        label: 'すべて',
        items: Array.isArray(items) ? items : [],
      },
    ],
  }))
}

function amdPlatform(item: PricePart): string {
  const generation = String(item.generation || '')
  if (generation.includes('5000')) return 'AM4'
  if (generation.includes('7000') || generation.includes('9000')) return 'AM5'
  return 'その他'
}

export function PricesPage({ showToast }: Props) {
  const [data, setData] = useState<PricesPayload | null>(null)
  const [tracked, setTracked] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [openCategories, setOpenCategories] = useState<Record<string, boolean>>({})
  const [openBrands, setOpenBrands] = useState<Record<string, boolean>>({})
  const [intelGenFilter, setIntelGenFilter] = useState<string>('all')
  const [amdPlatformFilter, setAmdPlatformFilter] = useState<string>('all')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await getPrices()
      setData(payload)
      setTracked(new Set(payload.tracked_ids || []))
      const groups = asCatalogGroups(payload.groups)
      const nextOpen: Record<string, boolean> = {}
      groups.forEach((g, index) => {
        nextOpen[g.category] = index === 0
      })
      setOpenCategories(nextOpen)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
      showToast(`価格情報の取得に失敗: ${message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const catalogGroups = useMemo(() => asCatalogGroups(data?.groups), [data])

  const intelGenerations = useMemo(() => {
    const set = new Set<string>()
    catalogGroups
      .filter((g) => g.category === 'cpu')
      .forEach((g) => {
        ;(g.items || []).forEach((item) => {
          if (item.brand === 'Intel' && item.generation) set.add(String(item.generation))
        })
      })
    return [...set]
  }, [catalogGroups])

  const amdPlatforms = useMemo(() => {
    const set = new Set<string>()
    catalogGroups
      .filter((g) => g.category === 'cpu')
      .forEach((g) => {
        ;(g.items || []).forEach((item) => {
          if (item.brand === 'AMD') set.add(amdPlatform(item))
        })
      })
    return [...set]
  }, [catalogGroups])

  const toggle = (id: string) => {
    setTracked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const saveTracked = async () => {
    setSaving(true)
    try {
      const payload = await putTracked([...tracked])
      setData(payload)
      setTracked(new Set(payload.tracked_ids || []))
      showToast('追跡リストを保存しました')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`保存に失敗: ${message}`)
    } finally {
      setSaving(false)
    }
  }

  const refresh = async () => {
    setRefreshing(true)
    try {
      const payload = await postPriceRefresh(true)
      setData(payload)
      setTracked(new Set(payload.tracked_ids || []))
      showToast('価格を更新しました')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`価格更新に失敗: ${message}`)
    } finally {
      setRefreshing(false)
    }
  }

  const resolveOrphan = async (id: string, decision: 'keep' | 'drop') => {
    try {
      const payload = await postOrphans({ [id]: decision })
      setData(payload)
      setTracked(new Set(payload.tracked_ids || []))
      showToast(decision === 'keep' ? '旧パーツをキープしました' : '旧パーツを外しました')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`処理に失敗: ${message}`)
    }
  }

  const filterCpuItem = (item: PricePart) => {
    if (item.brand === 'Intel' && intelGenFilter !== 'all') {
      return String(item.generation || '') === intelGenFilter
    }
    if (item.brand === 'AMD' && amdPlatformFilter !== 'all') {
      return amdPlatform(item) === amdPlatformFilter
    }
    return true
  }

  if (loading) {
    return (
      <div className="page">
        <div className="panel muted">読み込み中…</div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="page">
        <div className="page-head">
          <h2>価格</h2>
          <p>パーツの相場を追跡します。</p>
        </div>
        <section className="panel">
          <p className="muted">価格情報を読み込めませんでした: {error}</p>
          <button type="button" className="btn primary" onClick={() => void load()}>
            再読み込み
          </button>
        </section>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>価格</h2>
        <p>
          パーツの相場を追跡します。最終取得:{' '}
          {data?.last_price_fetch
            ? new Date(data.last_price_fetch).toLocaleString('ja-JP')
            : '未取得'}
        </p>
      </div>

      <section className="panel">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn primary"
            disabled={saving}
            onClick={() => void saveTracked()}
          >
            {saving && <span className="btn-spinner" aria-hidden />}
            追跡を保存
          </button>
          <button
            type="button"
            className="btn ghost"
            disabled={refreshing}
            onClick={() => void refresh()}
          >
            {refreshing && <span className="btn-spinner" aria-hidden />}
            価格を更新
          </button>
        </div>
      </section>

      {(data?.orphans || []).length > 0 && (
        <section className="panel">
          <h3>カタログ更新の確認</h3>
          <p className="muted">リストから外れた旧世代パーツです。キープか削除を選んでください。</p>
          <div className="stack" style={{ marginTop: 10 }}>
            {(data?.orphans || []).map((item) => (
              <div className="list-row" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <p className="muted" style={{ margin: '4px 0 0' }}>
                    {item.generation || item.category}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    className="btn ghost"
                    onClick={() => void resolveOrphan(item.id, 'keep')}
                  >
                    キープ
                  </button>
                  <button
                    type="button"
                    className="btn danger"
                    onClick={() => void resolveOrphan(item.id, 'drop')}
                  >
                    外す
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <h3>追跡中の価格</h3>
        {(data?.overview || []).length === 0 ? (
          <p className="muted" style={{ marginTop: 8 }}>
            まだ追跡中のパーツがありません。下のカタログから選んで保存してください。
          </p>
        ) : (
          <div className="stack" style={{ marginTop: 8 }}>
            {(data?.overview || []).map((item: PricePart) => (
              <div className="list-row" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <p className="muted" style={{ margin: '4px 0 0' }}>
                    価格.com {formatYen(item.latest_kakaku?.price_yen)} · Amazon{' '}
                    {formatYen(item.latest_amazon?.price_yen)}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {item.kakaku_url && (
                    <a className="btn ghost" href={item.kakaku_url} target="_blank" rel="noreferrer">
                      価格.com
                    </a>
                  )}
                  {item.amazon_url && (
                    <a className="btn ghost" href={item.amazon_url} target="_blank" rel="noreferrer">
                      Amazon
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h3>カタログから追跡</h3>
        <p className="muted" style={{ marginTop: 4 }}>
          カテゴリ → メーカーの順に折りたためます。CPU は世代 / ソケットで絞り込みできます。
        </p>

        {catalogGroups.some((g) => g.category === 'cpu') && (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 12 }}>
            <label className="muted" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              Intel 世代
              <select value={intelGenFilter} onChange={(e) => setIntelGenFilter(e.target.value)}>
                <option value="all">すべて</option>
                {intelGenerations.map((gen) => (
                  <option key={gen} value={gen}>
                    {gen}
                  </option>
                ))}
              </select>
            </label>
            <label className="muted" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              AMD ソケット
              <select
                value={amdPlatformFilter}
                onChange={(e) => setAmdPlatformFilter(e.target.value)}
              >
                <option value="all">すべて</option>
                {amdPlatforms.map((sock) => (
                  <option key={sock} value={sock}>
                    {sock}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        <div className="catalog-scroll">
          {catalogGroups.map((group) => {
            const categoryOpen = Boolean(openCategories[group.category])
            const brands =
              group.brands && group.brands.length > 0
                ? group.brands
                : [
                    {
                      brand: 'すべて',
                      label: 'すべて',
                      items: group.items || [],
                    },
                  ]
            return (
              <div key={group.category} className="catalog-fold">
                <button
                  type="button"
                  className="catalog-fold-head"
                  onClick={() =>
                    setOpenCategories((prev) => ({
                      ...prev,
                      [group.category]: !prev[group.category],
                    }))
                  }
                >
                  <strong>{group.label || group.category}</strong>
                  <span>{categoryOpen ? '閉じる' : '開く'}</span>
                </button>
                {categoryOpen && (
                  <div className="catalog-fold-body">
                    {brands.map((brandBlock) => {
                      const brandKey = `${group.category}::${brandBlock.brand}`
                      const brandOpen = openBrands[brandKey] ?? true
                      const items = (brandBlock.items || []).filter((item) =>
                        group.category === 'cpu' ? filterCpuItem(item) : true,
                      )
                      if (items.length === 0) return null
                      return (
                        <div key={brandKey} className="catalog-brand">
                          <button
                            type="button"
                            className="catalog-brand-head"
                            onClick={() =>
                              setOpenBrands((prev) => ({
                                ...prev,
                                [brandKey]: !brandOpen,
                              }))
                            }
                          >
                            <strong>{brandBlock.label || brandBlock.brand}</strong>
                            <span>
                              {items.length}件 · {brandOpen ? '閉じる' : '開く'}
                            </span>
                          </button>
                          {brandOpen && (
                            <div className="catalog-item-grid">
                              {items.map((item) => (
                                <label className="catalog-item" key={item.id}>
                                  <div className="catalog-item-text">
                                    <strong>{item.name}</strong>
                                    <span className="muted">
                                      {item.generation}
                                      {item.brand === 'AMD' ? ` · ${amdPlatform(item)}` : ''}
                                    </span>
                                  </div>
                                  <input
                                    type="checkbox"
                                    checked={tracked.has(item.id)}
                                    onChange={() => toggle(item.id)}
                                  />
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}
