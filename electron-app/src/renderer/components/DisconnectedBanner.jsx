import React, { useState, useEffect, useRef } from 'react';

const STATUS_LABELS = {
  disconnected: '未连接 — 请启动后端服务',
  connecting: '连接中...',
};

export default function DisconnectedBanner({ status }) {
  const [visible, setVisible] = useState(true);
  const [exiting, setExiting] = useState(false);
  const prevStatusRef = useRef(status);

  useEffect(() => {
    // If transitioning from disconnected/connecting → connected, fade out
    if (status === 'connected' && prevStatusRef.current !== 'connected') {
      setExiting(true);
      const timer = setTimeout(() => setVisible(false), 300);
      return () => clearTimeout(timer);
    }
    // If transitioning to disconnected/connecting, show immediately
    if (status !== 'connected' && prevStatusRef.current === 'connected') {
      setVisible(true);
      setExiting(false);
    }
    prevStatusRef.current = status;
  }, [status]);

  if (!visible || status === 'connected') return null;

  return (
    <div className={`disconnected-banner ${exiting ? 'disconnected-banner-exit' : ''}`}>
      <span>⚠ {STATUS_LABELS[status] || status}</span>
    </div>
  );
}
