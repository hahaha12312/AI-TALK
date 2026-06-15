// Derive backend URL from the current page's origin so it works in production.
// When served via docker-compose (nginx on :3000, backend on :8000) the origin
// is http://localhost:3000, but the backend lives on port 8000.
// Override by setting window.AI_TALK_API before loading this script, e.g.:
//   <script>window.AI_TALK_API = "https://api.example.com";</script>
const API_BASE =
  window.AI_TALK_API ||
  (window.location.port === "3000"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : window.location.origin);

const chatBox = document.getElementById("chat-box");
const recordBtn = document.getElementById("record-btn");
const statusEl = document.getElementById("status");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");

// Conversation history sent to the backend for multi-turn context
let history = [];

// ── Helpers ───────────────────────────────────────────────────────────────────

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = text;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function setStatus(msg) {
  statusEl.textContent = msg;
}

async function playAudioBase64(base64) {
  const binary = atob(base64);
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: "audio/mpeg" });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  return new Promise((resolve, reject) => {
    audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
    audio.onerror = reject;
    audio.play();
  });
}

// ── Voice chat (microphone) ───────────────────────────────────────────────────

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(audioChunks, { type: mimeType });
      sendVoice(blob);
    };

    mediaRecorder.start();
    isRecording = true;
    recordBtn.classList.add("recording");
    recordBtn.querySelector(".btn-label").textContent = "录音中…";
    setStatus("🔴 正在录音，松开发送");
  } catch (err) {
    setStatus("⚠️ 无法访问麦克风：" + err.message);
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    recordBtn.classList.remove("recording");
    recordBtn.querySelector(".btn-label").textContent = "按住说话";
    setStatus("⏳ 正在处理…");
  }
}

async function sendVoice(blob) {
  const formData = new FormData();
  formData.append("audio", blob, "recording.webm");
  formData.append("history", JSON.stringify(history));

  try {
    const res = await fetch(`${API_BASE}/api/voice-chat`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    appendMessage("user", data.user_text);
    appendMessage("assistant", data.reply_text);

    history.push({ role: "user", content: data.user_text });
    history.push({ role: "assistant", content: data.reply_text });

    setStatus("🔊 正在播放语音…");
    await playAudioBase64(data.audio_base64);
    setStatus("准备就绪");
  } catch (err) {
    setStatus("❌ 请求失败：" + err.message);
  }
}

// Touch / mouse events for the record button
recordBtn.addEventListener("mousedown", startRecording);
recordBtn.addEventListener("mouseup", stopRecording);
recordBtn.addEventListener("mouseleave", stopRecording);
recordBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
recordBtn.addEventListener("touchend", (e) => { e.preventDefault(); stopRecording(); });

// ── Text chat ─────────────────────────────────────────────────────────────────

async function sendText() {
  const text = textInput.value.trim();
  if (!text) return;

  textInput.value = "";
  appendMessage("user", text);
  setStatus("⏳ 等待 AI 回复…");

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    appendMessage("assistant", data.reply);
    history.push({ role: "user", content: text });
    history.push({ role: "assistant", content: data.reply });

    // Also speak the reply
    setStatus("🔊 正在合成语音…");
    const speakRes = await fetch(`${API_BASE}/api/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: data.reply }),
    });
    if (speakRes.ok) {
      const audioBlob = await speakRes.blob();
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      audio.play();
    }
    setStatus("准备就绪");
  } catch (err) {
    setStatus("❌ 请求失败：" + err.message);
  }
}

sendBtn.addEventListener("click", sendText);
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendText();
});
