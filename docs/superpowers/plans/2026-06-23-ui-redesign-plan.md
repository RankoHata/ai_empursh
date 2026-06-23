# UI Redesign — Bottom Nav + Collapsible Sidebar + Swipe Navigation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace TabBar + StatusBar with bottom navigation bar and collapsible sidebar, enabling horizontal swipe-based page switching for a cleaner, minimalist UI.

**Architecture:** Two new components (`BottomNavBar`, `DisconnectedBanner`) slot into `App.jsx`. `ConversationList` gains collapse. `App.jsx` wraps Chat/Notes/Secret panels in a horizontal sliding container controlled by `activePage` state + `transform: translateX`. `TabBar` and `StatusBar` are removed from the render tree.

**Tech Stack:** React 18, CSS transitions, Electron

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| CREATE | `src/renderer/components/BottomNavBar.jsx` | Bottom nav: 3 icons + collapse line + hover expand |
| CREATE | `src/renderer/components/DisconnectedBanner.jsx` | Floating disconnect warning banner |
| MODIFY | `src/renderer/components/ConversationList.jsx` | Add collapse toggle (◀/▶), settings gear |
| MODIFY | `src/renderer/App.jsx` | Wire new components, sliding page container, keyboard shortcuts |
| MODIFY | `src/renderer/App.css` | Add nav/fold/banner styles, remove status-bar/tab-bar styles |
| DELETE import | `src/renderer/components/StatusBar.jsx` | No longer imported (file kept on disk) |
| DELETE import | `src/renderer/components/TabBar.jsx` | No longer imported (file kept on disk) |

---

### Task 1: Create `BottomNavBar` component

**Files:**
- Create: `electron-app/src/renderer/components/BottomNavBar.jsx`

- [ ] **Step 1: Create BottomNavBar.jsx**

```jsx
import React, { useRef, useEffect, useCallback } from 'react';

const PAGES = [
  { key: 'notes', icon: '📝', label: '笔记' },
  { key: 'chat', icon: '💬', label: '聊天' },
  { key: 'secret', icon: '🔒', label: '秘密' },
];

export default function BottomNavBar({ activePage, onPageChange, collapsed, onToggleCollapse, isSpeaking }) {
  const navRef = useRef(null);
  const hoverZoneRef = useRef(null);
  const expandTimerRef = useRef(null);

  // Hover at bottom edge expands collapsed nav (macOS Dock style)
  const handleMouseEnterZone = useCallback(() => {
    if (collapsed) {
      expandTimerRef.current = setTimeout(() => onToggleCollapse(), 150);
    }
  }, [collapsed, onToggleCollapse]);

  const handleMouseLeaveZone = useCallback(() => {
    if (expandTimerRef.current) {
      clearTimeout(expandTimerRef.current);
      expandTimerRef.current = null;
    }
  }, []);

  // Cleanup timer
  useEffect(() => {
    return () => {
      if (expandTimerRef.current) clearTimeout(expandTimerRef.current);
    };
  }, []);

  return (
    <div className="bottom-nav-wrapper">
      {/* Hover detection zone (20px invisible strip at screen bottom, only when collapsed) */}
      {collapsed && (
        <div
          ref={hoverZoneRef}
          className="bottom-nav-hover-zone"
          onMouseEnter={handleMouseEnterZone}
          onMouseLeave={handleMouseLeaveZone}
        />
      )}

      {/* Nav content */}
      <div className={`bottom-nav ${collapsed ? 'bottom-nav-collapsed' : ''}`} ref={navRef}>
        <div className="bottom-nav-items">
          {PAGES.map((page) => (
            <button
              key={page.key}
              className={`bottom-nav-item ${activePage === page.key ? 'active' : ''}`}
              onClick={() => onPageChange(page.key)}
              title={page.label}
            >
              <span className="bottom-nav-icon">
                {page.icon}
                {/* Speaking indicator: small floating note on chat icon */}
                {page.key === 'chat' && isSpeaking && (
                  <span className="bottom-nav-speaking-badge">♪</span>
                )}
              </span>
              <span className="bottom-nav-label">{page.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Collapse trigger line (always visible) */}
      <div
        className="bottom-nav-collapse-line"
        onClick={onToggleCollapse}
        title={collapsed ? '展开导航栏' : '折叠导航栏'}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add electron-app/src/renderer/components/BottomNavBar.jsx
git commit -m "feat: add BottomNavBar component with collapse hover"
```

---

### Task 2: Create `DisconnectedBanner` component

**Files:**
- Create: `electron-app/src/renderer/components/DisconnectedBanner.jsx`

- [ ] **Step 1: Create DisconnectedBanner.jsx**

```jsx
import React, { useState, useEffect, useRef } from 'react';

const STATUS_LABELS = {
  disconnected: '未连接 — 请启动后端服务',
  connecting: '连接中...',
};

export default function DisconnectedBanner({ status }) {
  const [visible, setVisible] = useState(true);
  const [exiting, setExiting] = useState(false);
  const prevStatusRef = useRef(status);

  useEffect(() => {
    // If transitioning from disconnected/connecting → connected, fade out
    if (status === 'connected' && prevStatusRef.current !== 'connected') {
      setExiting(true);
      const timer = setTimeout(() => setVisible(false), 300);
      return () => clearTimeout(timer);
    }
    // If transitioning to disconnected/connecting, show immediately
    if (status !== 'connected' && prevStatusRef.current === 'connected') {
      setVisible(true);
      setExiting(false);
    }
    prevStatusRef.current = status;
  }, [status]);

  if (!visible || status === 'connected') return null;

  return (
    <div className={`disconnected-banner ${exiting ? 'disconnected-banner-exit' : ''}`}>
      <span>⚠ {STATUS_LABELS[status] || status}</span>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add electron-app/src/renderer/components/DisconnectedBanner.jsx
git commit -m "feat: add DisconnectedBanner component with fade-out"
```

---

### Task 3: Modify `ConversationList` — add collapse, settings gear

**Files:**
- Modify: `electron-app/src/renderer/components/ConversationList.jsx`

- [ ] **Step 1: Add collapsed prop and toggle, settings gear**

Read the current file at `electron-app/src/renderer/components/ConversationList.jsx`. Replace the outer return JSX with the version below that adds collapse support and a settings gear.

The key changes:
1. Accept new props: `collapsed`, `onToggleCollapse`, `onOpenSettings`
2. Add ◀/▶ toggle button in header
3. Collapsed mode: render narrow icon column (44px)
4. Settings gear in sidebar footer

```jsx
import React, { useState, useRef } from 'react';

export default function ConversationList({
  conversations, activeId, onNew, onSelect, onDelete, onRename,
  collapsed, onToggleCollapse, onOpenSettings,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const editRef = useRef(null);

  const startEdit = (e, conv) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title || '');
    setTimeout(() => editRef.current?.select(), 50);
  };

  const saveEdit = () => {
    if (editingId && editTitle.trim()) {
      onRename && onRename(editingId, editTitle.trim());
    }
    setEditingId(null);
  };

  const cancelEdit = () => setEditingId(null);

  // --- Collapsed mode: narrow icon column ---
  if (collapsed) {
    return (
      <div className="conv-list collapsed">
        <button className="conv-collapse-toggle" onClick={onToggleCollapse} title="展开侧边栏">
          ▶
        </button>
        <button className="conv-icon-btn" onClick={onNew} title="新对话">+</button>
        <div className="conv-collapsed-spacer" />
        <button className="conv-icon-btn" onClick={onOpenSettings} title="设置">⚙️</button>
      </div>
    );
  }

  // --- Expanded mode: full sidebar ---
  return (
    <div className="conv-list">
      <div className="conv-header">
        <span className="conv-header-title">对话</span>
        <div className="conv-header-actions">
          <button className="conv-icon-btn" onClick={onNew} title="新对话">+</button>
          <button className="conv-collapse-toggle" onClick={onToggleCollapse} title="收起侧边栏">◀</button>
        </div>
      </div>

      <div className="conv-items">
        {conversations.map(c => (
          <div
            key={c.id}
            className={`conv-item ${c.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(c.id)}
          >
            {editingId === c.id ? (
              <input
                ref={editRef}
                className="conv-edit-input"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onBlur={saveEdit}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveEdit();
                  if (e.key === 'Escape') cancelEdit();
                }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <div
                className="conv-item-title"
                onDoubleClick={(e) => startEdit(e, c)}
                title="双击修改标题"
              >{c.title || '新对话'}</div>
            )}
            <div className="conv-item-meta">
              <span>{c.created_at?.slice(0, 10)}</span>
            </div>
            <button
              className="conv-delete-btn"
              onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
              title="删除"
            >🗑</button>
          </div>
        ))}
        {conversations.length === 0 && (
          <div className="conv-empty">暂无对话</div>
        )}
      </div>

      <div className="conv-footer">
        <span className="conv-version">v1.0</span>
        <button className="conv-icon-btn" onClick={onOpenSettings} title="设置">⚙️</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add electron-app/src/renderer/components/ConversationList.jsx
git commit -m "feat: add collapse toggle and settings gear to ConversationList"
```

---

### Task 4: Modify `App.jsx` — wire everything together

**Files:**
- Modify: `electron-app/src/renderer/App.jsx`

This is the core integration task. Changes:
1. Replace `activeTab` with `activePage`
2. Add `sidebarCollapsed`, `navCollapsed` states
3. Remove `TabBar` and `StatusBar` imports
4. Add `BottomNavBar` and `DisconnectedBanner` imports  
5. Build horizontal sliding page container
6. Add keyboard shortcut listener
7. Pass new props to ConversationList, ChatPanel, NotesPanel, SecretNotesPanel
8. Move TTS/connection info from removed StatusBar to settings

- [ ] **Step 1: Update imports**

Replace lines 1-14 of `App.jsx` (imports):

```jsx
import React, { useState, useCallback, useRef, useEffect } from 'react';
import useWebSocket from './hooks/useWebSocket';
import BottomNavBar from './components/BottomNavBar';
import DisconnectedBanner from './components/DisconnectedBanner';
import ConversationList from './components/ConversationList';
import ChatPanel from './components/ChatPanel';
import NotesPanel from './components/NotesPanel';
import SecretNotesPanel from './components/SecretNotesPanel';
import NewNoteModal from './components/NewNoteModal';
import AvatarStatus from './components/AvatarStatus';
import MarkdownPreview from './components/MarkdownPreview';
import SettingsPanel from './components/SettingsPanel';
import Avatar from './components/Avatar';
import FeatureGuard from './components/FeatureGuard';
```

Note: `TabBar` and `StatusBar` imports are removed.

- [ ] **Step 2: Replace `activeTab` with `activePage`, add new states**

Replace line 47:
```jsx
  const [activeTab, setActiveTab] = useState('chat');
```
With:
```jsx
  const [activePage, setActivePage] = useState('chat');
```

After `const [wallpaper, setWallpaper] = useState(...)` (line 78-ish), add:
```jsx
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(false);
```

- [ ] **Step 3: Add keyboard shortcut handler**

After `ttsEnabledRef.current = ttsEnabled;` (line 83-ish), add:

```jsx
  // Keyboard shortcuts for navigation
  useEffect(() => {
    if (isLive2DOnly) return;
    const handleKeyDown = (e) => {
      // Don't intercept when typing in inputs
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;

      if (e.ctrlKey && !e.altKey && !e.metaKey) {
        switch (e.key) {
          case 'b':
          case 'B':
            e.preventDefault();
            setSidebarCollapsed(prev => !prev);
            break;
          case 'd':
          case 'D':
            e.preventDefault();
            setNavCollapsed(prev => !prev);
            break;
          case '1':
            e.preventDefault();
            setActivePage('chat');
            break;
          case '2':
            e.preventDefault();
            setActivePage('notes');
            break;
          case '3':
            e.preventDefault();
            setActivePage('secret');
            break;
          case ',':
            e.preventDefault();
            setSettingsOpen(true);
            break;
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isLive2DOnly]);
```

- [ ] **Step 4: Replace the return JSX**

Replace the entire return block (from line 635 `return (` to the closing `)` before `export default App`) with:

```jsx
  if (isLive2DOnly) {
    return (
      <div className="live2d-only-container">
        <Avatar state={avatarState} />
      </div>
    );
  }

  // Page order for horizontal sliding: notes(0) | chat(1) | secret(2)
  const pageIndex = { notes: 0, chat: 1, secret: 2 };
  const translateX = -pageIndex[activePage] * 100;

  // Determine which panels to render (always mount all three to preserve state)
  const pagePanels = [
    { key: 'notes', component: (
      <NotesPanel
        notes={notes}
        onGetNotes={handleGetNotes}
        onSearch={handleSearchNotes}
        onDelete={handleDeleteNote}
        onExport={handleExportNotes}
        onNewNote={() => handleOpenNewNote(false)}
      />
    )},
    { key: 'chat', component: (
      <ChatPanel
        messages={messages}
        isStreaming={isStreaming}
        onSend={handleSend}
        onStop={handleStop}
        onSaveNote={handleSaveNote}
        onVoiceInput={handleVoiceInput}
        onToggleDebug={handleToggleDebug}
        debugMsgId={debugMsgId}
        compactMode={compactMode}
        onDeleteMessage={handleDeleteMessage}
      />
    )},
    { key: 'secret', component: (
      <SecretNotesPanel
        notes={secretNotes}
        onGetNotes={handleGetSecretNotes}
        onSearch={handleSearchSecretNotes}
        onDelete={handleDeleteSecretNote}
        onNewNote={() => handleOpenNewNote(true)}
      />
    )},
  ];

  return (
    <div className="app-container">
      <ConversationList
        conversations={conversations}
        activeId={activeConvId}
        onNew={handleNewConv}
        onSelect={handleSelectConv}
        onDelete={handleDeleteConv}
        onRename={handleRenameConv}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(prev => !prev)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="main-content">
        {/* Disconnected banner — only visible when not connected */}
        <DisconnectedBanner status={connectionStatus} />

        {/* Tool toast (unchanged) */}
        {toolToast && (
          <div className="tool-toast">
            <span>🔧</span>
            <span>{toolToast.text}</span>
          </div>
        )}

        {/* Secret notification banner */}
        {secretNotification && (
          <div
            className="secret-notification-banner"
            onClick={() => { setActivePage('secret'); setSecretNotification(null); }}
          >
            🔒 AI 查找了秘密空间，找到 {secretNotification.count} 条结果 — 点击切换到秘密标签查看
            <button
              className="secret-notification-close"
              onClick={(e) => { e.stopPropagation(); setSecretNotification(null); }}
            >✕</button>
          </div>
        )}

        {/* Wallpaper layer */}
        {wallpaper && (
          <div className="wallpaper-layer" style={{ backgroundImage: `url(${wallpaper})` }} />
        )}

        {/* Horizontal sliding page container */}
        <div className="page-container">
          <div
            className="page-track"
            style={{ transform: `translateX(${translateX}%)` }}
          >
            {pagePanels.map(p => (
              <div key={p.key} className="page-panel">
                {p.component}
              </div>
            ))}
          </div>
        </div>

        {/* Bottom navigation bar */}
        <BottomNavBar
          activePage={activePage}
          onPageChange={setActivePage}
          collapsed={navCollapsed}
          onToggleCollapse={() => setNavCollapsed(prev => !prev)}
          isSpeaking={isSpeaking}
        />
      </div>

      {/* Settings Drawer (unchanged) */}
      {settingsOpen && (
        <div className="settings-modal-overlay" onClick={() => setSettingsOpen(false)}>
          <div className="settings-panel-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="settings-drawer-header">
              <h2>⚙️ 设置</h2>
              <button className="settings-drawer-close" onClick={() => setSettingsOpen(false)}>✕</button>
            </div>
            <SettingsPanel
              config={config}
              onUpdateConfig={handleUpdateConfig}
              onLoad={handleGetConfig}
              compactMode={compactMode}
              onToggleCompact={(v) => { setCompactMode(v); localStorage.setItem('compactMode', v ? '1' : '0'); }}
              personalities={personalities}
              currentPersonalityId={currentPersonalityId}
              onSetPersonality={(pid) => { send('set_personality', { personality_id: pid }); }}
              onCreatePersonality={(data) => { send('create_personality', data); }}
              onUpdatePersonality={(id, data) => { send('update_personality', { id, ...data }); }}
              onDeletePersonality={(id) => { if (confirm('确定删除此人格？')) send('delete_personality', { id }); }}
              wallpaper={wallpaper}
              onSetWallpaper={(v) => { setWallpaper(v); localStorage.setItem('wallpaper', v); }}
              grouped={groupedPersonalities}
              userName={userName}
              onUserNameChange={handleUserNameChange}
              emotionFollowEnabled={emotionFollowEnabled}
              onSetEmotionFollow={setEmotionFollowEnabled}
              ttsEnabled={ttsEnabled}
              onToggleTts={handleToggleTts}
            />
          </div>
        </div>
      )}

      {/* Modals (unchanged) */}
      {saveModal && (
        <div className="modal-overlay" onClick={() => setSaveModal(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h3>💾 保存为笔记</h3>
            <div className="modal-preview">{saveModal.content.slice(0, 300)}</div>
            <input
              className="modal-input"
              type="text"
              placeholder="输入标签（空格分隔）"
              value={saveTags}
              onChange={(e) => setSaveTags(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleConfirmSave(); }}
              autoFocus
            />
            <div className="modal-buttons">
              <button className="btn-send" onClick={handleConfirmSave}>保存</button>
              <button className="btn-modal-cancel" onClick={() => setSaveModal(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {newNoteModal && (
        <NewNoteModal
          secretMode={newNoteModal.secretMode}
          onSave={handleAddNoteFromModal}
          onCancel={() => setNewNoteModal(null)}
        />
      )}

      {markdownPreview && (
        <MarkdownPreview
          content={markdownPreview.content}
          suggestedFilename={markdownPreview.suggestedFilename}
          onSave={handleSaveMarkdown}
          onCancel={handleCancelPreview}
        />
      )}

      <FeatureGuard flag="showLive2D">
        <div className="live2d-sidebar">
          <Avatar state={avatarState} />
        </div>
      </FeatureGuard>
    </div>
  );
}
```

- [ ] **Step 3 (continued): Remove `isSpeaking` banner from old JSX**

The old `isSpeaking` banner block:
```jsx
        {isSpeaking && (
          <div className="speaking-bar">
            <span>🔊 正在朗读...</span>
            <button className="btn-stop-speaking" onClick={stopAudio}>⏹ 停止朗读</button>
          </div>
        )}
```
is already removed in the new JSX above (the speaking indicator is now handled by `BottomNavBar`'s `isSpeaking` prop showing ♪ on the chat icon).

- [ ] **Step 4: Remove old page-switching conditional**

The old JSX had:
```jsx
        {activeTab === 'chat' ? (
          <ChatPanel ... />
        ) : activeTab === 'secret' ? (
          <SecretNotesPanel ... />
        ) : (
          <NotesPanel ... />
        )}
```
This is replaced by the sliding `page-container` which always mounts all three panels.

- [ ] **Step 5: Verify no unused variables remain**

Ensure the following are NOT referenced in the new JSX (they were removed):
- `TabBar` (import removed)
- `StatusBar` (import removed)

These variables remain used:
- `activePage` (replaces `activeTab`)
- `sidebarCollapsed`, `navCollapsed` (new)
- `stopAudio` — keep the function but the `isSpeaking` banner is gone; `stopAudio` is still called by `handleStop` and `handleToggleTts`

- [ ] **Step 6: Commit**

```bash
git add electron-app/src/renderer/App.jsx
git commit -m "feat: integrate BottomNavBar + sliding pages + keyboard shortcuts"
```

---

### Task 5: Update `App.css` — add new styles, remove old

**Files:**
- Modify: `electron-app/src/renderer/App.css`

- [ ] **Step 1: Remove old StatusBar and TabBar styles**

Find and delete these sections from `App.css`:
1. The entire `/* === StatusBar === */` block (lines 77-139, containing `.status-bar`, `.status-dot`, `.status-bar-spacer`, `.voice-toggle`, `.btn-settings`)
2. The entire `/* === TabBar === */` block (lines 406-433, containing `.tab-bar` and `.tab-btn`)
3. The entire `/* === Speaking Bar === */` block (lines 882-906, containing `.speaking-bar` and `.btn-stop-speaking`)

- [ ] **Step 2: Add new styles at the end of the file**

Append the following CSS blocks before the final closing of the file:

```css
/* ============================================================
   Bottom Navigation Bar
   ============================================================ */
.bottom-nav-wrapper {
  flex-shrink: 0;
  position: relative;
}

.bottom-nav {
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
  transition: max-height 0.25s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.bottom-nav-collapsed {
  max-height: 0;
  opacity: 0;
  border-top-color: transparent;
}

.bottom-nav-items {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 40px;
  padding: 6px 0 8px;
}

.bottom-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px 12px;
  border: none;
  border-radius: 8px;
  background: none;
  color: var(--text-secondary);
  font-size: 10px;
  font-family: var(--font);
  cursor: pointer;
  transition: color 0.15s, background 0.15s, transform 0.15s;
  opacity: 0.55;
}
.bottom-nav-item:hover {
  color: var(--text-primary);
  background: var(--bg-input);
  opacity: 0.8;
}
.bottom-nav-item.active {
  color: var(--accent);
  opacity: 1;
}

.bottom-nav-icon {
  font-size: 17px;
  position: relative;
  line-height: 1;
}

/* Speaking indicator badge */
.bottom-nav-speaking-badge {
  position: absolute;
  top: -6px;
  right: -10px;
  font-size: 10px;
  color: var(--accent);
  animation: speaking-float 1s ease-in-out infinite;
}
@keyframes speaking-float {
  0%, 100% { transform: translateY(0); opacity: 1; }
  50% { transform: translateY(-4px); opacity: 0.6; }
}

.bottom-nav-label {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.3px;
}

/* Collapse trigger line */
.bottom-nav-collapse-line {
  height: 3px;
  cursor: pointer;
  background: linear-gradient(90deg, transparent 35%, var(--border) 50%, transparent 65%);
  position: relative;
  transition: background 0.2s;
}
.bottom-nav-collapse-line::after {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 28px;
  height: 2px;
  border-radius: 1px;
  background: var(--accent);
  opacity: 0.4;
  transition: opacity 0.2s, width 0.2s;
}
.bottom-nav-collapse-line:hover {
  background: linear-gradient(90deg, transparent 30%, rgba(114,137,218,0.15) 50%, transparent 70%);
}
.bottom-nav-collapse-line:hover::after {
  opacity: 0.7;
  width: 36px;
}

/* Hover detection zone for expanding collapsed nav */
.bottom-nav-hover-zone {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 20px;
  z-index: 10;
}

/* ============================================================
   Page Sliding Container
   ============================================================ */
.page-container {
  flex: 1;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.page-track {
  display: flex;
  height: 100%;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-panel {
  flex: 1 0 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ============================================================
   Disconnected Banner
   ============================================================ */
.disconnected-banner {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  padding: 5px 14px;
  background: rgba(240, 165, 0, 0.12);
  border-bottom: 1px solid rgba(240, 165, 0, 0.25);
  color: #f0a500;
  font-size: 12px;
  text-align: center;
  font-weight: 500;
  letter-spacing: 0.3px;
  animation: bannerIn 0.25s ease-out;
}
.disconnected-banner-exit {
  animation: bannerOut 0.3s ease-out forwards;
}
@keyframes bannerIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes bannerOut {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-4px); }
}

/* ============================================================
   ConversationList — collapse mode additions
   ============================================================ */
.conv-list.collapsed {
  width: 44px;
  padding: 10px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.conv-list.collapsed .conv-header,
.conv-list.collapsed .conv-items,
.conv-list.collapsed .conv-footer { display: none; }

.conv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}
.conv-header-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.conv-header-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.conv-collapse-toggle {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, background 0.15s;
  font-family: var(--font);
}
.conv-collapse-toggle:hover {
  color: var(--text-primary);
  background: var(--bg-input);
}

.conv-icon-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 15px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, background 0.15s;
  font-family: var(--font);
  flex-shrink: 0;
}
.conv-icon-btn:hover {
  color: var(--text-primary);
  background: var(--bg-input);
}

.conv-collapsed-spacer {
  flex: 1;
}

.conv-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid var(--border);
}
.conv-version {
  font-size: 11px;
  color: var(--text-muted);
}
```

- [ ] **Step 3: Update `.main-content` to not have gap from old bars**

Ensure `.main-content` style remains as:
```css
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  position: relative;
}
```

- [ ] **Step 4: Commit**

```bash
git add electron-app/src/renderer/App.css
git commit -m "style: add bottom-nav/sliding/banner/collapse CSS, remove status-bar/tab-bar styles"
```

---

### Task 6: Verify app builds and runs

- [ ] **Step 1: Check for import errors**

```bash
cd electron-app && npx vite build --config vite.renderer.config.mjs 2>&1 | tail -20
```
Expected: Build succeeds with no errors.

- [ ] **Step 2: Start the app and visually verify**

```bash
# Terminal 1: Start backend
cd backend && python main.py

# Terminal 2: Start frontend
cd electron-app && npm start
```

Verify these behaviors:
1. ✅ App launches with bottom nav bar visible, no top TabBar or StatusBar
2. ✅ Chat page is default active
3. ✅ Click 📝 / 🔒 icons to switch pages — smooth slide animation
4. ✅ Click ◀ on sidebar — collapses to 44px icon column
5. ✅ Click ▶ on collapsed sidebar — expands back
6. ✅ Click thin line below bottom nav — nav collapses to 3px line
7. ✅ Move mouse to screen bottom — nav slides back out (when collapsed)
8. ✅ `Ctrl+1/2/3` switches pages
9. ✅ `Ctrl+B` toggles sidebar
10. ✅ `Ctrl+D` toggles bottom nav
11. ✅ `Ctrl+,` opens settings drawer
12. ✅ Disconnect backend — orange banner appears at top
13. ✅ Reconnect backend — banner fades out
14. ✅ TTS speaking — ♪ badge appears on chat icon
15. ✅ Right-click context menu still works on messages
16. ✅ Save as note, delete message still work
17. ✅ Settings drawer opens from sidebar gear icon

- [ ] **Step 3: Commit if any minor fixes were needed, or confirm completion**

```bash
git status
```

---

### Task 7: Clean up unused CSS and verify no regressions

- [ ] **Step 1: Search for any remaining references to removed components**

```bash
cd electron-app && grep -r "StatusBar\|TabBar" src/ --include="*.jsx" --include="*.js"
```
Expected: No results (or only in the component files themselves, which are kept on disk but not imported).

- [ ] **Step 2: Search for remaining `.status-bar` or `.tab-bar` usage in CSS**

```bash
cd electron-app && grep -r "status-bar\|tab-bar\|speaking-bar" src/ --include="*.css"
```
Expected: No results.

- [ ] **Step 3: Final commit if cleanup was needed**

```bash
git add -A
git commit -m "chore: remove remaining references to StatusBar/TabBar"
```
