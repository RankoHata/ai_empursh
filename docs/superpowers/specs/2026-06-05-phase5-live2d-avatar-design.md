# 阶段 5：Live2D 拟人形象 — 设计文档

**日期**：2026-06-05
**状态**：部分完成（Haru 模型正常，G36 模型渲染正常但动画不兼容）

---

## 1. 目标

集成 Live2D Cubism 5 SDK，将 emoji 头像替换为 Live2D 模型。

---

## 2. 技术选型

| 组件 | 方案 |
|------|------|
| SDK | Cubism SDK for Web 5-r.5 (Framework + Core 6.0.1) |
| 集成方式 | `CubismUserModel` 子类 + WebGL 渲染 |
| React 包装 | 34 行容器组件 |
| 模型 | SDK 示例 Haru + 用户提供的 G36 (Girls Frontline) |

---

## 3. 架构

```
src/live2d/
├── framework/          ← Cubism 5 SDK Framework, 85 个 .ts 文件，零改动
├── Model.ts            ← 我们的 CubismUserModel 子类 (~230 行)
│
src/renderer/components/
└── Live2DAvatar.jsx    ← React 包装组件 (~100 行)

渲染循环：
  Live2DAvatar → Model.setup() → loadModel(moc3) → initRenderer(gl) → draw(gl, w, h)
```

---

## 4. 结果

| 模型 | 渲染 | 纹理 | 动画 | 备注 |
|------|------|------|------|------|
| Haru (SDK 示例) | ✅ | ✅ | ✅ | Cubism 5 原生模型 |
| G36 (Girls Frontline) | ✅ | ✅ | ✅ | Cubism 3 模型，motion 经修复后正常循环 |

---

## 5. 实现过程中的 Bug 与陷阱

### 5.1 架构级陷阱

| # | 陷阱 | 教训 |
|---|------|------|
| 1 | `pixi-live2d-display` 版本混乱 | v0.4.0 只支持 Cubism 2 模型，v0.5.0-beta 需要 PixiJS 8 的子包 `@pixi/core`。库本身不稳定，放弃使用 |
| 2 | 自写渲染管线的复杂性 | 从头实现 Cubism 渲染需要 2000+ 行代码处理 clipping mask、offscreen buffer、shader 等。应优先使用 SDK 内置框架 |
| 3 | SDK demo 代码的耦合 | 官方 demo 创建自己的 canvas 并 append 到 `document.body`，与 React 虚拟 DOM 冲突。点触事件处理也会与 React 事件冲突 |
| 4 | 使用 `str.replace` 批量修改 85 个 SDK 文件中的脚本引用 | 这是错误做法。SDK 文件应原封不动，我们自己写 `CubismUserModel` 子类调用其 API |

### 5.2 API 陷阱

| # | 问题 | 原因 | 修复 |
|---|------|------|------|
| 1 | `CubismUserModel.loadModel()` 接受 `ArrayBuffer` 而非 `CubismModel` | Model 内部自己调 `CubismMoc.create()` | 传入原始 moc3 的 ArrayBuffer |
| 2 | `_expressionManager` / `_motionManager` 无 public getter | 它们是 `protected` 成员 | 子类中直接用 `this._expressionManager` |
| 3 | 必须先 `CubismFramework.startUp()` + `initialize()` | Framework 初始化是模型加载的前提 | 在 `setup()` 开头调用 `ensureFramework()` |
| 4 | `UNPACK_PREMULTIPLY_ALPHA_WEBGL` 必须设置 | Cubism 使用 premultiplied alpha，纹理不设此标志会显示白色遮罩块 | `gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true)` |
| 5 | 纹理必须 `renderer.bindTexture(i, id)` 注册 | 仅创建 GL texture 不够，渲染器不知道纹理存在 | `r.bindTexture(i, texId)` |
| 6 | 矩阵必须用 `projection.multiplyByMatrix(modelMatrix)` | 直接 `setMatrix()` 会覆盖缩放/位置设置 | 先乘后设 |

### 5.3 模型兼容性陷阱（G36 Cubism 3 → 5 迁移）

| # | 问题 | 原因 | 修复 | 状态 |
|---|------|------|------|------|
| 1 | `UserData: {Value: ""}` 空字符串 | 空值导致解析异常 | 删除 UserData 节 | ✅ |
| 2 | Meta 计数与实际数据不匹配（225 seg → 538 seg） | JSON Metadata 声明的 segment/point 数量少于实际数据 | 遍历 Curves 重新计算 TotalSegmentCount/TotalPointCount | ✅ |
| 3 | 动画不播放 | `setEffectIds` 签名是 `(Array, Array)`，但传入了单值而非数组 | `motion.setEffectIds([EyeLOpen,EyeROpen], [MouthOpenY])` | ✅ |
| 4 | 播一次就停 | Cubism 5 不再从 JSON `"Loop": true` 读取循环标志，默认 `_isLoop = false` | `motion.setLoop(true)` | ✅ |
| 5 | 循环点卡顿 | `paramopai` 曲线首尾值不一致（0.01 vs -0.24） | 将末帧值设为与首帧一致（0.01） | ✅ |
| 6 | 帧率不匹配 | 固定 `1/60` delta 与真实帧率不同步 | `performance.now()` 计算真实帧间隔 | ✅ |

### 5.4 渲染陷阱

| # | 问题 | 原因 | 修复 |
|---|------|------|------|
| 1 | 模型显示为黑色剪影 | 纹理未加载 | 添加纹理加载 + `bindTexture()` |
| 2 | 身体部分为白色矩形 | 未设置 `UNPACK_PREMULTIPLY_ALPHA_WEBGL` | `gl.pixelStorei(..., true)` |
| 3 | 双重渲染（"4只手"） | 矩阵设置方式错误，`setMatrix()` 覆盖了 model matrix | 改为 `projection.multiplyByMatrix(modelMatrix)` |
| 4 | `fetch().arrayBuffer()` 加载 moc3 失败 | Vite 可能需要 `assetsInclude` 配置 | 改用 `XMLHttpRequest` + `responseType='arraybuffer'` |
| 5 | 纹理加载失败无报错 | 图片 `onerror` 事件静默 | 添加详细 URL 日志 |

### 5.5 显示缩放陷阱

| # | 问题 | 原因 | 修复 |
|---|------|------|------|
| 1 | 模型太小，周围大量空白 | 模型 .moc3 画布包含透明边距，修改投影矩阵无法消除 | CSS `overflow: hidden` + `transform: scale(1.5)` 放大裁切 |
| 2 | 左右布局下模型比例失调 | 上下布局浪费空间 | 改为 flex 左右布局：左侧内容 + 右侧 Live2D 侧边栏 |

---

## 6. 动画修复总结

G36 模型是 Cubism 3 产物，motion 文件存在 5 个兼容性问题，均已在数据层面修复：

1. **UserData 空值** — 删除空 UserData 节
2. **Meta 计数错误** — 重算 segments/points
3. **API 误用** — `setEffectIds()` 应传数组
4. **Loop 标志丢失** — Cubism 5 不再解析 JSON `Loop`，需手动 `setLoop(true)`
5. **曲线不闭环** — `paramopai` 首尾值不一致（关键！）

**经验教训：** Cubism 3→5 迁移中，motion JSON 文件需要逐项检查。最隐蔽的问题是曲线首尾值不匹配——只有 1/29 条曲线有问题，但就这一条导致整个动画循环卡顿。

---

## 7. 遗留问题

### 7.1 循环点轻微卡顿（未完全解决）

**现象：** G36 待机动画循环时，角色有轻微"点头"——在循环点位置出现不连续。

**根因：** 贝塞尔曲线控制点的切线在循环边界不连续。以 `ParamAngleX`（头部旋转）为例：
- 末段入速度：-15.5（t=8.334→8.867，v=8.24→0，斜率≈-15.5）
- 首段出速度：0.33（t=0→1，v=0→0.333，斜率≈0.33）
- 速度差约 47 倍，导致循环瞬间角色位置跳变。

29 条曲线中有 14 条存在不同程度的切线不连续。

**已尝试的修复：**
| 方法 | 结果 |
|------|------|
| 修改末段 P2 控制点使切线匹配 | 曲线形状被破坏，引入新问题（眨眼异常等） |
| 添加 blend tail 关键帧 | 破坏了受限贝塞尔曲线段的格式约束，解析失败 |
| `setLoopFadeIn(true)` + `setFadeInTime(0.5s)` | 部分缓解但无法完全消除 |

**正确修复方向：** 需要理解 Cubism 受限贝塞尔曲线（`AreBeziersRestricted: true`）的精确段格式，并同时调整末段 P1/P2 和首段控制点，保证 G1 连续性（值和切线都连续）。这需要专门的 motion 编辑工具或 Cubism Editor。

**当前状态：** 接受轻微循环不连续，代码层面已用 `setLoopFadeIn(true)` + `MotionBehavior_V2` + 真实帧间隔做最大程度平滑。

---

## 8. 正确的集成模式（经验总结）

```
1. SDK Framework/ 目录原封不动复制
2. 写自己的 CubismUserModel 子类
3. setup() 中按顺序调用：
   - CubismFramework.startUp() → initialize()
   - CubismModelSettingJson (解析 model3.json)
   - loadModel(moc3 ArrayBuffer)
   - loadExpression/loadPhysics/loadPose/loadMotion (逐个)
   - CubismEyeBlink.create() + CubismBreath.create()
4. initRenderer() 中：
   - createRenderer() → initialize() → startUp()
   - loadShaders(path)
   - 加载纹理 → bindTexture()
5. draw() 中每帧：
   - motion/expression update
   - model.update() → loadParameters
   - eye blink update
   - projection.multiplyByMatrix(modelMatrix) → setMatrix
   - drawModel(shaderPath)
   - saveParameters
   - endFrameProcess
```
