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
import { CubismPhysics } from './framework/physics/cubismphysics';
import { CubismPose } from './framework/effect/cubismpose';
import { CubismModelUserData } from './framework/model/cubismmodeluserdata';
import { ICubismModelSetting } from './framework/icubismmodelsetting';

type ModelFiles = {
  model3Json: string;
  textures: string[];
  motions: Record<string, string>;
};

type LoadCallback = (message: string) => void;

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
    onLog?: LoadCallback
  ): Promise<void> {
    this._canvas = canvas;
    const gl = canvas.getContext('webgl', {
      alpha: true,
      premultipliedAlpha: true,
    });
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

    onLog?.('Loading model...');

    // 1. Load model3.json to get file references
    const jsonResp = await fetch(modelFiles.model3Json);
    const jsonText = await jsonResp.text();
    const settingJson = JSON.parse(jsonText);

    const mocPath = settingJson.FileReferences.Moc;
    const mocUrl = new URL(mocPath, modelFiles.model3Json).href;

    onLog?.(`Loading moc3: ${mocUrl}`);

    // 2. Load moc3
    const mocResp = await fetch(mocUrl);
    const mocBuffer = await mocResp.arrayBuffer();
    const moc = CubismMoc.create(mocBuffer, mocBuffer.byteLength);
    if (!moc) throw new Error('Failed to load moc3');

    // 3. Create model
    const model = new CubismUserModel();
    model.loadModel(moc.createModel());

    // 4. Setup renderer
    const renderer = new CubismRenderer_WebGL();
    renderer.initialize(model.getModel(), gl);
    renderer.setIsPremultipliedAlpha(true);
    renderer.startUp(gl);

    // 5. Load textures
    const texturePaths = settingJson.FileReferences.Textures || [];
    for (let i = 0; i < texturePaths.length; i++) {
      const texUrl = new URL(texturePaths[i], modelFiles.model3Json).href;
      onLog?.(`Loading texture ${i}: ${texUrl}`);
      const img = new Image();
      img.src = texUrl;
      await new Promise<void>((resolve, reject) => {
        img.onload = () => {
          const texId = gl.createTexture();
          gl.bindTexture(gl.TEXTURE_2D, texId);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
          gl.generateMipmap(gl.TEXTURE_2D);
          gl.bindTexture(gl.TEXTURE_2D, null);
          resolve();
        };
        img.onerror = (e) => reject(new Error(`Failed to load texture: ${texUrl}`));
      });
    }

    // 6. Load motions
    const motionGroups = settingJson.FileReferences.Motions || {};
    for (const [, motionList] of Object.entries(motionGroups)) {
      for (const m of motionList as any[]) {
        const motionUrl = new URL(m.File, modelFiles.model3Json).href;
        onLog?.(`Loading motion: ${motionUrl}`);
        const mResp = await fetch(motionUrl);
        const mBuffer = await mResp.arrayBuffer();
        const motion = CubismMotion.create(mBuffer, mBuffer.byteLength, () => {
          onLog?.('Motion finished');
        });
        if (motion) {
          motion.setEffectIds(
            CubismDefaultParameterId.EyeLOpen,
            CubismDefaultParameterId.EyeROpen
          );
          const key = (m.File as string).split('/').pop()!.replace('.motion3.json', '');
          this._motions[key] = motion;
        }
      }
    }

    // 7. Auto animations
    if (model.getModel()) {
      this._eyeBlink = CubismEyeBlink.create(model.getModel().getModel());
    }
    this._breath = CubismBreath.create();

    this._model = model;
    this._renderer = renderer;
    this._initialized = true;
    onLog?.('Model loaded');

    // 8. Start render loop
    this._lastTime = performance.now();
    this._loop();
  }

  private _loop = (): void => {
    if (!this._initialized || !this._model || !this._renderer || !this._gl) return;

    const now = performance.now();
    const delta = Math.min(now - this._lastTime, 100);
    this._lastTime = now;

    const gl = this._gl;
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    if (this._model.getModel()) {
      this._model.getModel().update();
      this._model.getModel().loadParameters();
      this._eyeBlink?.updateParameters(this._model.getModel(), delta / 1000);
      this._breath?.updateParameters(this._model.getModel(), delta / 1000);
    }

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
    this._model?.getModel()?.setParameterValueById(id, value);
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
