// src/renderer/components/Avatar.jsx
import React, { useRef, useEffect, useState } from 'react';

const AVATAR_ASSETS = {
  default: { skel: 'c017_00/c017_00.skel', atlas: 'c017_00/c017_00.atlas' },
  alt:    { skel: 'c017_02/c017_02_00.skel', atlas: 'c017_02/c017_02_00.atlas' },
};

/**
 * Spine 2D Avatar 组件。模型通过 props 可配置。
 *
 * @param {string} state   - 情绪状态 (idle/happy/sad/thinking/...)
 * @param {string} model   - 模型标识: 'default' | 'alt' (默认 'default')
 * @param {string} skelUrl - 自定义 .skel 路径 (覆盖 model)
 * @param {string} atlasUrl- 自定义 .atlas 路径 (覆盖 model)
 */
const Avatar = React.memo(function Avatar({
  state = 'idle',
  model = 'default',
  skelUrl: customSkelUrl,
  atlasUrl: customAtlasUrl,
}) {
  const containerRef = useRef(null);
  const mgrRef = useRef(null);
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    let cancelled = false;

    async function initAvatar() {
      try {
        const { AvatarManager } = await import('../../avatar/AvatarManager');
        if (cancelled) return;

        const mgr = new AvatarManager();
        mgrRef.current = mgr;

        const assets = AVATAR_ASSETS[model] || AVATAR_ASSETS.default;
        const skelUrl = customSkelUrl
          || new URL(`../../../assets/spine/${assets.skel}`, import.meta.url).href;
        const atlasUrl = customAtlasUrl
          || new URL(`../../../assets/spine/${assets.atlas}`, import.meta.url).href;

        await mgr.init(containerRef.current, skelUrl, atlasUrl);
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
  }, [model, customSkelUrl, customAtlasUrl]);

  useEffect(() => {
    if (status === 'ready' && mgrRef.current) {
      console.log('[Avatar] setState called with:', state);
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
});

export default Avatar;
