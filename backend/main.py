import os
import io
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI-TALK API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TTS_VOICE = os.getenv("TTS_VOICE", "alloy")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "你是一个友好的语音助手，请用简洁自然的语言回答用户问题。",
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []


class SpeakRequest(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """语音 → 文字（Whisper）"""
    audio_bytes = await audio.read()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = audio.filename or "audio.webm"

    try:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"text": result.text}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """文字 → AI 回复"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    reply = response.choices[0].message.content
    return {"reply": reply}


@app.post("/api/speak")
def speak(req: SpeakRequest):
    """文字 → 语音（TTS）"""
    try:
        tts_response = client.audio.speech.create(
            model="tts-1",
            voice=TTS_VOICE,
            input=req.text,
            response_format="mp3",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    audio_bytes = tts_response.content
    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=speech.mp3"},
    )


@app.post("/api/voice-chat")
async def voice_chat(audio: UploadFile = File(...), history: str = "[]"):
    """完整语音对话：音频 → 文字 → AI → 语音"""
    import json

    # 1. 语音 → 文字
    audio_bytes = await audio.read()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = audio.filename or "audio.webm"

    try:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        user_text = transcription.text
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription error: {exc}")

    # 2. 解析历史
    try:
        history_list = json.loads(history)
    except json.JSONDecodeError:
        history_list = []

    # 3. 文字 → AI 回复
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history_list:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_text})

    try:
        chat_response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
        )
        reply_text = chat_response.choices[0].message.content
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat error: {exc}")

    # 4. AI 回复 → 语音
    try:
        tts_response = client.audio.speech.create(
            model="tts-1",
            voice=TTS_VOICE,
            input=reply_text,
            response_format="mp3",
        )
        audio_out = tts_response.content
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS error: {exc}")

    import base64

    return {
        "user_text": user_text,
        "reply_text": reply_text,
        "audio_base64": base64.b64encode(audio_out).decode(),
    }
