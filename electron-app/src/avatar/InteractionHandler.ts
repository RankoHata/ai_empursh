// src/avatar/InteractionHandler.ts
import * as PIXI from 'pixi.js';
import { Spine } from 'pixi-spine';
import { AnimationController } from './AnimationController';

declare global {
  interface Window {
    electronAPI?: {
      toggleMainWindow: () => void;
      moveLive2dWindow: (dx: number, dy: number) => void;
      platform: string;
    };
  }
}

export class InteractionHandler {
  private spine: Spine;
  private animCtrl: AnimationController;
  private container: PIXI.Container | null = null;

  private clickPoint = { x: 0, y: 0 };
  private isDragging = false;
  private readonly DRAG_THRESHOLD = 3;

  private boundOnMove: (e: PIXI.FederatedPointerEvent) => void;
  private boundOnUp: (e: PIXI.FederatedPointerEvent) => void;

  constructor(spine: Spine, animCtrl: AnimationController) {
    this.spine = spine;
    this.animCtrl = animCtrl;
    this.boundOnMove = this.onPointerMove.bind(this);
    this.boundOnUp = this.onPointerUp.bind(this);
  }

  attach(container: PIXI.Container): void {
    this.container = container;
    container.eventMode = 'static';
    container.cursor = 'pointer';
    container.on('pointerdown', this.onPointerDown, this);
    container.on('pointermove', this.boundOnMove);
    container.on('pointerup', this.boundOnUp);
    container.on('pointerupoutside', this.boundOnUp);
  }

  private onPointerDown = (e: PIXI.FederatedPointerEvent): void => {
    this.clickPoint = { x: e.screenX, y: e.screenY };
    this.isDragging = false;
  };

  private onPointerMove = (e: PIXI.FederatedPointerEvent): void => {
    // Gaze tracking
    const nx = e.globalX / window.innerWidth;
    const ny = e.globalY / window.innerHeight;
    this.animCtrl.setGazeTarget(nx, ny);

    // Drag detection
    const dx = e.screenX - this.clickPoint.x;
    const dy = e.screenY - this.clickPoint.y;

    if (!this.isDragging && (Math.abs(dx) > this.DRAG_THRESHOLD || Math.abs(dy) > this.DRAG_THRESHOLD)) {
      this.isDragging = true;
    }

    if (this.isDragging) {
      window.electronAPI?.moveLive2dWindow(dx, dy);
      this.clickPoint = { x: e.screenX, y: e.screenY };
    }
  };

  private onPointerUp = (e: PIXI.FederatedPointerEvent): void => {
    if (!this.isDragging) {
      // Click — check which body part was hit
      const local = this.spine.toLocal(new PIXI.Point(e.globalX, e.globalY));
      const bounds = this.spine.getLocalBounds();
      const relY = local.y - bounds.y;
      const heightFraction = bounds.height > 0 ? relY / bounds.height : 0.5;

      if (heightFraction < 0.25) {
        // Head click → play action animation
        this.animCtrl.playOneShot('action', 'idle');
      } else {
        // Body/legs click → toggle main window
        window.electronAPI?.toggleMainWindow();
      }
    }
    this.isDragging = false;
  };

  detach(): void {
    if (this.container) {
      this.container.off('pointerdown', this.onPointerDown, this);
      this.container.off('pointermove', this.boundOnMove);
      this.container.off('pointerup', this.boundOnUp);
      this.container.off('pointerupoutside', this.boundOnUp);
      this.container = null;
    }
  }
}
