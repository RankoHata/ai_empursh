# 助理人格增强 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现人格多版本管理、Jinja2 模板引擎、AI 驱动情绪标签 + Spine 动画同步。

**Architecture:** 新增 PersonalityManager 统一管理人格加载/版本聚合/模板渲染/情绪提取；main.py 全部通过 Manager 操作人格；Spine AnimationController 扩展情绪映射；SettingsPanel 改版为下拉选择器。

**Tech Stack:** Python FastAPI + SQLite + Jinja2 / React + @esotericsoftware/spine-player

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/personalities/cute-girl.yaml` | 删除 | — |
| `backend/personalities/professional.yaml` | 删除 | — |
| `backend/personalities/default.yaml` | 修改 | 精简为唯一默认种子 |
| `backend/db/init_db.py` | 修改 | personalities 表加 3 列 + 索引 |
| `backend/db/personalities.py` | 修改 | CRUD 支持新字段；种子函数读 version_tag/metadata |
| `backend/config.py` | 修改 | 新增 user 配置段 |
| `backend/config.yaml.example` | 修改 | 新增 user.name 模板 |
| `backend/utils/template.py` | 新增 | Jinja2 渲染薄封装 |
| `backend/agent/personality_manager.py` | 新增 | 人格统一管理器 |
| `backend/agent/personality.py` | 重写 | 简化为 Manager 单例工厂 |
| `backend/main.py` | 修改 | 集成 Manager；message_complete 加 emotion；config 加 user.name |
| `backend/pyproject.toml` | 修改 | 加 jinja2 依赖 |
| `electron-app/src/renderer/App.css` | 修改 | 新增 .toggle 滑动开关样式 |
| `electron-app/src/renderer/App.jsx` | 修改 | emotion 接收+回落；user.name 配置；开关状态管理 |
| `electron-app/src/renderer/components/SettingsPanel.jsx` | 重写 | 下拉人格选择器；用户名称输入；情绪跟随开关 |
| `electron-app/src/renderer/components/StatusBar.jsx` | 修改 | TTS 开关改为 .toggle 样式 |
| `electron-app/src/renderer/components/Avatar.jsx` | 修改 | 支持 emotion 临时播放+回落 |
| `electron-app/src/avatar/AnimationController.ts` | 修改 | 新增 EMOTION_ANIM_MAP；运行时探测动画列表 |

---

### Task 1: 清理种子人格 + DB 迁移 + Config 扩展

**Files:**
- Delete: `backend/personalities/cute-girl.yaml`
- Delete: `backend/personalities/professional.yaml`
- Modify: `backend/personalities/default.yaml`
- Modify: `backend/db/init_db.py`
- Modify: `backend/db/personalities.py`
- Modify: `backend/config.py`
- Modify: `backend/config.yaml.example`

- [ ] **Step 1: 删除旧种子文件**

```bash
rm backend/personalities/cute-girl.yaml
rm backend/personalities/professional.yaml
```

- [ ] **Step 2: 精简 default.yaml**

重写文件内容为：

```yaml
name: "默认助手"
description: "通用 AI 桌面助理，干净中立"
system_prompt: |
  你是一个智能、友好的 AI 桌面助理。
  请用中文回复用户的问题，提供准确、有用的帮助。
```

- [ ] **Step 3: DB 迁移 — init_db.py**

在 `init_db.py` 的 `DDL_CONVERSATIONS` 块中（personalities 表 CREATE 之后），新增迁移函数。找到 `init_db()` 函数，在其中已有的 `cur.executescript(DDL_CONVERSATIONS)` 之后添加：

```python
# Migration: add personality enhancement columns
migrations = [
    "ALTER TABLE personalities ADD COLUMN parent_id INTEGER",
    "ALTER TABLE personalities ADD COLUMN version_tag TEXT",
    "ALTER TABLE personalities ADD COLUMN metadata TEXT",
]
for sql in migrations:
    try:
        cur.execute(sql)
    except Exception:
        pass  # column already exists

cur.executescript("""
    CREATE INDEX IF NOT EXISTS idx_personalities_parent_id ON personalities(parent_id);
    CREATE INDEX IF NOT EXISTS idx_personalities_version_tag ON personalities(version_tag);
""")
```

- [ ] **Step 4: Personenalities CRUD 支持新字段**

修改 `db/personalities.py`：
- `seed_personalities()` 读取 YAML 时增加可选字段 `version_tag`、`parent_id`、`metadata`
- `list_personalities()` 返回全部字段（加 `parent_id, version_tag, metadata`）
- `get_personality()` 同上
- `create_personality()` 支持 `parent_id`、`version_tag`、`metadata` 参数
- `update_personality()` 支持更新 `version_tag`、`metadata`

`seed_personalities()` 修改后的 INSERT：

```python
cur.execute(
    """INSERT INTO personalities (name, description, system_prompt, is_seed, parent_id, version_tag, metadata)
       VALUES (?, ?, ?, 1, ?, ?, ?)""",
    (data["name"], data.get("description", ""), data.get("system_prompt", ""),
     data.get("parent_id"), data.get("version_tag"), data.get("metadata"))
)
```

`create_personality()` 修改：

```python
def create_personality(
    name: str,
    description: str = "",
    system_prompt: str = "",
    parent_id: int | None = None,
    version_tag: str | None = None,
    metadata: str | None = None,
) -> dict:
    now = datetime.now().isoformat()
    conn, cur = get_cursor()
    cur.execute(
        """INSERT INTO personalities (name, description, system_prompt, is_seed, parent_id, version_tag, metadata, created_at, updated_at)
           VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)""",
        (name, description, system_prompt, parent_id, version_tag, metadata, now, now),
    )
    conn.commit()
    return get_personality(cur.lastrowid)
```

`update_personality()` 增加 `version_tag` 和 `metadata` 参数。

- [ ] **Step 5: Config 扩展**

`config.py` 的 `AppConfig.__init__()` 增加：

```python
self.user = self._config.get("user", {"name": ""})
```

`config.yaml.example` 增加：

```yaml
user:
  name: ""
```

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "feat: 清理种子人格 + DB迁移 + config扩展user.name

- 删除 cute-girl.yaml 和 professional.yaml
- default.yaml 精简为唯一默认助手
- personalities 表加 parent_id, version_tag, metadata 列
- CRUD 函数支持新字段
- config 模块增加 user.name 字段

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Jinja2 模板引擎

**Files:**
- Create: `backend/utils/template.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 添加 jinja2 依赖**

在 `pyproject.toml` 的 `dependencies` 数组中增加 `"jinja2>=3.1.0"`。

如果使用 requirements.txt，则增加一行 `jinja2>=3.1.0`。

安装：

```bash
cd backend && uv sync
```

- [ ] **Step 2: 创建 utils/template.py**

```python
"""System Prompt 模板渲染 — Jinja2 薄封装."""

from jinja2 import Template


def render_prompt(template_str: str, context: dict) -> str:
    """渲染 Jinja2 模板字符串。

    Args:
        template_str: 包含 {{ var }} 占位符的模板字符串
        context: 变量上下文字典

    Returns:
        渲染后的字符串。未定义变量保留原样。
    """
    template = Template(template_str)
    return template.render(context)
```

- [ ] **Step 3: 提交**

```bash
git add backend/utils/template.py backend/pyproject.toml
git commit -m "feat: 新增 Jinja2 模板渲染工具

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: PersonalityManager 核心模块

**Files:**
- Create: `backend/agent/personality_manager.py`
- Rewrite: `backend/agent/personality.py`

- [ ] **Step 1: 创建 personality_manager.py**

```python
"""人格统一管理器 — 加载、版本聚合、模板渲染、情绪标签提取."""

import re
from datetime import datetime
from typing import Any

from config import AppConfig
from db import personalities as personalities_db
from utils.template import render_prompt


class PersonalityManager:
    """人格统一管理器。main.py 通过此类进行所有人格操作。"""

    def __init__(self, config: AppConfig):
        self._config = config

    # ── CRUD 委托 ──

    def get(self, pid: int) -> dict | None:
        return personalities_db.get_personality(pid)

    def get_default(self) -> dict:
        return personalities_db.get_default_personality()

    def list_all(self) -> list[dict]:
        return personalities_db.list_personalities()

    def create(self, **fields) -> dict:
        return personalities_db.create_personality(
            name=fields.get("name", ""),
            description=fields.get("description", ""),
            system_prompt=fields.get("system_prompt", ""),
            parent_id=fields.get("parent_id"),
            version_tag=fields.get("version_tag"),
            metadata=fields.get("metadata"),
        )

    def update(self, pid: int, **fields) -> dict | None:
        return personalities_db.update_personality(
            pid,
            name=fields.get("name"),
            description=fields.get("description"),
            system_prompt=fields.get("system_prompt"),
            version_tag=fields.get("version_tag"),
            metadata=fields.get("metadata"),
        )

    def delete(self, pid: int) -> bool:
        return personalities_db.delete_personality(pid)

    # ── 版本聚合 ──

    def list_grouped(self) -> list[dict]:
        """返回聚合后的人格列表，供前端直接渲染选择器。"""
        all_pers = self.list_all()
        roots = [p for p in all_pers if p.get("parent_id") is None]
        children = [p for p in all_pers if p.get("parent_id") is not None]

        result: list[dict] = []
        for root in roots:
            versions = [c for c in children if c["parent_id"] == root["id"]]
            # 为每个版本添加 label 方便前端显示
            _TAG_LABEL = {"simple": "简洁", "full": "完整", "arc": "深度"}
            for v in versions:
                v["label"] = _TAG_LABEL.get(v.get("version_tag", ""), v.get("version_tag", ""))
            root["versions"] = versions
            root["is_single"] = len(versions) == 0
            result.append(root)
        return result

    # ── 模板渲染 ──

    def render_prompt(self, personality: dict, extra_context: dict | None = None) -> str:
        """渲染 system_prompt 中的 Jinja2 模板变量，并追加情绪标签指令。"""
        ctx = {
            "user_name": self._config.user.get("name", "") or "用户",
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "personality_name": personality.get("name", "AI 助理"),
            "version_tag": personality.get("version_tag") or "",
        }
        if extra_context:
            ctx.update(extra_context)

        rendered = render_prompt(personality.get("system_prompt", ""), ctx)

        # 追加情绪标签指令
        emotion_instruction = (
            "\n\n[系统指令] 在每次回复的最后一行，单独输出 [!emotion:标签!] 表示你当前的情绪语气。"
            "可用标签：happy, sad, angry, thinking, surprised, bored, idle。"
            "此标记不会显示给用户，请务必带上。"
        )
        return rendered + emotion_instruction

    # ── 情绪标签提取 ──

    def extract_emotion(self, response_text: str) -> tuple[str, str]:
        """从回复中提取并剥离 [!emotion:xxx!] 标签。

        Returns:
            (clean_text, emotion_label) — clean_text 不含标签
        """
        match = re.search(r'\[!emotion:\s*(\w+)\s*!\]', response_text)
        if match:
            emotion = match.group(1)
            clean = re.sub(r'\[!emotion:\s*\w+\s*!\]\s*', '', response_text)
            return clean, emotion
        return response_text, "idle"


# ── 单例 ──

_manager: PersonalityManager | None = None


def get_manager(config: AppConfig | None = None) -> PersonalityManager:
    global _manager
    if _manager is None:
        if config is None:
            from config import AppConfig
            config = AppConfig.get()
        _manager = PersonalityManager(config)
    return _manager


def ensure_seeded():
    """种子初始化（首次启动时从 YAML 导入）。"""
    personalities_db.seed_personalities()
```

- [ ] **Step 2: 重写 agent/personality.py 为薄包装**

```python
"""人格模块入口 — 向后兼容的薄包装层."""

from .personality_manager import get_manager, ensure_seeded, PersonalityManager

__all__ = ["get_manager", "ensure_seeded", "PersonalityManager"]
```

- [ ] **Step 3: 提交**

```bash
git add backend/agent/personality_manager.py backend/agent/personality.py
git commit -m "feat: 新增 PersonalityManager 统一管理人各功能

- 版本聚合 (list_grouped)
- Jinja2 模板渲染 (render_prompt)
- 情绪标签提取 (extract_emotion)
- CRUD 委托 db/personalities
- agent/personality.py 简化为单例工厂

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: main.py 集成 PersonalityManager + 情绪提取

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 修改 import + 初始化**

将 `main.py` 中的：
```python
from agent.personality import (
    list_personalities, get_personality, get_default_personality,
    create_personality, update_personality, delete_personality,
    ensure_seeded,
)
```

替换为：
```python
from agent.personality import get_manager, ensure_seeded
```

在 `ensure_seeded()` 之后、`app.state.mcp_manager` 之后增加：
```python
personality_manager = get_manager(config)
```

- [ ] **Step 2: 替换所有的 personality CRUD 调用**

| 旧调用 | 新调用 |
|--------|--------|
| `get_default_personality()` | `personality_manager.get_default()` |
| `list_personalities()` | `personality_manager.list_all()` |
| `get_personality(pid)` | `personality_manager.get(pid)` |
| `create_personality(...)` | `personality_manager.create(...)` |
| `update_personality(pid, ...)` | `personality_manager.update(pid, ...)` |
| `delete_personality(pid)` | `personality_manager.delete(pid)` |

- [ ] **Step 3: System Prompt 注入改为渲染后的版本**

找到 `main.py` 中的：
```python
personality_prompt = current_personality.get("system_prompt", "")
if personality_prompt:
    session.set_system_prompt(personality_prompt)
```

替换为：
```python
personality_prompt = personality_manager.render_prompt(current_personality)
if personality_prompt:
    session.set_system_prompt(personality_prompt)
```

- [ ] **Step 4: message_complete 增加 emotion 提取**

在 `full = "".join(collected_chunks)` 之后，`message_complete` 之前，增加：

```python
# 提取情绪标签
clean_content, emotion = personality_manager.extract_emotion(full)

# 后续全部使用 clean_content 替代 full
```

然后：
- `message_complete` 的 `full_content` 用 `clean_content`
- `message_complete` payload 增加 `"emotion": emotion`
- TTS `_synthesize_and_send(websocket, clean_content)` 使用 `clean_content`
- `conv_db.add_turn(assistant_content=clean_content, ...)` 使用 `clean_content`
- markdown_preview 的 `content` 用 `clean_content`

- [ ] **Step 5: get_config / update_config 支持 user.name**

在 `get_config` 处理中，sanitized config 增加 `user` 段：
```python
sanitized = {
    "model": {...},
    "voice": config.voice,
    "workspaces": config.workspaces,
    "user": config.user,  # ← 新增
}
```

`update_config` 处理中，`config.save(updates)` 已支持嵌套合并（检查 `config.py` 的 `save` 方法是否支持嵌套 key。如只支持顶层 key，则需要额外处理 `user` 段的合并）。

检查 `config.py` 的 `save` 方法：当前实现是顶层 key 的浅合并。需要改为支持 `user.name` 这样的嵌套更新：

```python
def save(self, updates: dict) -> None:
    config = self._read_config()
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            # 嵌套合并
            config.setdefault(key, {}).update(value)
        elif value is not None and value != "":
            config[key] = value
        elif key in config:
            del config[key]
    self._write_config(config)
    self.reload()
```

- [ ] **Step 6: personalities_list 响应增加 grouped**

在 `get_personalities` 处理中，将：
```python
await websocket.send_json({
    "type": "personalities_list",
    "payload": {
        "personalities": personality_manager.list_all(),
        "current": current_personality["id"],
    },
})
```

改为：
```python
await websocket.send_json({
    "type": "personalities_list",
    "payload": {
        "personalities": personality_manager.list_all(),
        "grouped": personality_manager.list_grouped(),
        "current": current_personality["id"],
    },
})
```

- [ ] **Step 7: 提交**

```bash
git add backend/main.py backend/config.py
git commit -m "feat: main.py 集成 PersonalityManager + emotion 提取

- 所有人格操作改为走 Manager
- System Prompt 经 Jinja2 渲染后注入
- message_complete 新增 emotion 字段
- 回复正文剥离情绪标签后再用于 TTS/DB 存储
- config 支持 user.name 嵌套更新
- personalities_list 增加 grouped 聚合数组

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 前端 — CSS 开关样式 + StatusBar

**Files:**
- Modify: `electron-app/src/renderer/App.css`
- Modify: `electron-app/src/renderer/components/StatusBar.jsx`

- [ ] **Step 1: App.css 增加 .toggle 样式**

在 `App.css` 末尾追加：

```css
/* ── 滑动开关 ── */
.toggle {
  appearance: none;
  -webkit-appearance: none;
  width: 44px;
  height: 24px;
  background: #444;
  border-radius: 12px;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
}
.toggle:checked {
  background: #7289da;
}
.toggle::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s;
}
.toggle:checked::after {
  transform: translateX(20px);
}
```

- [ ] **Step 2: StatusBar TTS 开关改用 .toggle**

在 `StatusBar.jsx` 中找到 TTS checkbox：
```jsx
<input type="checkbox" ... />
```
改为：
```jsx
<input type="checkbox" className="toggle" ... />
```

- [ ] **Step 3: 提交**

```bash
git add electron-app/src/renderer/App.css electron-app/src/renderer/components/StatusBar.jsx
git commit -m "feat: CSS滑动开关样式 + StatusBar统一

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 前端 — SettingsPanel 重写

**Files:**
- Rewrite: `electron-app/src/renderer/components/SettingsPanel.jsx`

这是最大的前端改动。将现有 radio 列表替换为下拉选择器 + 新增 2 个设置项。（完整代码见附件，此处列出关键改动点）

需要读取当前 [SettingsPanel.jsx](electron-app/src/renderer/components/SettingsPanel.jsx) 了解完整结构后重写。

核心改动：
1. 人格选择区：`<select>` + `<optgroup>` 实现分组下拉
2. 用户名称：文本输入框，onBlur 时 save
3. 情绪跟随：`.toggle` 开关
4. 紧凑模式：改用 `.toggle` 开关
5. 从 props 接收 `groupedPersonalities`（来自 App.jsx 的 `personalities_list` 中的 `grouped` 数组）

关键 JSX 片段：

```jsx
{/* 助理人格 — 下拉选择器 */}
<div className="setting-group">
  <label>助理人格</label>
  <select
    value={currentPersonalityId || ''}
    onChange={(e) => onSetPersonality(Number(e.target.value))}
  >
    {grouped.map((group) =>
      group.is_single ? (
        <option key={group.id} value={group.id}>
          {group.name}
        </option>
      ) : (
        <optgroup key={group.id} label={group.name}>
          {group.versions.map((v) => (
            <option key={v.id} value={v.id}>
              {group.name} · {v.label}
            </option>
          ))}
        </optgroup>
      )
    )}
  </select>
  <button onClick={...}>+ 新建人格</button>
</div>

{/* 用户信息 */}
<div className="setting-group">
  <label>用户名称</label>
  <input
    type="text"
    value={userName}
    onChange={(e) => setUserName(e.target.value)}
    onBlur={() => onUpdateConfig({ user: { name: userName } })}
    placeholder="输入你的名字或昵称..."
  />
</div>

{/* Avatar 情绪跟随 */}
<div className="setting-group">
  <label>Live2D 情绪跟随</label>
  <div className="toggle-row">
    <span>AI 根据对话内容生成情绪，驱动 Avatar 表情动画</span>
    <input
      type="checkbox"
      className="toggle"
      checked={emotionFollowEnabled}
      onChange={(e) => setEmotionFollowEnabled(e.target.checked)}
    />
  </div>
</div>
```

需要新增 props：`grouped`, `userName`, `emotionFollowEnabled`, `onSetEmotionFollow`。

- [ ] **Step 1: 提交**

```bash
git add electron-app/src/renderer/components/SettingsPanel.jsx
git commit -m "feat: SettingsPanel重写 — 下拉人格选择器 + 新设置项

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: 前端 — App.jsx 整合

**Files:**
- Modify: `electron-app/src/renderer/App.jsx`

- [ ] **Step 1: 新增状态变量**

在 App.jsx 的 useState 区域增加：

```jsx
const [groupedPersonalities, setGroupedPersonalities] = useState([]);
const [emotionFollowEnabled, setEmotionFollowEnabled] = useState(
  () => localStorage.getItem('emotionFollowEnabled') !== 'false'
);
const [userName, setUserName] = useState('');
```

- [ ] **Step 2: personalities_list 处理增加 grouped**

```jsx
case 'personalities_list':
  setPersonalities(payload.personalities || []);
  setGroupedPersonalities(payload.grouped || []);
  if (payload.current) setCurrentPersonalityId(payload.current);
  break;
```

- [ ] **Step 3: message_complete 处理增加 emotion**

```jsx
case 'message_complete':
  // ... 现有 finalize 逻辑 ...
  // 新增：处理情绪
  if (emotionFollowEnabled && payload.emotion && payload.emotion !== 'idle') {
    setAvatarState(payload.emotion);
    // 3 秒后回落 idle
    clearTimeout(emotionTimerRef.current);
    emotionTimerRef.current = setTimeout(() => {
      setAvatarState('idle');
    }, 3000);
  }
  break;
```

新增 ref：`const emotionTimerRef = useRef(null);`

- [ ] **Step 4: config 处理增加 user.name**

```jsx
case 'config':
  setConfig(payload);
  setUserName(payload?.user?.name || '');
  break;
```

- [ ] **Step 5: emotionFollowEnabled 持久化到 localStorage**

```jsx
useEffect(() => {
  localStorage.setItem('emotionFollowEnabled', String(emotionFollowEnabled));
}, [emotionFollowEnabled]);
```

- [ ] **Step 6: 传递新 props 到 SettingsPanel**

```jsx
<SettingsPanel
  // ... 现有 props ...
  grouped={groupedPersonalities}
  userName={userName}
  setUserName={setUserName}
  emotionFollowEnabled={emotionFollowEnabled}
  onSetEmotionFollow={setEmotionFollowEnabled}
/>
```

- [ ] **Step 7: 提交**

```bash
git add electron-app/src/renderer/App.jsx
git commit -m "feat: App.jsx 整合 emotion接收 + user.name + emotion开关

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Spine 动画探测 + 情绪映射

**Files:**
- Modify: `electron-app/src/avatar/AnimationController.ts`
- Modify: `electron-app/src/renderer/components/Avatar.jsx`

- [ ] **Step 1: AnimationController 扩展**

在 `AnimationController.ts` 中增加情绪映射：

```typescript
// 情绪 → 动画映射（运行时探测后填充）
const EMOTION_ANIM_MAP: Record<string, string> = {
  idle: 'idle',
  happy: 'action',      // 待探测后调整
  sad: 'sad',
  angry: 'idle',        // fallback，探测到 angry/rage 后替换
  thinking: 'idle',     // fallback
  surprised: 'idle',    // fallback
  bored: 'idle',        // fallback
};

// 在 SpineModel 加载后探测
export function probeAnimations(model: IAvatarModel): void {
  const anims = model.getAnimationList();
  console.log('[Spine] Available animations:', anims);
  
  // 按名称语义自动匹配
  for (const anim of anims) {
    const lower = anim.toLowerCase();
    if (lower.includes('angry') || lower.includes('rage')) EMOTION_ANIM_MAP['angry'] = anim;
    if (lower.includes('sad')) EMOTION_ANIM_MAP['sad'] = anim;
    if (lower.includes('happy') || lower.includes('smile')) EMOTION_ANIM_MAP['happy'] = anim;
    if (lower.includes('think') || lower.includes('shy')) EMOTION_ANIM_MAP['thinking'] = anim;
    if (lower.includes('surprise') || lower.includes('shock')) EMOTION_ANIM_MAP['surprised'] = anim;
    if (lower.includes('bored') || lower.includes('yawn')) EMOTION_ANIM_MAP['bored'] = anim;
  }
  console.log('[Spine] Emotion mapping:', EMOTION_ANIM_MAP);
}
```

修改 `setState` 方法，先查情绪映射再查状态映射：

```typescript
setState(stateName: string): void {
  if (stateName === this.currentState) return;
  // 优先查情绪映射，再查状态映射
  let anim = EMOTION_ANIM_MAP[stateName] || STATE_ANIM_MAP[stateName];
  if (!anim) return;
  this.animState.setAnimation(0, anim, true);
  this.currentState = stateName;
}
```

- [ ] **Step 2: Avatar.jsx 启动时探测动画**

在 `Avatar.jsx` 的 `initAvatar` 中，模型加载完成后调用：

```javascript
const mgr = new AvatarManager();
// ... 现有 init 代码 ...
// 探测动画
const { probeAnimations } = await import('../../avatar/AnimationController');
probeAnimations(mgr);
```

- [ ] **Step 3: 提交**

```bash
git add electron-app/src/avatar/AnimationController.ts electron-app/src/renderer/components/Avatar.jsx
git commit -m "feat: Spine动画探测 + 情绪映射

- AnimationController 新增 EMOTION_ANIM_MAP
- 运行时自动探测模型可用动画并匹配情绪标签
- 未匹配的情绪 fallback idle
- probeAnimations() 输出动画列表到 console 供调优

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: 端到端验证

- [ ] **Step 1: 启动后端，验证数据库迁移**

```bash
cd backend && python main.py
```

预期：
- 启动成功，无报错
- `personalities` 表含 3 个新列
- `GET /ws` 连接后收到 `personalities_list` 含 1 个默认助手 + `grouped` 数组

- [ ] **Step 2: 创建多版本角色**

通过 WebSocket 发 `create_personality` 创建阿尼斯 simple 和 full 版本：

```json
{"type": "create_personality", "payload": {"name": "阿尼斯", "system_prompt": "你是阿尼斯，简洁版。", "version_tag": "simple"}}
{"type": "create_personality", "payload": {"name": "阿尼斯", "system_prompt": "你是阿尼斯，完整版。", "parent_id": <simple_id>, "version_tag": "full"}}
```

预期：`personalities_list` 的 `grouped` 数组中阿尼斯为 `is_single: false`，含 2 个版本。

- [ ] **Step 3: 测试情绪标签**

发一条聊天消息，验证：
- `message_complete` 含 `emotion` 字段
- `full_content` 不含 `[!emotion:xxx!]` 标签
- 前端 Avatar 短暂切换到情绪动画后回落 idle

- [ ] **Step 4: 测试模板渲染**

创建一个 system_prompt 含 `{{ user_name }}` 的人格，设置 `user.name` 为 "小明"，验证渲染后的提示词中 "小明" 正确替换。

- [ ] **Step 5: 测试开关**

- 关闭"Live2D 情绪跟随"开关 → Avatar 不响应 emotion
- 重新打开 → Avatar 恢复响应
- 刷新页面 → 开关状态持久化（localStorage）

---

### Task 10: 情绪映射调优

根据运行时探测到的完整动画列表，调整 `EMOTION_ANIM_MAP`，使每个情绪标签尽可能映射到语义匹配的动画。

```bash
git add electron-app/src/avatar/AnimationController.ts
git commit -m "tune: 情绪动画映射调优（基于运行时探测结果）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 实现顺序建议

Task 1 → Task 2 → Task 3 → Task 4 → (验证后端) → Task 5 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10

后端任务（1-4）可连续完成，因为每个 Task 之后有 commit；前端任务（5-8）同样。
