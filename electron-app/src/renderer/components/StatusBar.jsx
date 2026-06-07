import React from 'react';

const STATUS_LABELS = {
  disconnected: '未连接 — 请启动后端服务',
  connecting: '连接中...',
  connected: '已连接',
};

export default function StatusBar({ status, ttsEnabled, onToggleTts, onOpenSettings }) {
  return (
    <div className="status-bar">
      <span className={`status-dot ${status}`} />
      <span>{STATUS_LABELS[status] || status}</span>
      <div className="status-bar-spacer" />
      <label className="voice-toggle" title="TTS 语音朗读开关">
        <span>🗣️ 朗读</span>
        <input
          type="checkbox"
          checked={ttsEnabled}
          onChange={(e) => onToggleTts(e.target.checked)}
        />
        <span className={`toggle-switch ${ttsEnabled ? 'on' : ''}`}>
          {ttsEnabled ? '●' : '○'}
        </span>
      </label>
      <button className="btn-settings" onClick={onOpenSettings} title="设置">
        ⚙️
      </button>
    </div>
  );
}
