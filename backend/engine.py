"""对话引擎：整合人格、情绪、记忆，生成带情绪的回复。"""
import json
import logging
from typing import Any, Dict, List, Tuple

import config
from emotion import EmotionState, infer_user_emotion
from memory import ConversationMemory
from persona import Persona

logger = logging.getLogger("ai-talk.engine")

# 让模型在回复的同时输出情绪标签的结构化定义
_EMOTION_TOOL = {
    "type": "function",
    "function": {
        "name": "respond",
        "description": "以角色身份回复用户，并给出当前情绪。",
        "parameters": {
            "type": "object",
            "properties": {
                "reply": {"type": "string", "description": "对用户说的话（口语、简短、自然）"},
                "emotion": {
                    "type": "string",
                    "enum": [
                        "neutral", "happy", "excited", "tender",
                        "sad", "angry", "playful", "curious",
                    ],
                    "description": "你说这句话时的情绪",
                },
                "intensity": {
                    "type": "number",
                    "description": "情绪强度，0~1",
                },
            },
            "required": ["reply", "emotion", "intensity"],
        },
    },
}


class DialogueEngine:
    def __init__(self, client: Any, persona: Persona):
        self.client = client
        self.persona = persona

    def _build_messages(
        self, memory: ConversationMemory, emotion: EmotionState, user_text: str
    ) -> List[Dict[str, str]]:
        system_parts = [self.persona.base_system_prompt(), emotion.prompt_hint()]

        if memory.summary:
            system_parts.append(f"【之前对话摘要】{memory.summary}")

        mems = memory.relevant_memories(user_text)
        if mems:
            system_parts.append("【关于用户你记得的事】" + "；".join(mems))

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": "\n\n".join(system_parts)}
        ]
        messages.extend(self.persona.example_messages())
        messages.extend(memory.recent())
        messages.append({"role": "user", "content": user_text})
        return messages

    def respond(
        self, memory: ConversationMemory, emotion: EmotionState, user_text: str
    ) -> Tuple[str, EmotionState]:
        """生成回复并更新情绪状态。返回 (回复文本, 情绪)。"""
        messages = self._build_messages(memory, emotion, user_text)

        reply, emo_label, emo_int = self._call_model(messages)

        # 兜底：如果模型没给情绪，用用户文本推断
        if not emo_label:
            emo_label = infer_user_emotion(user_text)
            emo_int = 0.5
        emotion.update(emo_label, emo_int)

        # 写入记忆并按需压缩
        memory.add_turn("user", user_text)
        memory.add_turn("assistant", reply)
        if memory.needs_compaction():
            memory.compact()

        return reply, emotion

    def respond_stream(
        self, memory: ConversationMemory, emotion: EmotionState, user_text: str
    ):
        """流式生成回复。逐段 yield 文本增量，结束后更新情绪与记忆。

        流式模式下不走 function-calling 结构化情绪，改为用用户文本兜底推断情绪，
        以换取更低的首字延迟。
        """
        messages = self._build_messages(memory, emotion, user_text)
        full = []
        try:
            stream = self.client.chat.completions.create(
                model=config.CHAT_MODEL,
                messages=messages,
                temperature=0.9,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full.append(delta)
                    yield delta
        except Exception:  # noqa: BLE001
            logger.exception("respond_stream failed")
            yield "（抱歉，我这边出了点问题，稍后再聊好吗～）"

        reply = "".join(full).strip()
        emo_label = infer_user_emotion(user_text)
        emotion.update(emo_label, 0.5)
        memory.add_turn("user", user_text)
        memory.add_turn("assistant", reply)
        if memory.needs_compaction():
            memory.compact()

    def _call_model(self, messages: List[Dict[str, str]]) -> Tuple[str, str, float]:
        try:
            resp = self.client.chat.completions.create(
                model=config.CHAT_MODEL,
                messages=messages,
                tools=[_EMOTION_TOOL],
                tool_choice={"type": "function", "function": {"name": "respond"}},
                temperature=0.9,
            )
            msg = resp.choices[0].message
            if msg.tool_calls:
                args = json.loads(msg.tool_calls[0].function.arguments)
                return (
                    (args.get("reply") or "").strip(),
                    args.get("emotion", ""),
                    float(args.get("intensity", 0.5)),
                )
            return (msg.content or "").strip(), "", 0.5
        except Exception:
            # 结构化调用失败时退回普通对话
            resp = self.client.chat.completions.create(
                model=config.CHAT_MODEL, messages=messages, temperature=0.9
            )
            return (resp.choices[0].message.content or "").strip(), "", 0.5
