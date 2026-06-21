// src/avatar/PixiApp.ts
import * as PIXI from 'pixi.js';

export class PixiApp {
  private static instance: PixiApp;
  public app: PIXI.Application | null = null;

  static getInstance(): PixiApp {
    if (!PixiApp.instance) {
      PixiApp.instance = new PixiApp();
    }
    return PixiApp.instance;
  }

  async init(canvas: HTMLCanvasElement, width: number, height: number): Promise<void> {
    this.app = new PIXI.Application({
      width,
      height,
      backgroundAlpha: 0,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
      view: canvas,
    });
  }

  resize(width: number, height: number): void {
    if (this.app) {
      this.app.renderer.resize(width, height);
    }
  }

  destroy(): void {
    if (this.app) {
      this.app.destroy(false, { children: true, texture: true });
      this.app = null;
    }
  }
}
