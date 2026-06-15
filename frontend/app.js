// 后端地址，部署时改为实际地址（空字符串表示使用相同的 origin）
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? `${window.location.protocol}//localhost:8000`
  : "";

const recordBtn = document.getElementById("recordBtn");
const chatWindow = document.getElementById("chatWindow");
const statusEl = document.getElementById("status");

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// 对话历史（发送给后端以保持上下文）
let history = [];

// ──────────────────────────────────────────────
// UI helpers
// ──────────────────────────────────────────────
function setStatus(msg) {
  statusEl.textContent = msg;
}

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatar = document.createElement("span");
  avatar.className = "avatar";
  avatar.textContent = role === "ai" ? "🤖" : "🧑";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  div.appendChild(avatar);
  div.appendChild(bubble);
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

// ──────────────────────────────────────────────
// Recording
// ──────────────────────────────────────────────
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.addEventListener("dataavailable", (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    });

    mediaRecorder.start(100);
    isRecording = true;
    recordBtn.classList.add("recording");
    recordBtn.querySelector(".btn-label").textContent = "松开发送";
    setStatus("正在录音…");
  } catch (err) {
    setStatus("无法访问麦克风：" + err.message);
  }
}

function stopRecording() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;

  mediaRecorder.addEventListener("stop", async () => {
    const blob = new Blob(audioChunks, { type: "audio/webm" });
    audioChunks = [];
    await sendVoice(blob);

    // 停止麦克风轨道
    mediaRecorder.stream.getTracks().forEach((t) => t.stop());
    mediaRecorder = null;
  });

  mediaRecorder.stop();
  isRecording = false;
  recordBtn.classList.remove("recording");
  recordBtn.querySelector(".btn-label").textContent = "按住说话";
}

// ──────────────────────────────────────────────
// API call
// ──────────────────────────────────────────────
async function sendVoice(blob) {
  recordBtn.classList.add("loading");
  recordBtn.disabled = true;
  setStatus("AI 正在思考…");

  const formData = new FormData();
  formData.append("audio", blob, "recording.webm");
  formData.append("history", JSON.stringify(history));

  try {
    const res = await fetch(`${API_BASE}/api/voice-chat`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }

    // 从响应头读取文字内容
    const userText = decodeURIComponent(res.headers.get("X-User-Text") || "");
    const aiReply = decodeURIComponent(res.headers.get("X-AI-Reply") || "");

    if (userText) addMessage("user", userText);
    if (aiReply) addMessage("ai", aiReply);

    // 更新对话历史
    if (userText) history.push({ role: "user", content: userText });
    if (aiReply) history.push({ role: "assistant", content: aiReply });

    // 播放 AI 语音
    const audioBlob = await res.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    setStatus("AI 正在说话…");
    audio.addEventListener("ended", () => {
      URL.revokeObjectURL(audioUrl);
      setStatus("点击按钮继续对话");
    });
    await audio.play();
  } catch (err) {
    setStatus("出错了：" + err.message);
    console.error(err);
  } finally {
    recordBtn.classList.remove("loading");
    recordBtn.disabled = false;
  }
}

// ──────────────────────────────────────────────
// Event listeners – mouse & touch
// ──────────────────────────────────────────────
recordBtn.addEventListener("mousedown", (e) => {
  e.preventDefault();
  if (!isRecording) startRecording();
});

recordBtn.addEventListener("mouseup", () => {
  if (isRecording) stopRecording();
});

recordBtn.addEventListener("mouseleave", () => {
  if (isRecording) stopRecording();
});

recordBtn.addEventListener("touchstart", (e) => {
  e.preventDefault();
  if (!isRecording) startRecording();
}, { passive: false });

recordBtn.addEventListener("touchend", (e) => {
  e.preventDefault();
  if (isRecording) stopRecording();
});
