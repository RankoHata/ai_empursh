// src/avatar/AnimationController.ts
import type { AnimationState, Skeleton } from '@esotericsoftware/spine-core';

const STATE_ANIM_MAP: Record<string, string> = {
  idle: 'idle',
  speaking: 'idle', // fallback — talk_start is played as one-shot via playOneShot
  action: 'action',
  sad: 'sad',
};

export class AnimationController {
  private skeleton: Skeleton;
  private animState: AnimationState;
  private currentState: string = 'idle';

  // Gaze smoothing
  private gazeTargetX: number = 0;
  private gazeTargetY: number = 0;
  private gazeCurrentX: number = 0;
  private gazeCurrentY: number = 0;
  private readonly GAZE_SPEED: number = 0.1;
  private readonly GAZE_MAX_ANGLE: number = 0.15;

  constructor(skeleton: Skeleton, animState: AnimationState) {
    this.skeleton = skeleton;
    this.animState = animState;
  }

  setState(stateName: string): void {
    if (stateName === this.currentState) return;
    const anim = STATE_ANIM_MAP[stateName];
    if (!anim) return;
    this.animState.setAnimation(0, anim, true);
    this.currentState = stateName;
  }

  /** Play a one-shot, then return to idle */
  playOneShot(name: string): void {
    const entry = this.animState.setAnimation(0, name, false);
    if (entry) {
      // Mix back to idle over 0.6s when the one-shot ends
      entry.mixDuration = 0.6;
    }
    this.animState.addAnimation(0, 'idle', true, 0);
  }

  setGazeTarget(normalizedX: number, normalizedY: number): void {
    this.gazeTargetX = (normalizedX - 0.5) * 2 * this.GAZE_MAX_ANGLE;
    this.gazeTargetY = (normalizedY - 0.5) * 2 * this.GAZE_MAX_ANGLE;
  }

  updateGaze(): void {
    this.gazeCurrentX += (this.gazeTargetX - this.gazeCurrentX) * this.GAZE_SPEED;
    this.gazeCurrentY += (this.gazeTargetY - this.gazeCurrentY) * this.GAZE_SPEED;

    const eyeBoneL = this.skeleton.findBone('eye_l');
    const eyeBoneR = this.skeleton.findBone('eye_r');
    if (eyeBoneL) eyeBoneL.rotation = this.gazeCurrentX;
    if (eyeBoneR) eyeBoneR.rotation = this.gazeCurrentX;
  }

  destroy(): void {
    // nothing to clean up
  }
}
