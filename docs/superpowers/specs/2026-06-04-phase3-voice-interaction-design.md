# 阶段 3：语音交互 — 设计文档

**日期**：2026-06-04
**来源**：《AI 桌面拟人助理 - 项目需求规格说明书》第 9 章 阶段 3
**状态**：设计中 → 已确认

---

## 1. 目标

实现语音输入（STT）和语音输出（TTS），支持两种交互模式。

### 语音链路

```
[录音] → [STT 识别] → [显示+发送] → [AI 回复] → [TTS 合成] → [播放+显示]
```

---

## 2. 技术选型

| 组件 | 方案 | 理由 |
|------|------|------|
| 语音识别 | faster-whisper (本地) | 用户有 4060 GPU，本地免费 |
| 语音合成 | edge-tts | 微软免费，中文 Xiaoxiao 语音自然 |
| 录音 | MediaRecorder API (Electron 渲染进程) | 浏览器原生，无需额外依赖 |
| VAD | RMS 能量检测 (Python) | 轻量，无需额外模型 |
| 音频格式 | WAV 16kHz mono | faster-whisper 标准输入 |

---

## 3. 交互模式

### 模式 1：点击切换（默认）

1. 用户点击 🎤 → 开始录音（按钮变红闪烁）
2. 说完点击 🎤 → 停止 → 后端识别 → 文字自动填入 → 显示为用户气泡 → 自动发送
3. 或 3 秒静音自动停止

### 模式 2：常开模式

1. 状态栏开关切换到 ●（开启）
2. 麦克风持续监听，RMS 能量检测判断是否在说话
3. 说话时持续录音 → 静音 2 秒后自动断开 → 识别 → 显示 → 发送
4. 开关切换到 ○（关闭）→ 回到模式 1

### 语音文本双显

- 用户语音识别结果 → 正常显示为用户消息气泡
- AI 回复 → 流式文字正常显示 + TTS 音频同时播放
- 无需额外 UI 改动

---

## 4. 新增/修改文件

```
backend/
├── main.py                       # [修改] voice_input 处理 + VAD 常开模式
├── voice/
│   ├── __init__.py               # [新增]
│   ├── stt.py                    # [新增] faster-whisper 语音识别
│   └── tts.py                    # [新增] edge-tts 语音合成
├── requirements.txt              # [修改] 加 faster-whisper, edge-tts
└── temp/                         # [新增] 临时音频文件目录 (.gitignore)

electron-app/src/renderer/
├── App.jsx                       # [修改] voice 状态, alwaysOn 开关
├── App.css                       # [修改] 录音按钮、开关、动画样式
├── components/
│   ├── ChatPanel.jsx             # [修改] 录音按钮、录音状态、音频播放
│   └── StatusBar.jsx             # [修改] 常开模式开关
│   └── AvatarStatus.jsx          # [新增] emoji 头像状态指示
```

---

## 5. WebSocket 新增消息

| 方向 | type | payload | 说明 |
|------|------|---------|------|
| 前端→后端 | `voice_input` | `{"audio_data": "base64..."}` | 发送录音数据 |
| 前端→后端 | `voice_mode` | `{"always_on": true/false}` | 切换常开模式 |
| 后端→前端 | `voice_result` | `{"text": "识别文字"}` | STT 识别结果 |
| 后端→前端 | `play_audio` | `{"file_path": "/tmp/tts_xxx.mp3"}` | TTS 音频路径 |
| 后端→前端 | `avatar_state` | `{"action": "idle/listening/thinking/speaking"}` | 头像状态 |
| 后端→前端 | `voice_status` | `{"always_on": false, "recording": false}` | 常开模式状态同步 |

---

## 6. 后端模块设计

### voice/stt.py

```python
class STTEngine:
    def __init__(self, model_size="base"):
        # 加载 faster-whisper 模型（base 约 140MB，适合 4060）
        # 支持 CUDA 加速

    def transcribe(self, audio_path: str) -> str:
        # 读取 WAV → faster-whisper 识别 → 返回文本
```

### voice/tts.py

```python
async def synthesize(text: str, output_path: str) -> str:
    # edge-tts --voice zh-CN-XiaoxiaoNeural --text "..." --write-media output.mp3
    # 返回输出文件路径
```

### VAD（main.py 内嵌）

```python
def vad_detect(audio_bytes: bytes, threshold_rms: float = 0.02) -> bool:
    # 计算 RMS 能量 → 比较阈值 → 返回是否在说话
```

---

## 7. 前端组件修改

### ChatPanel — 录音按钮

- 输入框左侧新增 🎤 按钮
- 点击开/关录音（模式 1）
- 录音中：红色脉冲动画 + "录制中..."
- 通过 MediaRecorder 采集音频，以 base64 通过 WebSocket 发送

### StatusBar — 常开模式开关

- 状态栏右侧新增开关：`[🎤 常开: ○ / ●]`
- 点击切换，发送 `voice_mode` 消息

### AvatarStatus

- 根据 `avatar_state` 显示不同 emoji：
  - idle: 😊
  - listening: 👂
  - thinking: 🤔
  - speaking: 🗣️

### 音频播放

- ChatPanel 收到 `play_audio` 消息 → 创建 Audio 对象播放
- 后端返回路径为 `/tmp/tts_xxx.mp3`，需要在 preload.js 中暴露文件路径或通过本地 HTTP 提供

---

## 8. 不在阶段 3 范围

- 唤醒词
- Live2D 模型（阶段 5）
- 声音克隆
- 声纹识别多用户

---

## 9. 验收标准

1. 点击 🎤 按钮 → 开始录音 → 按钮变红 → 点击停止 → 识别文字显示为消息发送
2. 开启常开模式 → 说话 → 自动识别 → 文字显示 → AI 回复
3. AI 回复后 → TTS 朗读回复内容 → 恢复语音图标表示 TTS 已生成
4. 头像状态在待机/倾听/思考/说话之间正确切换
5. 所有用户语音的识别文字和 AI 回复的朗读文字均在聊天界面显示
