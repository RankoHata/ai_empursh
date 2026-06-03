import React, { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';

export default function ChatPanel({ messages, isStreaming, onSend, onStop, onSaveNote }) {
  const [input, setInput] = useState('');
  const [ctxMenu, setCtxMenu] = useState(null);
  const bottomRef = useRef(null);
  const messagesRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Native contextmenu handler via event delegation — more reliable in Electron
  useEffect(() => {
    const area = messagesRef.current;
    if (!area) return;

    const handler = (e) => {
      const bubble = e.target.closest('[data-msg-id]');
      if (!bubble) return;
      e.preventDefault();
      const msgId = parseInt(bubble.dataset.msgId, 10);
      const msg = messages.find((m) => m.id === msgId);
      console.log('[ChatPanel] right-click on msg:', msgId, 'role:', msg?.role);
      if (msg && msg.role === 'assistant' && msg.content && !msg.isStreaming) {
        setCtxMenu({ x: e.clientX, y: e.clientY, content: msg.content });
        console.log('[ChatPanel] context menu opened at', e.clientX, e.clientY);
      }
    };

    area.addEventListener('contextmenu', handler);
    return () => area.removeEventListener('contextmenu', handler);
  }, [messages]);

  // Close context menu on any click (delay to allow menu item onClick to fire first)
  useEffect(() => {
    if (!ctxMenu) return;
    const close = () => {
      console.log('[ChatPanel] closing context menu');
      setCtxMenu(null);
    };
    // Use setTimeout to ensure menu button onClick fires before close
    const timer = setTimeout(() => {
      window.addEventListener('click', close, { once: true });
    }, 0);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('click', close);
    };
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

  const handleSaveAsNote = () => {
    console.log('[ChatPanel] save as note clicked, content:', ctxMenu?.content?.slice(0, 50));
    if (ctxMenu && onSaveNote) {
      onSaveNote(ctxMenu.content);
    }
    setCtxMenu(null);
  };

  return (
    <div className="chat-panel">
      <div className="messages-area" ref={messagesRef}>
        {messages.length === 0 && (
          <div className="messages-empty">
            <span>向 AI 助理发送消息开始对话</span>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

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
