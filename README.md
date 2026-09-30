# 🎙️ AI-TALK — 更像真人的 AI 语音对话

基于 **OpenAI Whisper（语音识别）+ GPT（对话）+ TTS（语音合成）** 的全栈语音对话应用，
并在此之上加入 **人格系统、情绪状态机、记忆系统**，让 AI 尽可能模拟出真人的感情与性格。

## ✨ 功能

- 🎤 **录音** — 浏览器直接录制麦克风（按住说话）
- 📝 **语音 → 文字** — Whisper 模型转录
- 🤖 **AI 对话** — GPT 模型生成回复（多轮上下文）
- 🔊 **文字 → 语音** — 富情感 TTS 合成播放

### 🧬 拟人化增强

- **人格系统**：用结构化「角色卡」（背景故事、大五人格、说话风格、口头禅、价值观、禁忌、few-shot 示例）固化人设，减少人格漂移。
- **情绪状态机**：随对话平滑演变的情绪（开心/难过/兴奋/温柔…），模型每轮输出情绪标签，驱动 **TTS 语气** 与前端 **表情头像**。
- **记忆系统**：
  - 短期：滑动窗口历史 + 超长自动「摘要压缩」。
  - 长期：本地向量记忆（OpenAI Embeddings + 余弦相似度），跨会话「记得你」。无 Key 时自动降级，不影响主流程。

## 📁 项目结构

```
AI-TALK/
├── backend/
│   ├── main.py            # FastAPI 后端（STT / Chat / TTS 接口）
│   ├── engine.py          # 对话引擎（整合人格/情绪/记忆）
│   ├── persona.py         # 人格系统（角色卡 → system prompt）
│   ├── emotion.py         # 情绪状态机
│   ├── memory.py          # 记忆系统（摘要 + 向量长期记忆）
│   ├── config.py          # 配置与环境变量
│   ├── personas/          # 角色卡（companion.json）
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── index.html         # 对话界面（情绪头像）
│   ├── style.css
│   ├── app.js             # 录音 & API 调用逻辑
│   └── Dockerfile
└── docker-compose.yml
```

## 🚀 快速开始

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
cd frontend
python -m http.server 3000
```

## 🎭 自定义角色

编辑 `backend/personas/companion.json`，或新建一份角色卡后在 `.env` 中设置 `PERSONA_FILE`。
可配置：姓名、背景故事、大五人格（0~1）、性格、说话风格、口头禅、价值观、禁忌、示例对话。

## ⚙️ 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥（必填） | — |
| `OPENAI_BASE_URL` | 自建/代理网关（可选） | 官方 |
| `OPENAI_MODEL` | 对话模型 | `gpt-4o-mini` |
| `STT_MODEL` | 语音识别模型 | `whisper-1` |
| `TTS_MODEL` | 语音合成模型（`gpt-4o-*-tts` 支持情感指令） | `gpt-4o-mini-tts` |
| `EMBEDDING_MODEL` | 向量记忆模型 | `text-embedding-3-small` |
| `TTS_VOICE` | TTS 声音（alloy/echo/fable/onyx/nova/shimmer） | `nova` |
| `PERSONA_FILE` | 角色卡文件名 | `companion.json` |
| `MEMORY_ENABLED` | 是否启用长期记忆 | `true` |
| `MAX_HISTORY_TURNS` | 历史保留轮数（超过触发摘要） | `12` |
| `MEMORY_TOP_K` | 长期记忆检索条数 | `4` |

## 🔌 API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/voice-chat` | POST | 完整语音对话（音频→文字→AI→语音，情绪写入响应头） |
| `/api/transcribe` | POST | 仅语音转文字 |
| `/api/chat` | POST | 仅文字对话（返回回复 + 情绪 + 强度） |
| `/api/speak` | POST | 仅文字转语音（按当前情绪调节语气） |
| `/api/persona` | GET | 当前角色信息 |
| `/health` | GET | 健康检查 |

## 🖥️ 部署到 PC 端

- **桌面壳**：可用 Tauri / Electron 把 `frontend/` 打包为 Windows/macOS/Linux 桌面 App，后端以 sidecar 子进程随行启动。
- **本地一体化（隐私优先）**：把云 API 替换为本地模型（faster-whisper + Ollama + 本地 TTS），后端用 PyInstaller 打包为单可执行文件。
