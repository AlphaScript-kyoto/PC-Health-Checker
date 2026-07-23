import { useMemo } from 'react'
import { formatYen } from '../lib/format'
import type { PriceHistoryPoint } from '../types'

interface Series {
  hist?: PriceHistoryPoint[] | null
  className: string
  label: string
}

interface Props {
  kakakuHistory?: PriceHistoryPoint[] | null
  amazonHistory?: PriceHistoryPoint[] | null
  width?: number
  height?: number
}

function validPoints(hist?: PriceHistoryPoint[] | null) {
  return (hist || []).filter((h) => h.price_yen != null && Number.isFinite(Number(h.price_yen)))
}

export function DualPriceChart({
  kakakuHistory,
  amazonHistory,
  width = 320,
  height = 88,
}: Props) {
  const series: Series[] = useMemo(
    () => [
      { hist: kakakuHistory, className: 'is-kakaku', label: '価格.com' },
      { hist: amazonHistory, className: 'is-amazon', label: 'Amazon' },
    ],
    [kakakuHistory, amazonHistory],
  )

  const chart = useMemo(() => {
    const all = series.flatMap((s) => validPoints(s.hist))
    if (all.length < 2) return null

    const pad = { t: 8, r: 8, b: 18, l: 8 }
    const times = all.map((h) => new Date(String(h.fetched_at)).getTime()).filter(Number.isFinite)
    const prices = all.map((h) => Number(h.price_yen))
    const minT = Math.min(...times)
    const maxT = Math.max(...times)
    const minY = Math.min(...prices)
    const maxY = Math.max(...prices)
    const spanT = Math.max(maxT - minT, 1)
    const spanY = Math.max(maxY - minY, 1)

    const xOf = (t: number) => pad.l + ((t - minT) / spanT) * (width - pad.l - pad.r)
    const yOf = (v: number) => pad.t + (1 - (v - minY) / spanY) * (height - pad.t - pad.b)

    const paths = series.map((s) => {
      const pts = validPoints(s.hist)
      if (pts.length < 2) return null
      const d = pts
        .map((h, i) => {
          const x = xOf(new Date(String(h.fetched_at)).getTime())
          const y = yOf(Number(h.price_yen))
          return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`
        })
        .join(' ')
      return { className: s.className, d }
    })

    return { paths, minY, maxY }
  }, [series, width, height])

  if (!chart) {
    return (
      <p className="price-chart-empty">
        自前の推移は、価格更新を重ねるとここに線グラフが出ます
      </p>
    )
  }

  return (
    <div className="price-chart-wrap">
      <svg
        className="price-chart"
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label="価格推移グラフ"
      >
        <text x={8} y={height - 4} className="chart-label">
          {formatYen(chart.minY)}
        </text>
        <text x={width - 8} y={14} className="chart-label chart-label-end" textAnchor="end">
          {formatYen(chart.maxY)}
        </text>
        {chart.paths.map(
          (p) =>
            p && (
              <path
                key={p.className}
                d={p.d}
                className={`chart-line ${p.className}`}
                fill="none"
                strokeWidth={2}
                vectorEffect="non-scaling-stroke"
              />
            ),
        )}
      </svg>
      <div className="chart-legend">
        <span className="legend-kakaku">価格.com</span>
        <span className="legend-amazon">Amazon</span>
      </div>
    </div>
  )
}

interface KeepaProps {
  graphUrl?: string | null
  productUrl?: string | null
}

export function KeepaGraphFold({ graphUrl, productUrl }: KeepaProps) {
  if (!graphUrl) {
    return (
      <p className="muted keepa-hint">
        Keepa グラフは Amazon 価格取得で ASIN が取れたときに表示されます（「価格を更新」後）
      </p>
    )
  }

  return (
    <details className="keepa-fold">
      <summary className="keepa-summary">Keepa 過去価格グラフ（1年）</summary>
      <a
        href={productUrl || graphUrl}
        target="_blank"
        rel="noopener noreferrer"
        title="Keepaで詳細を見る"
      >
        <img
          className="keepa-chart"
          loading="lazy"
          src={graphUrl}
          alt="Keepa価格推移グラフ"
          onError={(e) => {
            const fold = (e.currentTarget as HTMLImageElement).closest('.keepa-fold')
            fold?.classList.add('keepa-error')
          }}
        />
      </a>
      <p className="muted keepa-note">
        グラフ提供: keepa.com（Amazon 新品・過去365日）。詳細は Keepa で確認できます。
      </p>
    </details>
  )
}
