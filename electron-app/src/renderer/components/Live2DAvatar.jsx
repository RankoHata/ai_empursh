import React, { useRef, useEffect, useState } from 'react';

/**
 * Live2D avatar using pixi-live2d-display + Cubism 4.
 *
 * Props:
 *   state: "idle" | "listening" | "thinking" | "speaking"
 *   modelPath: path to .model3.json (relative to index.html)
 *   motionMap: optional mapping of state → motion name
 */
const MODEL_PATH_DEFAULT = 'assets/live2d/g36_1904/normal.model3.json';

export default function Live2DAvatar({
  state = 'idle',
  modelPath = MODEL_PATH_DEFAULT,
  motionMap = {},
}) {
  const canvasRef = useRef(null);
  const appRef = useRef(null);
  const modelRef = useRef(null);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const { Application } = await import('pixi.js');
        const { Live2DModel } = await import('pixi-live2d-display/cubism4');

        // Wait for Cubism Core (loaded via <script> tag in index.html)
        let attempts = 0;
        while (typeof window.Live2DCubismCore === 'undefined' && attempts < 50) {
          await new Promise((r) => setTimeout(r, 100));
          attempts++;
        }
        if (typeof window.Live2DCubismCore === 'undefined') {
          throw new Error('Cubism Core not found. Check assets/live2d/live2dcubismcore.min.js');
        }
        console.log('[Live2D] Core detected, loading model:', modelPath);

        const app = new Application();
        await app.init({
          canvas: canvasRef.current,
          width: 300,
          height: 400,
          backgroundAlpha: 0,
          antialias: true,
        });
        appRef.current = app;
        console.log('[Live2D] PixiJS 8 renderer ready');

        const model = await Live2DModel.from(modelPath, { autoInteract: false });
        console.log('[Live2D] Model loaded');

        model.anchor.set(0.5, 0);
        model.x = app.screen.width / 2;
        model.y = app.screen.height - 40;
        model.scale.set(0.16);

        app.stage.addChild(model);
        modelRef.current = model;

        if (!cancelled) {
          setLoaded(true);
          console.log('[Live2D] Model loaded');
        }
      } catch (err) {
        console.error('[Live2D] Init error:', err);
        if (!cancelled) setError(err.message);
      }
    }

    init();

    return () => {
      cancelled = true;
      if (appRef.current) {
        appRef.current.destroy(true);
        appRef.current = null;
      }
      modelRef.current = null;
    };
  }, [modelPath]);

  // Control motion based on state
  useEffect(() => {
    if (!modelRef.current) return;
    const motionName = motionMap[state] || 'daiji_idle_01';
    try {
      modelRef.current.motion(motionName);
    } catch (e) {
      // motion might not exist
    }
  }, [state, motionMap]);

  return (
    <div className="live2d-container">
      <canvas ref={canvasRef} className="live2d-canvas" />
      {!loaded && !error && (
        <div className="live2d-loading">加载中...</div>
      )}
      {error && (
        <div className="live2d-error" title={error}>⚠️ Live2D 加载失败</div>
      )}
    </div>
  );
}
