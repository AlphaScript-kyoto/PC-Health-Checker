import {
  app,
  BrowserWindow,
  Tray,
  Menu,
  nativeImage,
  ipcMain,
  shell,
  Notification,
  dialog,
} from 'electron'
import { spawn, execSync, execFile, type ChildProcess } from 'node:child_process'
import { promisify } from 'node:util'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'

const execFileAsync = promisify(execFile)

const HOST = '127.0.0.1'
const PORT = 8787
const BASE = `http://${HOST}:${PORT}`
const APP_TITLE = 'PCの健康チェッカー'
const VITE_ARG_PREFIX = '--pchc-vite='

/** 通常起動と管理者起動で Temp が違うことがあるため、LOCALAPPDATA に置く */
function elevateStateDir(): string {
  const base =
    process.env.LOCALAPPDATA ||
    process.env.USERPROFILE ||
    os.tmpdir()
  const dir = path.join(base, 'PCHealthChecker')
  try {
    fs.mkdirSync(dir, { recursive: true })
  } catch {
    // ignore
  }
  return dir
}

function elevateMarkerPath(): string {
  return path.join(elevateStateDir(), 'elevate-marker.json')
}

function elevateReadyPath(): string {
  return path.join(elevateStateDir(), 'elevate-ready.txt')
}

function viteDevUrlPath(): string {
  return path.join(elevateStateDir(), 'vite-dev-url.txt')
}

/** dist-electron の親 = プロジェクトルート */
const ROOT = path.join(__dirname, '..')

// 通常起動と管理者起動で userData / シングルインスタンスロックがズレないように固定
{
  const userData = path.join(
    process.env.LOCALAPPDATA || os.homedir(),
    'PCHealthChecker',
  )
  try {
    fs.mkdirSync(userData, { recursive: true })
  } catch {
    // ignore
  }
  app.setPath('userData', userData)
}

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let pyProc: ChildProcess | null = null
let quitting = false

function quoteForPsSingle(value: string): string {
  return `'${value.replace(/'/g, "''")}'`
}

function getViteDevServerUrl(): string | undefined {
  const fromEnv = process.env.VITE_DEV_SERVER_URL?.trim()
  if (fromEnv) return fromEnv
  const fromArg = process.argv.find((a) => a.startsWith(VITE_ARG_PREFIX))
  if (fromArg) {
    const url = fromArg.slice(VITE_ARG_PREFIX.length).trim()
    if (url) return url
  }
  // 管理者再起動で引数/環境変数が落ちても、共有ファイルから復元する
  try {
    const fromFile = fs.readFileSync(viteDevUrlPath(), 'utf8').trim()
    if (fromFile) return fromFile
  } catch {
    // ignore
  }
  return undefined
}

function persistViteDevServerUrl(url: string | undefined) {
  if (!url) return
  try {
    fs.writeFileSync(viteDevUrlPath(), url, 'utf8')
    process.env.VITE_DEV_SERVER_URL = url
  } catch (error) {
    console.error('failed to persist vite url', error)
  }
}

function pythonPath(): string {
  if (app.isPackaged) {
    const packaged = path.join(process.resourcesPath, 'backend', 'pc-health-backend.exe')
    if (fs.existsSync(packaged)) return packaged
  }
  const pythonw = path.join(ROOT, 'backend', '.venv', 'Scripts', 'pythonw.exe')
  if (fs.existsSync(pythonw)) return pythonw
  const win = path.join(ROOT, 'backend', '.venv', 'Scripts', 'python.exe')
  if (fs.existsSync(win)) return win
  return 'pythonw'
}

function backendArgs(): string[] {
  const py = pythonPath()
  if (py.toLowerCase().endsWith('pc-health-backend.exe')) return []
  // cwd は backend/ なので app.main をモジュール実行
  return ['-m', 'app.main', '--headless']
}

function backendLogPath(): string {
  const base = app.isPackaged
    ? path.join(process.env.LOCALAPPDATA || ROOT, 'PCHealthChecker')
    : path.join(ROOT, 'backend', 'app', 'data')
  try {
    fs.mkdirSync(base, { recursive: true })
  } catch {
    // ignore
  }
  return path.join(base, 'backend-launch.log')
}

function startBackend() {
  const py = pythonPath()
  const args = backendArgs()
  // パッケージは backend、開発は backend を PYTHONPATH に
  const cwd = app.isPackaged
    ? path.join(process.resourcesPath, 'backend')
    : path.join(ROOT, 'backend')
  const logFile = backendLogPath()
  let logFd: number | 'ignore' = 'ignore'
  try {
    logFd = fs.openSync(logFile, 'a')
    fs.writeSync(logFd, `\n[${new Date().toISOString()}] spawn ${py} ${args.join(' ')}\n`)
  } catch {
    logFd = 'ignore'
  }

  pyProc = spawn(py, args, {
    cwd,
    windowsHide: true,
    stdio: ['ignore', logFd, logFd],
    detached: false,
    env: {
      ...process.env,
      PYTHONUTF8: '1',
      PYTHONPATH: app.isPackaged ? cwd : path.join(ROOT, 'backend'),
    },
  })
  pyProc.unref?.()
  pyProc.on('exit', (code) => {
    pyProc = null
    if (!quitting) console.error('backend exited', code)
  })
}

function stopBackend() {
  if (!pyProc) return
  const pid = pyProc.pid
  try {
    if (process.platform === 'win32' && pid) {
      // 子プロセスごと落として 8787 を解放する
      execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' })
    } else {
      pyProc.kill()
    }
  } catch {
    try {
      pyProc.kill()
    } catch {
      // ignore
    }
  }
  pyProc = null
}

/** トレイ常駐でも確実に終了する */
function forceQuitApp() {
  quitting = true
  stopBackend()
  try {
    tray?.destroy()
  } catch {
    // ignore
  }
  tray = null
  for (const win of BrowserWindow.getAllWindows()) {
    try {
      win.removeAllListeners('close')
      win.destroy()
    } catch {
      // ignore
    }
  }
  // quit() だとトレイ常駐で残ることがあるため exit で落とす
  app.exit(0)
}

function waitForServer(timeoutMs = 45000): Promise<void> {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(`${BASE}/api/health`, (res) => {
        res.resume()
        if (res.statusCode === 200) resolve()
        else if (Date.now() - start > timeoutMs) reject(new Error('timeout'))
        else setTimeout(tick, 400)
      })
      req.on('error', () => {
        if (Date.now() - start > timeoutMs) reject(new Error('timeout'))
        else setTimeout(tick, 400)
      })
    }
    tick()
  })
}

function resolveAppIconPath(): string | null {
  const candidates = [
    path.join(ROOT, 'build', 'icon.ico'),
    path.join(ROOT, 'assets', 'icon.ico'),
    path.join(ROOT, 'build', 'icon.png'),
    path.join(ROOT, 'assets', 'icon.png'),
  ]
  if (app.isPackaged) {
    candidates.unshift(
      path.join(process.resourcesPath, 'build', 'icon.ico'),
      path.join(process.resourcesPath, 'icon.ico'),
      path.join(process.resourcesPath, 'icon.png'),
    )
  }
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate
  }
  return null
}

function loadAppIcon(): Electron.NativeImage {
  const iconPath = resolveAppIconPath()
  if (iconPath) {
    try {
      const image = nativeImage.createFromPath(iconPath)
      if (!image.isEmpty()) return image
    } catch {
      // fall through
    }
  }
  // 最終手段の小さなプレースホルダ
  const png = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAvklEQVQ4T2NkYGD4z0ABYBzVMKoBBgxgYGBg+M+AARAHGBgYGBgYGBgY/jMwMDAwMDAw/GdgYGBgYGBg+M/AwMDAwMDAwPCfgYGBgYGBgYH/PwMDAwMDAwPDfwYGBgYGBgaG/wwMDAwMDAwM/xkYGBgYGBgY/jMwMDAwMDAw/GdgYGBgYGBg+M/AwMDAwMDAwPCfgYGBgYGBgYH/PwMDAwMDAwPDfwYGBgYGBgaG/wwMDAwMDAwM/xkYGBgYGBgY/jMwMDAwMDAw/GdgYGBgYGBg+M8AAK0aAxX1m7uVAAAAAElFTkSuQmCC',
    'base64',
  )
  try {
    return nativeImage.createFromBuffer(png)
  } catch {
    return nativeImage.createEmpty()
  }
}

function trayIcon(): Electron.NativeImage {
  const icon = loadAppIcon()
  if (icon.isEmpty()) return icon
  // トレイは小さめの方が見やすい
  try {
    return icon.resize({ width: 16, height: 16, quality: 'best' })
  } catch {
    return icon
  }
}

function isAdmin(): boolean {
  if (process.platform !== 'win32') return true
  try {
    execSync('net session', { stdio: 'ignore' })
    return true
  } catch {
    return false
  }
}

type ElevateMarker = { oldPid: number; at: number; viteUrl?: string }

function writeElevateMarker(oldPid: number, viteUrl?: string) {
  const data: ElevateMarker = { oldPid, at: Date.now(), viteUrl }
  fs.writeFileSync(elevateMarkerPath(), JSON.stringify(data), 'utf8')
  try {
    fs.unlinkSync(elevateReadyPath())
  } catch {
    // ignore
  }
  if (viteUrl) persistViteDevServerUrl(viteUrl)
}

function readElevateMarker(): ElevateMarker | null {
  try {
    const raw = JSON.parse(fs.readFileSync(elevateMarkerPath(), 'utf8')) as ElevateMarker
    if (!raw?.oldPid || !raw?.at) return null
    // 2分以上前のマーカーは無視
    if (Date.now() - raw.at > 120000) return null
    return raw
  } catch {
    return null
  }
}

function clearElevateMarker() {
  for (const p of [elevateMarkerPath(), elevateReadyPath()]) {
    try {
      fs.unlinkSync(p)
    } catch {
      // ignore
    }
  }
}

function markElevateReady() {
  fs.writeFileSync(elevateReadyPath(), String(Date.now()), 'utf8')
}

function isElevateReady(): boolean {
  try {
    const t = Number(fs.readFileSync(elevateReadyPath(), 'utf8'))
    return Number.isFinite(t) && Date.now() - t < 120000
  } catch {
    return false
  }
}

function killProcessTree(pid: number) {
  if (!pid || pid === process.pid) return
  try {
    if (process.platform === 'win32') {
      execSync(`taskkill /PID ${pid} /T /F`, { stdio: 'ignore' })
    } else {
      process.kill(pid, 'SIGTERM')
    }
  } catch {
    // 既に終了済みなど
  }
}

/**
 * 管理者で起動し、シングルインスタンスロック取得後に呼ぶ。
 * ready を書いて旧プロセスを終了する（旧側は ready までウィンドウを維持する）。
 */
function takeoverFromNonElevatedPredecessor() {
  if (!isAdmin()) return
  const marker = readElevateMarker()
  if (!marker) return

  // UI 用 Vite URL を先に復元（マーカー削除前）
  if (marker.viteUrl) {
    persistViteDevServerUrl(marker.viteUrl)
  }

  // ロック取得後にだけ ready を書く（早すぎる ready だと旧が先に落ちて昇格側が起動失敗する）
  markElevateReady()
  killProcessTree(marker.oldPid)

  try {
    fs.unlinkSync(elevateMarkerPath())
  } catch {
    // ignore
  }
}

/**
 * Electron 自体を UAC 付きで起動する。
 * キャンセルすると exit 1。許可するとプロセス生成直後に exit 0（アプリ終了は待たない）。
 */
function spawnElevatedElectron(): {
  waitExit: Promise<number>
  scriptPath: string
} {
  const exe = process.execPath
  const workDir = ROOT
  const viteUrl = getViteDevServerUrl() ?? ''
  persistViteDevServerUrl(viteUrl || undefined)

  const baseArgs = process.argv
    .slice(1)
    .filter((a) => a !== '--no-elevate' && !a.startsWith(VITE_ARG_PREFIX))
  const electronArgs =
    baseArgs.length > 0 ? [...baseArgs] : app.isPackaged ? [] : ['.']
  if (viteUrl) {
    electronArgs.push(`${VITE_ARG_PREFIX}${viteUrl}`)
  }

  const stamp = `${process.pid}-${Date.now()}`
  const scriptPath = path.join(elevateStateDir(), `elevate-runas-${stamp}.ps1`)

  // Start-Process -ArgumentList 配列は URL を壊しやすいので、1本の文字列にする
  const argString = electronArgs
    .map((a) => {
      if (/[\s"]/.test(a)) return `"${a.replace(/"/g, '\\"')}"`
      return a
    })
    .join(' ')

  const script = `
$ErrorActionPreference = 'Stop'
try {
  $exe = ${quoteForPsSingle(exe)}
  $workDir = ${quoteForPsSingle(workDir)}
  $argString = ${quoteForPsSingle(argString)}
  if ($argString.Length -gt 0) {
    Start-Process -FilePath $exe -WorkingDirectory $workDir -Verb RunAs -ArgumentList $argString
  } else {
    Start-Process -FilePath $exe -WorkingDirectory $workDir -Verb RunAs
  }
  exit 0
} catch {
  exit 1
}
`.trim()

  fs.writeFileSync(scriptPath, script, 'utf8')

  const waitExit = new Promise<number>((resolve) => {
    const child = spawn(
      'powershell.exe',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', scriptPath],
      { windowsHide: true, stdio: 'ignore' },
    )
    child.on('error', () => resolve(1))
    child.on('exit', (code) => resolve(code ?? 1))
  })

  return { waitExit, scriptPath }
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

async function waitForElevateReady(timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (isElevateReady()) return true
    await sleep(150)
  }
  return false
}

/**
 * 管理者として立ち上げ直す。
 * 旧ウィンドウは、管理者プロセスがロック取得＆ ready を書くまで閉じない。
 */
async function elevateAndQuit(): Promise<boolean> {
  if (process.platform !== 'win32') return false
  if (isAdmin()) return true

  stopBackend()
  const viteUrl = normalizeDevUrl(getViteDevServerUrl() || 'http://127.0.0.1:5173/')
  persistViteDevServerUrl(viteUrl)

  // 管理者プロセスは開発サーバーに繋がらないことがあるため、先に UI を dist へ書き出す
  if (!app.isPackaged) {
    const built = await buildRendererForElevation()
    if (!built) {
      console.error('elevation aborted: renderer dist missing')
      startBackend()
      return false
    }
  }

  writeElevateMarker(process.pid, viteUrl)
  // 先にロックを外す（昇格プロセスが 2 つ目扱いで即終了するのを防ぐ）
  app.releaseSingleInstanceLock()

  let scriptPath = ''
  try {
    const spawned = spawnElevatedElectron()
    scriptPath = spawned.scriptPath
    const code = await spawned.waitExit

    if (code !== 0) {
      // UAC キャンセルなど
      clearElevateMarker()
      app.requestSingleInstanceLock()
      startBackend()
      return false
    }

    // 管理者 Electron が本起動して ready を書くまで待つ（ここで初めて旧を閉じてよい）
    const ready = await waitForElevateReady(90000)
    if (ready) {
      try {
        mainWindow?.hide()
      } catch {
        // ignore
      }
      // 昇格側の taskkill と二重でもよいので、残っていれば自分でも終了
      setTimeout(() => forceQuitApp(), 100)
      return true
    }

    clearElevateMarker()
    app.requestSingleInstanceLock()
    startBackend()
    return false
  } catch (error) {
    console.error('elevation failed', error)
    clearElevateMarker()
    app.requestSingleInstanceLock()
    startBackend()
    return false
  } finally {
    if (scriptPath) {
      try {
        fs.unlinkSync(scriptPath)
      } catch {
        // ignore
      }
    }
  }
}

function probeHttpUrl(url: string, timeoutMs = 1000): Promise<boolean> {
  return new Promise((resolve) => {
    try {
      const req = http.get(url, (res) => {
        res.resume()
        resolve((res.statusCode ?? 500) < 500)
      })
      req.on('error', () => resolve(false))
      req.setTimeout(timeoutMs, () => {
        req.destroy()
        resolve(false)
      })
    } catch {
      resolve(false)
    }
  })
}

async function buildRendererForElevation(): Promise<boolean> {
  const distIndex = path.join(ROOT, 'dist', 'index.html')
  try {
    const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx'
    await execFileAsync(
      npx,
      ['vite', 'build', '--config', 'vite.renderer.config.ts'],
      {
        cwd: ROOT,
        windowsHide: true,
        timeout: 180000,
        env: { ...process.env },
      },
    )
    return fs.existsSync(distIndex)
  } catch (error) {
    console.error('renderer build for elevation failed', error)
    return fs.existsSync(distIndex)
  }
}

function normalizeDevUrl(url: string): string {
  return url.replace('://localhost', '://127.0.0.1')
}

async function loadRenderer(win: BrowserWindow) {
  const distIndex = path.join(ROOT, 'dist', 'index.html')

  // Windows では管理者プロセスから非管理者の Vite に繋がらないことがある。
  // その場合はビルド済み UI（dist）をファイルとして開く。
  if (isAdmin() && !app.isPackaged && fs.existsSync(distIndex)) {
    try {
      await win.loadFile(distIndex)
      return
    } catch (error) {
      console.error('failed to load dist as admin', error)
    }
  }

  const candidates: string[] = []
  const known = getViteDevServerUrl()
  if (known) {
    candidates.push(normalizeDevUrl(known))
    if (!candidates.includes(known)) candidates.push(known)
  }
  if (!app.isPackaged) {
    for (const port of [5173, 5174, 5175, 5176]) {
      const url = `http://127.0.0.1:${port}/`
      if (!candidates.includes(url)) candidates.push(url)
    }
  }

  for (const url of candidates) {
    if (!(await probeHttpUrl(url))) continue
    try {
      await win.loadURL(url)
      persistViteDevServerUrl(url)
      return
    } catch (error) {
      console.error('failed to load vite url', url, error)
    }
  }

  if (fs.existsSync(distIndex)) {
    try {
      await win.loadFile(distIndex)
      return
    } catch (error) {
      console.error('failed to load dist index', error)
    }
  }

  const message =
    '画面の読み込みに失敗しました。ターミナルで npm run dev が動いているか確認して、もう一度開き直してください。'
  await win.loadURL(
    `data:text/html;charset=utf-8,${encodeURIComponent(
      `<!doctype html><html><body style="font-family:Segoe UI,sans-serif;padding:40px;background:#eef3f7;color:#1c2430"><h2>PCの健康チェッカー</h2><p>${message}</p></body></html>`,
    )}`,
  )
}

function createWindow() {
  const iconPath = resolveAppIconPath()
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 980,
    minHeight: 680,
    title: APP_TITLE,
    backgroundColor: '#eef3f7',
    autoHideMenuBar: true,
    show: false,
    ...(iconPath ? { icon: iconPath } : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  void loadRenderer(mainWindow)

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.on('close', (e) => {
    if (!quitting) {
      e.preventDefault()
      mainWindow?.hide()
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function createTray() {
  tray = new Tray(trayIcon())
  tray.setToolTip(APP_TITLE)
  const menu = Menu.buildFromTemplate([
    {
      label: 'ウィンドウを表示',
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      },
    },
    {
      label: '今すぐスキャン',
      click: () => {
        http
          .request(`${BASE}/api/scan`, { method: 'POST' }, (res) => res.resume())
          .on('error', () => {})
          .end()
      },
    },
    {
      label: '管理者として再起動',
      click: () => {
        void (async () => {
          if (isAdmin()) return
          const ok = await elevateAndQuit()
          if (!ok) {
            await dialog.showMessageBox({
              type: 'warning',
              title: APP_TITLE,
              message: '管理者権限は許可されませんでした。',
              detail:
                'もう一度「管理者として再起動」を押すか、このまま非管理者で利用できます。',
            })
          }
        })()
      },
    },
    { type: 'separator' },
    {
      label: '終了',
      click: () => {
        forceQuitApp()
      },
    },
  ])
  tray.setContextMenu(menu)
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

function registerIpc() {
  ipcMain.handle('desktop:is-admin', async () => isAdmin())

  ipcMain.handle('desktop:elevate', async () => {
    if (isAdmin()) return true

    const ok = await elevateAndQuit()
    if (ok) return true

    await dialog.showMessageBox({
      type: 'warning',
      title: APP_TITLE,
      message: '管理者権限は許可されませんでした。',
      detail:
        'もう一度「管理者として再起動」を押すか、このまま非管理者で利用できます（SMART が不完全なことがあります）。',
    })
    return false
  })

  ipcMain.handle('desktop:openPath', async (_event, targetPath: string) => {
    if (!targetPath || String(targetPath).includes('__other__')) {
      await dialog.showMessageBox({
        type: 'info',
        title: APP_TITLE,
        message: 'この項目はまとめ表示のため、直接開けません。',
      })
      return 'skipped'
    }
    const result = await shell.openPath(String(targetPath))
    if (result) {
      dialog.showErrorBox('開けませんでした', result)
    }
    return result
  })

  ipcMain.handle('desktop:getBackendUrl', async () => BASE)
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  // トレイ常駐の quit() だと残ることがあるため exit
  app.exit(0)
} else {
  // 管理者で起動した側が、昇格前の旧プロセスを必ず落とす
  takeoverFromNonElevatedPredecessor()

  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })

  app.whenReady().then(async () => {
    registerIpc()
    createTray()
    createWindow()
    startBackend()

    try {
      await waitForServer(45000)
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.show()
        mainWindow.focus()
      }
    } catch (err) {
      console.error(err)
      if (Notification.isSupported()) {
        new Notification({
          title: APP_TITLE,
          body: app.isPackaged
            ? 'バックエンドの起動に失敗しました。トレイから一度終了して開き直してください。'
            : 'バックエンドの起動に失敗しました。backend/.venv や Python 環境を確認してください。',
        }).show()
      }
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.show()
        mainWindow.focus()
      }
    }
  })

  app.on('before-quit', () => {
    quitting = true
    stopBackend()
    try {
      tray?.destroy()
    } catch {
      // ignore
    }
    tray = null
  })

  // トレイ常駐のため、ウィンドウを全部閉じても app.quit() しない
  app.on('window-all-closed', () => {})
}
