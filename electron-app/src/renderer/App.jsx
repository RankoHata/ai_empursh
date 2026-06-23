import React, { useState, useRef, useEffect } from 'react';
import useWebSocket from './hooks/useWebSocket';
import useChat from './hooks/useChat';
import useNotes from './hooks/useNotes';
import useConversations from './hooks/useConversations';
import useSettings from './hooks/useSettings';
import BottomNavBar from './components/BottomNavBar';
import DisconnectedBanner from './components/DisconnectedBanner';
import ConversationList from './components/ConversationList';
import ChatPanel from './components/ChatPanel';
import NotesPanel from './components/NotesPanel';
import SecretNotesPanel from './components/SecretNotesPanel';
import NewNoteModal from './components/NewNoteModal';
import MarkdownPreview from './components/MarkdownPreview';
import SettingsPanel from './components/SettingsPanel';
import Avatar from './components/Avatar';
import FeatureGuard from './components/FeatureGuard';

export default function App() {
  // ── Layout / Routing ──
  const [activePage, setActivePage] = useState('chat');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(true);
  const isLive2DOnly = window.location.search.includes('mode=live2d');

  // ── Avatar (shared: chat emotion + live2d IPC) ──
  const [avatarState, setAvatarState] = useState('idle');

  // ── WebSocket ──
  const { connectionStatus, send } = useWebSocket({ onMessage: handleMessage });

  // ── Hooks ──
  const settings = useSettings(send);
  const chat = useChat(send, settings.settingsRefs, setAvatarState);
  const notes = useNotes(send);
  const conversations = useConversations(send, chat.clearMessages);

  const sendRef = useRef(send);
  sendRef.current = send;

  // ── Central message dispatcher ──
  function handleMessage(type, payload) {
    if (isLive2DOnly && type !== 'config' && type !== 'personalities_list' &&
        type !== 'personality_set' && type !== 'avatar_state') {
      return;
    }
    // Delegate to hooks in priority order
    if (settings.onMessage(type, payload)) return;
    if (chat.onMessage(type, payload)) return;
    if (notes.onMessage(type, payload)) return;
    if (conversations.onMessage(type, payload)) return;

    // voice_result: re-send recognized text
    if (type === 'voice_result') {
      const text = (payload.text || '').trim();
      if (text) {
        chat.stopAudio();
        chat.addUserMsgAndSend(text);
        send('chat', { message: text });
      }
    }
  }

  // ── Effects ──

  // Sync compact mode on connect
  useEffect(() => {
    if (connectionStatus === 'connected') {
      send('compact_mode', { enabled: settings.compactMode });
    }
  }, [connectionStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  // Persist emotionFollowEnabled
  useEffect(() => {
    localStorage.setItem('emotionFollowEnabled', String(settings.emotionFollowEnabled));
  }, [settings.emotionFollowEnabled]);

  // Initial data fetch on connect
  const prevStatusRef = useRef(connectionStatus);
  useEffect(() => {
    if (prevStatusRef.current !== 'connected' && connectionStatus === 'connected') {
      send('list_conversations', {});
      send('get_personalities', {});
      send('get_config', {});
    }
    prevStatusRef.current = connectionStatus;
  }, [connectionStatus, send]);

  // Keyboard shortcuts
  useEffect(() => {
    if (isLive2DOnly) return;
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
      if (e.ctrlKey && !e.altKey && !e.metaKey) {
        switch (e.key) {
          case 'b': case 'B': e.preventDefault(); setSidebarCollapsed(prev => !prev); break;
          case 'd': case 'D': e.preventDefault(); setNavCollapsed(prev => !prev); break;
          case '1': e.preventDefault(); setActivePage('chat'); break;
          case '2': e.preventDefault(); setActivePage('notes'); break;
          case '3': e.preventDefault(); setActivePage('secret'); break;
          case ',': e.preventDefault(); settings.setSettingsOpen(true); break;
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isLive2DOnly, settings.setSettingsOpen]);

  // Live2D pet mode: emotion relay via IPC
  useEffect(() => {
    if (!isLive2DOnly) return;
    window.electronAPI?.onAvatarEmotion((emotion) => {
      setAvatarState(emotion);
      clearTimeout(settings.emotionTimerRef.current);
      settings.emotionTimerRef.current = setTimeout(() => setAvatarState('idle'), 3000);
    });
  }, [isLive2DOnly, settings.emotionTimerRef]);

  // ── Pet mode: minimal render ──
  if (isLive2DOnly) {
    return (
      <div className="live2d-only-container">
        <Avatar state={avatarState} />
      </div>
    );
  }

  // ── Normal render ──
  return (
    <div className="app-container">
      <ConversationList
        conversations={conversations.conversations}
        activeId={conversations.activeConvId}
        onNew={conversations.handleNewConv}
        onSelect={conversations.handleSelectConv}
        onDelete={conversations.handleDeleteConv}
        onRename={conversations.handleRenameConv}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(prev => !prev)}
        onOpenSettings={() => settings.setSettingsOpen(true)}
      />

      <div className="main-content">
        <DisconnectedBanner status={connectionStatus} />

        {chat.toolToast && (
          <div className="tool-toast">
            <span className="tool-toast-icon">🔧</span>
            <span>{chat.toolToast.text}</span>
          </div>
        )}

        {notes.secretNotification && (
          <div className="secret-notification-banner">
            🔒 已检索到 {notes.secretNotification.count} 条秘密记录
            {notes.secretNotification.query ? `（关键词: ${notes.secretNotification.query}）` : ''}
            ，详情请查看安全面板
          </div>
        )}

        {settings.wallpaper && (
          <div className="wallpaper-layer" style={{ backgroundImage: `url(${settings.wallpaper})` }} />
        )}

        <div className="page-container">
          <div className="page-track" style={{ transform: `translateX(-${activePage === 'chat' ? 1 : activePage === 'notes' ? 0 : 2}00%)` }}>
            <div className="page-panel">
              <NotesPanel
                notes={notes.notes}
                onGetNotes={notes.handleGetNotes}
                onSearch={notes.handleSearchNotes}
                onDelete={notes.handleDeleteNote}
                onExport={notes.handleExportNotes}
                onNewNote={() => notes.handleOpenNewNote(false)}
              />
            </div>
            <div className="page-panel">
              <ChatPanel
                messages={chat.messages}
                isStreaming={chat.isStreaming}
                onSend={chat.handleSend}
                onStop={chat.handleStop}
                onSaveNote={notes.handleSaveNote}
                onVoiceInput={chat.handleVoiceInput}
                onToggleDebug={chat.handleToggleDebug}
                debugMsgId={chat.debugMsgId}
                compactMode={settings.compactMode}
                onDeleteMessage={chat.handleDeleteMessage}
              />
            </div>
            <div className="page-panel">
              <SecretNotesPanel
                notes={notes.secretNotes}
                onGetNotes={notes.handleGetSecretNotes}
                onSearch={notes.handleSearchSecretNotes}
                onDelete={notes.handleDeleteSecretNote}
                onNewNote={() => notes.handleOpenNewNote(true)}
              />
            </div>
          </div>
        </div>

        <BottomNavBar
          activePage={activePage}
          onPageChange={setActivePage}
          collapsed={navCollapsed}
          onToggleCollapse={() => setNavCollapsed(prev => !prev)}
          isSpeaking={chat.isSpeaking}
        />
      </div>

      {/* Settings drawer */}
      {settings.settingsOpen && (
        <div className="settings-backdrop" onClick={() => settings.setSettingsOpen(false)}>
          <div className="settings-panel-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="settings-drawer-header">
              <h2>⚙️ 设置</h2>
              <button className="settings-drawer-close" onClick={() => settings.setSettingsOpen(false)}>✕</button>
            </div>
            <SettingsPanel
              config={settings.config}
              onUpdateConfig={settings.handleUpdateConfig}
              onLoad={settings.handleGetConfig}
              compactMode={settings.compactMode}
              onToggleCompact={(v) => {
                settings.setCompactMode(v);
                localStorage.setItem('compactMode', v ? '1' : '0');
                send('compact_mode', { enabled: v });
              }}
              personalities={settings.personalities}
              currentPersonalityId={settings.currentPersonalityId}
              onSetPersonality={(pid) => { send('set_personality', { personality_id: pid }); }}
              onCreatePersonality={(data) => { send('create_personality', data); }}
              onUpdatePersonality={(id, data) => { send('update_personality', { id, ...data }); }}
              onDeletePersonality={(id) => { if (confirm('确定删除此人格？')) send('delete_personality', { id }); }}
              onReseedPersonalities={() => { send('reseed_personalities', {}); }}
              wallpaper={settings.wallpaper}
              onSetWallpaper={(v) => { settings.setWallpaper(v); localStorage.setItem('wallpaper', v); }}
              grouped={settings.groupedPersonalities}
              userName={settings.userName}
              onUserNameChange={settings.handleUserNameChange}
              emotionFollowEnabled={settings.emotionFollowEnabled}
              onSetEmotionFollow={settings.setEmotionFollowEnabled}
              ttsEnabled={settings.ttsEnabled}
              onToggleTts={(on) => settings.handleToggleTts(on, chat.stopAudio)}
            />
          </div>
        </div>
      )}

      {/* Modals */}
      {notes.saveModal && (
        <div className="modal-backdrop" onClick={() => notes.handleSaveNote(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h3>保存为笔记</h3>
            <textarea value={notes.saveModal.content} readOnly rows={6} />
            <input
              type="text"
              placeholder="标签（逗号分隔）"
              value={notes.saveTags}
              onChange={(e) => notes.setSaveTags(e.target.value)}
            />
            <div className="modal-actions">
              <button onClick={notes.handleConfirmSave}>保存</button>
              <button className="btn-secondary" onClick={() => notes.handleSaveNote(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {notes.newNoteModal && (
        <NewNoteModal
          secretMode={notes.newNoteModal.secretMode}
          onSave={(content, tags, title) => notes.handleAddNoteFromModal(content, tags, title)}
          onCancel={() => notes.setNewNoteModal(null)}
        />
      )}

      {notes.markdownPreview && (
        <MarkdownPreview
          content={notes.markdownPreview.content}
          suggestedFilename={notes.markdownPreview.suggestedFilename}
          onSave={notes.handleSaveMarkdown}
          onCancel={notes.handleCancelPreview}
        />
      )}

      <FeatureGuard flag="showAvatar">
        <div className="live2d-sidebar">
          <Avatar state={avatarState} />
        </div>
      </FeatureGuard>
    </div>
  );
}
