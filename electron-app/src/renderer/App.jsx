import React, { useState, useCallback, useRef, useEffect } from 'react';
import useWebSocket from './hooks/useWebSocket';
import StatusBar from './components/StatusBar';
import TabBar from './components/TabBar';
import ChatPanel from './components/ChatPanel';
import NotesPanel from './components/NotesPanel';
import AvatarStatus from './components/AvatarStatus';
import MarkdownPreview from './components/MarkdownPreview';
import SettingsPanel from './components/SettingsPanel';
import Live2DAvatar from './components/Live2DAvatar';
import FeatureGuard from './components/FeatureGuard';
import ConversationList from './components/ConversationList';

let nextId = 1;

function buildToolCallsFromTrace(trace) {
  if (!trace) return undefined;
  const toolCalls = [];
  trace.forEach(step => {
    if (step.step === 'tool_call') {
      toolCalls.push({
        id: step.id || `${step.name}_${Date.now()}`,
        name: step.name,
        args: step.args,
        state: 'completed',
      });
    }
    // Find matching tool_result
    if (step.step === 'tool_result') {
      const matching = toolCalls.find(tc => tc.name === step.name && tc.state === 'completed' && !tc.result);
      if (matching) {
        matching.result = { success: step.success, message: step.message, count: step.count };
        matching.duration_ms = step.duration_ms;
        matching.state = step.success ? 'completed' : 'error';
        if (!step.success) matching.error = step.message;
      }
    }
  });
  return toolCalls.length > 0 ? toolCalls : undefined;
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');
  const [notes, setNotes] = useState([]);
  const [saveModal, setSaveModal] = useState(null);
  const [saveTags, setSaveTags] = useState('');
  const [avatarState, setAvatarState] = useState('idle');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [markdownPreview, setMarkdownPreview] = useState(null);
  const [config, setConfig] = useState(null);
  const [toolToast, setToolToast] = useState(null);  // { name, text }
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [debugMsgId, setDebugMsgId] = useState(null);
  const [personalities, setPersonalities] = useState([]);
  const [currentPersonalityId, setCurrentPersonalityId] = useState(null);

  const [compactMode, setCompactMode] = useState(() => {
    return localStorage.getItem('compactMode') === '1';
  });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [wallpaper, setWallpaper] = useState(() => {
    return localStorage.getItem('wallpaper') || '';
  });
  const audioRef = useRef(null);
  const sendRef = useRef(null);
  const ttsEnabledRef = useRef(ttsEnabled);
  ttsEnabledRef.current = ttsEnabled;
  const toolToastTimerRef = useRef(null);

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
      setIsSpeaking(false);
    }
  }, []);

  const messagesRef = useRef(messages);
  const isStreamingRef = useRef(isStreaming);
  messagesRef.current = messages;
  isStreamingRef.current = isStreaming;

  const addUserMsgAndSend = useCallback((text) => {
    const userMsg = { id: nextId++, role: 'user', content: text, isStreaming: false, timestamp: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    return userMsg;
  }, []);

  const handleMessage = useCallback((type, payload) => {
    switch (type) {
      case 'message_chunk': {
        const chunk = payload.content || '';
        if (!isStreamingRef.current) {
          setMessages((prev) => [
            ...prev,
            { id: nextId++, role: 'assistant', content: chunk, isStreaming: true, timestamp: Date.now() },
          ]);
          setIsStreaming(true);
        } else {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.isStreaming) {
              updated[updated.length - 1] = { ...last, content: last.content + chunk };
            }
            return updated;
          });
        }
        break;
      }

      case 'message_complete': {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.isStreaming) {
            updated[updated.length - 1] = {
              ...last,
              isStreaming: false,
              trace: payload.trace,
            };
          }
          return updated;
        });
        setIsStreaming(false);
        break;
      }

      case 'voice_result': {
        const text = (payload.text || '').trim();
        if (text) {
          stopAudio();
          addUserMsgAndSend(text);
          if (sendRef.current) sendRef.current('chat', { message: text });
        }
        break;
      }

      case 'play_audio': {
        if (!ttsEnabledRef.current) break; // TTS disabled, skip
        const url = payload.url;
        if (url) {
          stopAudio();
          const audio = new Audio(url);
          audioRef.current = audio;
          audio.onended = () => { setIsSpeaking(false); };
          audio.onpause = () => { setIsSpeaking(false); };
          audio.play().then(() => setIsSpeaking(true)).catch((e) => console.error('Audio play failed:', e));
        }
        break;
      }

      case 'avatar_state':
        setAvatarState(payload.action || 'idle');
        break;

      case 'notes_list':
        setNotes(payload.notes || []);
        break;

      case 'note_saved':
        break;

      case 'note_deleted':
        setNotes((prev) => prev.filter((n) => n.id !== payload.note_id));
        break;

      case 'search_results':
        setNotes(payload.results || []);
        break;

      case 'notes_exported':
        alert(`笔记已导出到:\n${payload.file_path}`);
        break;

      case 'markdown_preview':
        setMarkdownPreview({
          content: payload.content || '',
          suggestedFilename: payload.suggested_filename || 'export.md',
        });
        break;

      case 'file_saved':
        alert(`文件已保存到:\n${payload.file_path}`);
        break;

      case 'config':
        setConfig(payload);
        break;

      case 'config_updated':
        break;

      case 'personalities_list': {
        setPersonalities(payload.personalities || []);
        if (payload.current) setCurrentPersonalityId(payload.current);
        break;
      }

      case 'personality_set': {
        setCurrentPersonalityId(payload.id);
        break;
      }

      case 'personality_created':
      case 'personality_updated':
      case 'personality_deleted':
        // Refresh list from backend
        send('get_personalities', {});
        break;

      case 'error': {
        console.error('Server error:', payload.message);
        break;
      }

      case 'tool_call_start': {
        const toolName = payload.name || 'unknown';
        // Show floating toast
        setToolToast({ name: toolName, text: `正在调用 ${toolName}...` });
        if (toolToastTimerRef.current) clearTimeout(toolToastTimerRef.current);

        // Append tool_call entry to the current streaming assistant message
        setMessages((prev) => {
          const updated = [...prev];
          // Find the most recent assistant message
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant') {
              const msg = updated[i];
              const toolCalls = msg.toolCalls ? [...msg.toolCalls] : [];
              toolCalls.push({
                id: `${toolName}_${Date.now()}`,
                name: toolName,
                args: payload.args || {},
                state: 'running',
              });
              updated[i] = { ...msg, toolCalls };
              break;
            }
          }
          return updated;
        });
        break;
      }

      case 'tool_call_result': {
        const resultName = payload.name || 'unknown';
        const durationMs = payload.duration_ms || 0;
        setToolToast({ name: resultName, text: `${resultName} 完成 · ${(durationMs / 1000).toFixed(1)}s` });
        toolToastTimerRef.current = setTimeout(() => setToolToast(null), 3000);

        setMessages((prev) => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].toolCalls) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls.map((tc) => {
                if (tc.name === resultName && tc.state === 'running') {
                  return {
                    ...tc,
                    state: 'completed',
                    result: payload.result || {},
                    duration_ms: durationMs,
                  };
                }
                return tc;
              });
              updated[i] = { ...msg, toolCalls };
              break;
            }
          }
          return updated;
        });
        break;
      }

      case 'tool_call_error': {
        const errName = payload.name || 'unknown';
        const errMsg = payload.error || 'Unknown error';
        setToolToast({ name: errName, text: `${errName} 失败: ${errMsg}` });
        toolToastTimerRef.current = setTimeout(() => setToolToast(null), 4000);

        setMessages((prev) => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].toolCalls) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls.map((tc) => {
                if (tc.name === errName && tc.state === 'running') {
                  return { ...tc, state: 'error', error: errMsg };
                }
                return tc;
              });
              updated[i] = { ...msg, toolCalls };
              break;
            }
          }
          return updated;
        });
        break;
      }

      case 'conversation_created': {
        const conv = payload;
        setActiveConvId(conv.id);
        setConversations(prev => [conv, ...prev]);
        break;
      }

      case 'conversations_list': {
        setConversations(payload.conversations || []);
        break;
      }

      case 'conversation_deleted': {
        const deletedId = payload.conversation_id;
        setConversations(prev => prev.filter(c => c.id !== deletedId));
        if (activeConvId === deletedId) {
          setActiveConvId(null);
          setMessages([]);
        }
        break;
      }

      case 'turn_deleted': {
        // Remove the deleted turn's messages from current view
        const deletedTurnIndex = payload.turn_index;
        setMessages((prev) => prev.filter((m) => m.turnIndex !== deletedTurnIndex));
        break;
      }

      case 'conversation_renamed': {
        const { conversation_id, title } = payload;
        setConversations(prev => prev.map(c =>
          c.id === conversation_id ? { ...c, title } : c
        ));
        break;
      }

      case 'conversation_loaded': {
        send('get_turns', { conversation_id: payload.conversation.id });
        break;
      }

      case 'turns_list': {
        const turns = payload.turns || [];
        const msgs = [];
        let msgId = 1;
        turns.forEach(turn => {
          msgs.push({
            id: msgId++, role: 'user', content: turn.user_message,
            isStreaming: false, timestamp: turn.created_at,
            turnIndex: turn.turn_index,
          });
          const tc = buildToolCallsFromTrace(turn.trace);
          msgs.push({
            id: msgId++, role: 'assistant', content: turn.assistant_content,
            isStreaming: false, timestamp: turn.created_at,
            trace: turn.trace,
            toolCalls: tc,
            turnIndex: turn.turn_index,
          });
        });
        setMessages(msgs);
        break;
      }

      default:
        break;
    }
  }, [addUserMsgAndSend]);

  const { connectionStatus, send } = useWebSocket({ onMessage: handleMessage });
  sendRef.current = send;

  const handleSend = useCallback((text) => {
    stopAudio();
    addUserMsgAndSend(text);
    const sent = send('chat', { message: text });
    if (!sent) {
      setMessages((prev) => [
        ...prev,
        { id: nextId++, role: 'assistant', content: '无法发送消息：后端未连接', isStreaming: false, timestamp: Date.now() },
      ]);
    }
  }, [send, addUserMsgAndSend]);

  const handleStop = useCallback(() => {
    stopAudio();
    send('stop', {});
  }, [send, stopAudio]);

  const handleSaveNote = useCallback((content) => {
    setSaveModal({ content });
    setSaveTags('');
  }, []);

  const handleDeleteMessage = useCallback((msgId, turnIndex) => {
    if (turnIndex !== undefined && turnIndex !== null) {
      // Delete from backend
      send('delete_turn', { turn_index: turnIndex });
    }
    // Remove from local state
    setMessages((prev) => prev.filter((m) => m.id !== msgId));
  }, [send]);

  const handleConfirmSave = useCallback(() => {
    if (!saveModal) return;
    const tags = saveTags.split(/[\s,]+/).map((t) => t.trim()).filter(Boolean);
    send('add_note', { content: saveModal.content, tags });
    setSaveModal(null);
  }, [saveModal, saveTags, send]);

  const handleVoiceInput = useCallback((base64Audio) => {
    send('voice_input', { audio_data: base64Audio });
  }, [send]);

  const handleToggleTts = useCallback((on) => {
    setTtsEnabled(on);
    if (!on) stopAudio();
    send('tts_enabled', { enabled: on });
  }, [send, stopAudio]);

  const handleGetNotes = useCallback(() => send('get_notes', {}), [send]);
  const handleSearchNotes = useCallback((q, t) => send('search_notes', { query: q, tags: t }), [send]);
  const handleDeleteNote = useCallback((id) => send('delete_note', { note_id: id }), [send]);
  const handleExportNotes = useCallback((ids) => send('export_notes', { note_ids: ids }), [send]);

  const handleSaveMarkdown = useCallback((content, filename) => {
    send('save_file', { content, filename });
    setMarkdownPreview(null);
  }, [send]);

  const handleCancelPreview = useCallback(() => setMarkdownPreview(null), []);

  const handleGetConfig = useCallback(() => {
    send('get_config', {});
  }, [send]);

  const handleUpdateConfig = useCallback((updates) => {
    send('update_config', { updates });
  }, [send]);

  const handleNewConv = useCallback(() => {
    send('create_conversation', { title: '' });
  }, [send]);

  const handleSelectConv = useCallback((convId) => {
    setActiveConvId(convId);
    setMessages([]);
    setDebugMsgId(null);
    send('load_conversation', { conversation_id: convId });
  }, [send]);

  const handleDeleteConv = useCallback((convId) => {
    if (confirm('确定删除此对话？')) {
      send('delete_conversation', { conversation_id: convId });
    }
  }, [send]);

  const handleRenameConv = useCallback((convId, title) => {
    send('rename_conversation', { conversation_id: convId, title });
  }, [send]);

  const handleToggleDebug = useCallback((msgId) => {
    setDebugMsgId(prev => prev === msgId ? null : msgId);
  }, []);

  // Request conversation list when connection is established
  const prevStatusRef = useRef(connectionStatus);
  useEffect(() => {
    if (connectionStatus === 'connected' && prevStatusRef.current !== 'connected') {
      send('list_conversations', {});
      send('get_personalities', {});
      send('get_config', {});
    }
    prevStatusRef.current = connectionStatus;
  }, [connectionStatus, send]);

  // Live2D-only desktop pet mode — JS drag + click to toggle
  const isLive2DOnly = window.location.search.includes('mode=live2d');
  const petDragRef = useRef({ startX: 0, startY: 0, moved: false });
  const petClickRef = useRef(null);

  if (isLive2DOnly) {
    const toggleMain = () => {
      if (window.electronAPI) window.electronAPI.toggleMainWindow();
    };

    const onPetMouseDown = (e) => {
      petDragRef.current = { startX: e.screenX, startY: e.screenY, moved: false };
      petClickRef.current = { x: e.screenX, y: e.screenY };

      const onMove = (ev) => {
        const dx = ev.screenX - petClickRef.current.x;
        const dy = ev.screenY - petClickRef.current.y;
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
          petDragRef.current.moved = true;
        }
        if (window.electronAPI?.moveLive2dWindow) {
          window.electronAPI.moveLive2dWindow(dx, dy);
        }
        petClickRef.current = { x: ev.screenX, y: ev.screenY };
      };

      const onUp = () => {
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
        if (!petDragRef.current.moved) {
          toggleMain();
        }
      };

      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    };

    return (
      <div className="live2d-only-container" onMouseDown={onPetMouseDown}>
        <Live2DAvatar state={avatarState} />
      </div>
    );
  }

  return (
    <div className="app-container">
      <ConversationList
        conversations={conversations}
        activeId={activeConvId}
        onNew={handleNewConv}
        onSelect={handleSelectConv}
        onDelete={handleDeleteConv}
        onRename={handleRenameConv}
      />
      <div className="main-content">
        <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
        <StatusBar
          status={connectionStatus}
          ttsEnabled={ttsEnabled}
          onToggleTts={handleToggleTts}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        {isSpeaking && (
          <div className="speaking-bar">
            <span>🔊 正在朗读...</span>
            <button className="btn-stop-speaking" onClick={stopAudio}>⏹ 停止朗读</button>
          </div>
        )}
        {toolToast && (
          <div className="tool-toast">
            <span>🔧</span>
            <span>{toolToast.text}</span>
          </div>
        )}
        {wallpaper && (
          <div className="wallpaper-layer" style={{ backgroundImage: `url(${wallpaper})` }} />
        )}
        {activeTab === 'chat' ? (
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
        ) : (
          <NotesPanel
            notes={notes}
            onGetNotes={handleGetNotes}
            onSearch={handleSearchNotes}
            onDelete={handleDeleteNote}
            onExport={handleExportNotes}
          />
        )}
      </div>

      {/* Settings Drawer */}
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
            />
          </div>
        </div>
      )}

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
          <Live2DAvatar state={avatarState} />
        </div>
      </FeatureGuard>
    </div>
  );
}
