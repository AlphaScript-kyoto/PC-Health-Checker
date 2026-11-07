export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'pchc-theme'

let current: ThemePreference = 'system'
let userChosen = false

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'system' || value === 'light' || value === 'dark'
}

export function readStoredTheme(): ThemePreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (isThemePreference(raw)) return raw
  } catch {
    // 保存先を読めないときはシステム設定に従う
  }
  return 'system'
}

export function resolvedTheme(preference: ThemePreference): 'light' | 'dark' {
  if (preference === 'light' || preference === 'dark') return preference
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(preference: ThemePreference): 'light' | 'dark' {
  const resolved = resolvedTheme(preference)
  document.documentElement.dataset.theme = resolved
  document.documentElement.style.colorScheme = resolved
  try {
    localStorage.setItem(STORAGE_KEY, preference)
  } catch {
    // 表示だけは切り替える
  }
  return resolved
}

export function installTheme(): () => void {
  current = readStoredTheme()
  applyTheme(current)
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const onChange = () => {
    if (current === 'system') applyTheme('system')
  }
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}

export function setThemePreference(preference: ThemePreference) {
  userChosen = true
  current = preference
  applyTheme(preference)
}

export function adoptServerTheme(preference: ThemePreference) {
  if (userChosen) return
  current = preference
  applyTheme(preference)
}
