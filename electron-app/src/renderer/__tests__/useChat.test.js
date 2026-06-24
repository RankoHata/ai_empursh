import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import useChat from '../hooks/useChat';

describe('useChat', () => {
  let send, settingsRefs, onAvatarState;

  beforeEach(() => {
    send = vi.fn(() => true);
    settingsRefs = {
      emotionFollowRef: { current: true },
      ttsEnabledRef: { current: false },
      emotionTimerRef: { current: null },
    };
    onAvatarState = vi.fn();
  });

  it('starts with empty messages', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
  });

  it('addUserMsgAndSend creates user message', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.addUserMsgAndSend('hello'); });
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].content).toBe('hello');
  });

  it('handleSend sends chat message and adds user msg', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.handleSend('hi'); });
    expect(send).toHaveBeenCalledWith('chat', { message: 'hi' });
    expect(result.current.messages).toHaveLength(1);
  });

  it('handleSend shows error when not connected', () => {
    send = vi.fn(() => false);
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.handleSend('hi'); });
    expect(result.current.messages[1]?.content).toContain('无法发送');
  });

  it('handleStop sends stop signal', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.handleStop(); });
    expect(send).toHaveBeenCalledWith('stop', {});
  });

  it('message_chunk creates streaming assistant message', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.onMessage('message_chunk', { content: 'Hello' }); });
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe('assistant');
    expect(result.current.messages[0].isStreaming).toBe(true);
  });

  it('message_chunk appends to existing streaming message', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.onMessage('message_chunk', { content: 'Hello' }); });
    act(() => { result.current.onMessage('message_chunk', { content: ' World' }); });
    expect(result.current.messages[0].content).toBe('Hello World');
  });

  it('message_complete finalizes and clears thinking', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.onMessage('message_chunk', { content: 'Hi' }); });
    act(() => { result.current.onMessage('thinking', { content: 'thinking...' }); });
    act(() => { result.current.onMessage('message_complete', { full_content: 'Hi!' }); });
    expect(result.current.messages[0].isStreaming).toBe(false);
    expect(result.current.messages[0].thinking).toBeNull();
  });

  it('done clears streaming state', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.onMessage('message_chunk', { content: 'Hi' }); });
    act(() => { result.current.onMessage('done', {}); });
    expect(result.current.messages[0].isStreaming).toBe(false);
  });

  it('tool_call_start attaches to streaming message', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.onMessage('message_chunk', { content: 'Let me check' }); });
    act(() => {
      result.current.onMessage('tool_call_start', {
        id: 'tc1', name: 'search_notes', args: { query: 'test' },
      });
    });
    expect(result.current.messages[0].toolCalls).toHaveLength(1);
    expect(result.current.messages[0].toolCalls[0].state).toBe('running');
  });

  it('tool_call_result updates tool state', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.onMessage('message_chunk', { content: 'Let me check' }); });
    act(() => {
      result.current.onMessage('tool_call_start', { id: 'tc1', name: 'search_notes', args: {} });
    });
    act(() => {
      result.current.onMessage('tool_call_result', { id: 'tc1', name: 'search_notes', duration_ms: 100 });
    });
    expect(result.current.messages[0].toolCalls[0].state).toBe('completed');
  });

  it('deleteMessage removes message', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.addUserMsgAndSend('test'); });
    const msgId = result.current.messages[0].id;
    act(() => { result.current.handleDeleteMessage(msgId); });
    expect(result.current.messages).toHaveLength(0);
  });

  it('clearMessages empties all messages', () => {
    const { result } = renderHook(() => useChat(send, settingsRefs, onAvatarState));
    act(() => { result.current.addUserMsgAndSend('a'); });
    act(() => { result.current.addUserMsgAndSend('b'); });
    act(() => { result.current.clearMessages(); });
    expect(result.current.messages).toHaveLength(0);
  });
});
