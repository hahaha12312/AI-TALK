"""记忆系统：短期会话历史（含摘要压缩）+ 长期向量记忆。

长期记忆采用轻量的本地向量存储：用 OpenAI Embeddings 把要点向量化，
存到 JSON 文件，检索时用余弦相似度召回，无需额外数据库依赖。
若未配置 API Key（无法生成向量），会自动降级为仅短期记忆，不影响主流程。
"""
import json
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import config


# ── 向量工具 ────────────────────────────────────────────────────────────
def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class LongTermMemory:
    """按会话持久化的向量记忆。"""

    session_id: str
    client: Any = None  # OpenAI client，可为 None（降级）
    items: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def _path(self) -> str:
        return os.path.join(config.DATA_DIR, f"memory_{self.session_id}.json")

    def load(self) -> "LongTermMemory":
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self.items = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.items = []
        return self

    def _save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _embed(self, text: str) -> Optional[List[float]]:
        if self.client is None:
            return None
        try:
            resp = self.client.embeddings.create(
                model=config.EMBEDDING_MODEL, input=text
            )
            return resp.data[0].embedding
        except Exception:
            return None

    def add(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.items.append(
            {"text": text, "ts": time.time(), "embedding": self._embed(text)}
        )
        self._save()

    def search(self, query: str, top_k: int | None = None) -> List[str]:
        top_k = top_k or config.MEMORY_TOP_K
        if not self.items:
            return []
        q_emb = self._embed(query)
        if q_emb is None:
            # 无法向量化 → 退化为返回最近的几条
            return [it["text"] for it in self.items[-top_k:]]
        scored = [
            (_cosine(q_emb, it.get("embedding") or []), it["text"])
            for it in self.items
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for s, t in scored[:top_k] if s > 0.15]


@dataclass
class ConversationMemory:
    """单个会话的完整记忆：滚动历史 + 摘要 + 长期向量记忆。"""

    session_id: str
    client: Any = None
    history: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""
    long_term: Optional[LongTermMemory] = None

    def __post_init__(self) -> None:
        if config.MEMORY_ENABLED and self.long_term is None:
            self.long_term = LongTermMemory(self.session_id, self.client).load()

    def add_turn(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def recent(self) -> List[Dict[str, str]]:
        """返回最近若干轮，供直接注入 prompt。"""
        max_msgs = config.MAX_HISTORY_TURNS * 2
        return self.history[-max_msgs:]

    def needs_compaction(self) -> bool:
        return len(self.history) > config.MAX_HISTORY_TURNS * 2

    def compact(self) -> None:
        """把较旧的历史压缩为摘要，并抽取要点写入长期记忆。"""
        if self.client is None or not self.needs_compaction():
            return
        keep = config.MAX_HISTORY_TURNS  # 保留最近的一半（按消息数）
        old = self.history[:-keep]
        if not old:
            return
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in old)
        try:
            resp = self.client.chat.completions.create(
                model=config.SUMMARY_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是对话记忆助手。请把下面的对话压缩成简洁的中文摘要，"
                            "重点保留：用户的身份/偏好/重要事实、情绪、以及未完成的话题。"
                            "另外用一行 KEYFACTS: 列出最多3条值得长期记住的用户事实（用；分隔）。"
                        ),
                    },
                    {"role": "user", "content": (self.summary + "\n" + convo).strip()},
                ],
                temperature=0.3,
            )
            text = resp.choices[0].message.content or ""
        except Exception:
            return

        summary_part = text
        if "KEYFACTS:" in text:
            summary_part, _, facts = text.partition("KEYFACTS:")
            if self.long_term is not None:
                for fact in facts.replace("\n", "；").split("；"):
                    fact = fact.strip("　 -·").strip()
                    if len(fact) > 3:
                        self.long_term.add(fact)
        self.summary = summary_part.strip()
        self.history = self.history[-keep:]

    def relevant_memories(self, query: str) -> List[str]:
        if self.long_term is None:
            return []
        return self.long_term.search(query)

    def remember_fact(self, text: str) -> None:
        if self.long_term is not None:
            self.long_term.add(text)


# ── 内存中的会话注册表 ─────────────────────────────────────────────────
_SESSIONS: Dict[str, ConversationMemory] = {}


def get_session(session_id: str, client: Any = None) -> ConversationMemory:
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = ConversationMemory(session_id, client)
    return _SESSIONS[session_id]
