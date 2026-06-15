import json
import os
import tempfile
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI(title="AI-TALK", description="AI 语音对话服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "你是一个友好、智能的 AI 语音助手。请用简洁、自然的语言回复用户，适合语音播放。",
)


class ChatRequest(BaseModel):
    text: str
    history: list[dict] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """将上传的音频文件转成文字（Whisper STT）"""
    suffix = Path(audio.filename).suffix if audio.filename else ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        return {"text": transcript.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


@app.post("/api/chat")
def chat(req: ChatRequest):
    """将文字发给 GPT，返回 AI 回复文字"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(req.history)
    messages.append({"role": "user", "content": req.text})

    try:
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
        )
        reply = response.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/speak")
async def speak(req: ChatRequest):
    """将文字转成语音文件（TTS），返回 mp3"""
    tmp_path = None
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=os.environ.get("TTS_VOICE", "alloy"),
            input=req.text,
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        async def _cleanup():
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        response_file = FileResponse(
            tmp_path, media_type="audio/mpeg", filename="reply.mp3"
        )
        response_file.background = _cleanup  # type: ignore[assignment]
        return response_file
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice-chat")
async def voice_chat(audio: UploadFile = File(...), history: str = "[]"):
    """
    一步完成完整语音对话流程：
      1. 语音 → 文字（Whisper）
      2. 文字 → AI 回复（GPT）
      3. AI 回复 → 语音（TTS）
    返回 mp3 音频，并在响应头中附带转录文字和 AI 回复文字。
    """
    parsed_history: list[dict] = json.loads(history)

    # Step 1: STT
    suffix = Path(audio.filename).suffix if audio.filename else ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        user_text = transcript.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT 失败: {e}")
    finally:
        os.unlink(tmp_path)

    # Step 2: Chat
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(parsed_history)
    messages.append({"role": "user", "content": user_text})

    try:
        chat_response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
        )
        ai_reply = chat_response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat 失败: {e}")

    # Step 3: TTS
    audio_path = None
    try:
        tts_response = client.audio.speech.create(
            model="tts-1",
            voice=os.environ.get("TTS_VOICE", "alloy"),
            input=ai_reply,
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(tts_response.content)
            audio_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS 失败: {e}")

    headers = {
        "X-User-Text": urllib.parse.quote(user_text),
        "X-AI-Reply": urllib.parse.quote(ai_reply),
    }

    captured_path = audio_path

    async def _cleanup():
        if captured_path and os.path.exists(captured_path):
            os.unlink(captured_path)

    response_file = FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename="reply.mp3",
        headers=headers,
    )
    response_file.background = _cleanup  # type: ignore[assignment]
    return response_file
