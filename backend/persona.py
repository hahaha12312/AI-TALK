"""人格系统：加载角色卡并生成稳定的 system prompt。"""
import json
import os
from typing import Any, Dict, List

import config


class Persona:
    """封装一个角色卡，并负责渲染出注入模型的系统提示词。"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.name: str = data.get("name", "AI")

    @classmethod
    def load(cls, filename: str | None = None) -> "Persona":
        filename = filename or config.PERSONA_FILE
        path = filename
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(__file__), "personas", filename)
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    # ── 提示词渲染 ────────────────────────────────────────────────────────
    def _big_five_text(self) -> str:
        bf = self.data.get("big_five") or {}
        if not bf:
            return ""
        labels = {
            "openness": "开放性",
            "conscientiousness": "尽责性",
            "extraversion": "外向性",
            "agreeableness": "宜人性",
            "neuroticism": "神经质",
        }
        parts = [f"{labels.get(k, k)}={v}" for k, v in bf.items()]
        return "、".join(parts)

    def base_system_prompt(self) -> str:
        d = self.data
        lines: List[str] = []
        lines.append(f"你要扮演一个名叫「{d.get('name')}」的角色，始终保持这个身份，绝不跳出角色。")
        if d.get("gender") or d.get("age"):
            lines.append(f"性别：{d.get('gender', '未知')}；年龄：{d.get('age', '未知')}。")
        if d.get("tagline"):
            lines.append(f"一句话人设：{d['tagline']}。")
        if d.get("background"):
            lines.append(f"背景故事：{d['background']}")
        bf = self._big_five_text()
        if bf:
            lines.append(f"大五人格倾向（0~1，越高越强）：{bf}。请让言行与之一致。")
        if d.get("personality"):
            lines.append(f"性格：{d['personality']}")
        if d.get("speaking_style"):
            lines.append(f"说话风格：{d['speaking_style']}")
        if d.get("catchphrases"):
            lines.append(f"口头禅（自然地偶尔使用，不要每句都用）：{'；'.join(d['catchphrases'])}。")
        if d.get("values"):
            lines.append(f"价值观：{d['values']}")
        if d.get("taboos"):
            lines.append(f"禁忌与边界：{d['taboos']}")

        lines.append(
            "对话要求：像真人一样自然口语化，回复简短（通常 1~3 句），"
            "有真实的情绪起伏和共情，会主动关心和追问，避免机械、说教或列清单式的回答。"
        )
        return "\n".join(lines)

    def example_messages(self) -> List[Dict[str, str]]:
        """few-shot 示例，用来锚定语气，减少人格漂移。"""
        msgs: List[Dict[str, str]] = []
        for turn in self.data.get("example_dialogue", []) or []:
            if turn.get("user"):
                msgs.append({"role": "user", "content": turn["user"]})
            if turn.get("assistant"):
                msgs.append({"role": "assistant", "content": turn["assistant"]})
        return msgs
