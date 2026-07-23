import { hierarchy, treemap, treemapSquarify } from 'd3-hierarchy'
import type { HierarchyRectangularNode } from 'd3-hierarchy'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { DirNode, SafetyLevel } from '../types'
import { formatBytes } from '../lib/format'
import './Treemap.css'

interface Props {
  root: DirNode
  rootLabel: string
  selectedPath: string | null
  onSelect: (node: DirNode) => void
}

function fillFor(s: SafetyLevel) {
  switch (s) {
    case 'safe':
      return 'var(--safe-fill)'
    case 'caution':
      return 'var(--caution-fill)'
    case 'danger':
      return 'var(--danger-fill)'
    default:
      return 'var(--neutral-fill)'
  }
}

function buildChildren(current: DirNode): DirNode[] {
  const children = [...(current.children ?? [])].sort((a, b) => b.size - a.size)
  if (!children.length) return [{ ...current, children: undefined }]
  const MAX = 16
  if (children.length <= MAX) return children.map((c) => ({ ...c, children: undefined }))
  const kept = children.slice(0, MAX - 1).map((c) => ({ ...c, children: undefined as undefined }))
  const rest = children.slice(MAX - 1)
  kept.push({
    name: `その他 (${rest.length}件)`,
    path: `${current.path}__other__`,
    size: rest.reduce((s, c) => s + c.size, 0),
    safety: 'neutral',
    reason: '小さめの項目をまとめた表示です。',
    children: undefined,
  })
  return kept
}

export function Treemap({ root, rootLabel, selectedPath, onSelect }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 800, height: 420 })
  const [breadcrumb, setBreadcrumb] = useState<DirNode[]>([root])

  useEffect(() => setBreadcrumb([root]), [root])
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect
      if (!r) return
      setSize({ width: Math.max(280, Math.floor(r.width)), height: Math.max(260, Math.floor(r.height)) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const current = breadcrumb[breadcrumb.length - 1] ?? root
  const cells = useMemo(() => {
    const data: DirNode = { ...current, children: buildChildren(current) }
    const rootH = hierarchy(data)
      .sum((d) => (d.children?.length ? 0 : Math.max(d.size, 1)))
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
    const layout = treemap<DirNode>()
      .tile(treemapSquarify.ratio(1.35))
      .size([size.width, size.height])
      .paddingInner(6)
      .paddingOuter(4)
      .round(true)
    const laid = layout(rootH) as HierarchyRectangularNode<DirNode>
    return laid.leaves().map((leaf) => ({
      node: leaf.data,
      x0: leaf.x0,
      y0: leaf.y0,
      x1: leaf.x1,
      y1: leaf.y1,
    }))
  }, [current, size])

  const drill = (node: DirNode) => {
    onSelect(node)
    const original = current.children?.find((c) => c.path === node.path)
    if (original?.children?.length && !node.path.includes('__other__')) {
      setBreadcrumb((b) => [...b, original])
    }
  }

  return (
    <section className="treemap-panel">
      <div className="treemap-toolbar">
        <div className="crumbs">
          {breadcrumb.map((n, i) => (
            <button key={`${n.path}-${i}`} type="button" className="crumb" onClick={() => setBreadcrumb((b) => b.slice(0, i + 1))}>
              {i === 0 ? rootLabel : n.name}
            </button>
          ))}
        </div>
        <p className="hint">クリック詳細 / ダブルクリックで中へ</p>
      </div>
      <div className="treemap-stage" ref={wrapRef}>
        <svg width={size.width} height={size.height}>
          {cells.map((c) => {
            const w = c.x1 - c.x0
            const h = c.y1 - c.y0
            const label = w > 72 && h > 40
            return (
              <g
                key={c.node.path}
                transform={`translate(${c.x0},${c.y0})`}
                className={selectedPath === c.node.path ? 'tm-cell is-selected' : 'tm-cell'}
                onClick={() => onSelect(c.node)}
                onDoubleClick={() => drill(c.node)}
              >
                <title>{`${c.node.name}\n${formatBytes(c.node.size)}`}</title>
                <rect width={w} height={h} rx={11} fill={fillFor(c.node.safety)} />
                {label && (
                  <foreignObject width={w} height={h}>
                    <div className="tm-label">
                      <strong>{c.node.name}</strong>
                      <span>{formatBytes(c.node.size)}</span>
                    </div>
                  </foreignObject>
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </section>
  )
}
