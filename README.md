# AI-TALK

云端 AI 语音对话助手，基于 OpenAI 兼容 API（OhMyGPT）实现文字对话与实时语音播放。

## 功能特性

- 🤖 接入云端大语言模型（`gpt-4o-mini`），响应速度快、成本低
- 🔊 TTS 语音合成，AI 回复自动转为语音播放
- 💾 对话历史记忆（可配置轮次上限），保持上下文连贯
- 🖥️ 轻量优化，对本地硬件配置无特殊要求

## 环境要求

- Python 3.8+
- 可用的 OhMyGPT（或兼容 OpenAI 接口的服务）API Key

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

**推荐方式：使用环境变量（避免将密钥提交到代码库）**

```bash
export OHMYGPT_API_KEY="你的_API_KEY"
# 可选，默认已指向 OhMyGPT
export OHMYGPT_BASE_URL="https://api.ohmygpt.com/v1"
```

**备用方式：直接编辑 `ai_talk.py`**

打开 `ai_talk.py`，将第 9 行的占位符替换为你的真实 API Key：

```python
API_KEY = os.environ.get("OHMYGPT_API_KEY", "你的_OHMYGPT_API_KEY")
```

## 运行

```bash
python ai_talk.py
```

## 使用说明

启动后直接输入文字与 AI 对话，AI 会同时在终端显示文字回复并通过扬声器播放语音。  
输入 `q` 或 `exit` 退出程序，按 `Ctrl+C` 也可强制终止。

## 可调参数

在 `ai_talk.py` 顶部的"配置中心"区域可自定义以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `CHAT_MODEL` | `gpt-4o-mini` | 对话模型 |
| `TTS_MODEL` | `tts-1` | 语音合成模型 |
| `VOICE_NAME` | `nova` | 音色（nova / alloy / onyx 等） |
| `MAX_HISTORY` | `10` | 保留的最大对话轮次 |
