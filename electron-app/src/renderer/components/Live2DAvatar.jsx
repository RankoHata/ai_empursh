import React, { useRef, useEffect } from 'react';

export default function Live2DAvatar({ state = 'idle' }) {
  const containerRef = useRef(null);
  const delegateRef = useRef(null);

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

        const { LAppDelegate } = await import('../../live2d/app/lappdelegate');
        const delegate = LAppDelegate.getInstance();

        delegate.setContainer(containerRef.current);
        if (!delegate.initialize()) {
          throw new Error('LAppDelegate init failed');
        }

        delegateRef.current = delegate;
        delegate.run();
        console.log('[Live2D] Initialized successfully');
      } catch (err) {
        console.error('[Live2D]', err);
      }
    }

    init();

    return () => {
      cancelled = true;
      if (delegateRef.current) {
        delegateRef.current.release();
        delegateRef.current = null;
      }
    };
  }, []);

  return (
    <div className="live2d-container" ref={containerRef} />
  );
}
