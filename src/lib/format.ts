export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unitIndex = -1
  do {
    value /= 1024
    unitIndex += 1
  } while (value >= 1024 && unitIndex < units.length - 1)
  const digits = value >= 100 ? 0 : value >= 10 ? 1 : 2
  return `${value.toFixed(digits)} ${units[unitIndex]}`
}

export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${minutes} 分 ${rest} 秒`
}

export function formatYen(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${Math.round(value).toLocaleString('ja-JP')} 円`
}

export function statusJa(status: string | null | undefined): string {
  switch (status) {
    case 'OK':
      return '良好'
    case 'Watch':
      return '注意'
    case 'ReplaceSoon':
      return 'まもなく交換'
    case 'Critical':
      return '危険'
    case 'Unknown':
      return '不明'
    default:
      return status || '不明'
  }
}

export function safetyLabel(safety: string): string {
  switch (safety) {
    case 'safe':
      return '比較的安全'
    case 'caution':
      return '注意'
    case 'danger':
      return '危険'
    default:
      return '要確認'
  }
}

export function formatGb(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${value.toFixed(value >= 100 ? 0 : 1)} GB`
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${value.toFixed(1)}%`
}
