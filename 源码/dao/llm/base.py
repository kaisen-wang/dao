"""Provider 抽象基类：定义所有大模型后端必须实现的统一契约。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .types import ChatRequest, ChatResponse, StreamChunk, UnsupportedError

# 回调签名：收到一个增量块，返回 False 表示调用方希望提前终止流。
OnChunk = Callable[[StreamChunk], bool | None]


class Provider(ABC):
    """大模型 Provider 的统一接口。

    子类通过 ``register_provider`` 装饰器注册到工厂；构造参数由各 Provider
    自行定义（如 Ollama 的 host / model）。
    """

    name: str = "base"

    def __init__(self, **config: Any) -> None:
        self.config = config

    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话，返回完整响应。"""

    @abstractmethod
    def chat_stream(self, request: ChatRequest, on_chunk: OnChunk) -> ChatResponse:
        """流式对话：逐块回调 ``on_chunk``，返回累积后的完整响应。

        回调返回 ``False`` 时应停止读取并立即返回已累积的内容。
        """

    @abstractmethod
    def list_models(self) -> list[str]:
        """列出当前后端可用的模型名。"""

    def chat_with_tools(self, request: ChatRequest) -> ChatResponse:
        """工具调用（预留扩展点）；默认不支持。"""
        raise UnsupportedError(f"Provider {self.name} 不支持工具调用")
