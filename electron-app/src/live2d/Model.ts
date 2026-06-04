import { CubismFramework, Option as CubismOption, LogLevel } from './framework/live2dcubismframework';
import { CubismUserModel } from './framework/model/cubismusermodel';
import { CubismModelSettingJson } from './framework/cubismmodelsettingjson';
import { CubismEyeBlink } from './framework/effect/cubismeyeblink';
import { CubismBreath } from './framework/effect/cubismbreath';
import { CubismMatrix44 } from './framework/math/cubismmatrix44';
import { ACubismMotion } from './framework/motion/acubismmotion';
import { ICubismModelSetting } from './framework/icubismmodelsetting';
import { CubismWebGLOffscreenManager } from './framework/rendering/cubismoffscreenmanager';

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

let _fwStarted = false;
function ensureFramework() {
  if (!_fwStarted) {
    CubismFramework.startUp({
      loggingLevel: LogLevel.LogLevel_Verbose,
    } as CubismOption);
    CubismFramework.initialize();
    _fwStarted = true;
  }
}

type LogFn = (msg: string) => void;

/** Load binary data via XHR — more reliable than fetch in Electron for moc3/etc. */
function xhrLoad(url: string): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = 'arraybuffer';
    xhr.onload = () => {
      if (xhr.status === 200) resolve(xhr.response as ArrayBuffer);
      else reject(new Error(`XHR ${url}: ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error(`XHR failed: ${url}`));
    xhr.send();
  });
}

export class Model extends CubismUserModel {
  private _modelSetting: ICubismModelSetting | null = null;
  private _motions: Map<string, ACubismMotion> = new Map();
  private _log: LogFn = () => {};

  setLog(fn: LogFn): void { this._log = fn; }

  async setup(model3JsonUrl: string): Promise<void> {
    ensureFramework();
    const baseUrl = window.location.origin + '/' + model3JsonUrl;

    // 1. Load model3.json
    this._log('Loading model3.json...');
    const jsonBuf = await xhrLoad(model3JsonUrl);
    this._modelSetting = new CubismModelSettingJson(jsonBuf, jsonBuf.byteLength);

    // 2. Load moc3
    const mocPath = this._modelSetting.getModelFileName();
    const mocUrl = new URL(mocPath, baseUrl).href;
    this._log(`Loading moc3: ${mocUrl}`);
    const mocBuf = await xhrLoad(mocUrl);
    this._log(`moc3: ${mocBuf.byteLength} bytes`);
    this.loadModel(mocBuf);

    // 3. Expressions (skip for now — requires CubismExpressionMotionManager setup)
    // TODO: implement expression loading later

    // 4. Physics
    const physFile = this._modelSetting.getPhysicsFileName();
    if (physFile) {
      const physUrl = new URL(physFile, baseUrl).href;
      const physBuf = await xhrLoad(physUrl);
      this.loadPhysics(physBuf, physBuf.byteLength);
    }

    // 5. Pose
    const poseFile = this._modelSetting.getPoseFileName();
    if (poseFile) {
      const poseUrl = new URL(poseFile, baseUrl).href;
      const poseBuf = await xhrLoad(poseUrl);
      this.loadPose(poseBuf, poseBuf.byteLength);
    }

    // 6. User data
    const udFile = this._modelSetting.getUserDataFile();
    if (udFile) {
      const udUrl = new URL(udFile, baseUrl).href;
      const udBuf = await xhrLoad(udUrl);
      this.loadUserData(udBuf, udBuf.byteLength);
    }

    // 7. Eye blink
    if (this._modelSetting.getEyeBlinkParameterCount() > 0) {
      this._eyeBlink = CubismEyeBlink.create(this._modelSetting);
    }

    // 8. Breath
    this._breath = CubismBreath.create();

    // 9. Motions
    const mgCount = this._modelSetting.getMotionGroupCount();
    let firstMotion: ACubismMotion | null = null;
    for (let g = 0; g < mgCount; g++) {
      const gName = this._modelSetting.getMotionGroupName(g);
      const mCount = this._modelSetting.getMotionCount(gName);
      for (let m = 0; m < mCount; m++) {
        const mFile = this._modelSetting.getMotionFileName(gName, m);
        const mUrl = new URL(mFile, baseUrl).href;
        const mBuf = await xhrLoad(mUrl);
        const motion = this.loadMotion(mBuf, mBuf.byteLength, gName);
        if (!firstMotion) firstMotion = motion;
      }
    }
    // Auto-start first idle motion
    if (firstMotion) {
      this._motionManager?.startMotionPriority(firstMotion, false, 3);
    }

    this._log('Setup complete');
  }

  async initRenderer(gl: WebGLRenderingContext, shaderPath: string, baseUrl: string): Promise<void> {
    this._shaderPath = shaderPath;
    this.createRenderer();
    const r = this.getRenderer();
    r.initialize(this.getModel(), gl);
    r.setIsPremultipliedAlpha(true);
    r.startUp(gl);
    r.loadShaders(shaderPath);

    // Load textures
    if (this._modelSetting) {
      const texCount = this._modelSetting.getTextureCount();
      for (let i = 0; i < texCount; i++) {
        const texFile = this._modelSetting.getTextureFileName(i);
        // Resolve relative to the model3.json's directory
        const texUrl = new URL(texFile, baseUrl).href;
        this._log(`Texture ${i}: file=${texFile}, url=${texUrl}`);
        const img = await loadImage(texUrl);
        this._log(`Texture ${i}: loaded ${img.width}x${img.height}`);
        const texId = gl.createTexture();
        if (!texId) { this._log(`Texture ${i}: createTexture returned null`); continue; }
        gl.bindTexture(gl.TEXTURE_2D, texId);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
        gl.generateMipmap(gl.TEXTURE_2D);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.bindTexture(gl.TEXTURE_2D, null);
        r.bindTexture(i, texId);
        this._log(`Texture ${i}: bound successfully`);
      }
    }

    // Center model
    const m = this.getModel();
    if (m) {
      const mat = this.getModelMatrix();
      mat.setWidth(2.0 / m.getCanvasWidth());
      mat.setCenterPosition(0, -0.3);
    }
  }

  private _shaderPath = '';

  draw(gl: WebGLRenderingContext, canvasWidth: number, canvasHeight: number): void {
    if (!this.getModel()) return;

    // Build projection matrix (matches SDK demo LAppLive2DManager)
    const projection = new CubismMatrix44();
    const model = this.getModel();
    const mw = model.getCanvasWidth();
    const mh = model.getCanvasHeight();
    const cw = canvasWidth;
    const ch = canvasHeight;

    if (mw > 1.0 && cw < ch) {
      this.getModelMatrix().setWidth(2.0);
      projection.scale(1.0, cw / ch);
    } else {
      projection.scale(ch / cw, 1.0);
    }

    // Update all animations (matches SDK LAppModel.doUpdate)
    const deltaSeconds = 1 / 60;
    this._motionManager?.updateMotion(model, deltaSeconds);
    this._expressionManager?.updateMotion(model, deltaSeconds);
    model.update();
    model.loadParameters();
    if (this._eyeBlink) this._eyeBlink.updateParameters(model, deltaSeconds);
    // Physics and pose updates
    const physics = (this as any)._physics;
    if (physics) physics.evaluate(model, deltaSeconds);
    const pose = (this as any)._pose;
    if (pose) pose.updateParameters(model, deltaSeconds);

    // Matrix: multiply projection by model matrix, then set (matches SDK demo)
    projection.multiplyByMatrix(this.getModelMatrix());
    this.getModelMatrix().setMatrix(projection);
    this.getRenderer().drawModel(this._shaderPath);

    model.saveParameters();

    // Offscreen buffer cleanup (required after drawModel)
    CubismWebGLOffscreenManager.getInstance().endFrameProcess(gl);
  }

  playMotion(name: string): void {
    const motion = this._motions.get(name);
    if (motion) this._motionManager?.startMotionPriority(motion, false, 3);
  }

  setParamById(id: string, value: number): void {
    this.getModel()?.setParameterValueById(id, value);
  }
}
