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
  private stage: PIXI.Container | null = null;

  private pointerDown = false;
  private isDragging = false;
  private readonly DRAG_THRESHOLD = 5;

  // Double-click detection
  private lastClickTime = 0;
  private readonly DOUBLE_CLICK_MS = 350;

  // Accumulated deltas for rAF-throttled IPC
  private pendingDx = 0;
  private pendingDy = 0;
  private rafId = 0;

  // Bound document handlers (for global drag tracking)
  private onDocMove: (e: PointerEvent) => void;
  private onDocUp: (e: PointerEvent) => void;

  constructor(spine: Spine, animCtrl: AnimationController) {
    this.spine = spine;
    this.animCtrl = animCtrl;
    this.onDocMove = this.handleDocMove.bind(this);
    this.onDocUp = this.handleDocUp.bind(this);
  }

  attach(stage: PIXI.Container): void {
    this.stage = stage;
    stage.eventMode = 'static';
    stage.cursor = 'pointer';
    stage.on('pointerdown', this.onPointerDown, this);
    // Right-click on the pet → open main window
    stage.on('rightclick', this.onRightClick, this);
  }

  // ── PIXI pointerdown ───────────────────────────────────────────────
  private onPointerDown = (_e: PIXI.FederatedPointerEvent): void => {
    this.pointerDown = true;
    this.isDragging = false;
    this.pendingDx = 0;
    this.pendingDy = 0;

    document.addEventListener('pointermove', this.onDocMove);
    document.addEventListener('pointerup', this.onDocUp);
  };

  // ── Right-click on pet → open main window ──────────────────────────
  private onRightClick = (_e: PIXI.FederatedPointerEvent): void => {
    window.electronAPI?.toggleMainWindow();
  };

  // ── Document move (fires globally) ─────────────────────────────────
  private handleDocMove(e: PointerEvent): void {
    // Gaze tracking
    const nx = e.clientX / window.innerWidth;
    const ny = e.clientY / window.innerHeight;
    this.animCtrl.setGazeTarget(nx, ny);

    if (!this.pointerDown) return;

    // Use movementX/Y — these are relative to the last pointermove,
    // immune to coordinate-system mismatches between PIXI and DOM.
    const dx = e.movementX;
    const dy = e.movementY;

    if (!this.isDragging && (Math.abs(dx) > this.DRAG_THRESHOLD || Math.abs(dy) > this.DRAG_THRESHOLD)) {
      this.isDragging = true;
    }

    if (this.isDragging) {
      this.pendingDx += dx;
      this.pendingDy += dy;
      this.scheduleFlush();
    }
  }

  private scheduleFlush(): void {
    if (this.rafId) return;
    this.rafId = requestAnimationFrame(() => {
      this.rafId = 0;
      if (this.pendingDx !== 0 || this.pendingDy !== 0) {
        window.electronAPI?.moveLive2dWindow(
          Math.round(this.pendingDx),
          Math.round(this.pendingDy),
        );
        this.pendingDx = 0;
        this.pendingDy = 0;
      }
    });
  }

  // ── Document release ───────────────────────────────────────────────
  private handleDocUp(e: PointerEvent): void {
    document.removeEventListener('pointermove', this.onDocMove);
    document.removeEventListener('pointerup', this.onDocUp);

    if (!this.pointerDown) return;

    if (!this.isDragging) {
      // Right-click → open main window
      if (e.button === 2) {
        window.electronAPI?.toggleMainWindow();
      } else {
        // Left-click → double-click detection
        const now = Date.now();
        if (now - this.lastClickTime < this.DOUBLE_CLICK_MS) {
          // Double click → open main window
          window.electronAPI?.toggleMainWindow();
          this.lastClickTime = 0; // reset to avoid triple-click triggering again
        } else {
          // Single click → pet reaction animation
          this.animCtrl.playOneShot('action', 'idle');
          this.lastClickTime = now;
        }
      }
    }

    // Flush remaining drag delta
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = 0;
    }
    if (this.isDragging && (this.pendingDx !== 0 || this.pendingDy !== 0)) {
      window.electronAPI?.moveLive2dWindow(
        Math.round(this.pendingDx),
        Math.round(this.pendingDy),
      );
    }
    this.pendingDx = 0;
    this.pendingDy = 0;
    this.pointerDown = false;
    this.isDragging = false;
  }

  detach(): void {
    if (this.stage) {
      this.stage.off('pointerdown', this.onPointerDown, this);
      this.stage.off('rightclick', this.onRightClick, this);
      this.stage = null;
    }
    document.removeEventListener('pointermove', this.onDocMove);
    document.removeEventListener('pointerup', this.onDocUp);
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = 0;
    }
  }
}
