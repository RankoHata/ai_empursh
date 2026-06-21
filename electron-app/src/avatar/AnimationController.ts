// src/avatar/AnimationController.ts
import { Spine } from 'pixi-spine';
import { AnimTrack, TrackAnim } from './types';

const STATE_ANIM_MAP: Record<string, TrackAnim[]> = {
  idle: [
    { track: AnimTrack.MAIN, anim: 'idle', loop: true },
  ],
  speaking: [
    { track: AnimTrack.MAIN, anim: 'idle', loop: true },
    { track: AnimTrack.FACE, anim: 'talk_start', loop: false },
  ],
  action: [
    { track: AnimTrack.MAIN, anim: 'action', loop: false },
  ],
  sad: [
    { track: AnimTrack.FACE, anim: 'sad', loop: true },
  ],
};

export class AnimationController {
  private spine: Spine;
  private currentState: string = 'idle';

  // Gaze smoothing
  private gazeTargetX: number = 0;
  private gazeTargetY: number = 0;
  private gazeCurrentX: number = 0;
  private gazeCurrentY: number = 0;
  private readonly GAZE_SPEED: number = 0.1;
  private readonly GAZE_MAX_ANGLE: number = 0.15; // radians (~8.6°)

  constructor(spine: Spine) {
    this.spine = spine;
  }

  /** Switch animation state with multi-track support */
  setState(stateName: string): void {
    if (stateName === this.currentState) return;

    const tracks = STATE_ANIM_MAP[stateName];
    if (!tracks) return;

    for (const t of tracks) {
      this.spine.state.setAnimation(t.track, t.anim, t.loop);
    }

    this.currentState = stateName;
  }

  /** Play a one-shot animation, then return to the specified loop */
  playOneShot(name: string, returnTo: string = 'idle'): void {
    this.spine.state.setAnimation(AnimTrack.MAIN, name, false);
    const idleEntry = this.spine.state.addAnimation(AnimTrack.MAIN, returnTo, true, 0);
    if (idleEntry) {
      // Mix back to idle over 0.6s — smooth, and only eats 0.6s of action's 3.6s tail.
      idleEntry.mixDuration = 0.6;
    }
  }

  /** Update gaze target (normalized screen coords 0-1) */
  setGazeTarget(normalizedX: number, normalizedY: number): void {
    this.gazeTargetX = (normalizedX - 0.5) * 2 * this.GAZE_MAX_ANGLE;
    this.gazeTargetY = (normalizedY - 0.5) * 2 * this.GAZE_MAX_ANGLE;
  }

  /** Per-frame gaze interpolation — call in render loop */
  updateGaze(): void {
    this.gazeCurrentX += (this.gazeTargetX - this.gazeCurrentX) * this.GAZE_SPEED;
    this.gazeCurrentY += (this.gazeTargetY - this.gazeCurrentY) * this.GAZE_SPEED;

    const eyeBoneL = this.spine.skeleton.findBone('eye_l');
    const eyeBoneR = this.spine.skeleton.findBone('eye_r');
    if (eyeBoneL) eyeBoneL.rotation = this.gazeCurrentX;
    if (eyeBoneR) eyeBoneR.rotation = this.gazeCurrentX;
  }

  destroy(): void {
    // Clean up references
  }
}
