export type OverallStatus = 'OK' | 'Watch' | 'ReplaceSoon' | 'Critical' | 'Unknown'
export type SafetyLevel = 'safe' | 'caution' | 'danger' | 'neutral'

export type TabId =
  | 'home'
  | 'disks'
  | 'space'
  | 'recommendations'
  | 'prices'
  | 'news'
  | 'settings'

export interface AboutInfo {
  name: string
  version: string
  author: string
  homepage: string
  contact: string
  elevated: boolean
  smartctl_available: boolean
}

export interface AlertItem {
  id?: number
  created_at?: string
  level: string
  title: string
  message: string
  device_id?: string | null
  notified?: boolean
  kind?: string
}

export interface VolumeInfo {
  letter?: string
  label?: string
  file_system?: string
  health_status?: string
  size_gb?: number
  free_gb?: number
  free_pct?: number
  physical_disk_ids?: string[]
}

export interface DiskInfo {
  device_id?: string
  model?: string
  serial?: string
  media_type?: string
  size_gb?: number
  health_status?: string
  free_pct?: number
  free_gb?: number
  risk_level?: string
  reasons?: string[]
  needs_replacement?: boolean
  volumes?: VolumeInfo[]
  smart?: {
    overall?: string
    temperature_c?: number
    power_on_hours?: number
    attributes?: Record<string, number>
  }
}

export interface InventoryInfo {
  hostname?: string
  os?: string
  os_caption?: string
  os_version?: string
  cpu?: string
  cpu_name?: string
  ram_gb?: number
  total_memory_gb?: number
  memory_summary?: string
  memory_used_pct?: number
  gpu?: string
  gpu_summary?: string
  motherboard?: string
  manufacturer?: string
  model?: string
  [key: string]: unknown
}

export interface ScanProgressInfo {
  running: boolean
  phase?: string
  percent?: number
  message?: string
  error?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export interface VolumeIssue {
  letter?: string
  free_pct?: number
  free_gb?: number
  size_gb?: number
  risk_level?: string
  reason?: string
}

export interface StatusPayload {
  overall_status: OverallStatus | string
  scanned_at?: string
  message?: string
  inventory?: InventoryInfo
  disks?: DiskInfo[]
  volumes?: VolumeInfo[]
  volume_issues?: VolumeIssue[]
  alerts?: AlertItem[]
  replacement_targets?: DiskInfo[]
  recommendations?: Recommendation[]
  elevated?: boolean
  smartctl_available?: boolean
  settings?: AppSettings
}

export interface RecommendationLink {
  source: string
  kind: string
  title: string
  url: string
  condition?: string
  price_hint?: string
}

export interface Recommendation {
  for_device_id?: string
  for_model?: string
  risk_level?: string
  query: string
  notes?: string[]
  price_band?: string
  candidates?: RecommendationLink[]
  disclaimer?: string
}

export interface AppSettings {
  notify_enabled?: boolean
  capacity_warn_pct?: number
  capacity_critical_pct?: number
  budget_max_yen?: number
  prefer_new_used?: string
  prefer_media?: string
  capacity_preference_tb?: number
  priority?: string
  daily_scan_time?: string
  startup_enabled?: boolean
  [key: string]: unknown
}

export interface NewsItem {
  id?: string
  title: string
  url: string
  source?: string
  published_at?: string
  published?: string
  summary?: string
  image_url?: string
  image?: string
}

export interface NewsPayload {
  items?: NewsItem[]
  fetched_at?: string | number
  [key: string]: unknown
}

export interface PricePart {
  id: string
  name: string
  category?: string
  brand?: string
  generation?: string
  query?: string
  tracked?: boolean
  keep_legacy?: boolean
  latest_kakaku?: { price_yen?: number; url?: string; fetched_at?: string } | null
  latest_amazon?: { price_yen?: number; url?: string; fetched_at?: string } | null
  kakaku_url?: string
  amazon_url?: string
  amazon_asin?: string | null
  keepa_graph_url?: string | null
  keepa_product_url?: string | null
  [key: string]: unknown
}

export interface PriceCatalogGroup {
  category: string
  label?: string
  brands?: Array<{
    brand: string
    label?: string
    items: PricePart[]
  }>
  items?: PricePart[]
}

export interface PricesPayload {
  catalog_version?: string
  /** 新形式は配列。旧形式の Record も許容する */
  groups?: PriceCatalogGroup[] | Record<string, PricePart[]>
  tracked_ids?: string[]
  overview?: PricePart[]
  legacy_items?: PricePart[]
  orphans?: PricePart[]
  last_price_fetch?: string | null
  next_due?: string | null
}

export interface DriveInfo {
  letter: string
  rootPath: string
  label: string
  totalBytes: number
  freeBytes: number
  usedBytes: number
}

export interface DirNode {
  name: string
  path: string
  size: number
  safety: SafetyLevel
  reason: string
  children?: DirNode[]
}

export interface ScanProgress {
  scannedFiles: number
  scannedDirs: number
  currentPath: string
  bytesSeen: number
  phase?: string
  percent?: number
}

export interface DiskUsage {
  totalBytes: number
  freeBytes: number
  usedBytes: number
}

export interface SpaceScanResult {
  root: DirNode
  disk: DiskUsage
  candidates: DirNode[]
  skippedCount: number
  durationMs: number
  rootPath: string
}
