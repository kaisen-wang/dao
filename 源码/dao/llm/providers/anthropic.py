"""Anthropic 兼容后端的大模型 Provider。

使用标准库 urllib 直连 Anthropic Messages / Models 接口，
不引入 anthropic 等第三方依赖；填入 API key 后即可直接使用。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from ..base import OnChunk, Provider
from ..factory import register_provider
from ..types import (
    ChatRequest,
    ChatResponse,
    ConfigError,
    ProviderError,
    StreamChunk,
    Usage,
)


@register_provider("anthropic")
class AnthropicProvider(Provider):
    """Anthropic Messages API 的 Provider 实现。"""

    def __init__(self, **config: Any) -> None:
        """读取配置；api_key 缺省时回退到环境变量 ANTHROPIC_API_KEY。"""
        super().__init__(**config)
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ConfigError(
                "Anthropic Provider 缺少 api_key：请传入 api_key 或设置环境变量 ANTHROPIC_API_KEY"
            )
        self.api_key = str(api_key)
        self.base_url = str(config.get("base_url") or "https://api.anthropic.com/v1").rstrip("/")
        self.model = str(config.get("model") or "claude-3-5-haiku-latest")
        self.timeout = float(config.get("timeout") or 120)

    def _请求头(self) -> dict[str, str]:
        """构造带鉴权与版本声明的请求头。"""
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _拆分消息(request: ChatRequest) -> tuple[list[str], list[dict[str, Any]]]:
        """把 system 消息抽到顶层文本列表，其余保留为对话消息。"""
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []
        for msg in request.messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            else:
                messages.append({"role": msg.role, "content": msg.content})
        return system_parts, messages

    def _打开(self, req: urllib.request.Request) -> Any:
        """发起请求，并把 urllib 异常统一转成中文 ProviderError。"""
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise ProviderError(f"Anthropic 请求失败：HTTP {e.code} {body}") from None
        except urllib.error.URLError as e:
            raise ProviderError(f"Anthropic 网络请求失败：{e.reason}") from None
        except Exception as e:  # noqa: BLE001 - 兜底转成中文 ProviderError
            raise ProviderError(f"Anthropic 请求异常：{e}") from None

    @staticmethod
    def _解析响应(raw: dict[str, Any], request: ChatRequest) -> ChatResponse:
        """把 Anthropic 的非流式 JSON 响应解析为统一 ChatResponse。"""
        blocks = raw.get("content") or []
        content = "".join(str(block.get("text") or "") for block in blocks if isinstance(block, dict))
        usage_raw = raw.get("usage") or {}
        prompt_tokens = int(usage_raw.get("input_tokens") or 0)
        completion_tokens = int(usage_raw.get("output_tokens") or 0)
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return ChatResponse(
            content=content,
            model=str(raw.get("model") or request.model or ""),
            role="assistant",
            finish_reason=raw.get("stop_reason"),
            usage=usage,
            raw=raw,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话：POST /messages 并解析完整响应。"""
        system_parts, messages = self._拆分消息(request)
        body: dict[str, Any] = {
            "model": request.model or self.model,
            "max_tokens": request.max_tokens or 4096,
            "messages": messages,
            "stream": False,
        }
        if system_parts:
            body["system"] = "\n".join(system_parts)
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/messages",
            data=data,
            headers=self._请求头(),
            method="POST",
        )
        with self._打开(req) as response:
            raw = json.loads(response.read().decode("utf-8"))
        return self._解析响应(raw, request)

    @staticmethod
    def _响应行(response: Any) -> Iterator[str]:
        """逐行产出解码后的响应文本，兼容字节行与字符串行。"""
        for raw_line in response:
            if isinstance(raw_line, bytes):
                yield raw_line.decode("utf-8", errors="replace")
            else:
                yield str(raw_line)

    @classmethod
    def _解析事件(cls, response: Any) -> Iterator[tuple[str | None, dict[str, Any]]]:
        """解析 Anthropic SSE，产出 ``(事件名, data 字典)``，跳过非法行。"""
        event_name: str | None = None
        for line in cls._响应行(response):
            line = line.rstrip("\r\n")
            if not line or line.startswith(":"):
                continue  # 忽略空行与注释行
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
                continue
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if not payload:
                continue
            try:
                data = json.loads(payload)
            except (ValueError, TypeError):
                continue  # 单条解析失败的行跳过，不影响整体流
            if isinstance(data, dict):
                yield event_name, data
            event_name = None

    def chat_stream(self, request: ChatRequest, on_chunk: OnChunk) -> ChatResponse:
        """流式对话：解析 SSE 增量并逐块回调，返回累积结果。"""
        system_parts, messages = self._拆分消息(request)
        body: dict[str, Any] = {
            "model": request.model or self.model,
            "max_tokens": request.max_tokens or 4096,
            "messages": messages,
            "stream": True,
        }
        if system_parts:
            body["system"] = "\n".join(system_parts)
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/messages",
            data=data,
            headers=self._请求头(),
            method="POST",
        )

        pieces: list[str] = []
        events: list[dict[str, Any]] = []
        finish_reason: str | None = None
        model = request.model or self.model
        prompt_tokens = 0
        completion_tokens = 0
        stopped = False

        with self._打开(req) as response:
            for event_name, data_event in self._解析事件(response):
                event_type = data_event.get("type") or event_name
                if event_type == "content_block_delta":
                    piece = (data_event.get("delta") or {}).get("text") or ""
                    if piece:
                        pieces.append(piece)
                        if on_chunk(StreamChunk(content=piece, raw=data_event)) is False:
                            stopped = True
                elif event_type == "message_start":
                    message = data_event.get("message") or {}
                    if message.get("model"):
                        model = str(message["model"])
                    prompt_tokens = int((message.get("usage") or {}).get("input_tokens") or 0)
                elif event_type == "message_delta":
                    reason = (data_event.get("delta") or {}).get("stop_reason")
                    if reason:
                        finish_reason = reason
                    completion_tokens = int((data_event.get("usage") or {}).get("output_tokens") or 0)
                elif event_type == "message_stop":
                    break
                events.append(data_event)
                if stopped:
                    break

        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return ChatResponse(
            content="".join(pieces),
            model=model,
            finish_reason=finish_reason,
            usage=usage,
            raw={"events": events},
        )

    def list_models(self) -> list[str]:
        """GET /models，返回可用模型 id 列表。"""
        req = urllib.request.Request(
            f"{self.base_url}/models",
            headers=self._请求头(),
            method="GET",
        )
        with self._打开(req) as response:
            raw = json.loads(response.read().decode("utf-8"))
        return [str(item["id"]) for item in raw.get("data", []) if "id" in item]
