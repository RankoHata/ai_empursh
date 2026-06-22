// src/renderer/components/Avatar.jsx
import React, { useRef, useEffect, useState } from 'react';

const Avatar = React.memo(function Avatar({ state = 'idle' }) {
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

        // Use Vite static imports for asset URLs
        const skelUrl = new URL('../../../assets/spine/c017_00/c017_00.skel', import.meta.url).href;
        const atlasUrl = new URL('../../../assets/spine/c017_00/c017_00.atlas', import.meta.url).href;

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
  }, []);

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
