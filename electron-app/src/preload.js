// Preload script — runs in a sandboxed context before the renderer loads.
// Use contextBridge to expose a safe, minimal API if needed later.
// For Phase 1 the renderer communicates directly via WebSocket, so
// preload only needs to exist for Forge's build pipeline.

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  toggleMainWindow: () => ipcRenderer.send('toggle-main-window'),
});
