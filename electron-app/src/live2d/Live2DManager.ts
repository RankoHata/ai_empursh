/**
 * Our Live2D manager — wraps the Cubism 5 SDK Framework API.
 * SDK files under src/live2d/framework/ are UNMODIFIED.
 */

import { CubismFramework, Option as CubismOption, LogLevel } from './framework/live2dcubismframework';
import { CubismUserModel } from './framework/model/cubismusermodel';
import { CubismModelSettingJson } from './framework/cubismmodelsettingjson';
import { CubismMoc } from './framework/model/cubismmoc';
import { CubismMotion } from './framework/motion/cubismmotion';
import { CubismEyeBlink } from './framework/effect/cubismeyeblink';
import { CubismBreath } from './framework/effect/cubismbreath';
import { CubismRenderer_WebGL } from './framework/rendering/cubismrenderer_webgl';
import { CubismDefaultParameterId } from './framework/cubismdefaultparameterid';
import { CubismMatrix44 } from './framework/math/cubismmatrix44';
import { CubismLogInfo } from './framework/utils/cubismdebug';

type ModelFiles = {
  model3Json: string;
  moc3: string;
  textures: string[];
  motions: Record<string, string>;
};

type LoadCallback = (message: string) => void;

const FRAME_TIME = 1000 / 60; // ~16.67ms target

/**
 * Minimal Live2D renderer using the official Cubism 5 Framework.
 */
export class Live2DManager {
  private _canvas: HTMLCanvasElement | null = null;
  private _gl: WebGLRenderingContext | null = null;
  private _model: CubismUserModel | null = null;
  private _renderer: CubismRenderer_WebGL | null = null;
  private _animFrameId: number | null = null;
  private _lastTime = 0;
  private _motions: Record<string, CubismMotion> = {};
  private _eyeBlink: CubismEyeBlink | null = null;
  private _breath: CubismBreath | null = null;
  private _initialized = false;

  async init(
    canvas: HTMLCanvasElement,
    modelFiles: ModelFiles,
    shaderPath: string,
    onLog?: LoadCallback
  ): Promise<void> {
    this._canvas = canvas;
    const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: true });
    if (!gl) throw new Error('WebGL not available');
    this._gl = gl;

    // Initialize Cubism Framework (once)
    if (!CubismFramework.isStarted()) {
      CubismFramework.startUp({
        logFunction: (msg: string) => onLog?.(msg),
        loggingLevel: LogLevel.LogLevel_Verbose,
      } as CubismOption);
      CubismFramework.initialize();
    }

    // Load model
    onLog?.('Loading model...');

    // Fetch model json
    const jsonResp = await fetch(modelFiles.model3Json);
    const jsonBuffer = await jsonResp.arrayBuffer();
    const setting = new CubismModelSettingJson(jsonBuffer, jsonBuffer.byteLength);

    // Fetch moc3
    const mocResp = await fetch(modelFiles.moc3);
    const mocBuffer = await mocResp.arrayBuffer();
    const moc = CubismMoc.create(mocBuffer, mocBuffer.byteLength);

    const model = new CubismUserModel();
    model.loadModel(moc.createModel());
    model.loadSetting(setting);

    // Setup renderer
    const renderer = new CubismRenderer_WebGL();
    renderer.initialize(model.getModel(), gl);
    renderer.setIsPremultipliedAlpha(true);
    renderer.startUp(gl);

    // Load textures
    for (let i = 0; i < modelFiles.textures.length; i++) {
      const img = new Image();
      img.src = modelFiles.textures[i];
      await new Promise<void>((resolve, reject) => {
        img.onload = () => {
          const texId = gl.createTexture();
          gl.bindTexture(gl.TEXTURE_2D, texId);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
          resolve();
        };
        img.onerror = reject;
      });
    }

    // Load motions
    for (const [name, path] of Object.entries(modelFiles.motions)) {
      const mResp = await fetch(path);
      const mBuffer = await mResp.arrayBuffer();
      // Use CubismMotion directly for Cubism 5
      const motion = CubismMotion.create(
        mBuffer,
        mBuffer.byteLength,
        () => {} // motion finished callback
      );
      if (motion) {
        motion.setEffectIds(
          CubismDefaultParameterId.EyeLOpen,
          CubismDefaultParameterId.EyeROpen
        );
        this._motions[name] = motion;
      }
    }

    // Auto animations
    this._eyeBlink = CubismEyeBlink.create(model.getModel().getModel());
    this._breath = CubismBreath.create();

    // Set up model matrix
    const matrix = new CubismMatrix44();
    const projection = new CubismMatrix44();
    const aspect = canvas.width / canvas.height;
    const sc = 1.0;

    // Center model vertically
    projection.scale(sc, sc * aspect);
    matrix.translate(0, -0.3);

    this._model = model;
    this._renderer = renderer;
    this._initialized = true;
    onLog?.('Model loaded');

    // Start render loop
    this._lastTime = performance.now();
    this._loop();
  }

  private _loop = (): void => {
    if (!this._initialized || !this._model || !this._renderer || !this._gl) return;

    const now = performance.now();
    const delta = Math.min(now - this._lastTime, 100); // cap delta
    this._lastTime = now;

    const gl = this._gl;
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    // Update model
    this._model.getModel().update();
    this._model.getModel().loadParameters();

    // Auto animations
    this._eyeBlink?.updateParameters(this._model.getModel(), delta / 1000);
    this._breath?.updateParameters(this._model.getModel(), delta / 1000);

    // Render
    this._renderer.drawModel();

    this._animFrameId = requestAnimationFrame(this._loop);
  };

  startMotion(name: string): void {
    if (!this._model) return;
    const motion = this._motions[name];
    if (motion) {
      this._model.getMotionManager().startMotionPriority(motion, false, 3);
    }
  }

  setParam(id: string, value: number): void {
    this._model?.getModel().setParameterValueById(id, value);
  }

  resize(w: number, h: number): void {
    if (this._canvas) {
      this._canvas.width = w;
      this._canvas.height = h;
    }
    if (this._gl) {
      this._gl.viewport(0, 0, w, h);
    }
  }

  release(): void {
    this._initialized = false;
    if (this._animFrameId != null) {
      cancelAnimationFrame(this._animFrameId);
      this._animFrameId = null;
    }
    this._renderer?.release();
    this._model?.release();
    this._renderer = null;
    this._model = null;
    this._gl = null;
  }
}
