import React, { useState, useRef, useEffect, useCallback } from 'react';
import MessageBubble from './MessageBubble';

// --- WAV encoding helpers ---
function encodeWAV(samples, sampleRate) {
  const numSamples = samples.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);

  function writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + numSamples * 2, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);       // chunk size
  view.setUint16(20, 1, true);        // PCM
  view.setUint16(22, 1, true);        // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);        // 16-bit per sample
  view.setUint16(34, 16, true);
  writeString(view, 36, 'data');
  view.setUint32(40, numSamples * 2, true);

  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    const val = s < 0 ? s * 0x8000 : s * 0x7FFF;
    view.setInt16(offset, val, true);
    offset += 2;
  }

  return buffer;
}

export default function ChatPanel({ messages, isStreaming, onSend, onStop, onSaveNote, onVoiceInput, onToggleDebug, debugMsgId, compactMode, onDeleteMessage }) {
  const [input, setInput] = useState('');
  const [ctxMenu, setCtxMenu] = useState(null);
  const [recording, setRecording] = useState(false);
  const bottomRef = useRef(null);
  const messagesRef = useRef(null);
  const audioCtxRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const area = messagesRef.current;
    if (!area) return;
    const handler = (e) => {
      const bubble = e.target.closest('[data-msg-id]');
      if (!bubble) return;
      e.preventDefault();
      const msgId = parseInt(bubble.dataset.msgId, 10);
      const msg = messages.find((m) => m.id === msgId);
      if (msg && msg.content && !msg.isStreaming) {
        setCtxMenu({ x: e.clientX, y: e.clientY, content: msg.content, msgId: msg.id, turnIndex: msg.turnIndex });
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

  // --- PCM Recording via AudioContext ---
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioCtx = new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      // ScriptProcessor is deprecated but works universally; AudioWorklet requires a separate file
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      chunksRef.current = [];

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        // Copy because the buffer is reused
        chunksRef.current.push(new Float32Array(inputData));
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);
      setRecording(true);
    } catch (err) {
      console.error('Failed to start recording:', err);
    }
  }, []);

  const stopRecording = useCallback(() => {
    // Disconnect audio graph
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    // Combine all Float32Arrays
    const allChunks = chunksRef.current;
    chunksRef.current = [];
    if (allChunks.length === 0) {
      setRecording(false);
      return;
    }

    let totalLen = 0;
    for (const c of allChunks) totalLen += c.length;
    const combined = new Float32Array(totalLen);
    let offset = 0;
    for (const c of allChunks) {
      combined.set(c, offset);
      offset += c.length;
    }

    // Encode as WAV (16-bit PCM, 16kHz, mono)
    const wavBuffer = encodeWAV(combined, 16000);
    const blob = new Blob([wavBuffer], { type: 'audio/wav' });

    if (blob.size < 100) {
      setRecording(false);
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result.split(',')[1];
      if (onVoiceInput) onVoiceInput(base64);
    };
    reader.readAsDataURL(blob);
    setRecording(false);
  }, [onVoiceInput]);

  const toggleRecording = useCallback(() => {
    if (recording) stopRecording();
    else startRecording();
  }, [recording, startRecording, stopRecording]);

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

  const handleDeleteMessage = () => {
    if (ctxMenu && onDeleteMessage) onDeleteMessage(ctxMenu.msgId, ctxMenu.turnIndex);
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
          <MessageBubble
            key={msg.id}
            message={{ ...msg, debugVisible: debugMsgId === msg.id }}
            onToggleDebug={onToggleDebug}
            compactMode={compactMode}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {ctxMenu && (
        <div className="context-menu" style={{ left: ctxMenu.x, top: ctxMenu.y }}>
          {messages.find(m => m.id === ctxMenu.msgId)?.role === 'assistant' && (
            <button className="context-menu-item" onClick={handleSaveAsNote}>
              💾 保存为笔记
            </button>
          )}
          <button className="context-menu-item context-menu-item-danger" onClick={handleDeleteMessage}>
            🗑 删除
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
