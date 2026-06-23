import { useState, useCallback, useRef, useEffect } from 'react';

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

/**
 * useChat — 聊天消息 + 流式状态 + 工具调用 + 思考状态 + 语音 + TTS + 情绪
 *
 * @param {Function} send           — WebSocket send 函数
 * @param {Object}   settingsRefs   — { emotionFollowRef, ttsEnabledRef, emotionTimerRef }
 * @param {Function} onAvatarState  — setAvatarState from outside
 */
export default function useChat(send, settingsRefs, onAvatarState) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [toolToast, setToolToast] = useState(null);
  const [debugMsgId, setDebugMsgId] = useState(null);

  const audioRef = useRef(null);
  const toolToastTimerRef = useRef(null);
  const messagesRef = useRef(messages);
  const isStreamingRef = useRef(isStreaming);
  messagesRef.current = messages;
  isStreamingRef.current = isStreaming;
  const settingsRefsRef = useRef(settingsRefs);
  settingsRefsRef.current = settingsRefs;

  // ── Audio / TTS ──

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
      setIsSpeaking(false);
    }
  }, []);

  // ── Messages ──

  const addUserMsgAndSend = useCallback((text) => {
    const userMsg = { id: nextId++, role: 'user', content: text, isStreaming: false, timestamp: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    return userMsg;
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  // ── Send / Stop / Delete ──

  const handleSend = useCallback((text) => {
    stopAudio();
    addUserMsgAndSend(text);
    const sent = send('chat', { message: text });
    if (!sent) {
      setMessages(prev => [
        ...prev,
        { id: nextId++, role: 'assistant', content: '无法发送消息：后端未连接', isStreaming: false, timestamp: Date.now() },
      ]);
    }
  }, [send, stopAudio, addUserMsgAndSend]);

  const handleStop = useCallback(() => {
    stopAudio();
    send('stop', {});
  }, [send, stopAudio]);

  const handleDeleteMessage = useCallback((msgId, turnIndex) => {
    if (turnIndex != null) {
      send('delete_turn', { turn_index: turnIndex });
    }
    setMessages(prev => prev.filter(m => m.id !== msgId));
  }, [send]);

  const handleToggleDebug = useCallback((msgId) => {
    setDebugMsgId(prev => prev === msgId ? null : msgId);
  }, []);

  // ── Voice ──

  const handleVoiceInput = useCallback((base64Audio) => {
    stopAudio();
    send('voice_input', { audio: base64Audio });
  }, [send, stopAudio]);

  // ── Save note (opens saveModal in useNotes, bridged by App) ──

  const handleSaveNoteBridge = useCallback((content, onSaveNote) => {
    if (onSaveNote) onSaveNote(content);
  }, []);

  // ── WS message handler ──

  const onMessage = useCallback((type, payload) => {
    const refs = settingsRefsRef.current;

    switch (type) {
      case 'message_chunk': {
        const chunk = payload.content || '';
        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].isStreaming) {
              updated[i] = { ...updated[i], content: updated[i].content + chunk };
              return updated;
            }
          }
          updated.push({ id: nextId++, role: 'assistant', content: chunk, isStreaming: true, timestamp: Date.now() });
          return updated;
        });
        setIsStreaming(true);
        return true;
      }

      case 'message_complete': {
        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant') {
              updated[i] = {
                ...updated[i],
                content: payload.full_content || updated[i].content,
                isStreaming: false,
                thinking: null,
                trace: payload.trace,
              };
              break;
            }
          }
          return updated;
        });
        setIsStreaming(false);
        if (refs.emotionFollowRef?.current && payload.emotion && payload.emotion !== 'idle') {
          onAvatarState?.(payload.emotion);
          window.electronAPI?.setAvatarEmotion(payload.emotion);
          if (refs.emotionTimerRef?.current) clearTimeout(refs.emotionTimerRef.current);
          refs.emotionTimerRef.current = setTimeout(() => {
            onAvatarState?.('idle');
            window.electronAPI?.setAvatarEmotion('idle');
          }, 3000);
        }
        return true;
      }

      case 'thinking': {
        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].isStreaming) {
              updated[i] = { ...updated[i], thinking: payload.content };
              break;
            }
          }
          return updated;
        });
        return true;
      }

      case 'done': {
        setIsStreaming(false);
        setMessages(prev =>
          prev.map(m => m.isStreaming ? { ...m, isStreaming: false, thinking: null } : m)
        );
        return true;
      }

      case 'voice_result':
        // Handled by App.handleMessage (needs send() for re-dispatch)
        return false;

      case 'play_audio': {
        if (!refs.ttsEnabledRef?.current) return true;
        stopAudio();
        const audio = new Audio(`data:audio/mp3;base64,${payload.audio}`);
        audioRef.current = audio;
        setIsSpeaking(true);
        audio.onended = () => setIsSpeaking(false);
        audio.onerror = () => setIsSpeaking(false);
        audio.play().catch(() => setIsSpeaking(false));
        return true;
      }

      case 'avatar_state': {
        onAvatarState?.(payload.emotion || 'idle');
        return true;
      }

      case 'tool_call_start': {
        const callId = payload.id || `${payload.name}_${Date.now()}`;
        const toolName = payload.name || 'unknown';
        setToolToast({ name: toolName, text: `正在调用 ${toolName}...` });
        if (toolToastTimerRef.current) clearTimeout(toolToastTimerRef.current);

        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].isStreaming) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls ? [...msg.toolCalls] : [];
              toolCalls.push({ id: callId, name: toolName, args: payload.args || {}, state: 'running' });
              updated[i] = { ...msg, toolCalls };
              return updated;
            }
          }
          updated.push({
            id: nextId++, role: 'assistant', content: '', isStreaming: true, timestamp: Date.now(),
            toolCalls: [{ id: callId, name: toolName, args: payload.args || {}, state: 'running' }],
          });
          return updated;
        });
        return true;
      }

      case 'tool_call_result': {
        const callId = payload.id || '';
        const resultName = payload.name || 'unknown';
        const durationMs = payload.duration_ms || 0;
        setToolToast({ name: resultName, text: `${resultName} 完成 · ${(durationMs / 1000).toFixed(1)}s` });
        toolToastTimerRef.current = setTimeout(() => setToolToast(null), 3000);

        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].isStreaming && updated[i].toolCalls) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls.map(tc => {
                const matches = callId ? tc.id === callId : (tc.name === resultName && tc.state === 'running');
                if (matches) return { ...tc, state: 'completed', result: payload.result || {}, duration_ms: durationMs };
                return tc;
              });
              updated[i] = { ...msg, toolCalls };
              return updated;
            }
          }
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].toolCalls) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls.map(tc => {
                const matches = callId ? tc.id === callId : (tc.name === resultName && tc.state === 'running');
                if (matches) return { ...tc, state: 'completed', result: payload.result || {}, duration_ms: durationMs };
                return tc;
              });
              updated[i] = { ...msg, toolCalls };
              return updated;
            }
          }
          return updated;
        });
        return true;
      }

      case 'tool_call_error': {
        const callId = payload.id || '';
        const errName = payload.name || 'unknown';
        const errMsg = payload.error || 'Unknown error';
        setToolToast({ name: errName, text: `${errName} 失败: ${errMsg}` });
        toolToastTimerRef.current = setTimeout(() => setToolToast(null), 4000);

        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].isStreaming && updated[i].toolCalls) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls.map(tc => {
                const matches = callId ? tc.id === callId : (tc.name === errName && tc.state === 'running');
                if (matches) return { ...tc, state: 'error', error: errMsg };
                return tc;
              });
              updated[i] = { ...msg, toolCalls };
              return updated;
            }
          }
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].toolCalls) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls.map(tc => {
                const matches = callId ? tc.id === callId : (tc.name === errName && tc.state === 'running');
                if (matches) return { ...tc, state: 'error', error: errMsg };
                return tc;
              });
              updated[i] = { ...msg, toolCalls };
              return updated;
            }
          }
          return updated;
        });
        return true;
      }

      case 'turns_list': {
        const turns = payload.turns || [];
        const msgs = [];
        turns.forEach(turn => {
          msgs.push({ id: nextId++, role: 'user', content: turn.user_content, isStreaming: false, timestamp: turn.created_at });
          const tc = buildToolCallsFromTrace(turn.trace);
          msgs.push({
            id: nextId++, role: 'assistant', content: turn.assistant_content,
            isStreaming: false, timestamp: turn.created_at,
            trace: turn.trace, toolCalls: tc, turnIndex: turn.turn_index,
          });
        });
        setMessages(msgs);
        return true;
      }

      case 'error': {
        console.error('Server error:', payload.message);
        return true;
      }

      default:
        return false;
    }
  }, [send, stopAudio, addUserMsgAndSend, onAvatarState]);

  return {
    messages,
    isStreaming,
    isSpeaking,
    toolToast,
    debugMsgId,
    audioRef,
    toolToastTimerRef,
    messagesRef,
    isStreamingRef,
    stopAudio,
    addUserMsgAndSend,
    clearMessages,
    handleSend,
    handleStop,
    handleDeleteMessage,
    handleToggleDebug,
    handleVoiceInput,
    handleSaveNoteBridge,
    onMessage,
  };
}
