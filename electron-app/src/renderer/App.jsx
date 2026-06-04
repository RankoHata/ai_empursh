import React, { useState, useCallback, useRef } from 'react';
import useWebSocket from './hooks/useWebSocket';
import StatusBar from './components/StatusBar';
import TabBar from './components/TabBar';
import ChatPanel from './components/ChatPanel';
import NotesPanel from './components/NotesPanel';
import AvatarStatus from './components/AvatarStatus';
import MarkdownPreview from './components/MarkdownPreview';
import SettingsPanel from './components/SettingsPanel';
import Live2DAvatar from './components/Live2DAvatar';

let nextId = 1;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');
  const [notes, setNotes] = useState([]);
  const [saveModal, setSaveModal] = useState(null);
  const [saveTags, setSaveTags] = useState('');
  const [avatarState, setAvatarState] = useState('idle');
  const [alwaysOn, setAlwaysOn] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [markdownPreview, setMarkdownPreview] = useState(null);
  const [config, setConfig] = useState(null);
  const audioRef = useRef(null);
  const sendRef = useRef(null);
  const ttsEnabledRef = useRef(ttsEnabled);
  ttsEnabledRef.current = ttsEnabled;

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
            updated[updated.length - 1] = { ...last, isStreaming: false };
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

      case 'voice_status':
        setAlwaysOn(payload.always_on || false);
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

      case 'error': {
        console.error('Server error:', payload.message);
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

  const handleConfirmSave = useCallback(() => {
    if (!saveModal) return;
    const tags = saveTags.split(/[\s,]+/).map((t) => t.trim()).filter(Boolean);
    send('add_note', { content: saveModal.content, tags });
    setSaveModal(null);
  }, [saveModal, saveTags, send]);

  const handleVoiceInput = useCallback((base64Audio) => {
    send('voice_input', { audio_data: base64Audio });
  }, [send]);

  const handleToggleAlwaysOn = useCallback((on) => {
    setAlwaysOn(on);
    send('voice_mode', { always_on: on });
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

  // Live2D-only desktop pet mode
  const isLive2DOnly = window.location.search.includes('mode=live2d');

  if (isLive2DOnly) {
    const toggleMain = () => {
      if (window.electronAPI) window.electronAPI.toggleMainWindow();
    };
    return (
      <div className="live2d-only-container" onContextMenu={(e) => { e.preventDefault(); toggleMain(); }}>
        <Live2DAvatar state={avatarState} />
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="main-content">
        <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
        <StatusBar
          status={connectionStatus}
          alwaysOn={alwaysOn}
          ttsEnabled={ttsEnabled}
          onToggleAlwaysOn={handleToggleAlwaysOn}
          onToggleTts={handleToggleTts}
        />
        {isSpeaking && (
          <div className="speaking-bar">
            <span>🔊 正在朗读...</span>
            <button className="btn-stop-speaking" onClick={stopAudio}>⏹ 停止朗读</button>
          </div>
        )}
        {activeTab === 'chat' ? (
          <ChatPanel
            messages={messages}
            isStreaming={isStreaming}
            onSend={handleSend}
            onStop={handleStop}
            onSaveNote={handleSaveNote}
            onVoiceInput={handleVoiceInput}
          />
        ) : activeTab === 'notes' ? (
          <NotesPanel
            notes={notes}
            onGetNotes={handleGetNotes}
            onSearch={handleSearchNotes}
            onDelete={handleDeleteNote}
            onExport={handleExportNotes}
          />
        ) : (
          <SettingsPanel
            config={config}
          onUpdateConfig={handleUpdateConfig}
          onLoad={handleGetConfig}
        />
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
      </div>
      <div className="live2d-sidebar">
        <Live2DAvatar state={avatarState} />
      </div>
    </div>
  );
}
