# -*- coding: utf-8 -*-
"""多模态工具：图片识别 + 语音转文字

图片识别: SiliconFlow Qwen2.5-VL-72B（复用 EMBEDDING_API_KEY）
语音转文字: 暂用文本兜底，后续接 Whisper API
"""

import base64
from pathlib import Path
from openai import OpenAI
from langchain.tools import tool
from loguru import logger
from app.config import settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
        )
    return _client


@tool
def recognize_image(image_path: str) -> str:
    """识别图片中的商品信息。

    当用户上传图片询问商品相关问题时调用。
    例如：上传一张运动鞋照片 → 返回品牌、型号、品类

    Args:
        image_path: 图片文件路径或 URL
    """
    logger.info(f"图片识别: {image_path[:80]}...")

    try:
        client = _get_client()

        # 如果是本地文件，转 base64
        if not image_path.startswith("http"):
            p = Path(image_path)
            if not p.exists():
                return "图片文件不存在，请重新上传。"
            with open(p, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            img_url = f"data:image/jpeg;base64,{img_b64}"
        else:
            img_url = image_path

        resp = client.chat.completions.create(
            model="Qwen/Qwen2.5-VL-72B-Instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": img_url}},
                    {"type": "text", "text": (
                        "请识别这张图片中的商品信息。返回：\n"
                        "1. 商品名称/品牌\n"
                        "2. 品类（如运动鞋/手机/T恤等）\n"
                        "3. 主要特征（颜色/材质/型号等）\n"
                        "如果图片中没有商品，请说明。"
                    )},
                ],
            }],
            max_tokens=500,
            timeout=30,
        )
        return resp.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"图片识别失败: {e}")
        return f"图片识别失败: {str(e)[:200]}"


@tool
def transcribe_audio(audio_path: str) -> str:
    """将语音转为文字。

    当用户发送语音消息时调用。

    Args:
        audio_path: 音频文件路径
    """
    logger.info(f"语音转文字: {audio_path[:80]}...")

    try:
        p = Path(audio_path)
        if not p.exists():
            return "音频文件不存在，请重新上传。"

        client = _get_client()
        with open(p, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        return resp.text.strip()

    except Exception as e:
        # Whisper 可能不可用，返回友好提示
        logger.error(f"语音识别失败: {e}")
        return f"[语音识别暂不可用] 请用文字描述你的需求。原始错误: {str(e)[:100]}"


# ── 上传处理 ──────────────────────────────────────────────────

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(file_bytes: bytes, filename: str) -> str:
    """保存上传文件，返回路径"""
    safe_name = f"{Path(filename).stem}_{hash(filename) % 10000}{Path(filename).suffix}"
    filepath = UPLOAD_DIR / safe_name
    filepath.write_bytes(file_bytes)
    return str(filepath)
