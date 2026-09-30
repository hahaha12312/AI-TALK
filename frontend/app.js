// ── 配置 ──────────────────────────────────────────────────────────────
const API_BASE = window.API_BASE || "http://localhost:8000";
const SESSION_ID =
  localStorage.getItem("ai_talk_session") ||
  (() => {
    const id = "s_" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("ai_talk_session", id);
    return id;
  })();

// 情绪 → 头像表情
const EMOTION_EMOJI = {
  neutral: "🙂",
  happy: "😄",
  excited: "🤩",
  tender: "🥰",
  sad: "🥺",
  angry: "😠",
  playful: "😜",
  curious: "🤔",
};

// ── DOM ───────────────────────────────────────────────────────────────
const chat = document.getElementById("chat");
const recordBtn = document.getElementById("recordBtn");
const textInput = document.getElementById("textInput");
const sendBtn = document.getElementById("sendBtn");
const statusEl = document.getElementById("status");
const player = document.getElementById("player");
const avatar = document.getElementById("avatar");
const emotionBadge = document.getElementById("emotionBadge");
const personaName = document.getElementById("personaName");
const personaTag = document.getElementById("personaTag");

// ── 工具 ──────────────────────────────────────────────────────────────
function addBubble(text, who) {
  const el = document.createElement("div");
  el.className = "bubble " + who;
  el.textContent = text;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

function setStatus(text) {
  statusEl.textContent = text || "";
}

function setEmotion(emotion, intensity) {
  if (!emotion) return;
  avatar.textContent = EMOTION_EMOJI[emotion] || "🙂";
  emotionBadge.textContent = `情绪：${emotion}${
    intensity ? " · " + intensity : ""
  }`;
  avatar.style.transform = "scale(1.15)";
  setTimeout(() => (avatar.style.transform = "scale(1)"), 300);
}

// ── 初始化人设 ────────────────────────────────────────────────────────
async function loadPersona() {
  try {
    const res = await fetch(`${API_BASE}/api/persona`);
    const data = await res.json();
    personaName.textContent = data.name || "AI-TALK";
    personaTag.textContent = data.tagline || "";
  } catch (e) {
    personaTag.textContent = "（后端未连接）";
  }
}

// ── 文字对话 ──────────────────────────────────────────────────────────
async function sendText(text) {
  addBubble(text, "user");
  setStatus("思考中…");
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_id: SESSION_ID }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    addBubble(data.reply, "ai");
    setEmotion(data.emotion, data.intensity);
    await speak(data.reply);
    setStatus("");
  } catch (e) {
    setStatus("出错了：" + e.message);
  }
}

// ── 合成并播放 ────────────────────────────────────────────────────────
async function speak(text) {
  try {
    const res = await fetch(`${API_BASE}/api/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_id: SESSION_ID }),
    });
    if (!res.ok) return;
    const blob = await res.blob();
    player.src = URL.createObjectURL(blob);
    await player.play().catch(() => {});
  } catch (e) {
    /* 忽略播放错误 */
  }
}

// ── 语音对话（录音 → 后端一条龙）────────────────────────────────────
let mediaRecorder = null;
let chunks = [];

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      handleAudio(new Blob(chunks, { type: "audio/webm" }));
    };
    mediaRecorder.start();
    recordBtn.classList.add("recording");
    recordBtn.textContent = "🔴 松开发送";
    setStatus("录音中…");
  } catch (e) {
    setStatus("无法访问麦克风：" + e.message);
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    recordBtn.classList.remove("recording");
    recordBtn.textContent = "🎤 按住说话";
  }
}

async function handleAudio(blob) {
  setStatus("识别中…");
  const form = new FormData();
  form.append("audio", blob, "audio.webm");
  form.append("session_id", SESSION_ID);
  try {
    const res = await fetch(`${API_BASE}/api/voice-chat`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error(await res.text());
    const userText = decodeURIComponent(res.headers.get("X-User-Text") || "");
    const replyText = decodeURIComponent(res.headers.get("X-Reply-Text") || "");
    const emotion = res.headers.get("X-Emotion");
    const intensity = res.headers.get("X-Intensity");
    if (userText) addBubble(userText, "user");
    if (replyText) addBubble(replyText, "ai");
    setEmotion(emotion, intensity);
    const audioBlob = await res.blob();
    player.src = URL.createObjectURL(audioBlob);
    await player.play().catch(() => {});
    setStatus("");
  } catch (e) {
    setStatus("出错了：" + e.message);
  }
}

// ── 事件绑定 ──────────────────────────────────────────────────────────
recordBtn.addEventListener("mousedown", startRecording);
recordBtn.addEventListener("mouseup", stopRecording);
recordBtn.addEventListener("mouseleave", stopRecording);
recordBtn.addEventListener("touchstart", (e) => {
  e.preventDefault();
  startRecording();
});
recordBtn.addEventListener("touchend", (e) => {
  e.preventDefault();
  stopRecording();
});

sendBtn.addEventListener("click", () => {
  const t = textInput.value.trim();
  if (t) {
    textInput.value = "";
    sendText(t);
  }
});
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendBtn.click();
});

loadPersona();
