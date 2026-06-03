import React from 'react';

const STATUS_LABELS = {
  disconnected: '未连接 — 请启动后端服务',
  connecting: '连接中...',
  connected: '已连接',
};

export default function StatusBar({ status }) {
  return (
    <div className="status-bar">
      <span className={`status-dot ${status}`} />
      <span>{STATUS_LABELS[status] || status}</span>
    </div>
  );
}
