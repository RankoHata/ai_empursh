import React, { useState, useRef, useEffect, useCallback } from 'react';
import MessageBubble from './MessageBubble';

export default function ChatPanel({ messages, isStreaming, onSend, onStop, onSaveNote, onVoiceInput }) {
  const [input, setInput] = useState('');
  const [ctxMenu, setCtxMenu] = useState(null);
  const [recording, setRecording] = useState(false);
  const bottomRef = useRef(null);
  const messagesRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Native contextmenu handler via event delegation
  useEffect(() => {
    const area = messagesRef.current;
    if (!area) return;
    const handler = (e) => {
      const bubble = e.target.closest('[data-msg-id]');
      if (!bubble) return;
      e.preventDefault();
      const msgId = parseInt(bubble.dataset.msgId, 10);
      const msg = messages.find((m) => m.id === msgId);
      if (msg && msg.role === 'assistant' && msg.content && !msg.isStreaming) {
        setCtxMenu({ x: e.clientX, y: e.clientY, content: msg.content });
      }
    };
    area.addEventListener('contextmenu', handler);
    return () => area.removeEventListener('contextmenu', handler);
  }, [messages]);

  useEffect(() => {
    if (!ctxMenu) return;
    const close = () => setCtxMenu(null);
    const timer = setTimeout(() => window.addEventListener('click', close, { once: true }), 0);
    return () => { clearTimeout(timer); window.removeEventListener('click', close); };
  }, [ctxMenu]);

  // --- Recording ---
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorderRef.current = mr;
      chunksRef.current = [];

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        chunksRef.current = [];
        if (blob.size < 100) return; // too small, skip

        // Read as base64
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64 = reader.result.split(',')[1];
          if (onVoiceInput) onVoiceInput(base64);
        };
        reader.readAsDataURL(blob);
      };

      mr.start();
      setRecording(true);
    } catch (err) {
      console.error('Failed to start recording:', err);
    }
  }, [onVoiceInput]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
  }, []);

  const toggleRecording = useCallback(() => {
    if (recording) stopRecording();
    else startRecording();
  }, [recording, startRecording, stopRecording]);

  // --- Chat ---
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
    if (ctxMenu && onSaveNote) onSaveNote(ctxMenu.content);
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
        <button
          className={`btn-voice ${recording ? 'recording' : ''}`}
          onClick={toggleRecording}
          title={recording ? '停止录音' : '开始录音'}
        >
          {recording ? '🔴' : '🎤'}
        </button>
        <input
          type="text"
          placeholder={recording ? '录制中...' : '输入消息... (Enter 发送)'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={recording}
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
