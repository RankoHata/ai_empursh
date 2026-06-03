import React, { useState, useCallback, useRef } from 'react';
import useWebSocket from './hooks/useWebSocket';
import StatusBar from './components/StatusBar';
import TabBar from './components/TabBar';
import ChatPanel from './components/ChatPanel';
import NotesPanel from './components/NotesPanel';
import AvatarStatus from './components/AvatarStatus';

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
  const audioRef = useRef(null);
  const sendRef = useRef(null);

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
          addUserMsgAndSend(text);
          // Also send via WebSocket to trigger AI reply
          if (sendRef.current) sendRef.current('chat', { message: text });
        }
        break;
      }

      case 'play_audio': {
        const url = payload.url;
        if (url) {
          const audio = new Audio(url);
          audioRef.current = audio;
          audio.play().catch((e) => console.error('Audio play failed:', e));
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
    addUserMsgAndSend(text);
    const sent = send('chat', { message: text });
    if (!sent) {
      setMessages((prev) => [
        ...prev,
        { id: nextId++, role: 'assistant', content: '无法发送消息：后端未连接', isStreaming: false, timestamp: Date.now() },
      ]);
    }
  }, [send, addUserMsgAndSend]);

  const handleStop = useCallback(() => send('stop', {}), [send]);

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

  const handleGetNotes = useCallback(() => send('get_notes', {}), [send]);
  const handleSearchNotes = useCallback((q, t) => send('search_notes', { query: q, tags: t }), [send]);
  const handleDeleteNote = useCallback((id) => send('delete_note', { note_id: id }), [send]);
  const handleExportNotes = useCallback((ids) => send('export_notes', { note_ids: ids }), [send]);

  return (
    <div className="app-container">
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
      <StatusBar status={connectionStatus} alwaysOn={alwaysOn} onToggleAlwaysOn={handleToggleAlwaysOn} />
      <AvatarStatus state={avatarState} />
      {activeTab === 'chat' ? (
        <ChatPanel
          messages={messages}
          isStreaming={isStreaming}
          onSend={handleSend}
          onStop={handleStop}
          onSaveNote={handleSaveNote}
          onVoiceInput={handleVoiceInput}
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
    </div>
  );
}
