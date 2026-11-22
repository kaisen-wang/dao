"""大模型接口层：统一的 Provider 抽象与数据模型。

为「常驻研发协作 Agent」提供与后端无关的大模型调用契约。当前内置
Ollama 实现，后续可平滑接入 OpenAI / Anthropic，业务层无需改动。
"""

from .base import Provider
from .factory import available_providers, create_provider, register_provider
from .types import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConfigError,
    LLMError,
    ProviderError,
    StreamChunk,
    ToolCall,
    ToolDefinition,
    UnsupportedError,
    Usage,
    assistant,
    system,
    user,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ConfigError",
    "LLMError",
    "Provider",
    "ProviderError",
    "StreamChunk",
    "ToolCall",
    "ToolDefinition",
    "UnsupportedError",
    "Usage",
    "assistant",
    "available_providers",
    "create_provider",
    "register_provider",
    "system",
    "user",
]
