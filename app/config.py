# -*- coding: utf-8 -*-
"""IntelliDesk 全局配置

使用 pydantic-settings 管理配置，支持 .env 文件和环境变量自动加载。
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


# 项目根目录固定为 app/ 的上级目录，不依赖运行时 cwd
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
ENV_FILE: str = str(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """全局配置"""

    # ================== 服务器 ====================
    HOST: str = Field("0.0.0.0", description="服务监听地址")
    PORT: int = Field(8000, description="服务端口")

    # ================== DeepSeek LLM ====================
    DEEPSEEK_API_KEY: str = Field(..., description="DeepSeek API 密钥")
    DEEPSEEK_BASE_URL: str = Field(
        "https://api.deepseek.com", description="DeepSeek API 地址"
    )
    DEEPSEEK_MODEL_NAME: str = Field(
        "deepseek-chat", description="DeepSeek 模型名称"
    )

    # ================== Embedding ====================
    EMBEDDING_MODEL_NAME: str = Field(
        "text-embedding-3-small", description="Embedding 模型名"
    )
    EMBEDDING_API_KEY: str = Field("", description="Embedding 模型 API Key")
    EMBEDDING_BASE_URL: str = Field(
        "https://api.deepseek.com", description="Embedding 模型 API 地址"
    )

    # ================== RAG ====================
    CHROMA_PERSIST_DIR: str = Field(
        "data/chroma_db", description="ChromaDB 持久化目录"
    )
    CHUNK_SIZE: int = Field(500, description="文档切分块大小")
    CHUNK_OVERLAP: int = Field(50, description="文档切分重叠大小")
    TOP_K_RETRIEVAL: int = Field(3, description="RAG 检索返回数量")

    # ================== Agent ====================
    AGENT_TEMPERATURE: float = Field(0.7, description="Agent LLM 温度")
    AGENT_MAX_ITERATIONS: int = Field(5, description="Agent 最大工具调用轮数")

    model_config = ConfigDict(
        env_file=ENV_FILE,
        env_prefix="",
        case_sensitive=False,
        extra="allow",
    )


# 全局配置单例
settings = Settings()
