import React, { useState, useCallback, useRef } from 'react';
import useWebSocket from './hooks/useWebSocket';
import StatusBar from './components/StatusBar';
import TabBar from './components/TabBar';
import ChatPanel from './components/ChatPanel';
import NotesPanel from './components/NotesPanel';

let nextId = 1;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');
  const [notes, setNotes] = useState([]);

  // Use refs for values that onMessage closure needs to see without re-subscribing
  const messagesRef = useRef(messages);
  const isStreamingRef = useRef(isStreaming);
  messagesRef.current = messages;
  isStreamingRef.current = isStreaming;

  const handleMessage = useCallback((type, payload) => {
    switch (type) {
      // --- Chat messages ---
      case 'message_chunk': {
        const chunk = payload.content || '';
        if (!isStreamingRef.current) {
          setMessages((prev) => [
            ...prev,
            {
              id: nextId++,
              role: 'assistant',
              content: chunk,
              isStreaming: true,
              timestamp: Date.now(),
            },
          ]);
          setIsStreaming(true);
        } else {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.isStreaming) {
              updated[updated.length - 1] = {
                ...last,
                content: last.content + chunk,
              };
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
            };
          }
          return updated;
        });
        setIsStreaming(false);
        break;
      }

      // --- Notes messages ---
      case 'notes_list':
        setNotes(payload.notes || []);
        break;

      case 'note_saved':
        // Refresh notes list after saving
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
        setMessages((prev) => [
          ...prev,
          {
            id: nextId++,
            role: 'assistant',
            content: `错误: ${payload.message}`,
            isStreaming: false,
            timestamp: Date.now(),
          },
        ]);
        setIsStreaming(false);
        break;
      }

      default:
        break;
    }
  }, []);

  const { connectionStatus, send } = useWebSocket({ onMessage: handleMessage });

  // --- Chat actions ---
  const handleSend = useCallback(
    (text) => {
      const userMsg = {
        id: nextId++,
        role: 'user',
        content: text,
        isStreaming: false,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);

      const sent = send('chat', { message: text });
      if (!sent) {
        setMessages((prev) => [
          ...prev,
          {
            id: nextId++,
            role: 'assistant',
            content: '无法发送消息：后端未连接',
            isStreaming: false,
            timestamp: Date.now(),
          },
        ]);
      }
    },
    [send],
  );

  const handleStop = useCallback(() => {
    send('stop', {});
  }, [send]);

  const handleSaveNote = useCallback(
    (content) => {
      const tagStr = window.prompt('输入标签（用空格或逗号分隔）:', '');
      if (tagStr === null) return; // user cancelled
      const tags = tagStr
        .split(/[\s,]+/)
        .map((t) => t.trim())
        .filter(Boolean);
      send('add_note', { content, tags });
    },
    [send],
  );

  // --- Notes actions ---
  const handleGetNotes = useCallback(() => {
    send('get_notes', {});
  }, [send]);

  const handleSearchNotes = useCallback(
    (query, tags) => {
      send('search_notes', { query, tags });
    },
    [send],
  );

  const handleDeleteNote = useCallback(
    (id) => {
      send('delete_note', { note_id: id });
    },
    [send],
  );

  const handleExportNotes = useCallback(
    (ids) => {
      send('export_notes', { note_ids: ids });
    },
    [send],
  );

  return (
    <div className="app-container">
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
      <StatusBar status={connectionStatus} />
      {activeTab === 'chat' ? (
        <ChatPanel
          messages={messages}
          isStreaming={isStreaming}
          onSend={handleSend}
          onStop={handleStop}
          onSaveNote={handleSaveNote}
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
  );
}
