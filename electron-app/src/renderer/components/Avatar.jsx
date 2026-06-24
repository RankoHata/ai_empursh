// src/renderer/components/Avatar.jsx
import React, { useRef, useEffect, useState } from 'react';

// 模型注册表 — key → { skel, atlas }
const AVATAR_ASSETS = {
  default: { skel: 'c017_00/c017_00.skel', atlas: 'c017_00/c017_00.atlas' },
  alt:    { skel: 'c017_02/c017_02_00.skel', atlas: 'c017_02/c017_02_00.atlas' },
};

/**
 * Spine 2D Avatar 组件。
 * @param {string} state   - 情绪状态
 * @param {string} model   - 模型标识: 'default' | 'alt'
 * @param {string} skelUrl - 自定义 .skel URL (覆盖 model)
 * @param {string} atlasUrl- 自定义 .atlas URL (覆盖 model)
 */
function Avatar({ state = 'idle', model = 'default', skelUrl, atlasUrl }) {
  const containerRef = useRef(null);
  const mgrRef = useRef(null);
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    let cancelled = false;
    const m = model || 'default';
    const assets = AVATAR_ASSETS[m] || AVATAR_ASSETS.default;

    async function initAvatar() {
      try {
        const { AvatarManager } = await import('../../avatar/AvatarManager');
        if (cancelled) return;

        const mgr = new AvatarManager();
        mgrRef.current = mgr;

        const resolvedSkel = skelUrl
          || new URL(`../../../assets/spine/${assets.skel}`, import.meta.url).href;
        const resolvedAtlas = atlasUrl
          || new URL(`../../../assets/spine/${assets.atlas}`, import.meta.url).href;

        await mgr.init(containerRef.current, resolvedSkel, resolvedAtlas);
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

