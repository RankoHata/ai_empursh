// src/renderer/components/Avatar.jsx
import React, { useRef, useEffect, useState } from 'react';

const Avatar = React.memo(function Avatar({ state = 'idle' }) {
  const canvasRef = useRef(null);
  const mgrRef = useRef(null);
  const [status, setStatus] = useState('loading');  // 'loading' | 'ready' | 'error'

  useEffect(() => {
    let cancelled = false;

    async function initAvatar() {
      try {
        const { AvatarManager } = await import('../../avatar/AvatarManager');
        if (cancelled) return;

        const mgr = new AvatarManager();
        mgrRef.current = mgr;
        await mgr.init(canvasRef.current, 'assets/spine/c017_02/c017_02_00.skel');
        if (!cancelled) setStatus('ready');
      } catch (err) {
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

  // Respond to backend avatar_state changes
  useEffect(() => {
    if (status === 'ready' && mgrRef.current) {
      mgrRef.current.setState(state);
    }
  }, [state, status]);

  return (
    <div className="avatar-container">
      <canvas ref={canvasRef} width={280} height={450} />
      {status !== 'ready' && (
        <div className="avatar-overlay">
          {status === 'loading' ? '加载中...' : status}
        </div>
      )}
    </div>
  );
});

export default Avatar;
