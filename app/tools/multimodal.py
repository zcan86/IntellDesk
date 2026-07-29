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

_vlm_client: OpenAI | None = None
_embedding_client: OpenAI | None = None


def _get_vlm_client() -> OpenAI:
    """VLM 图片识别客户端（阿里百炼优先，硅基流动兜底）"""
    global _vlm_client
    if _vlm_client is None:
        if settings.VLM_API_KEY:
            # 用户配置了 VLM Key → 用阿里百炼
            _vlm_client = OpenAI(
                api_key=settings.VLM_API_KEY,
                base_url=settings.VLM_BASE_URL,
            )
            logger.info("VLM: 阿里百炼模式")
        else:
            # 未配置 → 用硅基流动兜底
            _vlm_client = OpenAI(
                api_key=settings.EMBEDDING_API_KEY,
                base_url=settings.EMBEDDING_BASE_URL,
            )
            logger.info("VLM: 硅基流动模式（VL模型可能不可用，建议配置 VLM_API_KEY）")
    return _vlm_client


def _get_embedding_client() -> OpenAI:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAI(
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
        )
    return _embedding_client


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
        client = _get_vlm_client()

        # 根据配置选择模型：有 VLM_API_KEY → 阿里百炼 qwen-vl-max，否则硅基流动 VLM
        if settings.VLM_API_KEY:
            vlm_models = [settings.VLM_MODEL_NAME]  # 阿里百炼: qwen-vl-max
        else:
            vlm_models = [
                "Qwen/Qwen2.5-VL-72B-Instruct",
                "Qwen/Qwen2-VL-72B-Instruct",
            ]  # 硅基流动（可能被禁用）
        if not image_path.startswith("http"):
            p = Path(image_path)
            if not p.exists():
                return "图片文件不存在，请重新上传。"
            with open(p, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            img_url = f"data:image/jpeg;base64,{img_b64}"
        else:
            img_url = image_path

        # 尝试 VLM 模型列表
        last_error = ""
        for model_name in vlm_models:
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": img_url}},
                            {"type": "text", "text": "请识别这张图片中的商品信息。返回商品名称、品类、主要特征。如果图片中没有商品请说明。"},
                        ],
                    }],
                    max_tokens=300,
                    timeout=20,
                )
                logger.info(f"VLM 模型: {model_name}")
                return resp.choices[0].message.content.strip()
            except Exception as e:
                last_error = str(e)[:100]
                continue

        # 所有 VLM 不可用 → 降级
        logger.warning(f"所有 VLM 模型不可用: {last_error}")
        return (
            "[图片识别暂不可用] 我已收到你上传的图片，但视觉模型当前不可用。\n"
            "请用文字描述图片内容（如：这是一双Nike运动鞋，白色款），我会根据你的描述来帮你。"
        )

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

        client = _get_embedding_client()
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
