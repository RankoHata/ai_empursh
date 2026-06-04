import React, { useRef, useEffect } from 'react';

export default function Live2DAvatar({ state = 'idle' }) {
  const containerRef = useRef(null);

  useEffect(() => {
    let delegate = null;

    async function init() {
      // Wait for Cubism Core
      let n = 0;
      while (typeof window.Live2DCubismCore === 'undefined' && n < 50) {
        await new Promise((r) => setTimeout(r, 100)); n++;
      }
      if (typeof window.Live2DCubismCore === 'undefined') return;

      const { LAppDelegate } = await import('../../live2d/demo/lappdelegate');
      delegate = LAppDelegate.getInstance();
      delegate.setContainer(containerRef.current);
      delegate.initialize();
      delegate.run();
    }

    init();

    return () => {
      if (delegate) {
        LAppDelegate.releaseInstance?.();
      }
    };
  }, []);

  return <div className="live2d-container" ref={containerRef} />;
}
