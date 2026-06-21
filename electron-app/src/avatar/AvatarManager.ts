// src/avatar/AvatarManager.ts
import { PixiApp } from './PixiApp';
import { SpineModel } from './SpineModel';
import { AnimationController } from './AnimationController';
import { InteractionHandler } from './InteractionHandler';
import { IAvatarModel } from './IAvatarModel';

export class AvatarManager {
  private pixiApp: PixiApp;
  private model: IAvatarModel | null = null;
  private animCtrl: AnimationController | null = null;
  private interaction: InteractionHandler | null = null;
  private animFrameId: number = 0;

  /**
   * Initialize the full avatar system:
   * PixiApp → load model → AnimationController → InteractionHandler → render loop
   */
  async init(canvas: HTMLCanvasElement, modelPath: string): Promise<void> {
    this.pixiApp = PixiApp.getInstance();
    await this.pixiApp.init(canvas, canvas.width, canvas.height);

    this.model = new SpineModel();
    await this.model.load(modelPath);

    // AnimationController needs direct access to Spine instance
    const spineInstance = (this.model as SpineModel).getSpine();
    if (!spineInstance) {
      throw new Error('Spine instance not available after model load');
    }

    this.animCtrl = new AnimationController(spineInstance);
    this.interaction = new InteractionHandler(spineInstance, this.animCtrl);
    this.interaction.attach(this.pixiApp.app!.stage);

    this.startLoop();
  }

  private startLoop(): void {
    const loop = (): void => {
      // Note: Spine animation updates are driven by PixiJS ticker (autoUpdate=true).
      // This loop only handles our custom per-frame logic (gaze interpolation).
      if (this.animCtrl) {
        this.animCtrl.updateGaze();
      }
      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  /** Backend state → animation state mapping */
  setState(state: string): void {
    this.animCtrl?.setState(state);
  }

  /** Future: switch to a different model */
  async switchModel(_newPath: string): Promise<void> {
    throw new Error('switchModel not implemented in v1');
  }

  destroy(): void {
    cancelAnimationFrame(this.animFrameId);
    this.interaction?.detach();
    this.animCtrl?.destroy();
    this.model?.destroy();
    this.pixiApp.destroy();
  }
}
