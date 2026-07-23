import { useEffect, useState } from 'react'
import { getSettings, putSettings } from '../api'
import type { AppSettings } from '../types'

interface Props {
  showToast: (message: string) => void
}

const DEFAULTS: AppSettings = {
  notify_enabled: true,
  capacity_warn_pct: 10,
  capacity_critical_pct: 5,
  budget_max_yen: 30000,
  prefer_new_used: 'either',
  prefer_media: 'ssd',
  capacity_preference_tb: 2,
  priority: 'speed',
  daily_scan_time: '09:00',
  startup_enabled: false,
}

export function SettingsPage({ showToast }: Props) {
  const [form, setForm] = useState<AppSettings>(DEFAULTS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const settings = await getSettings()
        if (!cancelled) setForm({ ...DEFAULTS, ...settings })
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err)
          showToast(`設定の取得に失敗: ${message}`)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [showToast])

  const update = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const save = async () => {
    setSaving(true)
    try {
      const saved = await putSettings({
        notify_enabled: Boolean(form.notify_enabled),
        capacity_warn_pct: Number(form.capacity_warn_pct),
        capacity_critical_pct: Number(form.capacity_critical_pct),
        budget_max_yen: Number(form.budget_max_yen),
        prefer_new_used: String(form.prefer_new_used),
        prefer_media: String(form.prefer_media),
        capacity_preference_tb: Number(form.capacity_preference_tb),
        priority: String(form.priority),
        daily_scan_time: String(form.daily_scan_time),
        startup_enabled: Boolean(form.startup_enabled),
      })
      setForm({ ...DEFAULTS, ...saved })
      showToast('設定を保存しました')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast(`設定の保存に失敗: ${message}`)
    } finally {
      setSaving(false)
    }
  }

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
        <h2>設定</h2>
        <p>通知・容量しきい値・買い替え希望を調整できます。</p>
      </div>

      <section className="panel">
        <div className="grid-2">
          <label className="field">
            <span>通知を有効にする</span>
            <select
              value={form.notify_enabled ? '1' : '0'}
              onChange={(e) => update('notify_enabled', e.target.value === '1')}
            >
              <option value="1">オン</option>
              <option value="0">オフ</option>
            </select>
          </label>

          <label className="field">
            <span>Windows 起動時に起動</span>
            <select
              value={form.startup_enabled ? '1' : '0'}
              onChange={(e) => update('startup_enabled', e.target.value === '1')}
            >
              <option value="1">オン</option>
              <option value="0">オフ</option>
            </select>
          </label>

          <label className="field">
            <span>毎日のスキャン時刻（HH:MM）</span>
            <input
              type="time"
              value={String(form.daily_scan_time || '09:00')}
              onChange={(e) => update('daily_scan_time', e.target.value)}
            />
          </label>

          <label className="field">
            <span>容量注意（空き％以下）</span>
            <input
              type="number"
              min={1}
              max={50}
              step={0.5}
              value={Number(form.capacity_warn_pct ?? 10)}
              onChange={(e) => update('capacity_warn_pct', Number(e.target.value))}
            />
          </label>

          <label className="field">
            <span>容量危険（空き％以下）</span>
            <input
              type="number"
              min={0.5}
              max={30}
              step={0.5}
              value={Number(form.capacity_critical_pct ?? 5)}
              onChange={(e) => update('capacity_critical_pct', Number(e.target.value))}
            />
          </label>

          <label className="field">
            <span>予算上限（円）</span>
            <input
              type="number"
              min={1000}
              max={500000}
              step={1000}
              value={Number(form.budget_max_yen ?? 30000)}
              onChange={(e) => update('budget_max_yen', Number(e.target.value))}
            />
          </label>

          <label className="field">
            <span>希望容量（TB）</span>
            <input
              type="number"
              min={0.1}
              max={20}
              step={0.1}
              value={Number(form.capacity_preference_tb ?? 2)}
              onChange={(e) => update('capacity_preference_tb', Number(e.target.value))}
            />
          </label>

          <label className="field">
            <span>新品 / 中古</span>
            <select
              value={String(form.prefer_new_used || 'either')}
              onChange={(e) => update('prefer_new_used', e.target.value)}
            >
              <option value="either">どちらでも</option>
              <option value="new">新品優先</option>
              <option value="used">中古も可</option>
            </select>
          </label>

          <label className="field">
            <span>メディア希望</span>
            <select
              value={String(form.prefer_media || 'ssd')}
              onChange={(e) => update('prefer_media', e.target.value)}
            >
              <option value="ssd">SSD</option>
              <option value="hdd">HDD</option>
              <option value="either">どちらでも</option>
            </select>
          </label>

          <label className="field">
            <span>優先事項</span>
            <select
              value={String(form.priority || 'speed')}
              onChange={(e) => update('priority', e.target.value)}
            >
              <option value="speed">速度</option>
              <option value="quiet">静音</option>
              <option value="capacity">容量</option>
              <option value="price">価格</option>
            </select>
          </label>
        </div>

        <div style={{ marginTop: 16 }}>
          <button type="button" className="btn primary" disabled={saving} onClick={() => void save()}>
            {saving && <span className="btn-spinner" aria-hidden />}
            設定を保存
          </button>
        </div>
      </section>
    </div>
  )
}
