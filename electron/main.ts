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
import { spawn, execSync, type ChildProcess } from 'node:child_process'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'

const HOST = '127.0.0.1'
const PORT = 8787
const BASE = `http://${HOST}:${PORT}`
const APP_TITLE = 'PCの健康チェッカー'
const VITE_ARG_PREFIX = '--pchc-vite='
/** 昇格引き継ぎ用（旧PIDの強制終了・成功通知） */
const ELEVATE_MARKER = path.join(os.tmpdir(), 'pchc-elevate-marker.json')
const ELEVATE_READY = path.join(os.tmpdir(), 'pchc-elevate-ready.txt')

/** dist-electron の親 = プロジェクトルート */
const ROOT = path.join(__dirname, '..')

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
  if (fromArg) return fromArg.slice(VITE_ARG_PREFIX.length).trim() || undefined
  return undefined
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

function trayIcon(): Electron.NativeImage {
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

function isAdmin(): boolean {
  if (process.platform !== 'win32') return true
  try {
    execSync('net session', { stdio: 'ignore' })
    return true
  } catch {
    return false
  }
}

type ElevateMarker = { oldPid: number; at: number }

function writeElevateMarker(oldPid: number) {
  const data: ElevateMarker = { oldPid, at: Date.now() }
  fs.writeFileSync(ELEVATE_MARKER, JSON.stringify(data), 'utf8')
  try {
    fs.unlinkSync(ELEVATE_READY)
  } catch {
    // ignore
  }
}

function readElevateMarker(): ElevateMarker | null {
  try {
    const raw = JSON.parse(fs.readFileSync(ELEVATE_MARKER, 'utf8')) as ElevateMarker
    if (!raw?.oldPid || !raw?.at) return null
    // 2分以上前のマーカーは無視
    if (Date.now() - raw.at > 120000) return null
    return raw
  } catch {
    return null
  }
}

function clearElevateMarker() {
  for (const p of [ELEVATE_MARKER, ELEVATE_READY]) {
    try {
      fs.unlinkSync(p)
    } catch {
      // ignore
    }
  }
}

function markElevateReady() {
  fs.writeFileSync(ELEVATE_READY, String(Date.now()), 'utf8')
}

function isElevateReady(): boolean {
  try {
    const t = Number(fs.readFileSync(ELEVATE_READY, 'utf8'))
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
 * 管理者で起動した瞬間に、昇格前プロセスを強制終了する。
 * （旧側の PowerShell -Wait が宙吊りになりウィンドウが残る問題の対策）
 */
function takeoverFromNonElevatedPredecessor() {
  if (!isAdmin()) return
  const marker = readElevateMarker()
  if (!marker) return

  // 先に ready を書き、殺し損ねても旧側が自分で終了できるようにする
  markElevateReady()
  killProcessTree(marker.oldPid)
  killOtherAppElectronProcesses()

  try {
    fs.unlinkSync(ELEVATE_MARKER)
  } catch {
    // ignore
  }
}

/** 同じアプリの他 Electron を落とす（二重起動の掃除） */
function killOtherAppElectronProcesses() {
  if (process.platform !== 'win32') return
  const self = process.pid
  const ps = `
$ErrorActionPreference = 'SilentlyContinue'
Get-CimInstance Win32_Process | Where-Object {
  $_.ProcessId -ne ${self} -and
  (
    ($_.Name -match 'electron|PCHealth|pc-health' -and $_.CommandLine -match 'pc-health-checker') -or
    ($_.CommandLine -match 'pc-health-checker' -and $_.CommandLine -match 'electron')
  )
} | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force
}
`
  try {
    execSync(`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ${JSON.stringify(ps)}`, {
      stdio: 'ignore',
      windowsHide: true,
    })
  } catch {
    // ignore
  }
}

/**
 * UAC ダイアログだけ起動する（完了を待たない）。
 * -Wait すると Electron まで待ち続け、旧ウィンドウが残るため待たない。
 */
function spawnElevatedNoWait(): boolean {
  if (process.platform !== 'win32') return false

  const exe = process.execPath
  const workDir = ROOT
  const viteUrl = getViteDevServerUrl() ?? ''

  const baseArgs = process.argv
    .slice(1)
    .filter((a) => a !== '--no-elevate' && !a.startsWith(VITE_ARG_PREFIX))
  const electronArgs =
    baseArgs.length > 0 ? [...baseArgs] : app.isPackaged ? [] : ['.']
  if (viteUrl) {
    electronArgs.push(`${VITE_ARG_PREFIX}${viteUrl}`)
  }

  const argListPs = electronArgs.map(quoteForPsSingle).join(', ')
  const stamp = `${process.pid}-${Date.now()}`
  const workerPath = path.join(os.tmpdir(), `pchc-elevated-${stamp}.ps1`)

  const elevatedWorker = `
$ErrorActionPreference = 'Stop'
$workDir = ${quoteForPsSingle(workDir)}
Set-Location -LiteralPath $workDir
${viteUrl ? `$env:VITE_DEV_SERVER_URL = ${quoteForPsSingle(viteUrl)}` : ''}
$exe = ${quoteForPsSingle(exe)}
$argList = @(${argListPs})
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.WorkingDirectory = $workDir
$psi.UseShellExecute = $true
if ($argList.Count -gt 0) {
  $psi.Arguments = ($argList | ForEach-Object {
    if ($_ -match '[\\s"]') { '"' + ($_ -replace '"','""') + '"' } else { $_ }
  }) -join ' '
}
[void][System.Diagnostics.Process]::Start($psi)
Remove-Item -LiteralPath ${quoteForPsSingle(workerPath)} -Force -ErrorAction SilentlyContinue
[Environment]::Exit(0)
`.trim()

  try {
    fs.writeFileSync(workerPath, elevatedWorker, 'utf8')
    // UAC だけ出して即座に戻る（-Wait しない）
    const child = spawn(
      'powershell.exe',
      [
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        `Start-Process -FilePath 'powershell.exe' -Verb RunAs -WindowStyle Hidden -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',${quoteForPsSingle(workerPath)})`,
      ],
      { windowsHide: true, stdio: 'ignore', detached: true },
    )
    child.unref()
    return true
  } catch (error) {
    console.error('elevation spawn failed', error)
    try {
      fs.unlinkSync(workerPath)
    } catch {
      // ignore
    }
    return false
  }
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

/**
 * 管理者として立ち上げ直す。
 * 1) 旧PIDをマーカーに書く
 * 2) UAC を待つ（待たない起動）
 * 3) 昇格プロセスが旧PIDを taskkill する
 * 4) ready を確認したら自分も終了（殺し損ね対策）
 */
async function elevateAndQuit(): Promise<boolean> {
  if (isAdmin()) return true

  stopBackend()
  writeElevateMarker(process.pid)
  app.releaseSingleInstanceLock()

  const spawned = spawnElevatedNoWait()
  if (!spawned) {
    clearElevateMarker()
    app.requestSingleInstanceLock()
    startBackend()
    return false
  }

  // 昇格側が ready を書くか、自分が高々殺されるまで待つ
  const deadline = Date.now() + 120000
  while (Date.now() < deadline) {
    if (isElevateReady()) {
      try {
        mainWindow?.hide()
      } catch {
        // ignore
      }
      setTimeout(() => forceQuitApp(), 50)
      return true
    }
    await sleep(200)
  }

  // UAC キャンセル or 失敗
  clearElevateMarker()
  app.requestSingleInstanceLock()
  startBackend()
  return false
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 980,
    minHeight: 680,
    title: APP_TITLE,
    backgroundColor: '#eef3f7',
    autoHideMenuBar: true,
    show: false,
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

  const viteUrl = getViteDevServerUrl()
  if (viteUrl) {
    void mainWindow.loadURL(viteUrl)
  } else {
    void mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

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
