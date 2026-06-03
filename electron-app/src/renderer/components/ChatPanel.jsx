import React, { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';

export default function ChatPanel({ messages, isStreaming, onSend, onStop, onSaveNote }) {
  const [input, setInput] = useState('');
  const [ctxMenu, setCtxMenu] = useState(null); // { x, y, content } or null
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Close context menu on any click
  useEffect(() => {
    const close = () => setCtxMenu(null);
    if (ctxMenu) {
      window.addEventListener('click', close);
      return () => window.removeEventListener('click', close);
    }
  }, [ctxMenu]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    onSend(text);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleContextMenu = (e, msg) => {
    e.preventDefault();
    // Only allow saving assistant messages with content
    if (msg.role === 'assistant' && msg.content && !msg.isStreaming) {
      setCtxMenu({ x: e.clientX, y: e.clientY, content: msg.content });
    }
  };

  const handleSaveAsNote = () => {
    if (ctxMenu && onSaveNote) {
      onSaveNote(ctxMenu.content);
    }
    setCtxMenu(null);
  };

  return (
    <div className="chat-panel">
      <div className="messages-area">
        {messages.length === 0 && (
          <div className="messages-empty">
            <span>向 AI 助理发送消息开始对话</span>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            onContextMenu={(e) => handleContextMenu(e, msg)}
            style={{ display: 'contents' }}
          >
            <MessageBubble message={msg} />
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Context menu */}
      {ctxMenu && (
        <div className="context-menu" style={{ left: ctxMenu.x, top: ctxMenu.y }}>
          <button className="context-menu-item" onClick={handleSaveAsNote}>
            💾 保存为笔记
          </button>
        </div>
      )}

      <div className="input-area">
        <input
          type="text"
          placeholder="输入消息... (Enter 发送)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />
        {isStreaming ? (
          <button className="btn-stop" onClick={onStop}>停止</button>
        ) : (
          <button className="btn-send" onClick={handleSend} disabled={!input.trim()}>
            发送
          </button>
        )}
      </div>
    </div>
  );
}
