import io
import os
import sys
from openai import OpenAI
import pygame

# ==================== 配置中心 ====================
# 优先从环境变量读取 API Key，也可直接在下方填写
API_KEY = os.environ.get("OHMYGPT_API_KEY", "你的_OHMYGPT_API_KEY")
BASE_URL = os.environ.get("OHMYGPT_BASE_URL", "https://api.ohmygpt.com/v1")

# 模型选择（低配电脑推荐使用高性价比、响应极快的模型）
CHAT_MODEL = "gpt-4o-mini"  # 响应速度极快，且非常便宜
TTS_MODEL = "tts-1"         # 实时语音优化版，延迟极低
VOICE_NAME = "nova"         # 预设音色：nova（甜美女声）, alloy（中性）, onyx（深沉男声）

# 对话记忆限制（防止低配电脑内存溢出及Token暴涨）
MAX_HISTORY = 10
# ==================================================

# 初始化 OpenAI 客户端
try:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
except Exception as e:
    print(f"[错误] 客户端初始化失败，请检查网络或配置: {e}")
    sys.exit(1)

# 初始化 Pygame 音频播放器
pygame.mixer.init()

# 初始化对话历史（加入系统提示词，从源头控制 AI 的回答字数和风格）
conversation_history = [
    {
        "role": "system",
        "content": (
            "你是一个贴心的智能语音助手。由于你的回答会通过语音播放给用户，"
            "请务必保持回答口语化、简明扼要，字数控制在 20-60 字以内。"
            "绝对不要使用 Markdown 语法（如 **、#、列表符号等），不要输出复杂的表格或代码。"
        )
    }
]


def chat_with_ai(user_input):
    """向大语言模型发送对话并获取文本回复"""
    global conversation_history

    # 添加用户输入到历史中
    conversation_history.append({"role": "user", "content": user_input})

    # 限制记忆长度，防止低配电脑负担过重
    if len(conversation_history) > MAX_HISTORY:
        # 保留系统提示词，移除最早的一轮对话
        conversation_history = [conversation_history[0]] + conversation_history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=conversation_history,
            temperature=0.7
        )
        reply = response.choices[0].message.content

        # 将 AI 的回复记录到历史，以便下次对话时保持连贯性
        conversation_history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"\n[错误] 获取 AI 回复失败: {e}")
        return None


def text_to_speech_and_play(text):
    """调用 TTS API 并在内存中直接播放音频"""
    try:
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=VOICE_NAME,
            input=text,
            response_format="mp3"
        )

        # 将二进制音频流读入内存，不写入硬盘，优化低配 I/O
        audio_data = io.BytesIO(response.content)
        pygame.mixer.music.load(audio_data)
        pygame.mixer.music.play()

        # 等待音频播放完毕，期间释放 CPU
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as e:
        print(f"\n[错误] 语音合成或播放失败: {e}")


# ==================== 主程序入口 ====================
if __name__ == "__main__":
    print("==============================================")
    print("   🚀 专属云端 AI 语音对话助手（轻量优化版）已启动")
    print("   提示：当前使用云端大模型与官方 TTS，对本地配置无要求")
    print("   输入 'q' 或 'exit' 可退出程序")
    print("==============================================")

    while True:
        try:
            user_input = input("\n👤 你: ")
            if user_input.strip().lower() in ['q', 'exit']:
                print("👋 再见！")
                break

            if not user_input.strip():
                continue

            print("🤖 AI 正在思考...", end="\r")
            # 1. 获取文本回复
            ai_reply = chat_with_ai(user_input)

            if ai_reply:
                # 清除"正在思考"的提示，并打印回复
                print(" " * 20, end="\r")
                print(f"🤖 AI: {ai_reply}")

                # 2. 将文本转为语音并播放
                text_to_speech_and_play(ai_reply)

        except KeyboardInterrupt:
            print("\n👋 程序被强制终止。")
            break
