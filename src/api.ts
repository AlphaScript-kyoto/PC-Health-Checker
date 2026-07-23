const DEFAULT_BASE = 'http://127.0.0.1:8787'

export function apiBase(): string {
  return DEFAULT_BASE
}

export class ApiError extends Error {
  status: number
  body: string

  constructor(status: number, body: string) {
    super(body || `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${apiBase()}${path.startsWith('/') ? path : `/${path}`}`
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  const text = await res.text()
  if (!res.ok) {
    throw new ApiError(res.status, text || res.statusText)
  }
  if (!text) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    return text as unknown as T
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PUT',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
}

export async function getHealth() {
  return api.get<{ status: string }>('/api/health')
}

export async function getAbout() {
  return api.get<import('./types').AboutInfo>('/api/about')
}

export async function getStatus() {
  return api.get<import('./types').StatusPayload>('/api/status')
}

export async function postScan() {
  return api.post<{ ok?: boolean; started?: boolean; message?: string }>('/api/scan')
}

export async function getScanProgress() {
  return api.get<import('./types').ScanProgressInfo>('/api/scan/progress')
}

export async function getAlerts() {
  return api.get<import('./types').AlertItem[]>('/api/alerts')
}

export async function getRecommendations() {
  return api.get<{
    recommendations: import('./types').Recommendation[]
    scanned_at?: string | null
  }>('/api/recommendations')
}

export async function getNews(force = false) {
  return api.get<import('./types').NewsPayload>(`/api/news${force ? '?force=true' : ''}`)
}

export async function getPrices() {
  return api.get<import('./types').PricesPayload>('/api/prices')
}

export async function putTracked(ids: string[]) {
  return api.put<import('./types').PricesPayload>('/api/prices/tracked', { ids })
}

export async function postPriceRefresh(force = true) {
  return api.post<import('./types').PricesPayload>(`/api/prices/refresh?force=${force}`)
}

export async function postOrphans(decisions: Record<string, 'keep' | 'drop'>) {
  return api.post<import('./types').PricesPayload>('/api/prices/orphans', { decisions })
}

export async function getSettings() {
  return api.get<import('./types').AppSettings>('/api/settings')
}

export async function putSettings(body: Partial<import('./types').AppSettings>) {
  return api.put<import('./types').AppSettings>('/api/settings', body)
}

export async function getDrives() {
  return api.get<import('./types').DriveInfo[]>('/api/drives')
}

export async function postSpaceScan(rootPath: string) {
  return api.post<{ ok?: boolean; message?: string }>('/api/space/scan', { rootPath })
}

export async function getSpaceProgress() {
  return api.get<import('./types').ScanProgress | null>('/api/space/progress')
}

export async function getSpaceResult() {
  return api.get<import('./types').SpaceScanResult | null>('/api/space/result')
}
