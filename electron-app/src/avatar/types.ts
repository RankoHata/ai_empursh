// src/avatar/types.ts

/** 命中检测结果 */
export interface HitResult {
  boneName: string;
  slotName: string;
}

/** 动画轨道枚举 */
export enum AnimTrack {
  MAIN = 0,
  FACE = 1,
  EYE  = 2,
}

/** 单轨动画描述 */
export interface TrackAnim {
  track: AnimTrack;
  anim: string;
  loop: boolean;
}

/** 后端 → 前端状态映射条目 */
export type StateAnimMap = Record<string, TrackAnim[]>;

/** 组件加载状态 */
export type AvatarStatus = 'loading' | 'ready' | 'error';
