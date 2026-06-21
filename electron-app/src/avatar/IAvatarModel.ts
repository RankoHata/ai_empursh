// src/avatar/IAvatarModel.ts

export interface IAvatarModel {
  load(container: HTMLElement, skelUrl: string, atlasUrl: string): Promise<void>;
  playAnimation(name: string, loop?: boolean): any;
  getAnimationList(): string[];
  destroy(): void;
}
