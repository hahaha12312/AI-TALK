"""集中管理环境变量与默认配置。"""
import os

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


# ── OpenAI ────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None

# 对话 / 识别 / 合成 / 摘要 / 向量 模型
CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
STT_MODEL = os.getenv("STT_MODEL", "whisper-1")
TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", CHAT_MODEL)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ── 语音 ──────────────────────────────────────────────────────────────────
TTS_VOICE = os.getenv("TTS_VOICE", "nova")

# ── 人格 ──────────────────────────────────────────────────────────────────
# 角色卡文件（位于 personas/ 目录）
PERSONA_FILE = os.getenv("PERSONA_FILE", "companion.json")

# ── 记忆 ──────────────────────────────────────────────────────────────────
MEMORY_ENABLED = _get_bool("MEMORY_ENABLED", True)
# 会话历史保留的最大轮数（超过则触发摘要压缩）
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "12"))
# 长期记忆检索返回的条数
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "4"))
# 数据持久化目录
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))

os.makedirs(DATA_DIR, exist_ok=True)
