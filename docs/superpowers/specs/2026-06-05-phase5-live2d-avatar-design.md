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
| G36 (Girls Frontline) | ✅ | ✅ | ❌ | Cubism 3 模型，motion 不兼容 |

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

### 5.3 模型兼容性陷阱

| # | 问题 | 状态 |
|---|------|------|
| 1 | G36 motion 文件 `UserData: {Value: ""}` 空字符串 | ✅ 已修复：删除 UserData 节 |
| 2 | G36 motion Meta 计数与实际数据不匹配（声明 225 seg 实际 538） | ✅ 已修复：重算 TotalSegmentCount/TotalPointCount |
| 3 | G36 motion 使用 `"Target": "Parameter"` 格式（Cubism 3），Cubism 5 运行时无法解析参数引用为 null | ❌ **未修复**：需要 Cubism Editor 重新导出 motion |

### 5.4 渲染陷阱

| # | 问题 | 原因 | 修复 |
|---|------|------|------|
| 1 | 模型显示为黑色剪影 | 纹理未加载 | 添加纹理加载 + `bindTexture()` |
| 2 | 身体部分为白色矩形 | 未设置 `UNPACK_PREMULTIPLY_ALPHA_WEBGL` | `gl.pixelStorei(..., true)` |
| 3 | 双重渲染（"4只手"） | 矩阵设置方式错误，`setMatrix()` 覆盖了 model matrix | 改为 `projection.multiplyByMatrix(modelMatrix)` |
| 4 | `fetch().arrayBuffer()` 加载 moc3 失败 | Vite 可能需要 `assetsInclude` 配置 | 改用 `XMLHttpRequest` + `responseType='arraybuffer'` |
| 5 | 纹理加载失败无报错 | 图片 `onerror` 事件静默 | 添加详细 URL 日志 |

---

## 6. 未解决问题

### G36 模型动画不兼容（#5.3-3）

**现象：** G36 模型可以正常渲染（模型+纹理都正确），但 motion 动画无法播放。

**根因：** G36 motion 文件使用 Cubism 3 的 `"Target": "Parameter"` 格式。Cubism 5 的 `CubismMotion.doUpdateParameters()` 在查找 motion 中的参数 ID 时，返回 null 引用。这是因为 Cubism 5 的 motion 系统期望 `"Target": "Model"` 格式的参数绑定方式。

**修复方向：**
- 使用 Cubism Editor 5 重新导入模型并导出 motion（推荐）
- 或使用 Cubism 3/4 兼容层（SDK 不提供）
- 或使用 Haru 等 Cubism 5 原生模型

**当前处理：** motion 更新被 try/catch 包裹，模型显示默认 T-pose。

---

## 7. 正确的集成模式（经验总结）

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
