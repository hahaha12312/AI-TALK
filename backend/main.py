"""FastAPI 后端：STT（Whisper）+ 带人格/情绪/记忆的对话 + 富情感 TTS。"""
import io
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

import config
from emotion import EmotionState
from engine import DialogueEngine
from memory import get_session
from persona import Persona

app = FastAPI(title="AI-TALK", description="更像真人的 AI 语音对话", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局单例 ────────────────────────────────────────────────────────────
_client: Optional[OpenAI] = None
_persona = Persona.load()
_engine: Optional[DialogueEngine] = None
# 每个会话保留一份情绪状态
_emotions: dict[str, EmotionState] = {}


def get_client() -> OpenAI:
    global _client, _engine
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise HTTPException(500, "未配置 OPENAI_API_KEY")
        _client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)
        _engine = DialogueEngine(_client, _persona)
    return _client


def get_emotion(session_id: str) -> EmotionState:
    if session_id not in _emotions:
        _emotions[session_id] = EmotionState()
    return _emotions[session_id]


# ── 数据模型 ────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    text: str
    session_id: str = "default"


class SpeakRequest(BaseModel):
    text: str
    session_id: str = "default"
    style: Optional[str] = None


# ── 核心能力 ────────────────────────────────────────────────────────────
def _transcribe(audio_bytes: bytes, filename: str) -> str:
    client = get_client()
    buf = io.BytesIO(audio_bytes)
    buf.name = filename or "audio.webm"
    resp = client.audio.transcriptions.create(model=config.STT_MODEL, file=buf)
    return resp.text.strip()


def _chat(text: str, session_id: str) -> dict:
    client = get_client()
    memory = get_session(session_id, client)
    emotion = get_emotion(session_id)
    reply, emotion = _engine.respond(memory, emotion, text)
    return {
        "reply": reply,
        "emotion": emotion.label,
        "intensity": round(emotion.intensity, 2),
    }


def _synthesize(text: str, session_id: str, style: Optional[str]) -> bytes:
    client = get_client()
    emotion = get_emotion(session_id)
    instructions = style or emotion.tts_style_instruction()
    kwargs = dict(model=config.TTS_MODEL, voice=config.TTS_VOICE, input=text)
    # gpt-4o-*-tts 支持 instructions 控制语气；旧模型忽略
    if "gpt-4o" in config.TTS_MODEL:
        kwargs["instructions"] = instructions
    resp = client.audio.speech.create(**kwargs)
    return resp.read()


# ── 接口 ────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "persona": _persona.name, "model": config.CHAT_MODEL}


@app.get("/api/persona")
def persona_info():
    return {
        "name": _persona.name,
        "tagline": _persona.data.get("tagline", ""),
    }


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    text = _transcribe(data, audio.filename or "audio.webm")
    return {"text": text}


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.text.strip():
        raise HTTPException(400, "text 不能为空")
    return _chat(req.text, req.session_id)


@app.post("/api/chat-stream")
def chat_stream(req: ChatRequest):
    """流式对话（SSE）。逐段返回文本增量，结束时发送情绪。"""
    if not req.text.strip():
        raise HTTPException(400, "text 不能为空")
    client = get_client()
    memory = get_session(req.session_id, client)
    emotion = get_emotion(req.session_id)

    def event_gen():
        import json as _json

        for delta in _engine.respond_stream(memory, emotion, req.text):
            yield f"data: {_json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
        done = {
            "done": True,
            "emotion": emotion.label,
            "intensity": round(emotion.intensity, 2),
        }
        yield f"data: {_json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/api/speak")
def speak(req: SpeakRequest):
    if not req.text.strip():
        raise HTTPException(400, "text 不能为空")
    audio = _synthesize(req.text, req.session_id, req.style)
    return StreamingResponse(io.BytesIO(audio), media_type="audio/mpeg")


@app.post("/api/voice-chat")
async def voice_chat(
    audio: UploadFile = File(...), session_id: str = Form("default")
):
    """完整链路：音频 → 文字 → AI（人格/情绪/记忆）→ 语音。

    返回音频流，并把识别文本/回复/情绪放到响应头（前端可读取）。
    """
    data = await audio.read()
    user_text = _transcribe(data, audio.filename or "audio.webm")
    if not user_text:
        raise HTTPException(400, "未识别到语音内容")
    result = _chat(user_text, session_id)
    speech = _synthesize(result["reply"], session_id, None)

    import urllib.parse

    headers = {
        "X-User-Text": urllib.parse.quote(user_text),
        "X-Reply-Text": urllib.parse.quote(result["reply"]),
        "X-Emotion": result["emotion"],
        "X-Intensity": str(result["intensity"]),
        "Access-Control-Expose-Headers": "X-User-Text,X-Reply-Text,X-Emotion,X-Intensity",
    }
    return StreamingResponse(io.BytesIO(speech), media_type="audio/mpeg", headers=headers)


@app.exception_handler(Exception)
async def unhandled(request, exc):  # noqa: ANN001
    return JSONResponse(status_code=500, content={"error": str(exc)})
