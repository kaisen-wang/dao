"""OpenAI 兼容后端的大模型 Provider。

使用标准库 urllib 直连 OpenAI Chat Completions / Models 接口，
不引入 httpx、openai 等第三方依赖；填入 API key 后即可直接使用。
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


@register_provider("openai")
class OpenAIProvider(Provider):
    """OpenAI 兼容 API 的 Provider 实现。"""

    def __init__(self, **config: Any) -> None:
        """读取配置；api_key 缺省时回退到环境变量 OPENAI_API_KEY。"""
        super().__init__(**config)
        api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ConfigError(
                "OpenAI Provider 缺少 api_key：请传入 api_key 或设置环境变量 OPENAI_API_KEY"
            )
        self.api_key = str(api_key)
        self.base_url = str(config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        self.model = str(config.get("model") or "gpt-4o-mini")
        self.timeout = float(config.get("timeout") or 120)

    def _请求头(self) -> dict[str, str]:
        """构造带鉴权的通用请求头。"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _消息列表(request: ChatRequest) -> list[dict[str, Any]]:
        """把统一消息转换为 OpenAI 的 ``{role, content}`` 结构。"""
        return [{"role": msg.role, "content": msg.content} for msg in request.messages]

    def _打开(self, req: urllib.request.Request) -> Any:
        """发起请求，并把 urllib 异常统一转成中文 ProviderError。"""
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise ProviderError(f"OpenAI 请求失败：HTTP {e.code} {body}") from None
        except urllib.error.URLError as e:
            raise ProviderError(f"OpenAI 网络请求失败：{e.reason}") from None
        except Exception as e:  # noqa: BLE001 - 兜底转成中文 ProviderError
            raise ProviderError(f"OpenAI 请求异常：{e}") from None

    @staticmethod
    def _解析响应(raw: dict[str, Any], request: ChatRequest) -> ChatResponse:
        """把 OpenAI 的非流式 JSON 响应解析为统一 ChatResponse。"""
        choices = raw.get("choices") or []
        first = choices[0] if choices else {}
        message = first.get("message") or {}
        usage_raw = raw.get("usage") or {}
        usage = Usage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
            total_tokens=int(usage_raw.get("total_tokens") or 0),
        )
        return ChatResponse(
            content=str(message.get("content") or ""),
            model=str(raw.get("model") or request.model or ""),
            role=str(message.get("role") or "assistant"),
            finish_reason=first.get("finish_reason"),
            usage=usage,
            raw=raw,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话：POST /chat/completions 并解析完整响应。"""
        body: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": self._消息列表(request),
            "stream": False,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
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

    def chat_stream(self, request: ChatRequest, on_chunk: OnChunk) -> ChatResponse:
        """流式对话：解析 SSE 增量并逐块回调，返回累积结果。"""
        body: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": self._消息列表(request),
            "stream": True,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers=self._请求头(),
            method="POST",
        )

        pieces: list[str] = []
        events: list[dict[str, Any]] = []
        finish_reason: str | None = None
        model = request.model or self.model
        stopped = False

        with self._打开(req) as response:
            for line in self._响应行(response):
                if stopped:
                    break
                line = line.strip()
                # 忽略空行、注释行（以 ':' 开头）与非 data 行。
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                except (ValueError, TypeError):
                    continue  # 单条解析失败的行跳过，不影响整体流
                if not isinstance(event, dict):
                    continue
                events.append(event)
                if event.get("model"):
                    model = str(event["model"])
                choices = event.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
                piece = (choice.get("delta") or {}).get("content") or ""
                if piece:
                    pieces.append(piece)
                    if on_chunk(StreamChunk(content=piece, raw=event)) is False:
                        stopped = True

        return ChatResponse(
            content="".join(pieces),
            model=model,
            finish_reason=finish_reason,
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
