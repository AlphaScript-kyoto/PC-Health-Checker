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
import path from 'node:path'

const HOST = '127.0.0.1'
const PORT = 8787
const BASE = `http://${HOST}:${PORT}`
const APP_TITLE = 'PCの健康チェッカー'

/** dist-electron の親 = プロジェクトルート */
const ROOT = path.join(__dirname, '..')

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let pyProc: ChildProcess | null = null
let quitting = false

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

function relaunchElevated() {
  const exe = process.execPath
  // Dev: electron.exe にはアプリパスを渡す。Packaged: そのまま起動。
  const appArgs = app.isPackaged ? [] : [ROOT]
  const exeEsc = exe.replace(/'/g, "''")
  const argsEsc = appArgs.map((a) => `'${String(a).replace(/'/g, "''")}'`).join(', ')
  const argClause = appArgs.length ? ` -ArgumentList @(${argsEsc})` : ''
  const workDir = (app.isPackaged ? path.dirname(exe) : ROOT).replace(/'/g, "''")

  quitting = true
  stopBackend()
  try {
    app.releaseSingleInstanceLock()
  } catch {
    // ignore
  }

  const ps = `
$ErrorActionPreference = 'Stop'
Start-Sleep -Milliseconds 900
try {
  Start-Process -FilePath '${exeEsc}'${argClause} -WorkingDirectory '${workDir}' -Verb RunAs
} catch {
  Start-Process -FilePath '${exeEsc}'${argClause} -WorkingDirectory '${workDir}'
}
`
  spawn('powershell.exe', ['-NoProfile', '-WindowStyle', 'Hidden', '-Command', ps], {
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  }).unref()

  app.quit()
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

  const viteUrl = process.env.VITE_DEV_SERVER_URL?.trim()
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
      click: () => relaunchElevated(),
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
    relaunchElevated()
    return true
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
