import React, { useState, useEffect } from 'react';

/**
 * ToolCallCard — an expandable card showing a tool invocation in the chat.
 *
 * States:
 *   - "running":  tool is executing (animated pulse border, no result yet)
 *   - "completed": tool finished successfully (green checkmark, auto-collapse)
 *   - "error":    tool failed (red cross)
 *
 * Props:
 *   toolCall: { id, name, args, state, result, duration_ms, error }
 */
export default function ToolCallCard({ toolCall }) {
  const [expanded, setExpanded] = useState(false);
  const { id, name, args, state, result, duration_ms, error } = toolCall;

  const displayName = name || 'unknown_tool';
  const argStr = args ? JSON.stringify(args, null, 0) : '{}';

  // Auto-collapse when tool completes successfully (after 1.5s)
  useEffect(() => {
    if (state === 'completed') {
      const timer = setTimeout(() => setExpanded(false), 1500);
      return () => clearTimeout(timer);
    }
  }, [state]);

  let statusIcon, statusText, statusClass;
  if (state === 'running') {
    statusIcon = '⏳';   // ⏳
    statusText = '执行中...';   // 执行中...
    statusClass = 'tool-running';
  } else if (state === 'completed') {
    statusIcon = '✅';   // ✅
    const dur = duration_ms != null
      ? ` · ${(duration_ms / 1000).toFixed(1)}s`
      : '';
    statusText = `完成${dur}`;   // 完成
    statusClass = 'tool-completed';
  } else {
    statusIcon = '❌';   // ❌
    statusText = error ? error.slice(0, 40) : '失败';   // 失败
    statusClass = 'tool-error';
  }

  const resultSummary = result ? (
    result.message
    || (result.data ? `${result.count || 0} 条结果` : null)   // 条结果
    || JSON.stringify(result).slice(0, 100)
  ) : null;

  // Compact tool name display (strip mcp__ prefix for readability)
  const shortName = displayName.startsWith('mcp__')
    ? displayName.split('__').slice(1).join(' › ')   // ›
    : displayName;

  return (
    <div className={`tool-call-card ${statusClass}`}>
      <div
        className="tool-call-header"
        onClick={() => setExpanded(!expanded)}
        title="点击展开/折叠"   // 点击展开/折叠
      >
        <span className="tool-call-icon">{statusIcon}</span>
        <span className="tool-call-name" title={displayName}>{shortName}</span>
        <span className="tool-call-status">
          {statusText}
        </span>
        <span className="tool-call-expand">{expanded ? '▴' : '▾'}</span>
      </div>

      {expanded && (
        <div className="tool-call-body">
          <div className="tool-call-section">
            <span className="tool-call-label">参数:</span>
            <code className="tool-call-code">{argStr}</code>
          </div>
          {state === 'running' && (
            <div className="tool-call-section">
              <div className="tool-call-progress-bar">
                <div className="tool-call-progress-fill" />
              </div>
            </div>
          )}
          {state !== 'running' && resultSummary && (
            <div className="tool-call-section">
              <span className="tool-call-label">结果:</span>
              <span className="tool-call-summary">{resultSummary}</span>
            </div>
          )}
          {state !== 'running' && result && (
            <div className="tool-call-section">
              <span className="tool-call-label">详情:</span>
              <pre className="tool-call-json">{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
          {state === 'error' && error && (
            <div className="tool-call-section tool-call-error-detail">
              <span className="tool-call-label">错误:</span>
              <span className="tool-call-summary">{error}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
