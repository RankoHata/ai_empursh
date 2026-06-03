import React from 'react';

export default function MessageBubble({ message }) {
  const { role, content, isStreaming, timestamp } = message;
  const label = role === 'user' ? '你' : '助理';

  const bubbleClass = [
    'message-bubble',
    role === 'user' ? 'user' : 'assistant',
  ].join(' ');

  const contentClass = [
    'bubble-content',
    isStreaming ? 'streaming' : '',
  ].filter(Boolean).join(' ');

  const timeStr = timestamp
    ? new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={bubbleClass}>
      <span className="bubble-label">{label}</span>
      <div className={contentClass}>{content}</div>
      {timeStr && <span className="bubble-timestamp">{timeStr}</span>}
    </div>
  );
}
