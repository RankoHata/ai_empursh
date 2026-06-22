# 前端 UI 重新设计 — 详细设计文档

> 版本：v1.0
> 日期：2026-06-23
> 依据：用户反馈 + 高星开源项目调研 (LobeChat, Open WebUI, ChatGPT Desktop)
> 状态：📐 设计完成，待实现

---

## 1. 设计目标

当前界面存在以下问题：
- **StatusBar** "已连接" 常驻占一行 — 无信息价值
- **TabBar** "💬聊天/📝笔记/🔒秘密" 在顶部平铺 — 桌面端 AI 应用不采用标签页模式
- 顶部栏 + 状态栏 + 朗读条 + 通知条 — 多层 banner 堆叠，界面拥挤
- 信息密度低，聊天区被压缩

**目标**：极简、桌面原生体验、聊天为主体、辅助功能滑动可达。

---

## 2. 参考项目调研

| 项目 | Stars | 设计特征 |
|------|-------|---------|
| **LobeChat** | ~50k⭐ | 左侧栏聚合对话+市场+设置，主聊天区最大化 |
| **Open WebUI** | ~45k⭐ | 极简实用主义，几乎没有冗余 chrome |
| **ChatGPT Desktop** | 商业 | 可折叠左侧栏 + 聊天区，零状态指示，设置入菜单 |
| **WardenApp** | 新项目 | 原生 SwiftUI，Apple 风格极致简约 |

**共性**：左侧对话列表 + 右侧聊天区、连接状态隐式化、设置收进深层入口、标签页导航罕见。

---

## 3. 新布局总览

```
┌──────────────┬────────────────────────────────────┬──────────┐
│  侧边栏      │         主内容区                    │  Live2D  │
│  (可折叠)    │                                     │  角色    │
│              │  ┌──────────────────────────────┐   │  (固定)  │
│  ┌────────┐  │  │  断连提示 (仅断连时显示)     │   │          │
│  │ + 新对话│  │  ├──────────────────────────────┤   │          │
│  │ ◀ 收起 │  │  │                              │   │          │
│  ├────────┤  │  │      消息列表 (可滚动)        │   │          │
│  │ 对话 1 │  │  │                              │   │          │
│  │ 对话 2 │  │  │                              │   │          │
│  │ 对话 3 │  │  ├──────────────────────────────┤   │          │
│  │        │  │  │  🎤 [____输入框____] 发送    │   │          │
│  ├────────┤  │  ├──────────────────────────────┤   │          │
│  │ v1.0 ⚙️│  │  │  📝笔记  💬聊天  🔒秘密      │   │          │
│  └────────┘  │  │  ─────── (细线悬停折叠) ────  │   │          │
│              │  └──────────────────────────────┘   │          │
└──────────────┴────────────────────────────────────┴──────────┘
```

### 3.1 尺寸规划

| 区域 | 展开 | 折叠 |
|------|------|------|
| 侧边栏 | 200px | 44px（仅图标列） |
| 主内容区 | flex: 1（自适应） | — |
| Live2D | 320px（固定） | 320px |
| 输入栏 | ~52px | 不变 |
| 底部导航 | ~36px + 3px 分隔线 | 仅 3px 细线 |

---

## 4. 组件变更

### 4.1 新增组件

#### `BottomNavBar`

底部胶囊式导航栏，替代原 `TabBar`。

```
┌─────────────────────────────────────────────┐
│         📝           💬           🔒         │
│        笔记         聊天         秘密        │
│  ────────────────────────────────────────   │ ← 3px 细线（折叠触发器）
└─────────────────────────────────────────────┘
```

**Props**:
- `activePage: 'chat' | 'notes' | 'secret'`
- `onPageChange: (page) => void`
- `collapsed: boolean`
- `onToggleCollapse: () => void`

**交互**:
- 点击图标 → 切换到对应页面（CSS transition 滑动动画）
- 鼠标横向滚轮（Shift+Scroll / 触控板）→ 页面左右切换
- 点击底部细线 / `Ctrl+D` → 折叠导航栏
- 折叠后：导航收缩为 3px 装饰线，鼠标移到屏幕底部 20px 区域时自动滑出展开（类似 macOS Dock 自动隐藏）
- `Ctrl+1` / `Ctrl+2` / `Ctrl+3` → 直接跳转聊天/笔记/秘密

**滑动动画**:
- 三个页面（聊天/笔记/秘密）横向排列在 `overflow: hidden` 容器内
- 切换时 `transform: translateX(-100%/0/+100%)` + `transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)`
- 页面组件保持挂载以保留状态

### 4.2 修改组件

#### `ConversationList`（原 `ConversationList.jsx`）

**修改点**:
- 新增折叠/展开按钮（◀ / ▶）在侧边栏顶部
- 折叠态：44px 宽，仅显示 `+` `▶` `⚙️` 三个纵向排列图标
- 展开态：200px 宽，完整对话列表 + 底部版本号 + 设置齿轮
- 设置齿轮 ⚙️ 从原 `StatusBar` 移入侧边栏底部
- 快捷键 `Ctrl+B` 切换折叠

**Props 新增**:
- `collapsed: boolean`
- `onToggleCollapse: () => void`

#### `App.jsx`

**修改点**:
- 新增 `navCollapsed` 状态（底部导航折叠）
- 新增 `sidebarCollapsed` 状态（侧边栏折叠）
- 新增 `activePage` 状态（替代 `activeTab`）
- 移除 `StatusBar` 组件引用
- 移除 `TabBar` 组件引用
- 断连提示改为条件渲染：`connectionStatus !== 'connected' && <DisconnectedBanner />`
- 朗读状态不再独立占行，播放时底部导航聊天图标显示小动画（如音符 ♪ 浮动）
- 注册全局快捷键监听（Ctrl+B / Ctrl+D / Ctrl+1/2/3）

#### `ChatPanel` / `NotesPanel` / `SecretNotesPanel`

**修改点**:
- 三个面板作为横向 `flex` 容器的子元素，通过 `transform` 滑动切换
- 各自保持独立状态（消息列表 / 笔记列表 / 秘密笔记列表）
- `ChatPanel` 的 `input-area` 保持在底部导航上方（共享输入栏，仅聊天页可见）

### 4.3 移除组件

| 组件 | 原因 |
|------|------|
| `StatusBar.jsx` | 连接状态改为条件浮动横幅，不再常驻 |
| `TabBar.jsx` | 被 `BottomNavBar` 替代 |

### 4.4 新增临时组件

#### `DisconnectedBanner`

仅当 `connectionStatus !== 'connected'` 时在消息区顶部渲染：

```
┌──────────────────────────────────────────┐
│  ⚠ 未连接 — 请启动后端服务               │
└──────────────────────────────────────────┘
```

- 黄色/橙色背景，高度 ~28px
- 连接恢复后自动消失（带动画 fadeOut）
- 不占用布局空间（`position: absolute` 覆盖在消息区上方）

---

## 5. 状态管理

`App.jsx` 新增/变更状态：

```jsx
// 新增
const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
const [navCollapsed, setNavCollapsed] = useState(false);
const [activePage, setActivePage] = useState('chat');  // 替代 activeTab

// 移除
// const [activeTab, setActiveTab] = useState('chat');  → 替换为 activePage
// const [settingsOpen, setSettingsOpen] = useState(false);  → 保留
```

---

## 6. 快捷键映射

| 快捷键 | 行为 |
|--------|------|
| `Ctrl+B` | 切换侧边栏折叠 |
| `Ctrl+D` | 切换底部导航折叠 |
| `Ctrl+1` | 切换到聊天页 |
| `Ctrl+2` | 切换到笔记页 |
| `Ctrl+3` | 切换到秘密页 |
| `Ctrl+,` | 打开设置抽屉（额外便利） |

全局 `keydown` 事件监听，仅在主窗口生效（`isLive2DOnly` 模式下不注册）。

---

## 7. CSS 变更要点

### 7.1 新增样式

```css
/* 底部导航栏 */
.bottom-nav { /* flex row, centered, gap, border-top */ }
.bottom-nav-item { /* column flex, icon + label */ }
.bottom-nav-item.active { color: var(--accent); }
.bottom-nav-collapse-line { /* 3px height, gradient, cursor pointer */ }

/* 页面滑动容器 */
.page-container { /* flex row, overflow hidden */ }
.page-panel { /* flex: 1 0 100%, transition transform 0.3s */ }

/* 侧边栏折叠 */
.conv-list.collapsed { width: 44px; }
.conv-list.collapsed .conv-new-btn,
.conv-list.collapsed .conv-items,
.conv-list.collapsed .conv-item-title { display: none; }

/* 断连横幅 */
.disconnected-banner { /* position absolute, top 0, fade animation */ }
```

### 7.2 移除样式

- `.status-bar` 及所有子选择器
- `.tab-bar` / `.tab-btn` 及状态变体
- `.speaking-bar`（朗读状态改为底部图标动画，不再独立占行）

### 7.3 保留样式

- 暗色主题变量（`:root`）
- 消息气泡样式（`.message-bubble`）
- Markdown 渲染样式（`.bubble-content h1-6, code, pre, table` 等）
- 输入栏样式（`.input-area`）
- 设置抽屉样式（`.settings-panel-drawer`）
- Live2D 相关样式
- 笔记/秘密面板样式
- 滚动条样式

---

## 8. 实现步骤概览

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1 | `BottomNavBar.jsx` | 新建底部导航组件 |
| 2 | `DisconnectedBanner.jsx` | 新建断连提示组件 |
| 3 | `ConversationList.jsx` | 添加折叠/展开功能 |
| 4 | `App.jsx` | 移除 TabBar/StatusBar，接入新组件，新增状态和快捷键 |
| 5 | `App.css` | 新增导航/折叠/横幅样式，移除旧样式 |
| 6 | `ChatPanel.jsx` | 适配滑动容器（外层包裹） |
| 7 | 全局 | 测试所有交互和快捷键 |

---

## 9. 风险与注意事项

1. **横向滚轮兼容性**：不同鼠标/触控板的横向滚轮行为不一致（`wheel` 事件的 `deltaX` vs `deltaY` + `shiftKey`），需要同时处理 `wheel` 事件和 `Shift+wheel`
2. **底部悬停区域**：折叠态细线的 hover 区域需要扩展到屏幕底部 ~20px（视觉 3px 但 hit area 更大），否则用户难以触发
3. **页面状态保持**：三个页面切换时不应卸载组件（否则丢失滚动位置/输入状态），用 `display: none` 或 visibility 而非条件渲染
4. **Live2D 窗口**：`isLive2DOnly` 模式下不注册快捷键、不渲染导航组件
5. **现有功能兼容**：右键菜单、保存笔记、删除消息、TTS 开关等功能不受影响，仅入口位置变化

---

## 10. 与现有关键路径的兼容

- **WebSocket 消息处理**（`handleMessage`）：不变
- **TTS 朗读**：开关移至设置抽屉，状态仍为 `ttsEnabled`。播放中状态从独立横幅改为底部聊天图标小动画（如音符 ♪ 浮动在 💬 图标上）
- **情绪系统**：IPC 推送到桌宠不变
- **笔记/秘密 CRUD**：面板切换不丢失列表状态
- **设置抽屉**：入口从状态栏齿轮 → 侧边栏底部齿轮（或 `Ctrl+,`）
