"""情绪状态机：维护角色随对话演变的情绪，并驱动语气与 TTS。"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# 基础情绪标签及其对 TTS 语气的指令映射
EMOTION_STYLES: Dict[str, str] = {
    "neutral": "语气平和自然。",
    "happy": "语气轻快、上扬，带着笑意和活力。",
    "excited": "语气兴奋、热烈，节奏偏快，充满能量。",
    "tender": "语气温柔、放慢，充满关怀和安慰。",
    "sad": "语气低沉、放缓，带着一丝心疼和共情。",
    "angry": "语气略微加重、坚定，但克制不失礼貌。",
    "playful": "语气俏皮、活泼，带点调侃和幽默。",
    "curious": "语气好奇、上扬，带着探究的兴趣。",
}

# 简单的中文情绪关键词，用于在无结构化输出时的兜底推断
_USER_EMOTION_HINTS: List[Tuple[str, List[str]]] = [
    ("sad", ["难过", "伤心", "累", "哭", "崩溃", "失落", "孤独", "压力", "烦"]),
    ("happy", ["开心", "高兴", "太好了", "哈哈", "棒", "耶", "爽"]),
    ("excited", ["升职", "中了", "成功", "太厉害", "惊喜", "!!!", "！！"]),
    ("angry", ["生气", "气死", "讨厌", "烦死", "可恶", "愤怒"]),
    ("curious", ["为什么", "怎么", "是不是", "吗？", "好奇"]),
]

VALID_EMOTIONS = set(EMOTION_STYLES.keys())


@dataclass
class EmotionState:
    """当前情绪标签 + 强度(0~1)，随对话平滑演变。"""

    label: str = "neutral"
    intensity: float = 0.4
    history: List[str] = field(default_factory=list)

    def update(self, new_label: str, new_intensity: float) -> None:
        if new_label not in VALID_EMOTIONS:
            new_label = "neutral"
        new_intensity = max(0.0, min(1.0, float(new_intensity)))
        # 平滑：情绪不会瞬间反转，做一次加权
        if new_label == self.label:
            self.intensity = min(1.0, self.intensity * 0.5 + new_intensity * 0.6)
        else:
            self.label = new_label
            self.intensity = new_intensity
        self.history.append(f"{self.label}:{self.intensity:.2f}")
        self.history = self.history[-20:]

    # ── 提示词 / TTS ─────────────────────────────────────────────────────
    def prompt_hint(self) -> str:
        return (
            f"你当前的情绪是「{self.label}」（强度 {self.intensity:.1f}）。"
            "让你的回复自然地体现这种情绪，但不要直接说出情绪名称。"
        )

    def tts_style_instruction(self) -> str:
        base = EMOTION_STYLES.get(self.label, EMOTION_STYLES["neutral"])
        if self.intensity >= 0.7:
            return "请用较强烈的情绪表达：" + base
        if self.intensity <= 0.3:
            return "请用较收敛的情绪表达：" + base
        return base


def infer_user_emotion(text: str) -> str:
    """无模型结构化输出时，从用户文本兜底推断情绪标签。"""
    if not text:
        return "neutral"
    for label, keywords in _USER_EMOTION_HINTS:
        if any(k in text for k in keywords):
            return label
    return "neutral"
