const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

app.commandLine.appendSwitch('enable-webgl');
app.commandLine.appendSwitch('ignore-gpu-blacklist');
app.commandLine.appendSwitch('disable-gpu-vsync');

let mainWindow = null;
let live2dWindow = null;
let tray = null;
let appIconPath = null;
const isDev = !!MAIN_WINDOW_VITE_DEV_SERVER_URL;

// Generate a simple app icon (32x32 PNG) at startup so the taskbar shows it
function createAppIcon() {
  const size = 64;
  const canvas = Buffer.alloc(size * size * 4);
  const cx = size / 2, cy = size / 2, r = size / 2 - 2;
  const r2 = r * r;

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - cx, dy = y - cy;
      const dist2 = dx * dx + dy * dy;
      const idx = (y * size + x) * 4;
      if (dist2 <= r2) {
        // Gradient circle: purple-blue theme
        const t = dist2 / r2;
        canvas[idx]     = Math.round(100 + 55 * t);   // R
        canvas[idx + 1] = Math.round(60 + 90 * t);    // G
        canvas[idx + 2] = Math.round(220 - 60 * t);   // B
        canvas[idx + 3] = 255;                         // A
      } else {
        canvas[idx] = canvas[idx + 1] = canvas[idx + 2] = 0;
        canvas[idx + 3] = 0;
      }
    }
  }

  const img = nativeImage.createFromBuffer(canvas, { width: size, height: size });
  const pngBuffer = img.toPNG();
  const iconDir = path.join(app.getPath('userData'), 'icons');
  fs.mkdirSync(iconDir, { recursive: true });
  const iconPath = path.join(iconDir, 'app_icon.png');
  fs.writeFileSync(iconPath, pngBuffer);
  return iconPath;
}

function loadPage(win, query = '') {
  if (isDev) {
    win.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL + query);
  } else {
    win.loadFile(path.join(__dirname, '../renderer/main_window/index.html'), {
      query: query.startsWith('?') ? query.slice(1) : undefined,
    });
  }
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 780,
    minWidth: 900,
    minHeight: 550,
    title: 'AI 桌面助理',
    icon: appIconPath,
    backgroundColor: '#1a1a2e',
    show: false, // start hidden
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webgl: true,
      experimentalFeatures: true,
    },
  });

  loadPage(mainWindow);

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

function createLive2dWindow() {
  live2dWindow = new BrowserWindow({
    width: 400,
    height: 650,
    x: 1200,
    y: 100,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    hasShadow: false,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webgl: true,
      experimentalFeatures: true,
    },
  });

  loadPage(live2dWindow, '?mode=live2d');

  // Open DevTools so we can see animation list in Console
  live2dWindow.webContents.openDevTools({ mode: 'detach' });

  // screen-saver level keeps the pet above screenshot overlays
  live2dWindow.setAlwaysOnTop(true, 'screen-saver');

  // Prevent accidental close (e.g. by screenshot overlays)
  live2dWindow.on('close', (event) => {
    if (!app.isQuitting) event.preventDefault();
  });
}

// IPC: live2d window click → toggle main window
ipcMain.on('toggle-main-window', () => {
  if (!mainWindow) return;
  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
});

// IPC: live2d window drag → move window
ipcMain.on('move-live2d-window', (_event, dx, dy) => {
  if (!live2dWindow) return;
  const [x, y] = live2dWindow.getPosition();
  live2dWindow.setPosition(x + dx, y + dy);
});

// IPC: main window → main process → live2d window (emotion relay)
ipcMain.on('set-avatar-emotion', (_event, emotion) => {
  if (live2dWindow && !live2dWindow.isDestroyed()) {
    live2dWindow.webContents.send('avatar-emotion', emotion);
  }
});

function createTray() {
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAOElEQVQ4T2NkYPj/n4EBBJgYKAQMowYM/ccCkA0YNoDmYf8/A8P/fwwMDAz/GRj+M1BmAAOhCgBWuQYrnC6FJgAAAABJRU5ErkJggg=='
  );

  tray = new Tray(icon);
  tray.setToolTip('AI 桌面助理');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示窗口',
      click: () => {
        if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
      },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => { app.isQuitting = true; app.quit(); },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
  });
}

app.whenReady().then(() => {
  appIconPath = createAppIcon();
  createMainWindow();
  createLive2dWindow();
  createTray();

  app.on('activate', () => {
    if (mainWindow) mainWindow.show();
  });
});

app.on('window-all-closed', () => {});
app.on('before-quit', () => { app.isQuitting = true; });
