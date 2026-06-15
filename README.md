# 🎙️ AI-TALK — AI 语音对话

基于 **OpenAI Whisper（语音识别）+ GPT（对话）+ TTS（语音合成）** 的全栈语音对话应用。

## 功能

- 🎤 **录音** — 浏览器直接录制麦克风
- 📝 **语音 → 文字** — Whisper 模型转录
- 🤖 **AI 对话** — GPT 模型生成回复（保持多轮上下文）
- 🔊 **文字 → 语音** — OpenAI TTS 合成语音播放

## 项目结构

```
AI-TALK/
├── backend/
│   ├── main.py          # FastAPI 后端（STT / Chat / TTS 接口）
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example     # 环境变量模板
├── frontend/
│   ├── index.html       # 对话界面
│   ├── style.css
│   └── app.js           # 录音 & API 调用逻辑
└── docker-compose.yml
```

## 快速开始

### 1. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入你的 OPENAI_API_KEY
```

### 2. Docker 一键启动（推荐）

```bash
docker-compose up --build
```

- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs

### 3. 本地开发启动

**后端：**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 填写 OPENAI_API_KEY
uvicorn main:app --reload
```

**前端：**
```bash
# 任意静态文件服务，例如：
cd frontend
python -m http.server 3000
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥（必填） | — |
| `OPENAI_MODEL` | 对话模型 | `gpt-4o-mini` |
| `TTS_VOICE` | TTS 声音（alloy/echo/fable/onyx/nova/shimmer） | `alloy` |
| `SYSTEM_PROMPT` | AI 角色设定 | 友好语音助手 |

## API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/voice-chat` | POST | 完整语音对话（音频→文字→AI→语音） |
| `/api/transcribe` | POST | 仅语音转文字 |
| `/api/chat` | POST | 仅文字对话 |
| `/api/speak` | POST | 仅文字转语音 |
| `/health` | GET | 健康检查 |
