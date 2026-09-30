# 🤝 AI-TALK 交接文档（HANDOFF）

本文档记录项目当前状态、架构、已完成/未完成工作与后续建议，便于接手。

## 1. 项目目标

让一个 Whisper(STT) + GPT(Chat) + TTS 的语音对话应用**尽可能模拟真人的感情与性格**，
并可**部署到 PC 端**。

## 2. 当前状态总览

| 模块 | 状态 | 位置 |
|------|------|------|
| 基础全栈应用（STT/Chat/TTS） | ✅ 完成 | `backend/`、`frontend/` |
| 人格系统（角色卡） | ✅ 完成 | `backend/persona.py`、`backend/personas/` |
| 情绪状态机 + 富情感 TTS | ✅ 完成 | `backend/emotion.py`、`backend/main.py` |
| 记忆系统（摘要 + 向量长期记忆） | ✅ 完成 | `backend/memory.py` |
| 流式对话(SSE) + 打断 + VAD | ✅ 完成 | `backend/main.py`、`frontend/app.js` |
| Tauri 桌面打包 | ✅ 脚手架完成（需本地构建） | `desktop/` |
| 数字人/头像口型 | ⛔ 未做 | — |
| 本地模型（离线）替换 | ⛔ 未做 | — |
| 自动化测试 | ⛔ 未做 | — |

## 3. 架构与数据流

```
麦克风录音 ──► /api/voice-chat ──► Whisper 转写
                                   │
用户文本 ──► DialogueEngine.respond ──► GPT（function-calling 输出 reply+emotion）
                │                          │
       ConversationMemory            EmotionState（情绪状态机）
       ├ 短期滑动窗口 + 摘要压缩          │
       └ 长期向量记忆(Embeddings)         ▼
                                    富情感 TTS（emotion → 语气 instructions）
                                          │
                                          ▼
                                   前端播放 + 情绪头像
```

- **人格**：`persona.py` 读取 `personas/*.json` 角色卡，渲染稳定 system prompt + few-shot 示例。
- **情绪**：`emotion.py` 维护 `label + intensity`，平滑演变；驱动 TTS `instructions` 与前端 emoji。
- **记忆**：`memory.py` 短期历史超过 `MAX_HISTORY_TURNS` 触发摘要，抽取 KEYFACTS 存入本地向量库
  （`data/memory_<session>.json`），检索用余弦相似度。无 API Key 时自动降级。
- **流式**：`/api/chat-stream` 走 SSE；前端逐字渲染，失败回退 `/api/chat`。

## 4. 关键接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/voice-chat` | POST | 音频→文字→AI→语音；情绪写入响应头 `X-Emotion`/`X-Intensity` |
| `/api/chat` | POST | 文字对话（非流式，返回 reply+emotion+intensity） |
| `/api/chat-stream` | POST | 文字对话（SSE 流式） |
| `/api/transcribe` | POST | 仅转写 |
| `/api/speak` | POST | 仅合成（按当前情绪调语气） |
| `/api/persona` | GET | 当前角色信息 |
| `/health` | GET | 健康检查 |

## 5. 本地运行

```bash
# 后端
cd backend
pip install -r requirements.txt
cp .env.example .env      # 填 OPENAI_API_KEY
uvicorn main:app --reload

# 前端
cd frontend && python -m http.server 3000

# 或 Docker 一键
docker-compose up --build
```

桌面端见 `desktop/README.md`。

## 6. 已知限制 / 待办（未完成工作）

1. **桌面端后端捆绑**：`desktop/` 仅脚手架，尚未把后端做成 sidecar 自动启动；
   当前需手动跑 `uvicorn`。方案已写在 `desktop/README.md`（PyInstaller + externalBin）。
   构建需在本地装 Rust/Node，CI 环境未执行 `tauri build`。
2. **图标缺失**：`desktop/src-tauri/icons/` 为空，打包前需 `npx @tauri-apps/cli icon logo.png` 生成。
3. **本地/离线模型**：仍依赖 OpenAI 云 API。若要隐私优先，可替换为
   faster-whisper + Ollama + 本地 TTS（GPT-SoVITS/Piper），并在 `config.py` 抽象 provider。
4. **情绪与流式的取舍**：流式模式(`/api/chat-stream`)为降低延迟未用 function-calling，
   情绪走关键词兜底推断，精度低于非流式。可改为“先流式出文本、末尾再单独分类情绪”。
5. **记忆存储**：长期记忆是 JSON 文件 + 线性扫描，数据量大时应换 Chroma/FAISS/Qdrant。
6. **并发/持久化**：会话状态 `_SESSIONS`/`_emotions` 在内存，多进程/重启会丢失；
   生产需外置（如 Redis）。情绪状态目前未持久化。
7. **鉴权与限流**：`/api/*` 无鉴权、CORS 全放开，仅适合本地/内网。
8. **测试**：无自动化测试。建议对 `persona/emotion/memory` 加单元测试，对接口加集成测试。
9. **数字人**：可选 Live2D/VRM 口型与表情同步，进一步增强真人感。

## 7. 后续建议优先级

1. 补自动化测试（保障重构安全）。
2. 桌面端后端 sidecar 化 + 图标，产出可安装包并配 CI 多平台构建。
3. provider 抽象层，支持云/本地一键切换。
4. 记忆升级为向量数据库；会话状态外置持久化。
5. 数字人头像（锦上添花）。

## 8. 安全备注

- `python-multipart` 固定 `0.0.30`（修复 DoS/任意写）。
- 前端会话 ID 使用 `crypto` 安全随机（非 `Math.random`）。
- `tauri-plugin-shell` 需 ≥ `2.2.1`（修复 open 端点范围校验漏洞）。
- `.env` 与 `backend/data/` 已在 `.gitignore`，勿提交密钥与记忆数据。
