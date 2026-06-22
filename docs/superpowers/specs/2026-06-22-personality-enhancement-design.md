# 助理人格增强 — 详细设计文档

> 版本：v1.0
> 日期：2026-06-22
> 依据：`doc/助理人格增强.md` v2.1 + 代码仓现状分析
> 状态：✅ 实现完成 (2026-06-23)

---

## 1. 功能范围（最终确认）

| 序号 | 功能 | 决策 |
|------|------|------|
| 1 | 人格多版本管理 | ✅ 实现 |
| 2 | 成长弧光阶段动态注入 | ❌ 砍掉 |
| 3 | System Prompt 模板引擎（Jinja2） | ✅ 实现 |
| 4 | 上下文动态路由（自动选版本） | ❌ 砍掉 |
| 5 | 长期记忆与智能摘要 | 📦 搁置 |
| 6 | 人格-技能绑定 | ❌ 砍掉 |
| 7 | Spine 情绪状态同步 | ✅ 实现 |

---

## 2. 架构总览

```
main.py  ──── PersonalityManager ──── db/personalities.py ──── SQLite
  │                    │
  │                    ├── Jinja2 模板渲染（utils/template.py）
  │                    ├── 版本聚合（list_grouped）
  │                    └── 情绪标签提取（正则剥离 [!emotion:xxx!]）
  │
  ├── ChatSession（agent/chat.py）
  │      └── system_prompt 经 PersonalityManager 渲染后注入
  │
  └── WebSocket ──── 前端
         ├── personalities_list（含 grouped 聚合数组）
         ├── set_personality（按版本 id 切换）
         ├── message_complete（新增 emotion 字段）
         └── config（新增 user.name）
```

**核心原则**：增量叠加，不改动现有核心流程。`main.py` 只跟 `PersonalityManager` 打交道，不再直接调 `db/personalities.py`。

---

## 3. 数据库变更

### 3.1 DDL

```sql
ALTER TABLE personalities ADD COLUMN parent_id INTEGER;
ALTER TABLE personalities ADD COLUMN version_tag TEXT;
ALTER TABLE personalities ADD COLUMN metadata TEXT;  -- JSON string

CREATE INDEX idx_personalities_parent_id ON personalities(parent_id);
CREATE INDEX idx_personalities_version_tag ON personalities(version_tag);
```

### 3.2 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `parent_id` | INTEGER | 指向同一角色首个版本的 id。NULL = 独立人格（无父版本） |
| `version_tag` | TEXT | `simple` / `full` / `arc` / NULL |
| `metadata` | TEXT | JSON 扩展（情绪映射覆盖、模板变量默认值等） |

### 3.3 种子人格清理

- 删除 `backend/personalities/cute-girl.yaml`
- 删除 `backend/personalities/professional.yaml`
- `backend/personalities/default.yaml` 精简为：

```yaml
name: "默认助手"
description: "通用 AI 桌面助理，干净中立"
system_prompt: |
  你是一个智能、友好的 AI 桌面助理。
  请用中文回复用户的问题，提供准确、有用的帮助。
```

### 3.4 种子函数改造

`db/personalities.py` 的 `seed_personalities()` 需扩展 YAML 读取字段：支持可选的 `version_tag`、`parent_id`、`metadata`。默认助手不含这些字段，使用 DB 默认值（NULL）。

### 3.5 迁移策略

`db/init_db.py` 中的 `init_db()` 负责执行 ALTER TABLE。使用 try-catch 包裹 ALTER TABLE，因 SQLite 不支持 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 语法。

---

## 4. 配置扩展

`config.yaml` 新增 `user` 段：

```yaml
user:
  name: ""   # 用户名称，为空时模板变量默认 "用户"
```

`config.py` 的 `AppConfig` 增加 `user` 属性。`get_config` / `update_config` 的 WebSocket 处理程序同步扩展。

---

## 5. PersonalityManager（新增核心模块）

### 5.1 文件位置

`backend/agent/personality_manager.py`

### 5.2 完整接口

```python
class PersonalityManager:
    """人格统一管理器 — 加载、版本聚合、模板渲染、情绪标签提取"""

    # ── 生命周期 ──
    def __init__(self):
        """初始化，持有 config 引用用于模板上下文"""

    # ── CRUD（委托 db/personalities.py）──
    def get(self, pid: int) -> dict | None
    def get_default(self) -> dict
    def list_all(self) -> list[dict]
    def create(self, **fields) -> dict
    def update(self, pid: int, **fields) -> dict | None
    def delete(self, pid: int) -> bool

    # ── 版本聚合 ──
    def list_grouped(self) -> list[dict]

    # ── 模板渲染 ──
    def render_prompt(self, personality: dict, extra_context: dict | None = None) -> str

    # ── 情绪标签 ──
    def extract_emotion(self, response_text: str) -> tuple[str, str]:
        """从回复中提取并剥离 [!emotion:xxx!] 标签。
        返回 (clean_text, emotion_label)"""
```

### 5.3 `list_grouped()` 返回格式

```json
[
  {
    "id": 1,
    "name": "默认助手",
    "parent_id": null,
    "version_tag": null,
    "is_single": true,
    "versions": []
  },
  {
    "id": 101,
    "name": "阿尼斯",
    "parent_id": null,
    "version_tag": "simple",
    "is_single": false,
    "versions": [
      {"id": 101, "version_tag": "simple", "label": "简洁"},
      {"id": 102, "version_tag": "full", "label": "完整"},
      {"id": 103, "version_tag": "arc", "label": "深度"}
    ]
  }
]
```

**聚合逻辑**：
- 所有 `parent_id IS NULL` 的记录为根节点
- `parent_id` 指向根节点的记录为该根节点的版本
- `is_single = len(versions) == 0`
- 前端直接使用 `grouped` 数组渲染选择器，无需再聚合

### 5.4 `render_prompt()` 模板上下文

| 变量 | 来源 | 默认值 |
|------|------|--------|
| `user_name` | `config.yaml` → `user.name` | `"用户"` |
| `current_time` | `datetime.now().strftime("%Y-%m-%d %H:%M")` | — |
| `personality_name` | `personality["name"]` | — |
| `version_tag` | `personality["version_tag"]` | `""` |

### 5.5 `extract_emotion()` 逻辑

```python
import re

def extract_emotion(self, response_text: str) -> tuple[str, str]:
    """提取并剥离 [!emotion:xxx!] 标签"""
    match = re.search(r'\[!emotion:\s*(\w+)\s*!\]', response_text)
    if match:
        emotion = match.group(1)
        clean = re.sub(r'\[!emotion:\s*\w+\s*!\]\s*', '', response_text)
        return clean, emotion
    return response_text, "idle"
```

### 5.6 与现有代码的集成

`agent/personality.py` 改为：

```python
from .personality_manager import PersonalityManager

_pm: PersonalityManager | None = None

def get_manager() -> PersonalityManager:
    global _pm
    if _pm is None:
        _pm = PersonalityManager()
    return _pm

# 向后兼容：ensure_seeded() 在 init 时自动调用
def ensure_seeded():
    from db.personalities import seed_personalities
    seed_personalities()
```

`main.py` 通过 `get_manager()` 获取实例，所有人格操作走 Manager。

---

## 6. Jinja2 模板引擎

### 6.1 文件位置

`backend/utils/template.py`

### 6.2 实现

```python
from jinja2 import Template

def render_prompt(template_str: str, context: dict) -> str:
    """渲染 system_prompt 中的 Jinja2 变量。
    未定义变量保留原样，不抛异常。
    """
    template = Template(template_str)
    return template.render(context)
```

### 6.3 依赖

在 `pyproject.toml` 或 `requirements.txt` 中增加 `jinja2`。

---

## 7. 情绪系统

### 7.1 后端：System Prompt 注入指令

在 `PersonalityManager.render_prompt()` 渲染后的 system_prompt **末尾追加**：

```
[系统指令] 在每次回复的最后一行，单独输出 [!emotion:标签!] 表示你当前的情绪语气。
可用标签：happy, sad, angry, thinking, surprised, bored, idle。
此标记不会显示给用户，请务必带上。
```

### 7.2 后端：提取与下发

`main.py` 在 `message_complete` 前调用：

```python
full = "".join(collected_chunks)
clean_content, emotion = personality_manager.extract_emotion(full)

await websocket.send_json({
    "type": "message_complete",
    "payload": {
        "full_content": clean_content,
        "partial": partial,
        "trace": trace,
        "emotion": emotion,  # ← 新增
    },
})
```

**重要**：`clean_content`（不含情绪标签）用于 TTS 合成（`_synthesize_and_send`）和数据库存储（`conv_db.add_turn`）。`full` 原始字符串不进入任何下游环节。

### 7.3 前端：Spine 动画映射

#### 运行时探测

实现时首先在浏览器 console 输出完整动画列表：

```typescript
// 在 SpineModel.load() 完成后
console.log('[Spine] Available animations:', this.animationNames);
```

#### 映射表（AnimationController.ts 扩展）

```typescript
const EMOTION_ANIM_MAP: Record<string, string> = {
  idle:      'idle',
  happy:     'action',     // 待探测后调整
  sad:       'sad',
  angry:     'idle',       // 待探测（用户提示模型有 angry/rage）
  thinking:  'idle',       // 待探测
  surprised: 'idle',       // 待探测
  bored:     'idle',       // 待探测
};
```

用户已确认模型存在 angry、pain、rage、sad、shy、shy2 等动画。实现步骤：

1. 运行时 `console.log(getAnimationList())` 获取完整列表
2. 按名称语义匹配：angry→angry/rage, sad→sad, happy→shy/shy2, thinking→shy2, etc.
3. 无法匹配的情绪 → fallback `idle`
4. 后续可尝试 Spine 参数 blend 或程序化生成缺失动作

#### 情绪接收流程

```
App.jsx: message_complete → emotion
  ↓ 检查 localStorage.emotionFollowEnabled（默认 true）
  ↓ 若开启: setAvatarState(emotion)
  ↓ Avatar.jsx: mgrRef.current.setState(emotion)
  ↓ AnimationController: EMOTION_ANIM_MAP[emotion] → 播放动画
  ↓ 3 秒后 setAvatarState('idle') 自动回落
```

#### 开关控制

- `localStorage` 键名：`emotionFollowEnabled`
- 默认值：`"true"`（开启）
- 关闭时：前端忽略 `message_complete` 的 `emotion` 字段，Avatar 保持 idle

---

## 8. WebSocket 协议变更

### 8.1 消息变更一览

| 消息 | 方向 | 变更 |
|------|------|------|
| `personalities_list` | 后端→前端 | 人格项增加 `parent_id`/`version_tag`/`metadata`；增加 `grouped` 聚合数组；增加 `current` 当前人格 id |
| `set_personality` | 前端→后端 | 不变（直接传目标版本的 id） |
| `personality_set` | 后端→前端 | 不变 |
| `message_complete` | 后端→前端 | 新增 `emotion` 字段 |
| `get_config` | 后端→前端 | 新增 `user.name` 字段 |
| `update_config` | 前端→后端 | 支持 `updates.user.name` |

### 8.2 `personalities_list` 完整格式

```json
{
  "type": "personalities_list",
  "payload": {
    "current": 102,
    "personalities": [...],
    "grouped": [
      {
        "id": 1, "name": "默认助手", "parent_id": null,
        "version_tag": null, "is_single": true, "versions": []
      },
      {
        "id": 101, "name": "阿尼斯", "parent_id": null,
        "version_tag": "simple", "is_single": false,
        "versions": [
          {"id": 101, "version_tag": "simple", "label": "简洁"},
          {"id": 102, "version_tag": "full", "label": "完整"}
        ]
      }
    ]
  }
}
```

### 8.3 `message_complete` 完整格式

```json
{
  "type": "message_complete",
  "payload": {
    "full_content": "你好呀！今天心情不错。",
    "partial": false,
    "trace": [...],
    "emotion": "happy"
  }
}
```

### 8.4 `set_personality` 行为

前端直接传目标版本的 `id`。无需额外 `version_tag`——每个版本在 DB 中有独立 `id`。

```json
{"type": "set_personality", "payload": {"personality_id": 102}}
```

### 8.5 Config 扩展

```json
// get_config 响应
{"type": "config", "payload": {"user": {"name": "小明"}, "model": {...}, ...}}

// update_config 请求
{"type": "update_config", "payload": {"updates": {"user": {"name": "小明"}}}}
```

---

## 9. 前端 UI 设计

### 9.1 人格选择器改版

**当前**：单选按钮列表（SettingsPanel 中 `<input type="radio">` 列表）

**改版**：下拉式选择器

- 单版本角色：点击直接选中，显示角色名
- 多版本角色：展开显示可用版本子项，选中目标版本
- 当前选中项：高亮背景 + ✓ 标记
- 角色和版本在同一选择器内展开，无需二级菜单

### 9.2 新增设置项

| 设置项 | 位置 | 类型 | 存储 | 默认值 |
|--------|------|------|------|--------|
| 用户名称 | 设置面板 → 新 section "用户信息" | 文本输入框 | `config.yaml` → `user.name` | 空（后端默认 "用户"） |
| Avatar 情绪跟随 | 设置面板 → 新 section "Avatar 情绪跟随" | CSS 滑动开关 | `localStorage` → `emotionFollowEnabled` | 开启 |

### 9.3 开关样式统一

将项目中现有的 checkbox（情绪跟随、TTS、紧凑模式）统一替换为 **纯 CSS 滑动开关**。在 `App.css` 中增加 ~20 行 `.toggle` 样式，零依赖。

```css
.toggle { 
  appearance: none; width: 44px; height: 24px; background: #444; 
  border-radius: 12px; position: relative; cursor: pointer; 
  transition: background 0.2s; 
}
.toggle:checked { background: #7289da; }
.toggle::after { 
  content: ''; position: absolute; top: 2px; left: 2px; 
  width: 20px; height: 20px; border-radius: 50%; background: #fff; 
  transition: transform 0.2s; 
}
.toggle:checked::after { transform: translateX(20px); }
```

### 9.4 组件改动清单

| 组件 | 改动 |
|------|------|
| `SettingsPanel.jsx` | 人格选择器从 radio 列表改为 dropdown；新增用户名称输入；新增情绪跟随开关；开关统一为 `.toggle` 样式 |
| `StatusBar.jsx` | TTS 开关样式改为 `.toggle` |
| `App.jsx` | 新增 `emotionFollowEnabled` 状态；`message_complete` 处理中根据开关决定是否传递 emotion 到 Avatar；新增 `update_config` 支持 `user.name` |
| `Avatar.jsx` | 支持 emotion 状态的临时播放 + 回落 idle |
| `AnimationController.ts` | 新增 `EMOTION_ANIM_MAP`；`setState` 兼容 emotion 标签 |
| `App.css` | 新增 `.toggle` 开关样式 |

---

## 10. 实现任务清单

| 序号 | 任务 | 涉及文件 | 估时 |
|------|------|----------|------|
| 1 | 删除种子文件 + 精简 default.yaml | `backend/personalities/` | 5min |
| 2 | DB 扩展（ALTER TABLE + 索引） | `backend/db/init_db.py` | 15min |
| 3 | 迁移 `db/personalities.py` 支持新字段 | `backend/db/personalities.py` | 30min |
| 4 | Config 扩展（添加 user.name） | `backend/config.py`, `config.yaml.example` | 15min |
| 5 | 新增 `utils/template.py`（Jinja2） | `backend/utils/template.py` | 15min |
| 6 | 新增 `agent/personality_manager.py` | `backend/agent/personality_manager.py` | 1h |
| 7 | 改造 `agent/personality.py`（向后兼容） | `backend/agent/personality.py` | 10min |
| 8 | `main.py` 集成 PersonalityManager + 情绪提取 | `backend/main.py` | 45min |
| 9 | 前端人格选择器改版（下拉 + 版本标签） | `SettingsPanel.jsx` | 1h |
| 10 | 前端新设置项（用户名称 + 情绪开关） | `SettingsPanel.jsx`, `App.jsx` | 45min |
| 11 | 开关样式统一（CSS .toggle） | `App.css`, `SettingsPanel.jsx`, `StatusBar.jsx` | 20min |
| 12 | Spine 动画探测 + 情绪映射 | `AnimationController.ts`, `Avatar.jsx` | 30min |
| 13 | 前端 emotion 接收 + 回落逻辑 | `App.jsx`, `Avatar.jsx` | 30min |
| 14 | 添加 jinja2 依赖 | `pyproject.toml` | 5min |

**总估时**：约 6-7 小时

---

## 11. 测试要点

| 测试场景 | 预期 |
|----------|------|
| 首次启动，仅默认助手一个种子人格 | `personalities_list` 返回 1 条记录，`is_single: true` |
| 用户新建多版本角色（同一 parent_id） | `grouped` 正确聚合，版本下拉正确显示 |
| 切换人格版本 | `set_personality` 生效，下一轮对话使用新版本的 system_prompt |
| System Prompt 含 `{{ user_name }}` | 渲染后变量被替换为实际用户名 |
| System Prompt 含 `{{ current_time }}` | 渲染后变量被替换为当前时间 |
| 用户名为空 | `{{ user_name }}` 渲染为 "用户" |
| AI 回复末尾含 `[!emotion:happy!]` | 前端收到 `emotion: "happy"`，回复文本中不含标签 |
| AI 回复不含情绪标签 | `emotion: "idle"`，回复文本完整 |
| 情绪跟随开关关闭 | 前端忽略 emotion，Avatar 保持 idle |
| 情绪跟随开关开启 | Avatar 播放对应动画，3 秒后回落 idle |
| 不支持的情绪标签 | AnimationController fallback 到 idle |
| 删除种子人格 | 后端拒绝 |
| 删除用户人格 | 成功，同 parent_id 的其他版本不受影响 |

---

## 12. 不实现/搁置

| 功能 | 原因 |
|------|------|
| 上下文动态路由（自动选版本） | 关键词规则不准，LLM 路由太贵 — 用户手动选择足够 |
| 成长弧光阶段注入 | 需求方砍掉 |
| 人格-技能绑定 | 需求方砍掉 |
| 长期记忆与智能摘要 | 合理但暂不实现，保留待办池 |

---

## 13. 实现变更记录（与设计差异）

### 13.1 架构调整

| 设计 | 实现 | 原因 |
|------|------|------|
| `on_done` 由 chat.py 的 `finally` 自动触发 | 移除 `on_done` 回调，改由 main.py 手动调用 `_send_done` | 流式缓冲 chunk 必须在 done 之前发送，`finally` 时序不可控 |
| 情绪标签 `[!emotion:xxx!]` | 正则可选匹配 `[` `]`：`\[?!emotion:...!\]?` | 模型有时会丢弃方括号，输出 `!emotion:happy!` |
| 单体窗口驱动 Avatar | IPC 中继：主窗口 WS → main process → 桌宠窗口 | 主窗口和桌宠窗口各有独立 React 实例，WebSocket emotion 只能到达主窗口 |
| 桌宠窗口处理所有 WS 消息 | 桌宠窗口跳过 chat 消息（message_chunk/play_audio/message_complete），仅通过 IPC 接收 emotion | 避免双窗口同时处理消息导致回复重复、TTS 双播 |
| 情绪动画关键词匹配（last-wins） | 优先级规则数组，精确匹配优先 | 实际模型动画名与关键词推测有出入，需基于探测结果精确映射 |

### 13.2 新增/修改文件（实现阶段）

| 文件 | 操作 | 说明 |
|------|------|------|
| `electron-app/src/preload.js` | 修改 | 新增 `setAvatarEmotion` / `onAvatarEmotion` IPC 通道 |
| `electron-app/src/main.js` | 修改 | 新增 `set-avatar-emotion` IPC handler → 转发到 live2dWindow |
| `backend/personalities/anis-01-simple.yaml` | 新增 | 阿尼斯简洁版种子 |
| `backend/personalities/anis-02-full.yaml` | 新增 | 阿尼斯完整版种子 |
| `backend/personalities/anis-03-arc.yaml` | 新增 | 阿尼斯深度版种子 |
| `backend/db/personalities.py` | 修改 | 种子函数支持 `parent_name` 符号引用 |

### 13.3 TTS 开关调整

- 默认值从 `true` 改为 `false`（用户反馈：常关场景不需要默认开启）
- 从 StatusBar 移至 SettingsPanel → 语音配置栏

---

## 14. Bug 修复记录

以下 Bug 在实现过程中发现并修复：

| # | Bug | 根因 | 修复 |
|---|-----|------|------|
| B1 | **朗读开关无法关闭** | 旧 CSS `.voice-toggle input { display: none }` 覆盖了 `.toggle` 样式 | 删除旧 CSS 规则 |
| B2 | **回复消息重复显示两条** | `stream_with_tool_loop` 的 `finally` 块先触发 `done`，然后 main.py 的缓冲 flush 才发送最后一条 chunk → 前端 `done` 已标记 `isStreaming=false` → chunk 找不到 streaming 消息 → 创建新消息 | 移除 `finally` 中的 `on_done`，改由 main.py 在 buffer flush + message_complete 之后手动调用 `_send_done` |
| B3 | **情绪标签 `!emotion:happy!` 显示在界面上** | 模型输出格式为 `!emotion:happy!`（无方括号），正则 `\[...\]` 匹配失败 | 正则改为 `\[?!emotion:\s*\w+\s*!\]?` 兼容有无括号 |
| B4 | **情绪不驱动 Avatar 动画** | 桌宠窗口是独立 BrowserWindow，其 React 实例的 `handleMessage` 虽然能收到 WS 消息，但 `setAvatarState` 只在主窗口生效；且 `message_complete` 在 `done` 之后到达时 `isStreaming` 已为 false，内容替换被跳过 | ① 主窗口通过 IPC (`set-avatar-emotion`) 将 emotion 推送到桌宠窗口；② `message_complete` 改用 `role==='assistant'` 查找而非 `isStreaming` 判断 |
| B5 | **情绪动画映射不准** | `probeAnimations` 使用 last-wins 策略，如 `shy` 被后出现的 `shy2` 覆盖，`angry` 被 `rage` 覆盖 | 重构为优先级规则数组，精确匹配名在前，探测时才按优先级命中 |
| B6 | **旧种子记录残留** | 删除 YAML 文件后 DB 中 `小E`/`专业顾问` 记录仍存在 | 迁移函数 `_migrate_personality_v2` 中增加清理 SQL |

### 其他技术说明

- **Backend**: Python 3.10 不支持 `X | None` 语法，统一用 `Optional[X]`
- **IPC relay**: 使用 Electron `ipcMain.on` + `webContents.send` 实现主窗口→桌宠的单向 emotion 推送
- **Stream Emotion Extraction**: `PersonalityManager.extract_emotion()` 对完整响应做正则提取+剥离，`message_complete.full_content` 始终为清洁文本
