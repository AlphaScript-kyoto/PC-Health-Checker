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

/**
 * UAC で管理者として同じアプリを起動する。
 * Start-Process -Verb RunAs だと環境変数が消えるため、
 * 昇格した PowerShell 内で VITE URL をセットしてから Electron を起動する。
 *
 * 重要: Electron は Process.Start(UseShellExecute) で完全に切り離す。
 * PowerShell の Start-Process -Wait が子の Electron まで待ち続け、
 * 旧ウィンドウが「確認画面を待機中」のまま残るのを防ぐ。
 */
async function relaunchElevated(): Promise<boolean> {
  if (process.platform !== 'win32') return false
  if (isAdmin()) return true

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
  const launcherPath = path.join(os.tmpdir(), `pchc-elevate-launch-${stamp}.ps1`)

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
[Environment]::Exit(0)
`.trim()

  const launcher = `
$ErrorActionPreference = 'Stop'
$p = Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -PassThru -WindowStyle Hidden -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',${quoteForPsSingle(workerPath)})
if ($null -eq $p) { exit 1 }
exit $(if ($null -eq $p.ExitCode) { 0 } else { $p.ExitCode })
`.trim()

  try {
    fs.writeFileSync(workerPath, elevatedWorker, 'utf8')
    fs.writeFileSync(launcherPath, launcher, 'utf8')
    await new Promise<void>((resolve, reject) => {
      const child = spawn(
        'powershell.exe',
        ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', launcherPath],
        { windowsHide: true, stdio: 'ignore' },
      )
      const timer = setTimeout(() => {
        try {
          child.kill()
        } catch {
          // ignore
        }
        reject(new Error('elevation timed out'))
      }, 180000)
      child.on('error', (err) => {
        clearTimeout(timer)
        reject(err)
      })
      child.on('exit', (code) => {
        clearTimeout(timer)
        if (code === 0) resolve()
        else reject(new Error(`elevation exited with code ${code}`))
      })
    })
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

/** 管理者として立ち上げ直す（成功後に旧ウィンドウを必ず閉じる） */
async function elevateAndQuit(): Promise<boolean> {
  if (isAdmin()) return true

  // 先にバックエンドを落とし、昇格側が 8787 を使えるようにする
  stopBackend()
  // ロックを外さないと、昇格プロセスが「2つ目」扱いですぐ終了する
  app.releaseSingleInstanceLock()

  const ok = await relaunchElevated()
  if (!ok) {
    app.requestSingleInstanceLock()
    // 開発中はバックエンドを戻す
    startBackend()
    return false
  }

  // 昇格プロセス起動済み → 旧プロセスは即終了（Vite が再起動しても single-instance で落ちる）
  try {
    mainWindow?.hide()
  } catch {
    // ignore
  }
  setTimeout(() => forceQuitApp(), 300)
  return true
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
