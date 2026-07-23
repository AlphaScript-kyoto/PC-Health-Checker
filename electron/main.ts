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
  try {
    pyProc.kill()
  } catch {
    // ignore
  }
  pyProc = null
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

/**
 * UAC で管理者として同じアプリを起動する。
 * Start-Process -Verb RunAs だと環境変数が消えるため、
 * 「昇格した PowerShell の中」で VITE URL をセットしてから Electron を起動する。
 */
async function relaunchElevated(): Promise<boolean> {
  if (process.platform !== 'win32') return false
  if (isAdmin()) return true

  const exe = process.execPath
  const workDir = ROOT
  const viteUrl = getViteDevServerUrl() ?? ''

  // vite-plugin-electron 開発時: ['.', '--no-elevate'] など
  const baseArgs = process.argv
    .slice(1)
    .filter((a) => a !== '--no-elevate' && !a.startsWith(VITE_ARG_PREFIX))
  const electronArgs =
    baseArgs.length > 0 ? [...baseArgs] : app.isPackaged ? [] : ['.']
  if (viteUrl) {
    electronArgs.push(`${VITE_ARG_PREFIX}${viteUrl}`)
  }

  const argListPs = electronArgs.map(quoteForPsSingle).join(', ')
  const elevatedWorker = `
$ErrorActionPreference = 'Stop'
$workDir = ${quoteForPsSingle(workDir)}
Set-Location -LiteralPath $workDir
${viteUrl ? `$env:VITE_DEV_SERVER_URL = ${quoteForPsSingle(viteUrl)}` : ''}
$exe = ${quoteForPsSingle(exe)}
$argList = @(${argListPs})
if ($argList.Count -gt 0) {
  Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $workDir
} else {
  Start-Process -FilePath $exe -WorkingDirectory $workDir
}
`.trim()

  const workerPath = path.join(
    os.tmpdir(),
    `pchc-elevated-${process.pid}-${Date.now()}.ps1`,
  )
  const launcherPath = path.join(
    os.tmpdir(),
    `pchc-elevate-launch-${process.pid}-${Date.now()}.ps1`,
  )
  const launcher = `
$ErrorActionPreference = 'Stop'
$p = Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -PassThru -WindowStyle Hidden -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',${quoteForPsSingle(workerPath)})
if ($null -eq $p) { exit 1 }
exit $p.ExitCode
`.trim()

  try {
    fs.writeFileSync(workerPath, elevatedWorker, 'utf8')
    fs.writeFileSync(launcherPath, launcher, 'utf8')
    await execFileAsync(
      'powershell.exe',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', launcherPath],
      { windowsHide: true },
    )
    return true
  } catch (error) {
    console.error('elevation failed', error)
    return false
  } finally {
    for (const p of [workerPath, launcherPath]) {
      try {
        fs.unlinkSync(p)
      } catch {
        // ignore
      }
    }
  }
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
          app.releaseSingleInstanceLock()
          const ok = await relaunchElevated()
          if (ok) {
            quitting = true
            stopBackend()
            app.quit()
          } else {
            app.requestSingleInstanceLock()
          }
        })()
      },
    },
    { type: 'separator' },
    {
      label: '終了',
      click: () => {
        quitting = true
        app.quit()
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
  ipcMain.handle('desktop:elevate', async () => {
    if (isAdmin()) return true

    // 先にロックを外さないと、昇格プロセスが「2つ目」扱いですぐ終了する
    app.releaseSingleInstanceLock()

    const ok = await relaunchElevated()
    if (ok) {
      quitting = true
      stopBackend()
      app.quit()
      return true
    }

    app.requestSingleInstanceLock()
    await dialog.showMessageBox({
      type: 'warning',
      title: APP_TITLE,
      message: '管理者権限が許可されませんでした。',
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
  app.quit()
} else {
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
  })

  // トレイ常駐のため、ウィンドウを全部閉じても app.quit() しない
  app.on('window-all-closed', () => {})
}
