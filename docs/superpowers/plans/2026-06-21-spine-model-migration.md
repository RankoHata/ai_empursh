# Spine 2D 角色渲染引擎迁移 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Live2D 角色系统完整替换为 Spine 4.1 + PixiJS，新建 `src/avatar/` 抽象层

**Architecture:** 7 个新文件构成 avatar 模块：IAvatarModel（接口）→ SpineModel（实现）→ AnimationController（状态机）→ InteractionHandler（交互）→ AvatarManager（调度器）→ Avatar.jsx（React 组件）。PixiApp（单例）管理 WebGL 上下文。

**Tech Stack:** PixiJS v7 + pixi-spine v4 + React 18 + Electron 33 + TypeScript

---

### Task 0: 环境准备 — 安装依赖 + 移动模型

**Files:**
- Modify: `package.json`
- Move: `assets/live2d/c017_02/` → `assets/spine/c017_02/`

- [ ] **Step 1: 安装 PixiJS 依赖**

```bash
cd electron-app
npm install pixi.js@^7.3.0 pixi-spine@^4.0.0
```

- [ ] **Step 2: 移动 Spine 模型到新目录**

```bash
mkdir -p assets/spine
mv assets/live2d/c017_02 assets/spine/c017_02
```

- [ ] **Step 3: 验证模型文件就位**

```bash
ls -la assets/spine/c017_02/
# 预期：c017_02_00.skel  c017_02_00.atlas  c017_02.png
```

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json assets/spine/c017_02/
git rm -r assets/live2d/c017_02/
git commit -m "chore: install PixiJS + pixi-spine, move spine model to assets/spine"
```

---

### Task 1: 共享类型定义 `types.ts`

**Files:**
- Create: `src/avatar/types.ts`

- [ ] **Step 1: 编写类型文件**

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add src/avatar/types.ts
git commit -m "feat: add avatar shared types"
```

---

### Task 2: 核心接口 `IAvatarModel.ts`

**Files:**
- Create: `src/avatar/IAvatarModel.ts`

- [ ] **Step 1: 编写接口**

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add src/avatar/IAvatarModel.ts
git commit -m "feat: add IAvatarModel interface"
```

---

### Task 3: PixiJS Application 单例 `PixiApp.ts`

**Files:**
- Create: `src/avatar/PixiApp.ts`

- [ ] **Step 1: 编写单例**

```typescript
// src/avatar/PixiApp.ts
import * as PIXI from 'pixi.js';

export class PixiApp {
  private static instance: PixiApp;
  public app: PIXI.Application | null = null;

  static getInstance(): PixiApp {
    if (!PixiApp.instance) {
      PixiApp.instance = new PixiApp();
    }
    return PixiApp.instance;
  }

  async init(canvas: HTMLCanvasElement, width: number, height: number): Promise<void> {
    this.app = new PIXI.Application({
      width,
      height,
      backgroundAlpha: 0,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
      view: canvas,
    });
  }

  resize(width: number, height: number): void {
    if (this.app) {
      this.app.renderer.resize(width, height);
    }
  }

  destroy(): void {
    if (this.app) {
      this.app.destroy(false, { children: true, texture: true });
      this.app = null;
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/avatar/PixiApp.ts
git commit -m "feat: add PixiApp singleton"
```

---

### Task 4: Spine 模型实现 `SpineModel.ts`

**Files:**
- Create: `src/avatar/SpineModel.ts`

- [ ] **Step 1: 编写 SpineModel 类**

```typescript
// src/avatar/SpineModel.ts
import * as PIXI from 'pixi.js';
import { Spine } from 'pixi-spine';
import { IAvatarModel } from './IAvatarModel';
import { HitResult } from './types';
import { PixiApp } from './PixiApp';

export class SpineModel implements IAvatarModel {
  private spine: Spine | null = null;
  private animationNames: string[] = [];

  async load(assetPath: string): Promise<void> {
    const pixiApp = PixiApp.getInstance();
    if (!pixiApp.app) {
      throw new Error('PixiApp not initialized');
    }

    // pixi-spine 自动解析 .atlas（通过 .skel 内部引用）
    const spineData = await PIXI.Assets.load(assetPath);

    this.spine = new Spine(spineData);

    // 居中放置
    const bounds = this.spine.getLocalBounds();
    this.spine.x = pixiApp.app.screen.width / 2;
    this.spine.y = pixiApp.app.screen.height / 2 + bounds.height * 0.15;
    this.spine.scale.set(0.5);

    pixiApp.app.stage.addChild(this.spine);

    // 缓存动画列表
    this.animationNames = this.spine.state.data.skeletonData.animations
      .map((a: any) => a.name);

    // 播放默认待机
    if (this.animationNames.includes('idle')) {
      this.playAnimation('idle', true);
    }
  }

  playAnimation(name: string, loop: boolean = true): void {
    if (this.spine) {
      this.spine.state.setAnimation(0, name, loop);
    }
  }

  getAnimationList(): string[] {
    return [...this.animationNames];
  }

  mixAnimation(trackIndex: number, name: string, duration: number): void {
    if (this.spine) {
      const entry = this.spine.state.setAnimation(trackIndex, name, false);
      if (entry) {
        entry.mixDuration = duration;
      }
    }
  }

  setParam(name: string, value: number): void {
    if (this.spine) {
      const bone = this.spine.skeleton.findBone(name);
      if (bone) {
        bone.rotation = value;
      }
    }
  }

  getParam(name: string): number {
    if (this.spine) {
      const bone = this.spine.skeleton.findBone(name);
      return bone ? bone.rotation : 0;
    }
    return 0;
  }

  hitTest(x: number, y: number): HitResult | null {
    if (!this.spine) return null;

    // 屏幕坐标 → stage 局部坐标
    const local = this.spine.toLocal(new PIXI.Point(x, y));

    // 简易区域检测：y < bounds.height * 0.25 视为头部
    const bounds = this.spine.getLocalBounds();
    const relY = local.y - bounds.y;
    const heightFraction = relY / bounds.height;

    if (heightFraction < 0.25) {
      return { boneName: 'head', slotName: '' };
    }
    if (heightFraction < 0.85) {
      return { boneName: 'body', slotName: '' };
    }
    return { boneName: 'legs', slotName: '' };
  }

  getBounds(): { x: number; y: number; width: number; height: number } {
    if (this.spine) {
      const b = this.spine.getLocalBounds();
      return { x: b.x, y: b.y, width: b.width, height: b.height };
    }
    return { x: 0, y: 0, width: 0, height: 0 };
  }

  update(deltaSec: number): void {
    // pixi-spine 由 PIXI ticker 驱动，手动调用 update 用于同步
    if (this.spine) {
      this.spine.update(deltaSec);
    }
  }

  destroy(): void {
    if (this.spine) {
      this.spine.destroy();
      this.spine = null;
    }
    this.animationNames = [];
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/avatar/SpineModel.ts
git commit -m "feat: add SpineModel (Spine 4.1 via pixi-spine)"
```

---

### Task 5: 动画状态机 `AnimationController.ts`

**Files:**
- Create: `src/avatar/AnimationController.ts`

- [ ] **Step 1: 编写 AnimationController**

```typescript
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

  // 用于视线平滑插值
  private gazeTargetX: number = 0;
  private gazeTargetY: number = 0;
  private gazeCurrentX: number = 0;
  private gazeCurrentY: number = 0;
  private readonly GAZE_SPEED: number = 0.1;
  private readonly GAZE_MAX_ANGLE: number = 0.15; // 弧度，约 8.6°
  private enabled: boolean = true;

  constructor(spine: Spine) {
    this.spine = spine;
  }

  /** 切换状态（多轨道并行） */
  setState(stateName: string): void {
    if (!this.enabled || stateName === this.currentState) return;

    const tracks = STATE_ANIM_MAP[stateName];
    if (!tracks) return;

    for (const t of tracks) {
      this.spine.state.setAnimation(t.track, t.anim, t.loop);
    }

    this.currentState = stateName;
  }

  /** 播放一次性动作，播完后回到指定动画 */
  playOneShot(name: string, returnTo: string = 'idle'): void {
    if (!this.enabled) return;
    this.spine.state.setAnimation(AnimTrack.MAIN, name, false);
    this.spine.state.addAnimation(AnimTrack.MAIN, returnTo, true, 0.3);
  }

  /** 更新注视目标（归一化坐标 0-1） */
  setGazeTarget(normalizedX: number, normalizedY: number): void {
    this.gazeTargetX = (normalizedX - 0.5) * 2 * this.GAZE_MAX_ANGLE;
    this.gazeTargetY = (normalizedY - 0.5) * 2 * this.GAZE_MAX_ANGLE;
  }

  /** 每帧调用，平滑插值注视角度 */
  updateGaze(): void {
    this.gazeCurrentX += (this.gazeTargetX - this.gazeCurrentX) * this.GAZE_SPEED;
    this.gazeCurrentY += (this.gazeTargetY - this.gazeCurrentY) * this.GAZE_SPEED;

    // 驱动眼球骨骼（如果模型有的话）
    const eyeBoneL = this.spine.skeleton.findBone('eye_l');
    const eyeBoneR = this.spine.skeleton.findBone('eye_r');
    if (eyeBoneL) eyeBoneL.rotation = this.gazeCurrentX;
    if (eyeBoneR) eyeBoneR.rotation = this.gazeCurrentX;
  }

  destroy(): void {
    this.enabled = false;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/avatar/AnimationController.ts
git commit -m "feat: add AnimationController with multi-track state machine"
```

---

### Task 6: 交互处理器 `InteractionHandler.ts`

**Files:**
- Create: `src/avatar/InteractionHandler.ts`

- [ ] **Step 1: 编写 InteractionHandler**

```typescript
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

  private dragStart = { x: 0, y: 0 };
  private isDragging = false;
  private clickPoint = { x: 0, y: 0 };
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
    this.dragStart = { x: e.globalX, y: e.globalY };
    this.clickPoint = { x: e.screenX, y: e.screenY };
    this.isDragging = false;
  };

  private onPointerMove = (e: PIXI.FederatedPointerEvent): void => {
    // 视线跟踪
    const nx = e.globalX / window.innerWidth;
    const ny = e.globalY / window.innerHeight;
    this.animCtrl.setGazeTarget(nx, ny);

    // 拖拽检测
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
      // 点击 → 检测部位
      const local = this.spine.toLocal(new PIXI.Point(e.globalX, e.globalY));
      const bounds = this.spine.getLocalBounds();
      const relY = local.y - bounds.y;
      const heightFraction = relY / bounds.height;

      if (heightFraction < 0.25) {
        // 点击头部 → 播放 action 动画
        this.animCtrl.playOneShot('action', 'idle');
      } else {
        // 点击其他部位 → 切换主窗口
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
```

- [ ] **Step 2: Commit**

```bash
git add src/avatar/InteractionHandler.ts
git commit -m "feat: add InteractionHandler (drag, click, gaze)"
```

---

### Task 7: 顶层调度器 `AvatarManager.ts`

**Files:**
- Create: `src/avatar/AvatarManager.ts`

- [ ] **Step 1: 编写 AvatarManager**

```typescript
// src/avatar/AvatarManager.ts
import { PixiApp } from './PixiApp';
import { SpineModel } from './SpineModel';
import { AnimationController } from './AnimationController';
import { InteractionHandler } from './InteractionHandler';
import { IAvatarModel } from './IAvatarModel';

export class AvatarManager {
  private pixiApp: PixiApp;
  private model: IAvatarModel | null = null;
  private animCtrl: AnimationController | null = null;
  private interaction: InteractionHandler | null = null;
  private animFrameId: number = 0;
  private lastTime: number = 0;

  async init(canvas: HTMLCanvasElement, modelPath: string): Promise<void> {
    this.pixiApp = PixiApp.getInstance();
    await this.pixiApp.init(canvas, canvas.width, canvas.height);

    this.model = new SpineModel();
    await this.model.load(modelPath);

    // AnimationController 需要直接访问 Spine 实例
    const spineInstance = (this.model as SpineModel).getSpine();
    if (!spineInstance) {
      throw new Error('Spine instance not available after load');
    }

    this.animCtrl = new AnimationController(spineInstance);

    this.interaction = new InteractionHandler(spineInstance, this.animCtrl);
    this.interaction.attach(this.pixiApp.app!.stage);

    this.startLoop();
  }

  private startLoop(): void {
    this.lastTime = performance.now();
    const loop = (now: number): void => {
      const delta = (now - this.lastTime) / 1000;
      this.lastTime = now;

      if (this.model) {
        this.model.update(delta);
      }
      if (this.animCtrl) {
        this.animCtrl.updateGaze();
      }

      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  setState(state: string): void {
    this.animCtrl?.setState(state);
  }

  async switchModel(newPath: string): Promise<void> {
    // v1 预留，暂不实现
    throw new Error('switchModel not implemented in v1');
  }

  destroy(): void {
    cancelAnimationFrame(this.animFrameId);
    this.interaction?.detach();
    this.animCtrl?.destroy();
    this.model?.destroy();
    this.pixiApp.destroy();
  }
}
```

- [ ] **Step 2: 给 SpineModel 添加 getSpine 方法**

编辑 `src/avatar/SpineModel.ts`，追加方法：

```typescript
  /** 获取底层 PIXI.spine.Spine 实例（供 AnimationController 使用） */
  getSpine(): import('pixi-spine').Spine | null {
    return this.spine;
  }
```

- [ ] **Step 3: Commit**

```bash
git add src/avatar/AvatarManager.ts src/avatar/SpineModel.ts
git commit -m "feat: add AvatarManager top-level orchestrator"
```

---

### Task 8: React 组件 `Avatar.jsx`

**Files:**
- Create: `src/renderer/components/Avatar.jsx`

- [ ] **Step 1: 编写 Avatar 组件**

```jsx
// src/renderer/components/Avatar.jsx
import React, { useRef, useEffect, useState } from 'react';

const Avatar = React.memo(function Avatar({ state = 'idle' }) {
  const canvasRef = useRef(null);
  const mgrRef = useRef(null);
  const [status, setStatus] = useState('loading');  // 'loading' | 'ready' | 'error'

  useEffect(() => {
    let cancelled = false;

    async function initAvatar() {
      try {
        // 动态导入，避免非 live2d 模式加载 pixi 代码
        const { AvatarManager } = await import('../../avatar/AvatarManager');
        if (cancelled) return;

        const mgr = new AvatarManager();
        mgrRef.current = mgr;
        await mgr.init(canvasRef.current, 'assets/spine/c017_02/c017_02_00.skel');
        if (!cancelled) setStatus('ready');
      } catch (err) {
        if (!cancelled) setStatus(`error: ${err.message}`);
      }
    }

    initAvatar();

    return () => {
      cancelled = true;
      if (mgrRef.current) {
        mgrRef.current.destroy();
        mgrRef.current = null;
      }
    };
  }, []);

  // 响应后端状态变更
  useEffect(() => {
    if (status === 'ready' && mgrRef.current) {
      mgrRef.current.setState(state);
    }
  }, [state, status]);

  return (
    <div className="avatar-container">
      <canvas ref={canvasRef} width={280} height={450} />
      {status !== 'ready' && (
        <div className="avatar-overlay">
          {status === 'loading' ? '加载中...' : status}
        </div>
      )}
    </div>
  );
});

export default Avatar;
```

- [ ] **Step 2: Commit**

```bash
git add src/renderer/components/Avatar.jsx
git commit -m "feat: add Avatar React component"
```

---

### Task 9: 集成 — 更新 App.jsx

**Files:**
- Modify: `src/renderer/App.jsx`

- [ ] **Step 1: 替换 import 行**

将第 10 行：
```jsx
import Live2DAvatar from './components/Live2DAvatar';
```
替换为：
```jsx
import Avatar from './components/Avatar';
```

- [ ] **Step 2: 替换 live2d-only 模式渲染**

将第 486-528 行（`isLive2DOnly` 逻辑块）替换为：

```jsx
  // Spine pet mode — 交互由 InteractionHandler 通过 PixiJS 事件处理
  const isLive2DOnly = window.location.search.includes('mode=live2d');

  if (isLive2DOnly) {
    return (
      <div className="live2d-only-container">
        <Avatar state={avatarState} />
      </div>
    );
  }
```

删除旧的 `petDragRef`、`petClickRef`、`onPetMouseDown` 等逻辑（这些现在由 `InteractionHandler` 内部处理）。

- [ ] **Step 3: 替换 sidebar 中的 Live2DAvatar**

将第 646 行：
```jsx
          <Live2DAvatar state={avatarState} />
```
替换为：
```jsx
          <Avatar state={avatarState} />
```

注意：FeatureGuard 包装保持不变。

- [ ] **Step 4: Commit**

```bash
git add src/renderer/App.jsx
git commit -m "feat: integrate Avatar component into App"
```

---

### Task 10: 调整宠物窗口尺寸 `main.js`

**Files:**
- Modify: `src/main.js`

- [ ] **Step 1: 修改窗口尺寸**

将第 91-92 行：
```js
    width: 250,
    height: 360,
```
修改为：
```js
    width: 280,
    height: 450,
```

- [ ] **Step 2: Commit**

```bash
git add src/main.js
git commit -m "feat: resize pet window to 280x450 for spine model"
```

---

### Task 11: 移除 Live2D 脚本引用 `index.html`

**Files:**
- Modify: `index.html`

- [ ] **Step 1: 删除 Cubism Core 脚本**

删除第 12 行：
```html
  <script src="assets/live2d/live2dcubismcore.min.js"></script>
```

- [ ] **Step 2: Commit**

```bash
git add index.html
git commit -m "chore: remove live2d cubism core script from index.html"
```

---

### Task 12: 更新 Vite 配置 `vite.renderer.config.mjs`

**Files:**
- Modify: `vite.renderer.config.mjs`

- [ ] **Step 1: 移除 Live2D alias，添加 Spine 资源处理**

将整个文件替换为：

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: '.',
  resolve: {
    alias: {},
  },
  assetsInclude: ['**/*.skel', '**/*.atlas'],
  build: {
    outDir: '.vite/renderer/main_window',
  },
});
```

变更说明：
- 移除 `@framework` alias（指向 `src/live2d/framework`）
- 移除 `path` import（不再需要）
- 将 `assetsInclude` 从 `.moc3, .model3.json, .motion3.json` 改为 `.skel, .atlas`

- [ ] **Step 2: Commit**

```bash
git add vite.renderer.config.mjs
git commit -m "chore: update vite config for spine assets"
```

---

### Task 13: 清理 Live2D 遗留代码

**Files:**
- Delete: `src/live2d/`（整个目录）
- Delete: `src/renderer/components/Live2DAvatar.jsx`
- Delete: `assets/live2d/g36_1904/`（整个目录）
- Delete: `assets/live2d/shaders/`（整个目录）

- [ ] **Step 1: 删除 Live2D 源码和资源**

```bash
git rm -r src/live2d/
git rm src/renderer/components/Live2DAvatar.jsx
git rm -r assets/live2d/g36_1904/
git rm -r assets/live2d/shaders/
```

- [ ] **Step 2: 检查残留引用**

```bash
grep -r "live2d\|Live2D\|live2D\|cubism\|Cubism" src/ --include="*.js" --include="*.jsx" --include="*.ts" --include="*.json" || echo "No residues found"
```

预期输出：`No residues found`（或仅在 `main.js` 的 IPC handler 注释中有残留，可忽略）

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove all Live2D legacy code and assets"
```

---

### Task 14: 验证构建 & 烟雾测试

**Files:** 无新增/修改

- [ ] **Step 1: 验证前端构建不报错**

```bash
cd electron-app
npx vite build --config vite.renderer.config.mjs 2>&1 | tail -20
```

预期：`✓ built in ...s`，无 TypeScript/导入错误。

- [ ] **Step 2: 检查 bundle 是否包含 pixi.js 和 pixi-spine**

```bash
ls -la .vite/renderer/main_window/assets/ | head -20
```

预期：存在 pixi 相关的 JS chunk。

- [ ] **Step 3: 手动启动验证清单**

按 CLAUDE.md 启动后端 + 前端：
```bash
# 终端 1
cd backend && python main.py

# 终端 2
cd electron-app && npm start
```

逐项验证：
| 验证项 | 预期 |
|--------|------|
| 宠物窗口出现 | 280×450，透明背景 |
| 角色显示 | NIKKE 角色立绘可见，idle 动画循环播放 |
| 点击宠物 | 主窗口弹出 |
| 拖拽宠物 | 窗口跟随鼠标移动 |
| 点击头部 | 播放 action 动画 |
| 发送消息 | 角色表情切换（talk_start） |
| 视线跟踪 | 眼球随鼠标移动 |
| 其他功能 | 聊天/笔记/设置正常 |

---

## 改动文件总览

| 操作 | 文件数 | 文件列表 |
|------|--------|---------|
| 🆕 新建 | 8 | `src/avatar/types.ts`, `IAvatarModel.ts`, `PixiApp.ts`, `SpineModel.ts`, `AnimationController.ts`, `InteractionHandler.ts`, `AvatarManager.ts`, `src/renderer/components/Avatar.jsx` |
| ✏️ 修改 | 4 | `package.json`, `src/renderer/App.jsx`, `src/main.js`, `index.html`, `vite.renderer.config.mjs` |
| 🗑 删除 | 4+ 目录 | `src/live2d/`, `Live2DAvatar.jsx`, `g36_1904/`, `shaders/` |
| 📦 移动 | 1 | `assets/live2d/c017_02/` → `assets/spine/c017_02/` |
