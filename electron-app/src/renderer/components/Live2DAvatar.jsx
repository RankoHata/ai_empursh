import React, { useRef, useEffect, useState } from 'react';

const MODEL_FILES = {
  model3Json: 'assets/live2d/g36_1904/normal/normal.model3.json',
  moc3: 'assets/live2d/g36_1904/normal/normal.moc3',
  textures: ['assets/live2d/g36_1904/normal/textures/texture_00.png'],
  motions: {
    idle: 'assets/live2d/g36_1904/normal/motions/daiji_idle_01.motion3.json',
  },
};

export default function Live2DAvatar({ state = 'idle' }) {
  const canvasRef = useRef(null);
  const managerRef = useRef(null);
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        // Wait for Cubism Core
        let attempts = 0;
        while (typeof window.Live2DCubismCore === 'undefined' && attempts < 50) {
          await new Promise((r) => setTimeout(r, 100));
          attempts++;
        }
        if (typeof window.Live2DCubismCore === 'undefined') {
          throw new Error('Cubism Core not loaded');
        }

        const { Live2DManager } = await import('../../live2d/Live2DManager');
        const mgr = new Live2DManager();
        managerRef.current = mgr;

        await mgr.init(
          canvasRef.current,
          MODEL_FILES,
          'assets/live2d/shaders/',
          (msg) => console.log('[Live2D]', msg)
        );

        if (!cancelled) {
          setStatus('ready');
          mgr.startMotion('idle');
        }
      } catch (err) {
        console.error('[Live2D] Init failed:', err);
        if (!cancelled) setStatus('error: ' + err.message);
      }
    }

    init();

    return () => {
      cancelled = true;
      if (managerRef.current) {
        managerRef.current.release();
        managerRef.current = null;
      }
    };
  }, []);

  // React to state changes
  useEffect(() => {
    if (!managerRef.current || status !== 'ready') return;
    const mgr = managerRef.current;
    switch (state) {
      case 'idle':
        mgr.startMotion('idle');
        break;
      case 'speaking':
        // Random open mouth
        mgr.setParam('ParamMouthOpenY', 0.5 + Math.random() * 0.5);
        break;
      case 'thinking':
        mgr.startMotion('idle');
        break;
      default:
        break;
    }
  }, [state, status]);

  return (
    <div className="live2d-container">
      <canvas ref={canvasRef} className="live2d-canvas" width="300" height="400" />
      {status === 'loading' && <div className="live2d-loading">加载中...</div>}
      {status.startsWith('error') && <div className="live2d-error">⚠️ {status}</div>}
    </div>
  );
}
