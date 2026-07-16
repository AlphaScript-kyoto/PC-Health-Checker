const { app, BrowserWindow, Tray, Menu, nativeImage, shell, Notification } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");
const fs = require("fs");

const ROOT = path.resolve(__dirname, "..");
const HOST = "127.0.0.1";
const PORT = 8787;
const BASE = `http://${HOST}:${PORT}`;

let mainWindow = null;
let tray = null;
let pyProc = null;
let quitting = false;

function pythonPath() {
  // Packaged: Electron resources/backend/pc-health-backend.exe
  if (app.isPackaged) {
    const packaged = path.join(process.resourcesPath, "backend", "pc-health-backend.exe");
    if (fs.existsSync(packaged)) return packaged;
  }
  // Dev: prefer live Python so UI/catalog edits apply without rebuilding the exe
  const pythonw = path.join(ROOT, ".venv", "Scripts", "pythonw.exe");
  if (fs.existsSync(pythonw)) return pythonw;
  const win = path.join(ROOT, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(win)) return win;

  const localBackend = path.join(ROOT, "dist-backend", "pc-health-backend", "pc-health-backend.exe");
  if (fs.existsSync(localBackend)) return localBackend;
  return "pythonw";
}

function backendArgs() {
  const py = pythonPath();
  if (py.toLowerCase().endsWith("pc-health-backend.exe")) {
    return [];
  }
  return [path.join(ROOT, "app", "main.py"), "--headless"];
}

function backendLogPath() {
  const base = app.isPackaged
    ? path.join(process.env.LOCALAPPDATA || ROOT, "PCHealth")
    : path.join(ROOT, "app", "data");
  try {
    fs.mkdirSync(base, { recursive: true });
  } catch (_) {}
  return path.join(base, "backend-launch.log");
}

function startBackend() {
  const py = pythonPath();
  const args = backendArgs();
  const cwd = app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : ROOT;
  const logFile = backendLogPath();
  let logFd = "ignore";
  try {
    logFd = fs.openSync(logFile, "a");
    fs.writeSync(
      logFd,
      `\n[${new Date().toISOString()}] spawn ${py} ${args.join(" ")}\n`
    );
  } catch (_) {
    logFd = "ignore";
  }
  pyProc = spawn(py, args, {
    cwd,
    windowsHide: true,
    stdio: ["ignore", logFd, logFd],
    detached: false,
    env: { ...process.env, PYTHONUTF8: "1" },
  });
  pyProc.unref?.();
  pyProc.on("exit", (code) => {
    pyProc = null;
    if (!quitting) {
      console.error("backend exited", code);
    }
  });
}

function stopBackend() {
  if (!pyProc) return;
  try {
    pyProc.kill();
  } catch (_) {}
  pyProc = null;
}

function waitForServer(timeoutMs = 30000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(`${BASE}/api/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) resolve();
        else if (Date.now() - start > timeoutMs) reject(new Error("timeout"));
        else setTimeout(tick, 400);
      });
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) reject(new Error("timeout"));
        else setTimeout(tick, 400);
      });
    };
    tick();
  });
}

function trayIcon() {
  // Simple programmatic icon
  const size = 16;
  const canvas = nativeImage.createEmpty();
  // fallback: use a data URL PNG 16x16 blue circle
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAvklEQVQ4T2NkYGD4z0ABYBzVMKoBBgxgYGBg+M+AARAHGBgYGBgYGBgY/jMwMDAwMDAw/GdgYGBgYGBg+M/AwMDAwMDAwPCfgYGBgYGBgYH/PwMDAwMDAwPDfwYGBgYGBgaG/wwMDAwMDAwM/xkYGBgYGBgY/jMwMDAwMDAw/GdgYGBgYGBg+M/AwMDAwMDAwPCfgYGBgYGBgYH/PwMDAwMDAwPDfwYGBgYGBgaG/wwMDAwMDAwM/xkYGBgYGBgY/jMwMDAwMDAw/GdgYGBgYGBg+M8AAK0aAxX1m7uVAAAAAElFTkSuQmCC",
    "base64"
  );
  try {
    return nativeImage.createFromBuffer(png);
  } catch {
    return canvas;
  }
}

function relaunchElevated() {
  // Dev: execPath is electron.exe — must pass the app folder as argv.
  // Packaged: execPath is PC Health.exe / portable host.
  const exe = process.execPath;
  const appArgs = app.isPackaged ? [] : [__dirname];
  const exeEsc = exe.replace(/'/g, "''");
  const argsEsc = appArgs.map((a) => `'${String(a).replace(/'/g, "''")}'`).join(", ");
  const argClause = appArgs.length ? ` -ArgumentList @(${argsEsc})` : "";
  const workDir = app.isPackaged
    ? path.dirname(exe).replace(/'/g, "''")
    : __dirname.replace(/'/g, "''");

  // Important: release the single-instance lock and quit BEFORE the elevated
  // process claims it. Otherwise the new admin instance exits immediately.
  quitting = true;
  stopBackend();
  try {
    app.releaseSingleInstanceLock();
  } catch (_) {}

  const ps = `
$ErrorActionPreference = 'Stop'
Start-Sleep -Milliseconds 900
try {
  Start-Process -FilePath '${exeEsc}'${argClause} -WorkingDirectory '${workDir}' -Verb RunAs
} catch {
  # UAC cancelled or elevation failed — relaunch without admin so the app is not gone
  Start-Process -FilePath '${exeEsc}'${argClause} -WorkingDirectory '${workDir}'
}
`;
  spawn(
    "powershell.exe",
    ["-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
    { detached: true, stdio: "ignore", windowsHide: true }
  ).unref();

  app.quit();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 800,
    minWidth: 920,
    minHeight: 640,
    title: "PC Health",
    backgroundColor: "#f5f5f7",
    autoHideMenuBar: true,
    show: true,
    icon: path.join(__dirname, "icon.png"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  const bust = Date.now();
  const loadDashboard = () => {
    mainWindow.loadURL(`${BASE}/?v=${bust}`).catch(() => {});
  };

  mainWindow.webContents.on("did-fail-load", (_e, code, desc) => {
    const msg = `バックエンドに接続できませんでした (${code}: ${desc}).<br/>
      少し待ってから再試行します…<br/>
      <button onclick="location.reload()">再読み込み</button>`;
    mainWindow.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(
        `<!doctype html><html><body style="font-family:Segoe UI,sans-serif;padding:40px;background:#f5f5f7;color:#1d1d1f">
        <h1>PC Health</h1><p>${msg}</p></body></html>`
      )}`
    );
    setTimeout(loadDashboard, 2000);
  });

  mainWindow.webContents.session.clearCache().finally(loadDashboard);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("pchealth://elevate")) {
      relaunchElevated();
      return { action: "deny" };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.webContents.on("will-navigate", (e, url) => {
    if (url.startsWith("pchealth://elevate")) {
      e.preventDefault();
      relaunchElevated();
    }
  });

  mainWindow.on("close", (e) => {
    if (!quitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

function createTray() {
  const iconPath = path.join(__dirname, "icon.png");
  tray = new Tray(fs.existsSync(iconPath) ? iconPath : trayIcon());
  tray.setToolTip("PC Health");
  const menu = Menu.buildFromTemplate([
    {
      label: "ウィンドウを表示",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: "今すぐスキャン",
      click: () => {
        http
          .request(`${BASE}/api/scan`, { method: "POST" }, (res) => res.resume())
          .on("error", () => {})
          .end();
      },
    },
    {
      label: "管理者として再起動",
      click: () => relaunchElevated(),
    },
    { type: "separator" },
    {
      label: "終了",
      click: () => {
        quitting = true;
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(menu);
  tray.on("double-click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    createTray();
    createWindow();
    startBackend();
    try {
      await waitForServer(45000);
      if (mainWindow && !mainWindow.isDestroyed()) {
        const bust = Date.now();
        mainWindow.loadURL(`${BASE}/?v=${bust}`).catch(() => {});
        mainWindow.show();
        mainWindow.focus();
      }
    } catch (err) {
      console.error(err);
      if (Notification.isSupported()) {
        new Notification({
          title: "PC Health",
          body: "バックエンドの起動に失敗しました。.venv や Python 環境を確認してください。",
        }).show();
      }
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });

  app.on("before-quit", () => {
    quitting = true;
    stopBackend();
  });

  app.on("window-all-closed", (e) => {
    // keep running in tray on Windows
    e.preventDefault();
  });
}
