import React, { useState, useCallback, useRef } from 'react';
import useWebSocket from './hooks/useWebSocket';
import StatusBar from './components/StatusBar';
import ChatPanel from './components/ChatPanel';

let nextId = 1;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);

  // Use refs for values that onMessage closure needs to see without re-subscribing
  const messagesRef = useRef(messages);
  const isStreamingRef = useRef(isStreaming);
  messagesRef.current = messages;
  isStreamingRef.current = isStreaming;

  const handleMessage = useCallback((type, payload) => {
    switch (type) {
      case 'message_chunk': {
        const chunk = payload.content || '';
        if (!isStreamingRef.current) {
          // First chunk: create the assistant message
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
          // Append to the last (streaming) message
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
        // Mark the streaming message as complete
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

      case 'error': {
        console.error('Server error:', payload.message);
        // Show error as a system message
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

  const handleSend = useCallback(
    (text) => {
      // Add user message to local state
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

  return (
    <div className="app-container">
      <StatusBar status={connectionStatus} />
      <ChatPanel
        messages={messages}
        isStreaming={isStreaming}
        onSend={handleSend}
        onStop={handleStop}
      />
    </div>
  );
}
