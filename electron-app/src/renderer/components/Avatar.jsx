// src/renderer/components/Avatar.jsx
import React, { useRef, useEffect, useState } from 'react';

// Vite 只在静态字符串字面量时转换 new URL(..., import.meta.url)
// 因此必须在模块顶层预计算所有 URL，不能在运行时拼接
const DEFAULT_SKEL  = new URL('../../../assets/spine/c017_00/c017_00.skel', import.meta.url).href;
const DEFAULT_ATLAS = new URL('../../../assets/spine/c017_00/c017_00.atlas', import.meta.url).href;
const ALT_SKEL      = new URL('../../../assets/spine/c017_02/c017_02_00.skel', import.meta.url).href;
const ALT_ATLAS     = new URL('../../../assets/spine/c017_02/c017_02_00.atlas', import.meta.url).href;

const MODEL_URLS = {
  default: { skel: DEFAULT_SKEL, atlas: DEFAULT_ATLAS },
  alt:     { skel: ALT_SKEL,     atlas: ALT_ATLAS },
};

function Avatar({ state = 'idle', model = 'default', skelUrl, atlasUrl }) {
  const containerRef = useRef(null);
  const mgrRef = useRef(null);
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    let cancelled = false;
    const urls = MODEL_URLS[model] || MODEL_URLS.default;

    async function initAvatar() {
      try {
        const { AvatarManager } = await import('../../avatar/AvatarManager');
        if (cancelled) return;

        const mgr = new AvatarManager();
        mgrRef.current = mgr;
        await mgr.init(
          containerRef.current,
          skelUrl || urls.skel,
          atlasUrl || urls.atlas,
        );
        if (!cancelled) setStatus('ready');
      } catch (err) {
        console.error('[Avatar] Init failed:', err);
        if (!cancelled) setStatus(`error: ${err.message}`);
      }
    }

    initAvatar();

    return () => {
      cancelled = true;
      if (mgrRef.current) {
        mgrRef.current.destroy();
        mgrRef.current = null;
      }
    };
  }, [model, skelUrl, atlasUrl]);

  useEffect(() => {
    if (status === 'ready' && mgrRef.current) {
      mgrRef.current.setState(state);
    }
  }, [state, status]);

  return (
    <div className="avatar-container">
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {status !== 'ready' && (
        <div className="avatar-overlay">
          {status === 'loading' ? '加载中...' : status}
        </div>
      )}
    </div>
  );
}

export default React.memo(Avatar);


