"""Provider 工厂与注册表：按名称创建后端实例。"""

from __future__ import annotations

from typing import Any

from .base import Provider
from .types import ConfigError

_Providers: dict[str, type[Provider]] = {}


def register_provider(name: str):
    """注册 Provider 类的装饰器。

    用法：``@register_provider("ollama") class OllamaProvider(Provider): ...``
    """

    def decorator(cls: type[Provider]) -> type[Provider]:
        _Providers[name] = cls
        cls.name = name
        return cls

    return decorator


def _ensure_providers() -> None:
    """惰性导入内置 Provider 以触发自注册，避免模块级循环导入。"""
    from . import providers  # noqa: F401


def create_provider(name: str, **config: Any) -> Provider:
    """按名称创建 Provider 实例。

    名称不存在时抛 ``ConfigError``，并列出生效的可用名称。
    """
    _ensure_providers()
    cls = _Providers.get(name)
    if cls is None:
        available = ", ".join(available_providers()) or "（无）"
        raise ConfigError(f"未知的大模型提供者：{name}；可用提供者：{available}")
    return cls(**config)


def available_providers() -> list[str]:
    """返回已注册的 Provider 名称列表（排序后）。"""
    _ensure_providers()
    return sorted(_Providers)
