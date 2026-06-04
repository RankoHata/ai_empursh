/**
 * Our Live2D model — a proper CubismUserModel subclass.
 * Follows the Cubism 5 SDK pattern without modifying any SDK files.
 */
import { CubismUserModel } from './framework/model/cubismusermodel';
import { CubismModelSettingJson } from './framework/cubismmodelsettingjson';
import { CubismMoc } from './framework/model/cubismmoc';
import { CubismMotion } from './framework/motion/cubismmotion';
import { CubismEyeBlink } from './framework/effect/cubismeyeblink';
import { CubismBreath } from './framework/effect/cubismbreath';
import { CubismPhysics } from './framework/physics/cubismphysics';
import { CubismPose } from './framework/effect/cubismpose';
import { CubismModelUserData } from './framework/model/cubismmodeluserdata';
import { CubismRenderer_WebGL } from './framework/rendering/cubismrenderer_webgl';
import { CubismDefaultParameterId } from './framework/cubismdefaultparameterid';
import { CubismMatrix44 } from './framework/math/cubismmatrix44';
import { ACubismMotion } from './framework/motion/acubismmotion';
import { ICubismModelSetting } from './framework/icubismmodelsetting';

type LogFn = (msg: string) => void;

export class Model extends CubismUserModel {
  private _modelSetting: ICubismModelSetting | null = null;
  private _motions: Map<string, ACubismMotion> = new Map();
  private _log: LogFn = () => {};

  setLog(fn: LogFn): void { this._log = fn; }

  /**
   * Full initialization — loads everything from model3.json.
   */
  async setup(model3JsonUrl: string): Promise<void> {
    const baseUrl = window.location.origin + '/' + model3JsonUrl;

    // 1. Load model3.json
    this._log('Loading model3.json...');
    const jsonResp = await fetch(model3JsonUrl);
    const jsonBuffer = await jsonResp.arrayBuffer();
    this._modelSetting = new CubismModelSettingJson(jsonBuffer, jsonBuffer.byteLength);

    // 2. Load moc3
    const mocPath = this._modelSetting.getModelFileName();
    const mocUrl = new URL(mocPath, baseUrl).href;
    this._log(`Loading moc3: ${mocUrl}`);
    const mocResp = await fetch(mocUrl);
    const mocBuffer = await mocResp.arrayBuffer();
    this.loadModel(mocBuffer); // CubismUserModel handles moc internally

    // 3. Setup expressions
    if (this._modelSetting.getExpressionCount() > 0) {
      const emm = this.getExpressionManager();
      for (let i = 0; i < this._modelSetting.getExpressionCount(); i++) {
        const expName = this._modelSetting.getExpressionName(i);
        const expFile = this._modelSetting.getExpressionFileName(i);
        const expUrl = new URL(expFile, baseUrl).href;
        this._log(`Loading expression: ${expName}`);
        const expResp = await fetch(expUrl);
        const expBuffer = await expResp.arrayBuffer();
        const motion = this.loadExpression(expBuffer, expBuffer.byteLength, expName);
        if (motion) emm?.startMotionPriority(motion, false, 1);
      }
    }

    // 4. Load physics
    const physicsFile = this._modelSetting.getPhysicsFileName();
    if (physicsFile) {
      const physicsUrl = new URL(physicsFile, baseUrl).href;
      this._log(`Loading physics: ${physicsUrl}`);
      const physResp = await fetch(physicsUrl);
      const physBuffer = await physResp.arrayBuffer();
      this.loadPhysics(physBuffer, physBuffer.byteLength);
    }

    // 5. Load pose
    const poseFile = this._modelSetting.getPoseFileName();
    if (poseFile) {
      const poseUrl = new URL(poseFile, baseUrl).href;
      const poseResp = await fetch(poseUrl);
      const poseBuffer = await poseResp.arrayBuffer();
      this.loadPose(poseBuffer, poseBuffer.byteLength);
    }

    // 6. Load user data
    const userDataFile = this._modelSetting.getUserDataFile();
    if (userDataFile) {
      const udUrl = new URL(userDataFile, baseUrl).href;
      const udResp = await fetch(udUrl);
      const udBuffer = await udResp.arrayBuffer();
      this.loadUserData(udBuffer, udBuffer.byteLength);
    }

    // 7. Setup eye blink
    if (this._modelSetting.getEyeBlinkParameterCount() > 0) {
      this._eyeBlink = CubismEyeBlink.create(this._modelSetting);
    }

    // 8. Setup breath
    this._breath = CubismBreath.create();
    this._breath?.setParameters(this.getModel().getModel().getParameterIds());

    // 9. Load motions
    const motionGroupCount = this._modelSetting.getMotionGroupCount();
    for (let g = 0; g < motionGroupCount; g++) {
      const groupName = this._modelSetting.getMotionGroupName(g);
      const motionCount = this._modelSetting.getMotionCount(groupName);
      for (let m = 0; m < motionCount; m++) {
        const motionFile = this._modelSetting.getMotionFileName(groupName, m);
        const motionUrl = new URL(motionFile, baseUrl).href;
        this._log(`Loading motion: ${groupName}/${motionFile}`);
        const mResp = await fetch(motionUrl);
        const mBuffer = await mResp.arrayBuffer();
        const motion = this.loadMotion(mBuffer, mBuffer.byteLength, groupName);
        if (motion) {
          motion.setEffectIds(
            CubismDefaultParameterId.EyeLOpen,
            CubismDefaultParameterId.EyeROpen
          );
          // Use filename as key
          const key = motionFile.split('/').pop()!.replace('.motion3.json', '');
          this._motions.set(key, motion);
        }
      }
    }

    this._log('Setup complete');
  }

  /** Initialize WebGL renderer. Call AFTER setup(). */
  initRenderer(gl: WebGLRenderingContext): void {
    this.createRenderer();
    const renderer = this.getRenderer();
    renderer.initialize(this.getModel(), gl);
    renderer.setIsPremultipliedAlpha(true);
    renderer.startUp(gl);
    this.setupMatrix();
  }

  private setupMatrix(): void {
    const model = this.getModel();
    if (!model) return;
    const matrix = this.getModelMatrix();
    const canvasWidth = model.getCanvasWidth();
    const canvasHeight = model.getCanvasHeight();
    // Scale to fit
    const sc = 2.0 / canvasWidth;
    matrix.setWidth(sc);
    matrix.setCenterPosition(0, -0.3);
  }

  /** Start a motion by name (filename without .motion3.json). */
  playMotion(name: string): void {
    const motion = this._motions.get(name);
    if (motion) {
      this.getMotionManager().startMotionPriority(motion, false, 3);
    }
  }

  /** Set a parameter by ID string. */
  setParamById(id: string, value: number): void {
    this.getModel()?.setParameterValueById(id, value);
  }
}
