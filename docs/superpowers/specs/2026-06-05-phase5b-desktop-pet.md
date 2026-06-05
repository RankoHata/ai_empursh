# 阶段 5b：桌面宠物模式 — 设计文档

**日期**：2026-06-05
**状态**：完成

---

## 1. 目标

将 Live2D 角色变为独立的桌面宠物——无边框、透明背景、浮动在桌面上。
点击宠物弹出主窗口，拖拽宠物可移动位置。

---

## 2. 架构

```
┌──────────────────────┐    点击/拖拽     ┌──────────────────────────┐
│   Live2D 宠物窗口     │ ←──────────→    │   主窗口（聊天/笔记等）   │
│   400×600 无边框      │   IPC 通信       │   正常应用界面            │
│   透明背景            │                  │   启动时隐藏              │
│   始终置顶            │                  │                          │
└──────────────────────┘                  └──────────────────────────┘
```

### 双窗口设计

| 窗口 | 类型 | 尺寸 | 特性 |
|------|------|------|------|
| `live2dWindow` | 桌面宠物 | 400×600 | `transparent: true`, `frame: false`, `alwaysOnTop: true`, `skipTaskbar: true` |
| `mainWindow` | 主应用 | 1320×780 | 标准窗口，启动时 `show: false` |

### 进程间通信

| 方向 | IPC Channel | 说明 |
|------|-------------|------|
| 渲染进程→主进程 | `toggle-main-window` | 点击宠物 → 弹出/隐藏主窗口 |
| 渲染进程→主进程 | `move-live2d-window` | 拖拽宠物 → 移动宠物窗口位置 |

### 页面路由

两个窗口加载同一 HTML，通过 URL 参数区分：

- `mainWindow` → 加载 `index.html`（完整应用界面）
- `live2dWindow` → 加载 `index.html?mode=live2d`（仅 Live2D 角色）

App.jsx 检测 `window.location.search.includes('mode=live2d')` 决定渲染内容。

### 窗口尺寸与模型适配

**问题：** Live2D 模型的 `.moc3` 画布包含透明边距，角色实际可见区域（~250×360）远小于画布（480×960）。直接缩小窗口会让角色跟着变小。

**解决：** 保持高分辨率画布（480×960），通过 CSS 缩放+裁剪：

```css
/* 宠物窗口容器：裁剪溢出 */
.live2d-only-container .live2d-container {
  width: 100%; height: 100%;
  overflow: hidden;          /* 裁掉画布边距 */
}

/* 高分辨率画布：居中 + 放大填满小窗口 */
.live2d-only-container .live2d-canvas {
  position: absolute;
  left: 50%; top: 50%;
  transform: translate(-50%, -50%) scale(1.5);
}
```

**原理：** 画布 480×960 居中放在 250×360 窗口内，`scale(1.5)` 放大 1.5 倍后，画布等效于 720×1440，窗口只显示中心 250×360 → 角色填满窗口，死区被裁掉。角色清晰度不变（高分辨率下采样）。

**注意：** 宠物模式的 CSS 规则独立于侧边栏——侧边栏有自己的 `scale(1.5)` 规则（`.live2d-sidebar .live2d-canvas`），两者不冲突。

---

## 3. JS 拖拽实现

### 为什么不用 CSS `-webkit-app-region: drag`？

Electron 的 CSS drag 区域会拦截所有鼠标事件（click、dblclick、contextmenu），导致无法在宠物身上触发交互。JS 实现既可拖又可点。

### 实现原理

```
mousedown → 记录起始位置，注册 mousemove/mouseup 监听
  │
mousemove → 计算位移 delta，IPC 发送 move-live2d-window(dx, dy)
  │              主进程执行 live2dWindow.setPosition(x+dx, y+dy)
  │
mouseup → 移除监听。若总位移 < 2px → 判定为点击，触发 toggle-main-window
```

### 关键代码（App.jsx）

```jsx
const onPetMouseDown = (e) => {
  petDragRef.current = { startX: e.screenX, startY: e.screenY, moved: false };
  petClickRef.current = { x: e.screenX, y: e.screenY };

  const onMove = (ev) => {
    const dx = ev.screenX - petClickRef.current.x;
    const dy = ev.screenY - petClickRef.current.y;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) petDragRef.current.moved = true;
    window.electronAPI?.moveLive2dWindow(dx, dy);
    petClickRef.current = { x: ev.screenX, y: ev.screenY };
  };

  const onUp = () => {
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
    if (!petDragRef.current.moved) toggleMain();
  };

  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
};
```

---

## 4. 涉及文件

| 文件 | 改动 |
|------|------|
| `electron-app/src/main.js` | 新增 `live2dWindow` 创建 + `move-live2d-window` IPC + `toggle-main-window` IPC |
| `electron-app/src/preload.js` | 新增 `toggleMainWindow()` 和 `moveLive2dWindow()` 暴露给渲染进程 |
| `electron-app/src/renderer/App.jsx` | 新增 `isLive2DOnly` 路由 + JS 拖拽逻辑 |
| `electron-app/src/renderer/main.jsx` | 新增 `live2d-pet` CSS class 设置 |
| `electron-app/src/renderer/App.css` | 新增 `.live2d-only-container` 样式（透明、无拖拽区域） |
| `electron-app/src/renderer/components/Live2DAvatar.jsx` | 无改动（纯展示组件） |

---

## 5. 交互设计

| 操作 | 效果 |
|------|------|
| 点击宠物（无移动） | 弹出/隐藏主聊天窗口 |
| 拖拽宠物（移动 > 2px） | 移动宠物窗口位置 |
| 关闭主窗口 | 主窗口隐藏（非退出），宠物仍在桌面 |
| 系统托盘 → 显示窗口 | 弹出主窗口 |
| 系统托盘 → 退出 | 关闭所有窗口并退出 |

---

## 6. 陷阱与注意事项

| # | 问题 | 原因 | 解决 |
|---|------|------|------|
| 1 | CSS drag 区域无法点击 | `-webkit-app-region: drag` 拦截所有鼠标事件 | 改用 JS mousedown/mousemove 模拟拖拽 |
| 2 | 右键冲突系统菜单 | 右键在 Windows 上触发系统窗口菜单 | 放弃右键，改用点击 |
| 3 | 双击不生效 | drag 区域同样拦截双击 | JS 模拟拖拽方案天然支持 |
| 4 | 宠物窗口任务栏可见 | 默认 BrowserWindow 显示在任务栏 | `skipTaskbar: true` |
| 5 | 宠物窗口关闭时退出应用 | `window-all-closed` 事件 | 不调用 `app.quit()`，改为不处理 |
| 6 | 主窗口关闭时退出 | 默认行为 | `mainWindow.on('close')` 改为 `hide()` |
| 7 | 缩小窗口后角色跟着变小 | 画布缩小导致分辨率不足 | 保持 480×960 画布 + CSS `overflow:hidden` + `scale(1.5)` 裁剪边距 |
| 8 | 宠物和侧边栏样式互相影响 | 共用 `.live2d-canvas` 选择器 | 用父选择器隔离：`.live2d-only-container .live2d-canvas` vs `.live2d-sidebar .live2d-canvas` |

---

## 7. 与主应用的协同

主窗口 App.jsx 中，正常模式（非 `mode=live2d`）保持全部功能不变：

- 聊天 / 笔记 / 设置面板
- Live2D 侧边栏（缩放 1.5x + 2:3 比例）
- 语音交互
- 系统托盘

桌面宠物模式（`mode=live2d`）只渲染 Live2DAvatar + JS 拖拽逻辑，不加载 WebSocket、聊天等。
