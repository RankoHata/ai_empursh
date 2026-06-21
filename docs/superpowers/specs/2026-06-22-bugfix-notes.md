# PR #1-3 合并后 Bug 修复记录

日期: 2026-06-21 ~ 2026-06-22

## 背景

三个 PR 合并到 master 后出现多个问题：
- PR #1: spine-model（Live2D → Spine 迁移）
- PR #2: notes-enhancement（双轨制笔记）
- PR #3: mcp-enhancement（MCP 工具调用）

---

## Bug 1: Avatar 宠物窗口不显示模型

**现象**: 宠物窗口显示"加载中..."，Spine 模型不出现

**根因**: 三个并行问题
1. `index.html` CSP `connect-src` 缺少 `data:` — PIXI 内部 `checkImageBitmap` 被拦截
2. `Avatar.jsx` 用裸路径 `'assets/spine/...'` 传给 `PIXI.Assets.load()`，Vite 不解析
3. `SpineModel.ts` `PIXI.Assets.load()` 返回 `{ spineData, spineAtlas }` 包装对象，
   `new Spine(result)` 应改为 `new Spine(result.spineData)` — 内层才有 `.version`

**修复**:
- `index.html`: `connect-src` 增加 `data:`
- `Avatar.jsx`: 改用 Vite `new URL(..., import.meta.url)` 解析路径
- `SpineModel.ts:22`: `new Spine(result.spineData)`

---

## Bug 2: 秘密笔记新增卡死 + 笔记页签打不开

**现象**: 秘密笔记页新增笔记后页面卡死，公开笔记页签完全打不开

**根因**: `NoteCard.jsx:4` 访问 `note.content`，但 PR #2 重构后数据库字段是 `content_raw`。
`undefined.length` → TypeError → React 崩溃

**修复**: `NoteCard.jsx`: `note.content_raw || ''`

---

## Bug 3: 宠物窗口模型被裁切

**现象**: 模型只显示腿部，上半身被截断

**根因**: `App.css:1074` 有旧 Live2D 遗留样式 `transform: scale(1.5)` + 父容器 `overflow:hidden`，
把 canvas 放大后裁切

**修复**: 移除 `scale(1.5)`，`transform: translate(-50%, -50%)` 即可

---

## Bug 4: 模型偏移、只显示下半身

**现象**: 模型原点在脚底，放在 canvas 正中央导致上半身在屏幕外

**根因**: `SpineModel.ts` 用 `screen.width/2, screen.height/2` 居中原点，但 Spine 原点在模型底部

**修复**: 加入 stage → `update(0)` → `getBounds()` 取实际渲染边界 → 用边界框居中

---

## Bug 5: 拖拽卡顿 + 范围受限

**现象**: 拖拽宠物窗口感觉卡，拖到一定距离就拖不动了

**根因**: 
- 每次 `pointermove` 都发 IPC `moveLive2dWindow`（60+ 次/秒）
- PIXI 的 `pointermove` 只在 canvas 内触发，鼠标移出窗口就丢事件

**修复**: 改用 document 级 `pointermove`/`pointerup`，`movementX/Y` 计算增量，`requestAnimationFrame` 节流 IPC

---

## Bug 6: 点击模型导致窗口瞬移

**现象**: 单击模型时窗口直接飞到鼠标右侧

**根因**: PIXI `pointerdown` 和 DOM `pointermove` 坐标体系不一致，点击时误判为拖拽

**修复**: 用 `PointerEvent.movementX/Y`（浏览器原生增量）替代 `screenX - clickPoint.x` 计算

---

## Bug 7: 右键闪一下就没了

**现象**: 右键打开主界面，窗口闪现后立即关闭

**根因**: `contextmenu` 事件触发一次 `toggleMainWindow`，随后的 `pointerup`（button=2）
又触发一次 — toggle 两次 = 开→关

**修复**: 右键只走 `contextmenu` 事件，`handleDocUp` 中移除 button=2 分支

---

## Bug 8: 截图后桌宠消失/不置顶

**现象**: Ctrl+Alt+A（微信截图）后宠物窗口消失或掉落到底层

**根因**: 微信截图工具使用 `screen-saver` 级全屏覆盖层，把 `floating` 级的
宠物窗口压下去后不恢复

**修复**: `setAlwaysOnTop(true, 'screen-saver')` — 用最高级别置顶

---

## Bug 9: 动画播放速度异常

**现象**: action 动画播放超快，"逗一下就没了"

**根因**: 两个渲染循环同时驱动 Spine 动画
- PixiJS ticker (`autoUpdate=true`) 调用一次 `spine.update(delta)`
- `AvatarManager` 的 rAF 循环又调用一次 `spine.update(delta)`
- 叠加 = 2x 速度

**修复**: `AvatarManager.ts` 移除手动 `model.update(delta)`，只保留 gaze 更新

---

## Bug 10: action 动画截断

**现象**: 3.57 秒的 action 动画感觉被截断

**根因**: `AnimationController.playOneShot` 用 `addAnimation(MAIN, idle, true, 0.3)`，
`delay=0.3` 让 idle 在 action 结束前 0.3s 就开始混入，吃掉结尾

**修复**: `delay=0` + `idleEntry.mixDuration=0.6` — 让 action 完整播放后在 0.6s 内过渡

---

## Bug 11: 脸红/暗色叠加显示为黑色（核心）

**现象**: action 动画中面部红晕（blush）显示为黑色阴影

**诊断过程**:
1. 排除缺贴图 — `check_model.mjs` 确认所有 306 个区域都在 atlas 中
2. 排除颜色问题 — `console.table` 全部 slot color 为 white，darkColor 为 null
3. 追踪 `f_bl_shy` Mesh 附件 — @2500ms 出现，tint=white，alpha=1，renderable=true
4. 发现 `slot.currentSprite` 为 null，`slot.currentMesh` 存在 — 这是 Mesh 附件不是 Sprite
5. pixi-spine 对 Mesh 走 `spriteColor.setLight`/`setDark` 路径
6. `dark` 数组为 `null`（未设置 `this.spine.color`）→ `dark[0]` TypeError → setLight/setDark 跳过
7. Mesh 保留默认 dark=[0,0,0] → shader `mix(1,0,luma)` 将半透明红晕压暗

**根因**: pixi-spine 社区的 PIXI 包装层对 mesh 附件的两色着色支持有缺陷：
- `dark` 数组未初始化导致运行时错误
- PIXI v7 mesh shader 对 PMA 纹理处理不正确
- 即使用 `this.spine.color = {light:[1,1,1], dark:[1,1,1]}` 修复 TypeErr，
  底层的 mesh shader 仍无法正确渲染 PMA 半透明叠加

**根本解决**: 放弃 pixi-spine，改用 EsotericSoftware 官方 `@esotericsoftware/spine-player`
- 官方运行时原生支持 PMA、两色着色、mesh 渲染
- 渲染管线使用 spine-webgl + Canvas，不依赖 PixiJS
- 与 nikke-db 项目使用相同技术栈
- 参考: https://github.com/Nikke-db/nikke-db-vue

---

## Bug 12: c017_00 模型配件不显示

**现象**: 切换到 c017_00 后，漂浮的 drone 机械部件不出现

**根因**: 模型有 `default` 和 `acc` 两个皮肤，acc 包含配件(drone 等)。
SpinePlayer 默认只加载 default 皮肤

**修复**: 用 spine-core `Skin` API 合并两个皮肤后设置到 skeleton：
```ts
const combined = new Skin('combined');
combined.addSkin(skeleton.data.findSkin('default'));
combined.addSkin(skeleton.data.findSkin('acc'));
skeleton.setSkin(combined);
skeleton.setSlotsToSetupPose();
```

---

## 数据结构关键发现

### c017_02 动画表
| 动画 | 时长 |
|------|------|
| action | 3.57s |
| delight | 5.33s |
| idle | 5.33s |
| sad | 5.33s |
| shy/shy2 | 5.33s |
| rage/pain/worry | 5.33s |
| talk_start | 0.50s |
| ... | ... |

### 附件引用完整性
- Atlas: 306 个纹理区域
- 模型引用: 308 个（3 个 PointAttachment 不需要纹理）
- **无缺失贴图**

### 知识库字段变更 (PR #2)
| 旧字段 | 新字段 |
|--------|--------|
| `notes.content` | `knowledge_items.content_raw` |

前端 `NoteCard` 需要引用 `content_raw` 而非 `content`。

---

## 经验总结

1. **先看日志，再看代码** — DevTools Console + Network 比盲猜有效 100 倍
2. **参考同类项目** — nikke-db 用官方 spine-player，直接指明了正确方向
3. **第三方包装层有坑** — pixi-spine 的 PMA/mesh 问题花了十几轮才定位
4. **数据库字段变更要前后端联查** — NoteCard 崩溃就是 PR #2 重构遗留的
