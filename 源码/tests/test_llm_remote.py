"""远程大模型 Provider 的单元测试。

全程用 unittest.mock.patch 拦截 urllib.request.urlopen，绝不发起真实网络请求。
覆盖请求结构、响应解析、流式增量、提前终止与配置/HTTP 异常。
"""

import io
import json
import os
import sys
import urllib.error
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dao.llm import ChatRequest, ConfigError, ProviderError, StreamChunk, system, user
from dao.llm.providers.anthropic import AnthropicProvider
from dao.llm.providers.openai import OpenAIProvider


class 假响应(io.BytesIO):
    """支持上下文管理的假 HTTP 响应，替代真实 urlopen 返回值。"""

    def __init__(self, body: bytes | str, status: int = 200) -> None:
        super().__init__(body.encode("utf-8") if isinstance(body, str) else body)
        self.status = status
        self.headers: dict[str, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def _SSE事件(事件: dict) -> str:
    """把单个事件字典序列化为一行 SSE ``data:`` 文本块。"""
    return "data: " + json.dumps(事件, ensure_ascii=False) + "\n\n"


# ------------------------------ OpenAI ------------------------------


def test_openai_chat成功():
    """校验 URL、鉴权头、请求体结构与响应解析（含 usage / finish_reason）。"""
    provider = OpenAIProvider(api_key="sk-test")
    request = ChatRequest(messages=[system("你是一个助手"), user("你好")], temperature=0.7)
    payload = {
        "id": "chatcmpl-1",
        "model": "gpt-4o-mini-2024",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "你好！"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))) as mock:
        resp = provider.chat(request)

    req = mock.call_args.args[0]
    assert req.full_url == "https://api.openai.com/v1/chat/completions"
    assert req.get_method() == "POST"
    assert req.get_header("Authorization") == "Bearer sk-test"
    assert dict(req.header_items())["Content-type"] == "application/json"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "gpt-4o-mini"
    assert body["messages"] == [
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好"},
    ]
    assert body["stream"] is False
    assert body["temperature"] == 0.7

    assert resp.content == "你好！"
    assert resp.model == "gpt-4o-mini-2024"
    assert resp.role == "assistant"
    assert resp.finish_reason == "stop"
    assert resp.usage.prompt_tokens == 10
    assert resp.usage.completion_tokens == 5
    assert resp.usage.total_tokens == 15
    assert resp.raw == payload


def test_openai缺api_key():
    """未传 api_key 且无环境变量时应抛 ConfigError。"""
    with patch.dict(os.environ, {}, clear=True), pytest.raises(ConfigError):
        OpenAIProvider()


def test_openai环境变量兜底api_key():
    """api_key 缺省时从 OPENAI_API_KEY 环境变量读取。"""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env"}):
        assert OpenAIProvider().api_key == "sk-env"


def test_openai_HTTP401抛ProviderError():
    """HTTP 401 应转成中文 ProviderError，消息含状态码。"""
    provider = OpenAIProvider(api_key="sk-test")
    err = urllib.error.HTTPError("http://example.com", 401, "Unauthorized", {}, None)
    with patch("urllib.request.urlopen", side_effect=err), pytest.raises(ProviderError) as exc:
        provider.chat(ChatRequest(messages=[user("hi")]))
    assert "401" in str(exc.value)


def test_openai_chat_stream多行解析与累积():
    """SSE 多行/注释/坏行应被正确处理，增量累积为全文。"""
    provider = OpenAIProvider(api_key="sk-test")
    request = ChatRequest(messages=[user("写首诗")])
    sse = (
        ": 这是注释行\n\n"
        + _SSE事件({"choices": [{"delta": {"content": "春"}}]})
        + "data: {不是合法JSON}\n\n"
        + _SSE事件({"choices": [{"delta": {"content": "眠"}}]})
        + _SSE事件({"choices": [{"delta": {"content": "不觉晓"}, "finish_reason": "stop"}]})
        + "data: [DONE]\n\n"
    )
    seen: list[str] = []

    def on_chunk(chunk: StreamChunk) -> bool:
        seen.append(chunk.content)
        return True

    with patch("urllib.request.urlopen", return_value=假响应(sse)) as mock:
        resp = provider.chat_stream(request, on_chunk)

    req = mock.call_args.args[0]
    body = json.loads(req.data.decode("utf-8"))
    assert req.full_url == "https://api.openai.com/v1/chat/completions"
    assert body["stream"] is True
    assert seen == ["春", "眠", "不觉晓"]
    assert resp.content == "春眠不觉晓"
    assert resp.finish_reason == "stop"
    assert len(resp.raw["events"]) == 3


def test_openai_chat_stream回调False提前终止():
    """回调返回 False 后应停止读取，仅保留已收到的增量。"""
    provider = OpenAIProvider(api_key="sk-test")
    sse = (
        _SSE事件({"choices": [{"delta": {"content": "第一段"}}]})
        + _SSE事件({"choices": [{"delta": {"content": "第二段"}}]})
        + "data: [DONE]\n\n"
    )
    seen: list[str] = []

    def on_chunk(chunk: StreamChunk) -> bool:
        seen.append(chunk.content)
        return False

    with patch("urllib.request.urlopen", return_value=假响应(sse)):
        resp = provider.chat_stream(ChatRequest(messages=[user("hi")]), on_chunk)

    assert seen == ["第一段"]
    assert resp.content == "第一段"


def test_openai_list_models():
    """GET /models 应解析出 data[*].id。"""
    provider = OpenAIProvider(api_key="sk-test", base_url="https://example.com/v1")
    payload = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))) as mock:
        models = provider.list_models()

    req = mock.call_args.args[0]
    assert req.full_url == "https://example.com/v1/models"
    assert req.get_method() == "GET"
    assert models == ["gpt-4o", "gpt-4o-mini"]


# ----------------------------- Anthropic -----------------------------


def test_anthropic_chat成功():
    """校验 x-api-key / anthropic-version 头、system 抽取与响应解析。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    request = ChatRequest(
        messages=[system("你是一个助手"), user("你好")],
        max_tokens=2048,
    )
    payload = {
        "id": "msg_1",
        "model": "claude-3-5-haiku-latest",
        "content": [
            {"type": "text", "text": "你好，"},
            {"type": "text", "text": "很高兴见到你。"},
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 12, "output_tokens": 8},
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))) as mock:
        resp = provider.chat(request)

    req = mock.call_args.args[0]
    assert req.full_url == "https://api.anthropic.com/v1/messages"
    assert req.get_method() == "POST"
    assert dict(req.header_items())["X-api-key"] == "sk-ant-test"
    assert dict(req.header_items())["Anthropic-version"] == "2023-06-01"
    assert dict(req.header_items())["Content-type"] == "application/json"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "claude-3-5-haiku-latest"
    assert body["max_tokens"] == 2048
    assert body["messages"] == [{"role": "user", "content": "你好"}]
    assert body["system"] == "你是一个助手"
    assert body["stream"] is False

    assert resp.content == "你好，很高兴见到你。"
    assert resp.model == "claude-3-5-haiku-latest"
    assert resp.role == "assistant"
    assert resp.finish_reason == "end_turn"
    assert resp.usage.prompt_tokens == 12
    assert resp.usage.completion_tokens == 8
    assert resp.usage.total_tokens == 20
    assert resp.raw == payload


def test_anthropic缺api_key():
    """未传 api_key 且无环境变量时应抛 ConfigError。"""
    with patch.dict(os.environ, {}, clear=True), pytest.raises(ConfigError):
        AnthropicProvider()


def test_anthropic_HTTP400抛ProviderError():
    """HTTP 错误应转成中文 ProviderError，消息含状态码。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    err = urllib.error.HTTPError("http://example.com", 400, "Bad Request", {}, None)
    with patch("urllib.request.urlopen", side_effect=err), pytest.raises(ProviderError) as exc:
        provider.chat(ChatRequest(messages=[user("hi")]))
    assert "400" in str(exc.value)


def test_anthropic_chat_stream增量解析():
    """content_block_delta 的 delta.text 应作为增量逐块回调并累积。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    sse = (
        "event: message_start\n"
        + "data: " + json.dumps({"type": "message_start", "message": {
            "model": "claude-test", "usage": {"input_tokens": 7}}}) + "\n\n"
        + "event: content_block_delta\n"
        + "data: " + json.dumps({"type": "content_block_delta", "delta": {"text": "你"}}) + "\n\n"
        + "data: " + json.dumps({"type": "content_block_delta", "delta": {"text": "好"}}) + "\n\n"
        + "event: message_delta\n"
        + "data: " + json.dumps({"type": "message_delta", "delta": {"stop_reason": "end_turn"},
                                  "usage": {"output_tokens": 3}}) + "\n\n"
        + "event: message_stop\ndata: " + json.dumps({"type": "message_stop"}) + "\n\n"
    )
    seen: list[str] = []

    def on_chunk(chunk: StreamChunk) -> bool:
        seen.append(chunk.content)
        return True

    with patch("urllib.request.urlopen", return_value=假响应(sse)) as mock:
        resp = provider.chat_stream(ChatRequest(messages=[user("hi")]), on_chunk)

    req = mock.call_args.args[0]
    body = json.loads(req.data.decode("utf-8"))
    assert body["stream"] is True
    assert body["max_tokens"] == 4096
    assert seen == ["你", "好"]
    assert resp.content == "你好"
    assert resp.finish_reason == "end_turn"
    assert resp.model == "claude-test"
    assert resp.usage.prompt_tokens == 7
    assert resp.usage.completion_tokens == 3


def test_anthropic_chat_stream回调False提前终止():
    """回调返回 False 后应停止读取，仅保留已收到的增量。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    sse = (
        "event: content_block_delta\n"
        + "data: " + json.dumps({"type": "content_block_delta", "delta": {"text": "第一段"}}) + "\n\n"
        + "event: content_block_delta\n"
        + "data: " + json.dumps({"type": "content_block_delta", "delta": {"text": "第二段"}}) + "\n\n"
    )
    seen: list[str] = []

    def on_chunk(chunk: StreamChunk) -> bool:
        seen.append(chunk.content)
        return False

    with patch("urllib.request.urlopen", return_value=假响应(sse)):
        resp = provider.chat_stream(ChatRequest(messages=[user("hi")]), on_chunk)

    assert seen == ["第一段"]
    assert resp.content == "第一段"


def test_anthropic_list_models():
    """GET /models 应解析出 data[*].id。"""
    provider = AnthropicProvider(api_key="sk-ant-test", base_url="https://example.com/v1")
    payload = {"data": [{"id": "claude-3-5-haiku-latest"}, {"id": "claude-3-7-sonnet-latest"}]}
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))) as mock:
        models = provider.list_models()

    req = mock.call_args.args[0]
    assert req.full_url == "https://example.com/v1/models"
    assert req.get_method() == "GET"
    assert dict(req.header_items())["X-api-key"] == "sk-ant-test"
    assert models == ["claude-3-5-haiku-latest", "claude-3-7-sonnet-latest"]
