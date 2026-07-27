# -*- coding: utf-8 -*-
"""测试 DeepSeek API 是否能正常调用

使用方式：
    1. 复制 .env.example 为 .env，填入你的 DEEPSEEK_API_KEY
    2. 运行：python test_llm.py

预期输出：
    ✅ DeepSeek API 连接成功！
    🤖 模型回复：你好！我是 DeepSeek Chat...
"""

import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

# ── 读取配置 ──────────────────────────────────────────────────
API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

if not API_KEY or API_KEY == "your_api_key_here":
    print("❌ 请先在 .env 文件中填入 DEEPSEEK_API_KEY")
    print("   复制 .env.example → .env，然后填入你的密钥")
    sys.exit(1)

# ── 测试调用 ──────────────────────────────────────────────────
print(f"🔗 连接地址: {BASE_URL}")
print(f"🧠 模型: {MODEL_NAME}")
print("⏳ 正在测试连接...\n")

try:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "你是一个智能客服助手。请用中文回复。"},
            {"role": "user", "content": "你好，请用一句话介绍你自己。"},
        ],
        temperature=0.7,
        max_tokens=200,
        timeout=60,
    )

    reply = response.choices[0].message.content
    print("✅ DeepSeek API 连接成功！\n")
    print(f"🤖 模型回复：{reply}\n")
    print(f"📊 Token 用量：{response.usage}")

except Exception as e:
    print(f"❌ 连接失败：{e}")
    print("\n可能原因：")
    print("  1. API Key 不正确")
    print("  2. 网络无法访问 api.deepseek.com（可能需要代理）")
    print("  3. 账户余额不足")
    sys.exit(1)
