// src/avatar/AnimationController.ts
import type { AnimationState, Skeleton } from '@esotericsoftware/spine-core';
import type { IAvatarModel } from './IAvatarModel';

const STATE_ANIM_MAP: Record<string, string> = {
  idle: 'idle',
  speaking: 'idle', // fallback — talk_start is played as one-shot via playOneShot
  action: 'action',
  sad: 'sad',
};

// 情绪 → 动画映射（运行时探测后自动填充）
const EMOTION_ANIM_MAP: Record<string, string> = {
  idle: 'idle',
  happy: 'action',       // fallback，探测到 smile/laugh 等自动替换
  sad: 'sad',
  angry: 'idle',         // fallback，探测到 angry/rage 等自动替换
  thinking: 'idle',      // fallback，探测到 think/shy 等自动替换
  surprised: 'idle',     // fallback，探测到 surprise/shock 等自动替换
  bored: 'idle',         // fallback，探测到 bored/yawn 等自动替换
};

/** 探测模型可用动画并自动匹配情绪映射 */
export function probeAnimations(model: IAvatarModel): void {
  const anims = model.getAnimationList();
  console.log('[Spine] Available animations:', anims);

  for (const anim of anims) {
    const lower = anim.toLowerCase();
    if (lower.includes('angry') || lower.includes('rage') || lower.includes('mad')) {
      EMOTION_ANIM_MAP['angry'] = anim;
    }
    if (lower.includes('sad') || lower.includes('cry')) {
      EMOTION_ANIM_MAP['sad'] = anim;
    }
    if (lower.includes('happy') || lower.includes('smile') || lower.includes('laugh') || lower.includes('cheer')) {
      EMOTION_ANIM_MAP['happy'] = anim;
    }
    if (lower.includes('think') || lower.includes('shy')) {
      EMOTION_ANIM_MAP['thinking'] = anim;
    }
    if (lower.includes('surprise') || lower.includes('shock') || lower.includes('wow')) {
      EMOTION_ANIM_MAP['surprised'] = anim;
    }
    if (lower.includes('bored') || lower.includes('yawn') || lower.includes('sigh')) {
      EMOTION_ANIM_MAP['bored'] = anim;
    }
  }
  console.log('[Spine] Emotion mapping:', JSON.stringify(EMOTION_ANIM_MAP, null, 2));
}

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
    // 优先查情绪映射，再查功能状态映射
    const anim = EMOTION_ANIM_MAP[stateName] || STATE_ANIM_MAP[stateName];
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
