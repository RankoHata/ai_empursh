// src/avatar/InteractionHandler.ts
import type { Skeleton } from '@esotericsoftware/spine-core';
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
  private canvas: HTMLCanvasElement;
  private animCtrl: AnimationController;
  private skeleton: Skeleton;

  private pointerDown = false;
  private isDragging = false;
  private readonly DRAG_THRESHOLD = 5;

  // rAF-throttled IPC flush
  private pendingDx = 0;
  private pendingDy = 0;
  private rafId = 0;

  // Bound handlers
  private onDocMove: (e: PointerEvent) => void;
  private onDocUp: (e: PointerEvent) => void;

  constructor(canvas: HTMLCanvasElement, animCtrl: AnimationController, skeleton: Skeleton) {
    this.canvas = canvas;
    this.animCtrl = animCtrl;
    this.skeleton = skeleton;
    this.onDocMove = this.handleDocMove.bind(this);
    this.onDocUp = this.handleDocUp.bind(this);
  }

  attach(): void {
    this.canvas.style.cursor = 'pointer';
    this.canvas.addEventListener('pointerdown', this.onPointerDown);
    this.canvas.addEventListener('contextmenu', this.onContextMenu);
  }

  private onPointerDown = (e: PointerEvent): void => {
    this.pointerDown = true;
    this.isDragging = false;
    this.pendingDx = 0;
    this.pendingDy = 0;

    document.addEventListener('pointermove', this.onDocMove);
    document.addEventListener('pointerup', this.onDocUp);
  };

  private onContextMenu = (e: Event): void => {
    e.preventDefault();
    window.electronAPI?.toggleMainWindow();
  };

  // ── Document move (global) ─────────────────────────────────────────
  private handleDocMove(e: PointerEvent): void {
    // Gaze tracking
    const nx = e.clientX / window.innerWidth;
    const ny = e.clientY / window.innerHeight;
    this.animCtrl.setGazeTarget(nx, ny);

    if (!this.pointerDown) return;

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

    if (!this.isDragging && e.button === 0) {
      // Left click → pet reaction
      this.animCtrl.playOneShot('action');
    }
    // Right-click → open main window (handled by contextmenu event)

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
    this.canvas.removeEventListener('pointerdown', this.onPointerDown);
    this.canvas.removeEventListener('contextmenu', this.onContextMenu);
    document.removeEventListener('pointermove', this.onDocMove);
    document.removeEventListener('pointerup', this.onDocUp);
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = 0;
    }
  }
}
