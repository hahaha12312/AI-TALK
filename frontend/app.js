// ── 配置 ──────────────────────────────────────────────────────────────
const API_BASE = window.API_BASE || "http://localhost:8000";
const SESSION_ID =
  localStorage.getItem("ai_talk_session") ||
  (() => {
    const id =
      "s_" +
      (crypto.randomUUID
        ? crypto.randomUUID()
        : crypto.getRandomValues(new Uint32Array(2)).join(""));
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

// ── 文字对话（流式）──────────────────────────────────────────────────
async function sendText(text) {
  addBubble(text, "user");
  setStatus("思考中…");
  stopPlayback(); // barge-in：发新消息时打断上一条播放
  const bubble = addBubble("", "ai");
  let full = "";
  try {
    const res = await fetch(`${API_BASE}/api/chat-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_id: SESSION_ID }),
    });
    if (!res.ok || !res.body) throw new Error(await res.text());

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const payload = JSON.parse(line.slice(5).trim());
        if (payload.delta) {
          full += payload.delta;
          bubble.textContent = full;
          chat.scrollTop = chat.scrollHeight;
        }
        if (payload.done) setEmotion(payload.emotion, payload.intensity);
      }
    }
    setStatus("");
    if (full) await speak(full);
  } catch (e) {
    // 流式失败则回退到普通对话
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, session_id: SESSION_ID }),
      });
      const data = await res.json();
      bubble.textContent = data.reply;
      setEmotion(data.emotion, data.intensity);
      await speak(data.reply);
      setStatus("");
    } catch (err) {
      setStatus("出错了：" + err.message);
    }
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
// VAD 相关
let audioCtx = null;
let vadRafId = null;
let silenceStart = 0;
const SILENCE_THRESHOLD = 0.012; // 均方根音量阈值
const SILENCE_DURATION = 1200; // 静音多久后自动停止(ms)

function stopPlayback() {
  // 打断(barge-in)：用户开始说话时立即停止 AI 播放
  if (player && !player.paused) {
    player.pause();
    player.currentTime = 0;
  }
}

function startVAD(stream) {
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const data = new Uint8Array(analyser.fftSize);
    silenceStart = 0;

    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / data.length);
      const now = performance.now();
      if (rms < SILENCE_THRESHOLD) {
        if (silenceStart === 0) silenceStart = now;
        else if (now - silenceStart > SILENCE_DURATION) {
          stopRecording(); // 自动断句
          return;
        }
      } else {
        silenceStart = 0; // 有声音，重置
      }
      vadRafId = requestAnimationFrame(tick);
    };
    vadRafId = requestAnimationFrame(tick);
  } catch (e) {
    /* VAD 不可用时忽略，仍可手动松开发送 */
  }
}

function stopVAD() {
  if (vadRafId) cancelAnimationFrame(vadRafId);
  vadRafId = null;
  if (audioCtx) {
    audioCtx.close().catch(() => {});
    audioCtx = null;
  }
}

async function startRecording() {
  stopPlayback(); // barge-in
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = () => {
      stopVAD();
      stream.getTracks().forEach((t) => t.stop());
      handleAudio(new Blob(chunks, { type: "audio/webm" }));
    };
    mediaRecorder.start();
    startVAD(stream);
    recordBtn.classList.add("recording");
    recordBtn.textContent = "🔴 松开发送";
    setStatus("录音中…（静音自动结束）");
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
