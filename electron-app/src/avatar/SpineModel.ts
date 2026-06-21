// src/avatar/SpineModel.ts
import * as PIXI from 'pixi.js';
import { Spine } from 'pixi-spine';
import { IAvatarModel } from './IAvatarModel';
import { HitResult } from './types';
import { PixiApp } from './PixiApp';

export class SpineModel implements IAvatarModel {
  private spine: Spine | null = null;
  private animationNames: string[] = [];

  async load(assetPath: string): Promise<void> {
    const pixiApp = PixiApp.getInstance();
    if (!pixiApp.app) {
      throw new Error('PixiApp not initialized');
    }

    // Register pixi-spine asset loader (side-effect import handles this in v4)
    // Load the .skel file — pixi-spine auto-resolves the .atlas in same directory
    const spineData = await PIXI.Assets.load(assetPath);

    this.spine = new Spine(spineData);

    // Dynamic scale: fit model within canvas with 15% margin
    const bounds = this.spine.getLocalBounds();
    const scaleX = pixiApp.app.screen.width / bounds.width;
    const scaleY = pixiApp.app.screen.height / bounds.height;
    const scale = Math.min(scaleX, scaleY) * 0.85;
    this.spine.scale.set(scale);

    // Center after scale
    this.spine.x = pixiApp.app.screen.width / 2;
    this.spine.y = pixiApp.app.screen.height / 2;

    pixiApp.app.stage.addChild(this.spine);

    // Cache animation names from skeleton data
    if (this.spine.state.data?.skeletonData?.animations) {
      this.animationNames = this.spine.state.data.skeletonData.animations
        .map((a: any) => a.name);
    }

    // Auto-play idle if available
    if (this.animationNames.includes('idle')) {
      this.playAnimation('idle', true);
    }
  }

  playAnimation(name: string, loop: boolean = true): void {
    if (this.spine) {
      this.spine.state.setAnimation(0, name, loop);
    }
  }

  getAnimationList(): string[] {
    return [...this.animationNames];
  }

  mixAnimation(trackIndex: number, name: string, duration: number): void {
    if (this.spine) {
      const entry = this.spine.state.setAnimation(trackIndex, name, false);
      if (entry) {
        entry.mixDuration = duration;
      }
    }
  }

  setParam(name: string, value: number): void {
    if (this.spine) {
      const bone = this.spine.skeleton.findBone(name);
      if (bone) {
        bone.rotation = value;
      }
    }
  }

  getParam(name: string): number {
    if (this.spine) {
      const bone = this.spine.skeleton.findBone(name);
      return bone ? bone.rotation : 0;
    }
    return 0;
  }

  hitTest(x: number, y: number): HitResult | null {
    if (!this.spine) return null;
    const local = this.spine.toLocal(new PIXI.Point(x, y));
    const bounds = this.spine.getLocalBounds();
    const relY = local.y - bounds.y;
    const heightFraction = relY / bounds.height;

    if (heightFraction < 0.25) {
      return { boneName: 'head', slotName: '' };
    }
    if (heightFraction < 0.85) {
      return { boneName: 'body', slotName: '' };
    }
    return { boneName: 'legs', slotName: '' };
  }

  getBounds(): { x: number; y: number; width: number; height: number } {
    if (this.spine) {
      const b = this.spine.getLocalBounds();
      return { x: b.x, y: b.y, width: b.width, height: b.height };
    }
    return { x: 0, y: 0, width: 0, height: 0 };
  }

  update(deltaSec: number): void {
    if (this.spine) {
      this.spine.update(deltaSec);
    }
  }

  /** Get the underlying PIXI.spine.Spine instance (for AnimationController direct access) */
  getSpine(): Spine | null {
    return this.spine;
  }

  destroy(): void {
    if (this.spine) {
      this.spine.destroy({ children: true, texture: true });
      this.spine = null;
    }
    this.animationNames = [];
  }
}
