// src/avatar/SpineModel.ts
// Uses official @esotericsoftware/spine-player (WebGL) instead of pixi-spine
// to fix PMA / two-color-tint / mesh rendering issues.
import { SpinePlayer } from '@esotericsoftware/spine-player';
import { Skin } from '@esotericsoftware/spine-core';
import type { AnimationState, Skeleton, TrackEntry } from '@esotericsoftware/spine-core';
import { IAvatarModel } from './IAvatarModel';

export class SpineModel implements IAvatarModel {
  private player: SpinePlayer | null = null;
  private _canvas: HTMLCanvasElement | null = null;
  private animationNames: string[] = [];

  async load(container: HTMLElement, skelUrl: string, atlasUrl: string): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.player = new SpinePlayer(container, {
          binaryUrl: skelUrl,
          atlasUrl: atlasUrl,
          animation: 'idle',
          premultipliedAlpha: true,
          alpha: true,
          backgroundColor: '#00000000',
          showControls: false,
          showLoading: false,
          preserveDrawingBuffer: true,
          success: (player: SpinePlayer) => {
            this.player = player;
            this._canvas = player.canvas;

            // Cache animation names and apply all skins
            if (player.skeleton) {
              this.animationNames = player.skeleton.data.animations.map(a => a.name);

              // Combine default + acc skins (accessories won't show otherwise)
              const combined = new Skin('combined');
              for (const skinName of ['default', 'acc']) {
                const skin = player.skeleton.data.findSkin(skinName);
                if (skin) combined.addSkin(skin);
              }
              player.skeleton.setSkin(combined);
              player.skeleton.setSlotsToSetupPose();
            }

            // Style the canvas to fill the container
            if (this._canvas) {
              this._canvas.style.width = '100%';
              this._canvas.style.height = '100%';
              this._canvas.style.position = 'absolute';
              this._canvas.style.left = '0';
              this._canvas.style.top = '0';
            }

            resolve();
          },
          error: (_player: SpinePlayer, msg: string) => {
            reject(new Error(msg));
          },
        });
      } catch (e) {
        reject(e);
      }
    });
  }

  get canvas(): HTMLCanvasElement | null {
    return this._canvas;
  }

  get skeleton(): Skeleton | null {
    return this.player?.skeleton ?? null;
  }

  get animationState(): AnimationState | null {
    return this.player?.animationState ?? null;
  }

  playAnimation(name: string, loop: boolean = true): TrackEntry | undefined {
    return this.player?.setAnimation(name, loop);
  }

  addAnimation(name: string, loop: boolean, delay: number): TrackEntry | undefined {
    return this.player?.addAnimation(name, loop, delay);
  }

  getAnimationList(): string[] {
    return [...this.animationNames];
  }

  /** Hit test in canvas coordinates */
  hitTest(canvasX: number, canvasY: number): { boneName: string } | null {
    // spine-player doesn't provide a direct hit-test API.
    // For now, approximate by vertical zone.
    if (!this._canvas) return null;
    const frac = canvasY / this._canvas.clientHeight;
    if (frac < 0.25) return { boneName: 'head' };
    if (frac < 0.85) return { boneName: 'body' };
    return { boneName: 'legs' };
  }

  getBounds(): { x: number; y: number; width: number; height: number } {
    const c = this._canvas;
    return c ? { x: 0, y: 0, width: c.clientWidth, height: c.clientHeight } : { x: 0, y: 0, width: 0, height: 0 };
  }

  destroy(): void {
    if (this.player) {
      this.player.dispose();
      this.player = null;
    }
    this._canvas = null;
    this.animationNames = [];
  }
}
