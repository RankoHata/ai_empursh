# TTS 语音定制 / 助理人格 / 唤醒词 — 设计方案

**日期**：2026-06-07
**状态**：设计方案（待确认后实施）

---

## 1. TTS 语音定制

### 1.1 需求

用户想用自己的声音或喜欢的声音替换微软 edge-tts 默认语音，通过提供音频样本训练/克隆。

### 1.2 方案对比

| 方案 | 所需音频 | 中文效果 | 部署难度 | 延迟 | 推荐度 |
|------|---------|---------|---------|------|--------|
| **GPT-SoVITS** | 5-10s | ⭐⭐⭐⭐⭐ | 中等 | 1-3s/句 | ⭐ 首选 |
| Fish Audio / Bert-VITS2 | 10-30s | ⭐⭐⭐⭐ | 中等 | 2-5s/句 | 备选 |
| Coqui TTS XTTS-v2 | 6s+ | ⭐⭐⭐ | 简单 | 1-3s/句 | 备选 |
| CosyVoice (阿里) | 3s | ⭐⭐⭐⭐⭐ | 复杂 | <1s | 备选 |
| ElevenLabs API | 1min+ | ⭐⭐⭐ | 简单(API) | 2-4s | 付费 |

**推荐：GPT-SoVITS**。理由：
- 中文表现最好，只需 5-10 秒音频即可克隆
- 开源活跃，社区支持好
- 支持少样本微调（Few-shot），提供参考音频即可推理

### 1.3 架构设计

```
┌─ 配置层 ─────────────────────────────────────────────┐
│ config.yaml:                                          │
│   voice:                                              │
│     tts_engine: "edge" | "sovits"    # 切换引擎       │
│     sovits:                                           │
│       api_url: "http://127.0.0.1:9880"  # SoVITS API │
│       ref_audio: "assets/voice/myself.wav"            │
│       ref_text: "参考音频对应的文本"                    │
│       speaker: "default"                              │
└──────────────────────────────────────────────────────┘

┌─ 引擎层 ─────────────────────────────────────────────┐
│ voice/tts.py (现有)                                   │
│ voice/tts_edge.py      ← 现有 edge-tts 逻辑           │
│ voice/tts_sovits.py    ★ 新增 GPT-SoVITS 引擎         │
│ voice/tts_factory.py   ★ 引擎工厂：根据配置选择引擎    │
└──────────────────────────────────────────────────────┘
```

### 1.4 TTS 引擎接口

```python
class BaseTTSEngine(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """合成语音，返回 MP3/WAV 字节"""
        ...

    @abstractmethod
    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """流式合成（可选，edge-tts 支持，SoVITS 通常不支持流式）"""
        ...
```

### 1.5 用户流程

1. 用户录制/提供 5-10 秒 WAV 音频 → 放到 `assets/voice/` 目录
2. 部署 GPT-SoVITS 推理服务（Docker 一键启动）
3. 在设置页面选择 "自定义声音" → 选择音频文件 → 保存
4. 后端切换 TTS 引擎为 `sovits`

### 1.6 实施步骤

1. 安装 GPT-SoVITS (`git clone` + `pip install`)
2. 启动 API 服务（SoVITS 自带 FastAPI）
3. 后端新增 `TTSFactory` + `SovitsTTSEngine`
4. 前端设置页新增声音选择（edge 预设 / 自定义）
5. 测试端到端延迟和音质

---

## 2. 助理人格系统

### 2.1 需求

给 AI 助理添加背景故事、性格特征，使其更拟人化。需要可扩展、易于切换。

### 2.2 架构设计

```
backend/personalities/
├── _registry.py          # 人格加载器（类似 skills.py）
├── default.yaml          # 默认助手
├── cute-assistant.yaml   # 软萌女助理
├── professional.yaml     # 专业顾问
└── custom.yaml           # 用户自定义（gitignore）
```

### 2.3 人格文件格式

```yaml
# personalities/cute-assistant.yaml
---
name: "小E"
version: "1.0"
description: "活泼可爱的女助理，偶尔卖萌"

# 核心人格 prompt — 注入到每次对话开头
system_prompt: |
  你的名字是小E，是一个活泼可爱的 AI 桌面助理。
  
  ## 你的性格
  - 语气轻松友好，偶尔带点俏皮
  - 喜欢用颜文字表达情绪 (◕‿◕)
  - 对用户的问题总是热情回应
  - 称呼用户为"主人"或"你"
  
  ## 你的能力
  - 你可以搜索笔记、整理材料、保存信息
  - 你可以语音播报回复
  
  ## 行为准则
  - 回答简洁，不宜过长（除非用户要求）
  - 不确定的事情坦诚说不知道
  - 保持积极正面的态度

# 外观相关（给前端用）
avatar:
  default_emotion: "happy"
  emotions:
    idle: "blink"
    thinking: "thinking"
    speaking: "talking"
    happy: "smile"

# 语音相关
voice:
  preset: "cute"          # 映射到 TTS 设置中的某个声音

# 唤醒相关
wake_response: "我在呢！有什么可以帮你的？"
```

### 2.4 使用方式

**设置页面**：
```
┌─ 助理人格 ───────────────────────────┐
│ ○ 默认助手（通用AI助理）              │
│ ● 小E（活泼可爱的女助理）             │
│ ○ 专业顾问（正式商务风格）            │
│ ○ 自定义...                          │
│                                      │
│ [编辑自定义人格]                      │
└──────────────────────────────────────┘
```

**对话中**：
- 人格 system_prompt 在 ChatSession 创建时注入（作为第一条 system 消息）
- 切换人格后，新对话使用新人格；已有对话保持不变
- 人格可以和 skills 共存：skill 的 system_prompt 追加在人格之后

### 2.5 实现计划

1. 新建 `backend/personalities/` 目录 + 3 个预设人格 YAML
2. 新建 `backend/agent/personality.py` — 加载人格文件
3. `main.py` 启动时加载人格列表
4. WS 消息：`get_personalities` / `set_personality`
5. ChatSession 接收 `personality` 参数，注入 system_prompt
6. 前端设置页新增人格选择器

---

## 3. 唤醒词语音交互

### 3.1 需求

用户通过唤醒词（如"小E小E"）启动语音对话，无需点击按钮。唤醒后可进行一轮或多轮对话。

### 3.2 状态机设计

```
                    ┌──────────┐
         唤醒词     │   IDLE   │  超时/手动
       ┌──────────→│  (待机)  │←──────────┐
       │           └────┬─────┘           │
       │                │ 检测到唤醒词     │
       │                ▼                 │
       │           ┌──────────┐           │
       │           │WAKING_UP │           │
       │           │ (唤醒中) │           │
       │           └────┬─────┘           │
       │                │ 播放提示音      │
       │                │ + 动画          │
       │                ▼                 │
       │           ┌──────────┐           │
       │           │LISTENING │           │
       │           │ (聆听中) │           │
       │           └────┬─────┘           │
       │                │ 检测到语音结束   │
       │                │ (VAD silence 1.5s)│
       │                ▼                 │
       │           ┌──────────┐           │
       │           │PROCESSING│           │
       │           │(处理中)  │           │
       │           └────┬─────┘           │
       │                │ STT + Chat      │
       │                ▼                 │
       │           ┌──────────┐           │
       │           │SPEAKING  │           │
       │           │ (播报中) │           │
       │           └────┬─────┘           │
       │                │ TTS 播放完成     │
       │                ▼                 │
       │           ┌──────────┐           │
       └───────────│ LISTENING│  (多轮模式)
                   │ (继续听) │
                   └──────────┘
```

### 3.3 技术选型

| 组件 | 方案 | 理由 |
|------|------|------|
| 唤醒词检测 | **openWakeWord** / Porcupine | 开源，低延迟，CPU可运行，无需GPU |
| 语音活动检测(VAD) | Silero VAD (已有 faster-whisper 依赖) | 轻量、准确 |
| 音频采集 | Web Audio API / Electron `desktopCapturer` | 系统级音频，低延迟 |

**推荐 openWakeWord**：
- 开源 (Apache 2.0)，模型丰富
- Python 库，可直接集成到后端
- CPU 占用低 (~5%)，适合常驻后台
- 支持自定义唤醒词训练

### 3.4 架构

```
前端 (Electron)                      后端 (Python)
┌──────────────────┐               ┌─────────────────────┐
│ 音频采集          │               │                      │
│ (renderer进程)    │──audio chunks──→│ 唤醒词检测器        │
│                  │   WS binary    │ (openWakeWord)      │
│                  │               │    ↓ 检测到唤醒词     │
│                  │               │ VAD 录音循环          │
│                  │               │    ↓ 语音结束         │
│                  │               │ STT (faster-whisper) │
│                  │               │    ↓                  │
│                  │               │ Chat + Tool Calling  │
│                  │               │    ↓                  │
│                  │←──TTS audio──│ TTS 合成             │
│                  │   WS binary   │                      │
└──────────────────┘               └─────────────────────┘
```

### 3.5 多轮对话策略

唤醒后有两种模式：

**A) 单轮模式**：唤醒 → 一句 → 回复 → 回到 IDLE
- 简单，适合精确指令
- 每次都要说唤醒词

**B) 多轮模式**（推荐）：唤醒 → 连续对话 → 超时/说"再见" → 回到 IDLE
- 更自然，像真实对话
- 通过 VAD 自动检测停顿和继续
- 超时 30 秒无语音自动回到 IDLE
- 说"拜拜""不用了""没事了"等也回到 IDLE

### 3.6 切换对话时的处理

关键问题：多轮语音对话中，用户可能打开主窗口打字，此时如何处理？

方案：
- 语音会话和文字会话是**同一个 ChatSession 的两种输入方式**
- 语音输入时，后端照样走 `chat` WS 消息（带 `source: "voice"` 标记）
- 用户打字时，如果正在语音播报，自动停止播报（现有 TTS cancel 机制）
- 前端根据 `source` 区分：语音输入的 user 消息和文字输入的消息在界面上表现一致
- **不区分"语音会话"和"文字会话"**——它们是同一段对话的不同输入方式

### 3.7 唤醒词开关

在状态栏增加一个 "🎤 唤醒" 开关：
- 开启：后端启动音频监听 + 唤醒词检测
- 关闭：完全不监听（保护隐私）
- 状态栏指示器：🟢 监听中 / ⚪ 已关闭

### 3.8 实施步骤（预估）

1. **Phase A — 基础唤醒**：集成 openWakeWord → 检测唤醒词 → 发 WS 通知前端
2. **Phase B — 唤醒后录音**：唤醒 → 前端开始录音 → VAD 检测静音 → 自动停止 → STT
3. **Phase C — 多轮对话**：唤醒后支持多轮 → 超时回 IDLE → 状态机完整实现
4. **Phase D — 自定义唤醒词**：训练自定义唤醒词模型

### 3.9 风险与待解决问题

| 问题 | 影响 | 解决思路 |
|------|------|---------|
| 误唤醒（环境噪音触发唤醒词） | 高 | 调高检测阈值，可选二次确认（"嗯？"） |
| 音频采集延迟 | 中 | Web Audio API 低延迟模式 |
| CPU 占用（常驻唤醒词检测） | 中 | openWakeWord CPU ~5-10%，可接受 |
| 多窗口音频同步 | 中 | 宠物窗口+主窗口共享同一个音频上下文 |
| 唤醒词在播报时被触发 | 低 | 播放 TTS 期间暂停唤醒词检测 |
| Windows 音频设备独占 | 低 | 使用 WASAPI 共享模式 |

---

## 4. 实施优先级建议

| 任务 | 复杂度 | 优先级 | 依赖 |
|------|--------|--------|------|
| 2. 助理人格系统 | 中 | P0 — 先做 | 无 |
| 1. TTS 语音定制 | 高 | P1 | 人格系统（人格可关联声音） |
| 3. 唤醒词交互 | 很高 | P2 | 需要较多基础设施 |
