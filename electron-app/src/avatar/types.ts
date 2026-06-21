// src/avatar/types.ts

export interface HitResult {
  boneName: string;
  slotName: string;
}

export type AvatarStatus = 'loading' | 'ready' | 'error';
