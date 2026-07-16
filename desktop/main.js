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
  // Dev fallback beside repo
  const localBackend = path.join(ROOT, "dist-backend", "pc-health-backend", "pc-health-backend.exe");
  if (fs.existsSync(localBackend)) return localBackend;

  const pythonw = path.join(ROOT, ".venv", "Scripts", "pythonw.exe");
  if (fs.existsSync(pythonw)) return pythonw;
  const win = path.join(ROOT, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(win)) return win;
  return "pythonw";
}

function backendArgs() {
  const py = pythonPath();
  if (py.toLowerCase().endsWith("pc-health-backend.exe")) {
    return [];
  }
  return [path.join(ROOT, "app", "main.py"), "--headless"];
}

function startBackend() {
  const py = pythonPath();
  const args = backendArgs();
  const cwd = app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : ROOT;
  pyProc = spawn(py, args, {
    cwd,
    windowsHide: true,
    stdio: "ignore",
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
  const exe = process.execPath;
  const escaped = exe.replace(/'/g, "''");
  const child = spawn(
    "powershell.exe",
    [
      "-NoProfile",
      "-WindowStyle",
      "Hidden",
      "-Command",
      `Start-Process -FilePath '${escaped}' -Verb RunAs`,
    ],
    { detached: true, stdio: "ignore", windowsHide: true }
  );
  child.unref();
  quitting = true;
  stopBackend();
  setTimeout(() => app.quit(), 400);
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
    show: false,
    icon: path.join(__dirname, "icon.png"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());
  // bust Chromium HTTP cache so UI updates (hero placement etc.) always apply
  const bust = Date.now();
  mainWindow.webContents.session.clearCache().finally(() => {
    mainWindow.loadURL(`${BASE}/?v=${bust}`);
  });

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
    startBackend();
    try {
      await waitForServer();
    } catch (err) {
      console.error(err);
      if (Notification.isSupported()) {
        new Notification({
          title: "PC Health",
          body: "バックエンドの起動に失敗しました。Python環境を確認してください。",
        }).show();
      }
    }
    createWindow();
    createTray();
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
