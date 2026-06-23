import React, { useState, useCallback, useRef, useEffect } from 'react';
import useWebSocket from './hooks/useWebSocket';
import useChat from './hooks/useChat';
import useNotes from './hooks/useNotes';
import useConversations from './hooks/useConversations';
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
  // ── Layout / Routing state ──
  const [activePage, setActivePage] = useState('chat');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const isLive2DOnly = window.location.search.includes('mode=live2d');

  // ── Settings state (not yet extracted) ──
  const [avatarState, setAvatarState] = useState('idle');
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [config, setConfig] = useState(null);
  const [personalities, setPersonalities] = useState([]);
  const [groupedPersonalities, setGroupedPersonalities] = useState([]);
  const [currentPersonalityId, setCurrentPersonalityId] = useState(null);
  const [emotionFollowEnabled, setEmotionFollowEnabled] = useState(() =>
    localStorage.getItem('emotionFollowEnabled') !== 'false'
  );
  const [userName, setUserName] = useState('');
  const [compactMode, setCompactMode] = useState(() =>
    localStorage.getItem('compactMode') === '1'
  );
  const [wallpaper, setWallpaper] = useState(() =>
    localStorage.getItem('wallpaper') || ''
  );

  // ── Refs for cross-hook communication ──
  const emotionTimerRef = useRef(null);
  const ttsEnabledRef = useRef(ttsEnabled);
  ttsEnabledRef.current = ttsEnabled;
  const emotionFollowRef = useRef(emotionFollowEnabled);
  emotionFollowRef.current = emotionFollowEnabled;
  const sendRef = useRef(null);

  const settingsRefs = { emotionFollowRef, ttsEnabledRef, emotionTimerRef };

  // ── WebSocket ──
  const { connectionStatus, send } = useWebSocket({ onMessage: handleMessage });
  sendRef.current = send;

  // ── Custom hooks ──
  const chat = useChat(send, settingsRefs, setAvatarState);
  const notes = useNotes(send);
  const conversations = useConversations(send, chat.clearMessages);

  // ── Central message dispatcher ──
  function handleMessage(type, payload) {
    if (isLive2DOnly && type !== 'config' && type !== 'personalities_list' &&
        type !== 'personality_set' && type !== 'avatar_state') {
      return;
    }
    // Delegate to hooks in priority order
    if (chat.onMessage(type, payload)) return;
    if (notes.onMessage(type, payload)) return;
    if (conversations.onMessage(type, payload)) return;

    // Remaining cases handled below
    switch (type) {
      case 'config':
        setConfig(payload);
        if (payload.user?.name !== undefined) setUserName(payload.user.name);
        break;
      case 'config_updated':
        break;
      case 'personalities_list':
      case 'personalities_reseeded':
        setPersonalities(payload.personalities || []);
        setGroupedPersonalities(payload.grouped || []);
        if (payload.current) setCurrentPersonalityId(payload.current);
        break;
      case 'personality_set':
        setCurrentPersonalityId(payload.id);
        break;
      case 'personality_created':
      case 'personality_updated':
      case 'personality_deleted':
        send('get_personalities', {});
        break;
      case 'voice_result': {
        const text = (payload.text || '').trim();
        if (text) {
          chat.stopAudio();
          chat.addUserMsgAndSend(text);
          send('chat', { message: text });
        }
        break;
      }
      default:
        break;
    }
  }

  // ── Effects ──

  // Sync compact mode on connect
  useEffect(() => {
    if (connectionStatus === 'connected') {
      send('compact_mode', { enabled: compactMode });
    }
  }, [connectionStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  // Persist emotionFollowEnabled
  useEffect(() => {
    localStorage.setItem('emotionFollowEnabled', String(emotionFollowEnabled));
  }, [emotionFollowEnabled]);

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
          case ',': e.preventDefault(); setSettingsOpen(true); break;
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isLive2DOnly]);

  // Live2D pet mode: emotion relay via IPC
  useEffect(() => {
    if (!isLive2DOnly) return;
    window.electronAPI?.onAvatarEmotion((emotion) => {
      setAvatarState(emotion);
      clearTimeout(emotionTimerRef.current);
      emotionTimerRef.current = setTimeout(() => setAvatarState('idle'), 3000);
    });
  }, [isLive2DOnly]);

  // ── Settings handlers ──

  const handleToggleTts = useCallback((on) => {
    setTtsEnabled(on);
    if (!on) chat.stopAudio();
    send('tts_enabled', { enabled: on });
  }, [send, chat.stopAudio]);

  const handleGetConfig = useCallback(() => send('get_config', {}), [send]);
  const handleUpdateConfig = useCallback((updates) => send('update_config', { updates }), [send]);
  const handleUserNameChange = useCallback((name) => {
    setUserName(name);
    send('update_config', { updates: { user: { name } } });
  }, [send]);

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
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <div className="main-content">
        <DisconnectedBanner status={connectionStatus} />

        {/* Tool toast */}
        {chat.toolToast && (
          <div className="tool-toast">
            <span className="tool-toast-icon">🔧</span>
            <span>{chat.toolToast.text}</span>
          </div>
        )}

        {/* Secret notification */}
        {notes.secretNotification && (
          <div className="secret-notification-banner">
            🔒 已检索到 {notes.secretNotification.count} 条秘密记录
            {notes.secretNotification.query ? `（关键词: ${notes.secretNotification.query}）` : ''}
            ，详情请查看安全面板
          </div>
        )}

        {/* Wallpaper layer */}
        {wallpaper && (
          <div className="wallpaper-layer" style={{ backgroundImage: `url(${wallpaper})` }} />
        )}

        {/* Sliding pages */}
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
                compactMode={compactMode}
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
      {settingsOpen && (
        <div className="settings-backdrop" onClick={() => setSettingsOpen(false)}>
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
              onToggleCompact={(v) => { setCompactMode(v); localStorage.setItem('compactMode', v ? '1' : '0'); send('compact_mode', { enabled: v }); }}
              personalities={personalities}
              currentPersonalityId={currentPersonalityId}
              onSetPersonality={(pid) => { send('set_personality', { personality_id: pid }); }}
              onCreatePersonality={(data) => { send('create_personality', data); }}
              onUpdatePersonality={(id, data) => { send('update_personality', { id, ...data }); }}
              onDeletePersonality={(id) => { if (confirm('确定删除此人格？')) send('delete_personality', { id }); }}
              onReseedPersonalities={() => { send('reseed_personalities', {}); }}
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
              onChange={(e) => notes.setSaveTags(e.target.value)} // need to expose setSaveTags
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
          onCancel={() => notes.setNewNoteModal(null)} // need to expose setNewNoteModal
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

      {/* Avatar Sidebar */}
      <FeatureGuard flag="showAvatar">
        <div className="live2d-sidebar">
          <Avatar state={avatarState} />
        </div>
      </FeatureGuard>
    </div>
  );
}
