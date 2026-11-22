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


def _解析工具参数(arguments: Any) -> dict[str, Any]:
    """把工具调用参数归一为字典：字典原样返回，JSON 字符串解码，失败回退空字典。"""
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str) and arguments.strip():
        try:
            结果 = json.loads(arguments)
        except (ValueError, TypeError):
            return {}
        return 结果 if isinstance(结果, dict) else {}
    return {}


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
        """把 system 抽到顶层，并把工具上下文转成 Anthropic 的 content 块。

        assistant 的 tool_calls 转成 ``tool_use`` 块；role=tool 的消息转成
        user 消息中的 ``tool_result`` 块，以满足多轮工具对话的协议要求。
        """
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []
        for msg in request.messages:
            if msg.role == "system":
                system_parts.append(msg.content)
                continue
            if msg.role == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id or "",
                                "content": msg.content,
                            }
                        ],
                    }
                )
                continue
            if not msg.tool_calls:
                # 普通消息保持字符串格式，与既有请求体兼容。
                messages.append({"role": msg.role, "content": msg.content})
                continue
            内容: list[dict[str, Any]] = []
            if msg.content:
                内容.append({"type": "text", "text": msg.content})
            for 调用 in msg.tool_calls:
                内容.append(
                    {
                        "type": "tool_use",
                        "id": 调用.get("id", ""),
                        "name": 调用.get("name", ""),
                        "input": 调用.get("arguments", {}),
                    }
                )
            messages.append({"role": msg.role, "content": 内容})
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

    @staticmethod
    def _转工具定义(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """把 OpenAI 风格 tool 字典转成 Anthropic 的 name/input_schema 定义。"""
        结果: list[dict[str, Any]] = []
        for 工具 in tools:
            if not isinstance(工具, dict):
                continue
            函数 = 工具.get("function") or {}
            if not isinstance(函数, dict):
                continue
            名称 = str(函数.get("name") or "")
            if not 名称:
                continue
            结果.append(
                {
                    "name": 名称,
                    "description": str(函数.get("description") or ""),
                    "input_schema": 函数.get("parameters") or {},
                }
            )
        return 结果

    @staticmethod
    def _解析工具响应(raw: dict[str, Any], request: ChatRequest) -> ChatResponse:
        """把含 tool_use 内容块的 Anthropic 响应归一为统一 ChatResponse。"""
        blocks = raw.get("content") or []
        文本片段: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for 块 in blocks:
            if not isinstance(块, dict):
                continue
            类型 = 块.get("type")
            if 类型 == "tool_use":
                tool_calls.append(
                    {
                        "id": str(块.get("id") or f"call_{len(tool_calls)}"),
                        "name": str(块.get("name") or ""),
                        "arguments": _解析工具参数(块.get("input")),
                    }
                )
            elif 类型 == "text":
                文本片段.append(str(块.get("text") or ""))
        usage_raw = raw.get("usage") or {}
        prompt_tokens = int(usage_raw.get("input_tokens") or 0)
        completion_tokens = int(usage_raw.get("output_tokens") or 0)
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return ChatResponse(
            content="".join(文本片段),
            model=str(raw.get("model") or request.model or ""),
            role="assistant",
            finish_reason=raw.get("stop_reason"),
            tool_calls=tool_calls,
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

    def chat_with_tools(self, request: ChatRequest) -> ChatResponse:
        """工具调用对话：把 tools 转成 Anthropic 风格并归一化 tool_use 响应。

        无 tools 时与 ``chat`` 行为一致（直接委托），保证向后兼容。
        """
        if not request.tools:
            return self.chat(request)
        system_parts, messages = self._拆分消息(request)
        body: dict[str, Any] = {
            "model": request.model or self.model,
            "max_tokens": request.max_tokens or 4096,
            "messages": messages,
            "stream": False,
            "tools": self._转工具定义(request.tools),
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
        return self._解析工具响应(raw, request)

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
