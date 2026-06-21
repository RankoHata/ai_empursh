// src/avatar/IAvatarModel.ts
import { HitResult } from './types';

export interface IAvatarModel {
  /** 加载模型资源 */
  load(assetPath: string): Promise<void>;

  /** 释放所有资源 */
  destroy(): void;

  /** 播放动画（默认循环） */
  playAnimation(name: string, loop?: boolean): void;

  /** 获取模型内所有动画名称 */
  getAnimationList(): string[];

  /** 在指定轨道混合过渡到新动画 */
  mixAnimation(trackIndex: number, name: string, duration: number): void;

  /** 设置骨骼/变形参数值 */
  setParam(name: string, value: number): void;

  /** 读取骨骼/变形参数值 */
  getParam(name: string): number;

  /** 每帧更新 */
  update(deltaSec: number): void;

  /** 交互命中检测（屏幕坐标 → 骨骼/插槽） */
  hitTest(x: number, y: number): HitResult | null;

  /** 获取模型包围盒 {x, y, width, height}（本地坐标） */
  getBounds(): { x: number; y: number; width: number; height: number };
}
