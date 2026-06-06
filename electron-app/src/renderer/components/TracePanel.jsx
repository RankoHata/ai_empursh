import React from 'react';

export default function TracePanel({ trace, visible, onClose }) {
  if (!visible || !trace || trace.length === 0) return null;

  return (
    <div className="trace-panel">
      <div className="trace-header">
        <span>🔍 调用追踪 ({trace.length} 步)</span>
        <button className="trace-close-btn" onClick={onClose}>✕</button>
      </div>
      <div className="trace-timeline">
        {trace.map((step, i) => (
          <TraceStep key={i} step={step} index={i} />
        ))}
      </div>
    </div>
  );
}

function TraceStep({ step, index }) {
  const { step: type } = step;

  const config = {
    api_call:   { icon: '📡', label: 'API 调用', cls: 'trace-api' },
    tool_call:  { icon: '🔧', label: step.name, cls: 'trace-tool' },
    tool_result:{ icon: step.success ? '✅' : '❌', label: step.success ? '成功' : '失败', cls: step.success ? 'trace-ok' : 'trace-err' },
    done:       { icon: '🏁', label: '完成', cls: 'trace-done' },
    stopped:    { icon: '⏹', label: '已停止', cls: 'trace-stopped' },
    max_rounds_reached: { icon: '⚠️', label: '达到最大轮次', cls: 'trace-warn' },
  };

  const cfg = config[type] || { icon: '●', label: type, cls: '' };

  return (
    <div className={`trace-step ${cfg.cls}`}>
      <div className="trace-step-icon">{cfg.icon}</div>
      <div className="trace-step-body">
        <div className="trace-step-header">
          <span className="trace-step-type">{cfg.label}</span>
          {step.round != null && <span className="trace-step-round">轮次 {step.round}</span>}
          {step.duration_ms != null && <span className="trace-step-dur">{step.duration_ms}ms</span>}
          {step.count != null && <span className="trace-step-count">{step.count} 条</span>}
        </div>
        {step.tools && (
          <div className="trace-step-detail">工具: {step.tools.join(', ')}</div>
        )}
        {step.args && (
          <div className="trace-step-detail">
            <code>{JSON.stringify(step.args, null, 0)}</code>
          </div>
        )}
        {step.message && (
          <div className="trace-step-detail">{step.message}</div>
        )}
        {step.history_msgs != null && (
          <div className="trace-step-detail">历史消息: {step.history_msgs} 条</div>
        )}
      </div>
    </div>
  );
}
