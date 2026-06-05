const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const path = require('path');

app.commandLine.appendSwitch('enable-webgl');
app.commandLine.appendSwitch('ignore-gpu-blacklist');
app.commandLine.appendSwitch('disable-gpu-vsync');

let mainWindow = null;
let live2dWindow = null;
let tray = null;
const isDev = !!MAIN_WINDOW_VITE_DEV_SERVER_URL;

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
    width: 250,
    height: 360,
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
  createMainWindow();
  createLive2dWindow();
  createTray();

  app.on('activate', () => {
    if (mainWindow) mainWindow.show();
  });
});

app.on('window-all-closed', () => {});
app.on('before-quit', () => { app.isQuitting = true; });
