# Spine 2D 角色渲染引擎迁移 — 详细设计

> **日期**：2026-06-21  
> **版本**：v1.0  
> **状态**：已确认  
> **分支**：feature/spine-model  
> **目标**：将 Live2D 驱动的 G36 角色替换为基于 Spine 4.1 + PixiJS 的高动态 2D 立绘，实现更丰富的动作交互与性能优化。

---

## 1. 背景与目标

### 1.1 现状

- 桌面助手使用 **Live2D Cubism SDK for Web 5** 加载 G36 角色
- 框架代码 55+ 个 TypeScript 文件以源码形式捆绑在 `src/live2d/framework/`
- `live2dcubismcore.min.js` 需从官网手动下载
- G36 模型为 Cubism 3 格式，motion 不兼容 Cubism 5，只能显示静态姿势
- 动画表现力有限，性能开销较高

### 1.2 目标

- **彻底移除** Live2D 所有代码、依赖和资源
- 使用 **Spine 4.1** 骨骼动画 + **PixiJS v8** 渲染 + **pixi-spine** 插件
- 新建 `src/avatar/` 抽象层，支持未来多模型类型切换
- 后端 WebSocket 协议不变，前端自行映射状态到动画

### 1.3 模型资源

| 属性 | 值 |
|------|-----|
| Spine 版本 | 4.1.20（`.skel` 二进制格式） |
| 图集 | `c017_02_00.atlas`，单张 2048×2048 PNG，PMA 启用 |
| 贴图 | `c017_02.png`（4.2 MB） |
| 内置动画 | `idle`、`action`、`sad`、`talk_start`、`talk_end`、`hair_side`（1-5 变体） |
| 部件数 | 305（手臂/身体/面部/头发/饰品等） |
| 存放路径 | `assets/spine/c017_02/` |

---

## 2. 总体架构

```
src/avatar/                              ← 新建，角色抽象层
├── IAvatarModel.ts                      ← 抽象接口
├── SpineModel.ts                        ← Spine 4.1 具体实现
├── PixiApp.ts                           ← PixiJS Application 单例
├── AnimationController.ts               ← 动画状态机
├── InteractionHandler.ts                ← 点击/拖拽/视线跟踪
├── AvatarManager.ts                     ← 单例，顶层调度器
└── types.ts                             ← 共享类型定义

React 组件：
├── src/renderer/components/Avatar.jsx   ← 新组件，替代 Live2DAvatar
└── src/renderer/App.jsx                 ← 更新引用 + 状态映射
```

### 设计原则

- **面向接口**：`AvatarManager` 只依赖 `IAvatarModel`，不感知底层是 Spine 还是其他引擎
- **单例 PixiApp**：全局唯一 Application 实例，所有模型共享渲染上下文
- **多轨道动画**：主动画/表情/视线三条轨道独立控制，互不干扰
- **协议不变**：后端 `avatar_state` 协议保持 `"idle" | "speaking"`，前端映射到动画

---

## 3. 核心接口 `IAvatarModel.ts`

```typescript
interface IAvatarModel {
  // 生命周期
  load(assetPath: string): Promise<void>;
  destroy(): void;

  // 动画控制
  playAnimation(name: string, loop?: boolean): void;
  getAnimationList(): string[];
  mixAnimation(name: string, duration: number): void;

  // 参数控制（骨骼/变形）
  setParam(name: string, value: number): void;
  getParam(name: string): number;

  // 每帧更新
  update(deltaSec: number): void;

  // 交互检测
  hitTest(x: number, y: number): HitResult | null;
}

interface HitResult {
  boneName: string;
  slotName: string;
}
```

- 只定义"做什么"，不涉及任何具体引擎 API
- 新增一种模型类型 = 新增一个实现类，`AvatarManager` 零改动

---

## 4. 模块详细设计

### 4.1 `PixiApp.ts` — PixiJS Application 单例

```typescript
class PixiApp {
  private static instance: PixiApp;
  app: PIXI.Application;

  static getInstance(): PixiApp { ... }

  async init(canvas: HTMLCanvasElement, width: number, height: number) {
    this.app = new PIXI.Application({
      width, height,
      backgroundAlpha: 0,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
      view: canvas,
    });
  }

  resize(w: number, h: number) { this.app.renderer.resize(w, h); }
  destroy() { this.app.destroy(false, { children: true, texture: true }); }
}
```

- 全局唯一，canvas 由 React 组件提供（不自行创建 DOM）
- 透明背景配合 Electron 透明窗口
- 支持窗口缩放

### 4.2 `SpineModel.ts` — Spine 4.1 实现

```typescript
class SpineModel implements IAvatarModel {
  private spine: PIXI.spine.Spine;
  private app: PIXI.Application;

  async load(assetPath: string) {
    // 1. PIXI.Assets.load('.skel') → SpineData
    // 2. new PIXI.spine.Spine(spineData)  
    // 3. 居中 + 初始 scale
    // 4. app.stage.addChild(spine)
    // 5. 缓存动画列表
    // 6. 播放默认 idle
  }

  playAnimation(name: string, loop = true) {
    this.spine.state.setAnimation(trackIndex, name, loop);
  }

  hitTest(x: number, y: number): HitResult | null {
    // 屏幕坐标 → Spine 局部坐标
    // 遍历骨骼边界框检测命中
  }

  update(deltaSec: number) { this.spine.update(deltaSec); }
  destroy() { this.spine.destroy(); }
}
```

- 实现 `IAvatarModel` 所有方法
- 内部使用 `pixi-spine` 原生 API，不向上层暴露

### 4.3 `AnimationController.ts` — 动画状态机

**动画轨道分配**：

| 轨道 | 索引 | 用途 |
|------|------|------|
| MAIN | 0 | 主动画（idle, action） |
| FACE | 1 | 表情（talk_start, talk_end, sad） |
| EYE | 2 | 视线跟踪（骨骼参数驱动） |

**状态映射表**：

```typescript
const STATE_ANIM_MAP: Record<string, TrackAnim[]> = {
  idle:     [{ track: MAIN, anim: 'idle', loop: true }],
  speaking: [{ track: MAIN, anim: 'idle', loop: true },
             { track: FACE, anim: 'talk_start', loop: false }],
  action:   [{ track: MAIN, anim: 'action', loop: false }],
  sad:      [{ track: FACE, anim: 'sad', loop: true }],
};
```

**核心方法**：

```typescript
class AnimationController {
  setState(stateName: string): void;
  setGazeTarget(normalizedX: number, normalizedY: number): void;
  playOneShot(name: string, returnTo?: string): void;
}
```

- `setState`: 驱动多轨道同时切换，通过 spine 的 track 机制实现混合过渡
- `setGazeTarget`: 修改眼球骨骼旋转值，3° 平滑跟随
- `playOneShot`: 播放一次性动作（如点击触发），播完后自动回到主动画

### 4.4 `InteractionHandler.ts` — 交互系统

继承现有行为，底层引擎从 DOM 事件迁移到 PixiJS Federated Events：

```
pointerdown  → 记录起点
pointermove  → |Δ| > 3px → electronAPI.moveLive2dWindow(dx, dy)（拖拽）
              → 同时 → animCtrl.setGazeTarget(x, y)（视线跟踪）
pointerup    → 无拖拽 → hitTest 检测部位
              → 命中 head 骨骼 → playOneShot('action')
              → 命中其他部位 → electronAPI.toggleMainWindow()
              → 未命中任何 → electronAPI.toggleMainWindow()
```

- 拖拽阈值 3px，对齐现有逻辑
- 视线跟踪在每次 `pointermove` 时更新

### 4.5 `AvatarManager.ts` — 顶层调度器

```typescript
class AvatarManager {
  async init(canvas: HTMLCanvasElement, modelPath: string): Promise<void>;
  setState(state: string): void;                              // 后端状态入口
  switchModel(newPath: string): Promise<void>;                // 未来：切模型
  destroy(): void;
}
```

- `init`: 初始化 PixiApp → 创建 SpineModel → 加载 → 挂载 InteractionHandler → 启动渲染循环
- `setState`: 对接 React 的 `avatarState`，委托 `AnimationController` 执行
- `switchModel`: 预留接口，v1 不实现但结构已就绪
- 渲染循环：`requestAnimationFrame`，计算 delta，调用 `model.update(delta)`

---

## 5. React 组件 `Avatar.jsx`

```jsx
function Avatar({ state = 'idle' }) {
  const canvasRef = useRef(null);
  const mgrRef = useRef(null);
  const [status, setStatus] = useState('loading');  // loading | ready | error

  useEffect(() => {
    const mgr = new AvatarManager();
    mgrRef.current = mgr;
    mgr.init(canvasRef.current, 'assets/spine/c017_02/c017_02_00.skel')
      .then(() => setStatus('ready'))
      .catch(e => setStatus(`error: ${e.message}`));
    return () => { mgr.destroy(); };
  }, []);

  useEffect(() => {
    if (status === 'ready') mgrRef.current.setState(state);
  }, [state, status]);

  return (
    <div className="avatar-container">
      <canvas ref={canvasRef} width={280} height={450} />
      {status !== 'ready' && (
        <div className="avatar-overlay">{status === 'loading' ? '加载中...' : status}</div>
      )}
    </div>
  );
}
```

- **接口兼容**：`<Avatar state={avatarState} />` — 与旧 `Live2DAvatar` 完全一致
- **Canvas 尺寸**：280×450，适配新角色比例

---

## 6. 改动面汇总

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/avatar/IAvatarModel.ts` | 抽象接口 |
| `src/avatar/SpineModel.ts` | Spine 4.1 实现 |
| `src/avatar/PixiApp.ts` | PixiJS 单例 |
| `src/avatar/AnimationController.ts` | 动画状态机 |
| `src/avatar/InteractionHandler.ts` | 交互系统 |
| `src/avatar/AvatarManager.ts` | 顶层调度器 |
| `src/avatar/types.ts` | 共享类型 |
| `src/renderer/components/Avatar.jsx` | 新 React 组件 |
| `assets/spine/c017_02/` | Spine 模型（从 `assets/live2d/c017_02/` 移动） |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/renderer/App.jsx` | `Live2DAvatar` → `Avatar`，删除 `FeatureGuard` 中的 `showLive2D` |
| `src/main.js` | 宠物窗口 250×360 → **280×450** |
| `index.html` | 删除 `<script src="assets/live2d/live2dcubismcore.min.js">` |
| `package.json` | 新增 `pixi.js`、`pixi-spine` 依赖 |
| `vite.renderer.config.mjs` | 移除 `@framework` alias，添加 `.skel`/`.atlas` 资源处理 |

### 删除文件

| 文件/目录 | 说明 |
|------|------|
| `src/live2d/`（整目录） | 55+ TypeScript 框架文件 + `Model.ts` |
| `src/renderer/components/Live2DAvatar.jsx` | 旧组件 |
| `assets/live2d/g36_1904/` | G36 模型资源 |
| `assets/live2d/shaders/` | Live2D WebGL 着色器（10 个 .glsl 文件） |
| `assets/live2d/c017_02/` | 移至 `assets/spine/c017_02/` |

### 不动文件

| 文件 | 原因 |
|------|------|
| `src/renderer/hooks/useWebSocket.js` | WS 连接管理无变更 |
| `src/preload.js` | IPC 接口不变 |
| `src/renderer/components/ChatPanel.jsx` 等 | 聊天/笔记/设置组件无影响 |
| `backend/`（全部） | 后端协议不变 |
| `App.css` | 仅需少量 `.avatar-container` 样式调整 |

---

## 7. 数据流

```
后端 WebSocket                      前端
──────────────────────────         ─────────────────────────────────
avatar_state: "speaking"   →       App.jsx: setAvatarState("speaking")
                                            │
                                   Avatar.jsx: useEffect → mgr.setState("speaking")
                                            │
                                   AnimationController.setState("speaking")
                                   ├── MAIN track → "idle" (loop)
                                   └── FACE track → "talk_start"
                                            │
                                   SpineModel.playAnimation("talk_start")
                                            │
                                   pixi-spine: spine.state.setAnimation(...)

InteractionHandler (并行):
  pointermove ──→ 视线跟踪（setGazeTarget）
  pointerdown/up → 拖拽（moveLive2dWindow）/ toggle（toggleMainWindow）
  hitTest ──────→ 部位检测 → playOneShot
```

---

## 8. 测试要点

| 测试项 | 预期结果 |
|--------|----------|
| Spine 模型加载 | 无报错，角色正常显示 |
| 待机动画 | idle 自动循环播放 |
| 后端发送 `speaking` | 面部播放 talk_start，身体保持 idle |
| 点击宠物（无拖拽） | 切换主窗口显示/隐藏 |
| 点击头部区域 | 播放 action 一次性动画 |
| 拖拽宠物 | 窗口跟随移动，无闪烁 |
| 鼠标移动 | 眼球跟踪平滑 |
| 透明背景 | 宠物窗口无背景色块 |
| 窗口缩放 | 角色居中自适应 |
| 性能 | 1080p 下保持 60fps |
| 聊天功能 | 正常收发消息 |
| 语音/笔记/设置 | 所有原有功能正常 |

---

## 9. 风险与注意事项

- **pixi-spine 兼容性**：确认 `pixi-spine` 4.x 对 Spine 4.1.20 的 `.skel` 二进制格式完全兼容。如遇问题，可降级到 `.json` 格式或使用 `pixi-spine` 3.x
- **透明窗口 + WebGL**：Electron 透明窗口配合 `backgroundAlpha: 0` 需要验证 Windows 下效果，部分 GPU 可能有问题
- **模型路径**：模型从 `assets/live2d/c017_02/` 移至 `assets/spine/c017_02/`
- **PMA 纹理**：atlas 声明 `pma: true`，pixi-spine 需对应配置
- **内存释放**：`AvatarManager.destroy()` 必须正确释放 PixiJS 资源（`app.destroy` + `spine.destroy`）
- **Electron Vite 构建**：`.skel` 和 `.atlas` 文件需 Vite 正确处理（非 JS 资源）

---

## 10. 验收标准

- [ ] 完全移除 Live2D 相关代码和依赖，项目无残留引用
- [ ] Spine 模型成功渲染，动态效果优于原 G36 立绘
- [ ] 实现基础交互：待机、拖拽、点击切换、视线跟随
- [ ] 实现表情联动：`speaking` 状态触发 talk 动画
- [ ] 宠物窗口 280×450，透明背景
- [ ] 性能稳定，60fps
- [ ] 所有原有助手功能（聊天、语音、笔记、设置）正常工作
- [ ] 后端协议零改动

---

## 11. 后续扩展方向（v1 不做）

- 多角色切换（`switchModel` 接口已预留）
- Layer Edit 换肤支持
- 物理引擎（Matter.js）头发/布料模拟
- 动作菜单 / 表情轮盘
- 多语言口型同步（基于音素分析）
