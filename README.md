# AI 桌面助理 (Desktop AI Companion)

本地 AI 桌面拟人助理，支持文字/语音对话、笔记管理、材料整理、Live2D 拟人形象。

## 前置条件

- Python 3.10+
- Node.js 18+
- DeepSeek API Key（或其他 OpenAI 兼容 API）
- Live2D Cubism SDK Core（从 https://www.live2d.com/download/cubism-sdk/ 下载，放到 electron-app/assets/live2d/）

## 快速开始

### 1. 配置 API Key

```
cp backend/config.yaml.example backend/config.yaml
编辑 backend/config.yaml，填入 api_key
```

### 2. 安装依赖

```
cd backend
pip install -r requirements.txt

cd electron-app
npm install
```

### 3. 启动

终端 1 (后端):
```
cd backend
python main.py
```

终端 2 (前端):
```
cd electron-app
npm start
```

## 功能

- 流式多轮聊天 (DeepSeek / OpenAI 兼容 API)
- 语音输入 (本地 faster-whisper) + 语音朗读 (edge-tts)
- 笔记系统 (SQLite + FTS5 全文搜索，标签管理，Markdown 导出)
- 材料整理 (/整理 命令，AI 归纳笔记生成文档)
- Live2D 拟人形象 (Cubism 5)
- 设置面板 + 系统托盘

## 项目结构

```
├── backend/              # Python FastAPI 后端
│   ├── main.py           # WebSocket 服务入口
│   ├── agent/            # 聊天引擎 + 技能系统
│   ├── db/               # SQLite 笔记数据库
│   ├── voice/            # STT/TTS 语音模块
│   └── skills/           # 技能定义 (.md)
├── electron-app/         # Electron + React 前端
│   ├── src/
│   │   ├── main.js       # Electron 主进程
│   │   ├── renderer/     # React 组件
│   │   └── live2d/       # Live2D Cubism 集成
│   └── assets/live2d/    # 模型 + Cubism Core
└── docs/                 # 设计文档
```

## 技术栈

| 层 | 技术 |
|---|------|
| 桌面 | Electron + React + Vite |
| 后端 | Python FastAPI + WebSocket |
| AI | DeepSeek API |
| 语音识别 | faster-whisper |
| 语音合成 | edge-tts |
| 数据库 | SQLite + FTS5 |
| Live2D | Cubism SDK for Web 5 |
