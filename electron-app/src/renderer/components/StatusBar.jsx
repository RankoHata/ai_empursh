import React from 'react';

const STATUS_LABELS = {
  disconnected: '未连接 — 请启动后端服务',
  connecting: '连接中...',
  connected: '已连接',
};

export default function StatusBar({ status, alwaysOn, onToggleAlwaysOn }) {
  return (
    <div className="status-bar">
      <span className={`status-dot ${status}`} />
      <span>{STATUS_LABELS[status] || status}</span>
      <div className="status-bar-spacer" />
      <label className="voice-toggle" title="常开模式：麦克风持续监听">
        <span>🎤 常开</span>
        <input
          type="checkbox"
          checked={alwaysOn}
          onChange={(e) => onToggleAlwaysOn(e.target.checked)}
        />
        <span className={`toggle-switch ${alwaysOn ? 'on' : ''}`}>
          {alwaysOn ? '●' : '○'}
        </span>
      </label>
    </div>
  );
}
