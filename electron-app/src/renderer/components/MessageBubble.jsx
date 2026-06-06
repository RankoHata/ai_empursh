import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ToolCallCard from './ToolCallCard';
import TracePanel from './TracePanel';

/** Collapse 3+ consecutive blank lines into 2, and trim leading/trailing newlines. */
function compactMarkdown(text) {
  if (!text) return text;
  return text
    .replace(/\n{3,}/g, '\n\n')
    .replace(/^\n+/, '')
    .replace(/\n+$/, '');
}

export default function MessageBubble({ message, onToggleDebug, compactMode }) {
  const { id, role, content, isStreaming, timestamp, toolCalls, trace, debugVisible } = message;
  const label = role === 'user' ? '你' : '助理';

  const bubbleClass = [
    'message-bubble',
    role === 'user' ? 'user' : 'assistant',
  ].join(' ');

  const contentClass = [
    'bubble-content',
    isStreaming ? 'streaming' : '',
    compactMode ? 'compact-md' : '',
  ].filter(Boolean).join(' ');

  const timeStr = timestamp
    ? new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '';

  const displayContent = role === 'assistant' && compactMode
    ? compactMarkdown(content)
    : content;

  return (
    <div className={bubbleClass} data-msg-id={id}>
      <span className="bubble-label">{label}</span>

      {/* Tool call cards (above content for assistant messages) */}
      {role === 'assistant' && toolCalls && toolCalls.length > 0 && (
        <div className="bubble-tools">
          {toolCalls.map((tc) => (
            <ToolCallCard key={tc.id} toolCall={tc} />
          ))}
        </div>
      )}

      {/* Content */}
      {content && (
        <div className={contentClass}>
          {role === 'assistant' ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {displayContent}
            </ReactMarkdown>
          ) : (
            content
          )}
        </div>
      )}

      {/* Debug toggle button */}
      {role === 'assistant' && !isStreaming && trace && trace.length > 0 && (
        <button className="trace-toggle-btn" onClick={() => onToggleDebug && onToggleDebug(id)}>
          🔍 调用追踪 ({trace.length} 步)
        </button>
      )}

      {/* Trace panel */}
      <TracePanel trace={trace} visible={debugVisible} onClose={() => onToggleDebug && onToggleDebug(id)} />

      {timeStr && <span className="bubble-timestamp">{timeStr}</span>}
    </div>
  );
}
