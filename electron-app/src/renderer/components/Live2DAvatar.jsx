import React, { useRef, useEffect, useState } from 'react';

const MODEL_URL = 'assets/live2d/haru/Haru.model3.json';

export default function Live2DAvatar({ state = 'idle' }) {
  const canvasRef = useRef(null);
  const modelRef = useRef(null);
  const glRef = useRef(null);
  const frameRef = useRef(null);
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        // Wait for Cubism Core
        let n = 0;
        while (typeof window.Live2DCubismCore === 'undefined' && n < 50) {
          await new Promise((r) => setTimeout(r, 100)); n++;
        }
        if (typeof window.Live2DCubismCore === 'undefined') {
          throw new Error('Cubism Core not loaded');
        }

        const gl = canvasRef.current.getContext('webgl', {
          alpha: true, premultipliedAlpha: true,
        });
        if (!gl) throw new Error('WebGL not available');
        glRef.current = gl;

        const { Model } = await import('../../live2d/Model');
        const model = new Model();
        model.setLog((msg) => console.log('[Live2D]', msg));

        await model.setup(MODEL_URL);
        model.initRenderer(gl);
        modelRef.current = model;

        if (!cancelled) {
          setStatus('ready');
          startLoop();
        }
      } catch (err) {
        console.error('[Live2D]', err);
        if (!cancelled) setStatus('error: ' + err.message);
      }
    }

    function startLoop() {
      const loop = () => {
        if (!modelRef.current || !glRef.current) return;
        const gl = glRef.current;
        const dt = 1 / 60;

        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

        modelRef.current.getModel()?.update();
        modelRef.current.getModel()?.loadParameters();
        modelRef.current.getRenderer()?.drawModel();
        modelRef.current.getModel()?.saveParameters();

        frameRef.current = requestAnimationFrame(loop);
      };
      loop();
    }

    init();

    return () => {
      cancelled = true;
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      modelRef.current?.release();
      modelRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!modelRef.current || status !== 'ready') return;
    switch (state) {
      case 'idle':
        modelRef.current.playMotion('daiji_idle_01');
        break;
      case 'speaking':
        modelRef.current.setParamById('ParamMouthOpenY', 0.3 + Math.random() * 0.4);
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
