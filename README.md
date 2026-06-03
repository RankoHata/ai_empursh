# AI 桌面助理 (Desktop AI Companion)

阶段 1：项目骨架与基础聊天功能。

## 前置条件

- Python 3.10+ (with pip)
- Node.js 18+ (with npm)
- DeepSeek API Key (or any OpenAI-compatible API)

## 快速开始

### 1. 配置 API Key

```bash
cp backend/config.yaml.example backend/config.yaml
# 编辑 backend/config.yaml，填入你的 api_key
```

### 2. 安装 Python 依赖

```bash
cd backend
pip install --proxy http://127.0.0.1:7890 -r requirements.txt
```

### 3. 安装前端依赖

```bash
cd electron-app
npm config set proxy http://127.0.0.1:7890
npm config set https-proxy http://127.0.0.1:7890
npm config set strict-ssl false
npm install
```

### 4. 启动后端

```bash
# Windows (需要代理时)
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
cd backend
python main.py
```

### 5. 启动前端（另一个终端）

```bash
cd electron-app
npm start
```

### 6. 开始聊天

在 Electron 窗口中输入消息，按 Enter 发送。
