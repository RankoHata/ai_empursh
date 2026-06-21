// src/avatar/AvatarManager.ts
import { SpineModel } from './SpineModel';
import { AnimationController } from './AnimationController';
import { InteractionHandler } from './InteractionHandler';

export class AvatarManager {
  private model: SpineModel | null = null;
  private animCtrl: AnimationController | null = null;
  private interaction: InteractionHandler | null = null;
  private animFrameId: number = 0;

  async init(container: HTMLElement, skelUrl: string, atlasUrl: string): Promise<void> {
    this.model = new SpineModel();
    await this.model.load(container, skelUrl, atlasUrl);

    const skeleton = this.model.skeleton;
    const animState = this.model.animationState;
    if (!skeleton || !animState) {
      throw new Error('SpinePlayer loaded but skeleton/animationState missing');
    }

    this.animCtrl = new AnimationController(skeleton, animState);

    const canvas = this.model.canvas;
    if (canvas) {
      this.interaction = new InteractionHandler(canvas, this.animCtrl, skeleton);
      this.interaction.attach();
    }

    this.startLoop();
  }

  private startLoop(): void {
    const loop = (): void => {
      if (this.animCtrl) {
        this.animCtrl.updateGaze();
      }
      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  setState(state: string): void {
    this.animCtrl?.setState(state);
  }

  destroy(): void {
    cancelAnimationFrame(this.animFrameId);
    this.interaction?.detach();
    this.animCtrl?.destroy();
    this.model?.destroy();
  }
}
