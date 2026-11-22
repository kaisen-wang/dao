"""远程 Provider（OpenAI / Anthropic）工具调用能力的单元测试。

全程用 unittest.mock.patch 拦截 urllib.request.urlopen，绝不发起真实网络请求。
覆盖请求体拼装、响应归一化、无 tools 委托、多工具调用、参数解析与异常降级。
"""

import io
import json
import os
import sys
import urllib.error
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dao.llm import (
    ChatRequest,
    ChatResponse,
    ConfigError,
    ProviderError,
    ToolDefinition,
    system,
    user,
)
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


def _查询天气工具() -> dict:
    """构造一个 OpenAI 风格的 function tool 字典。"""
    return ToolDefinition(
        name="查询天气",
        description="查询指定城市的天气",
        parameters={
            "type": "object",
            "properties": {"城市": {"type": "string", "description": "城市名"}},
            "required": ["城市"],
        },
    ).to_dict()


def _另一个工具() -> dict:
    """构造第二个 OpenAI 风格工具，用于多工具调用场景。"""
    return ToolDefinition(name="生成报告", description="根据数据生成报告").to_dict()


# ------------------------------ OpenAI ------------------------------


def test_openai_工具请求体拼装():
    """tools 原样透传、tool_choice=auto，且保留原有 URL/鉴权/消息结构。"""
    provider = OpenAIProvider(api_key="sk-test")
    工具 = _查询天气工具()
    request = ChatRequest(
        messages=[system("你是助手"), user("北京天气")],
        tools=[工具],
        temperature=0.3,
    )
    payload = {
        "choices": [{"message": {"role": "assistant", "content": ""}, "finish_reason": "tool_calls"}],
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))) as mock:
        provider.chat_with_tools(request)

    req = mock.call_args.args[0]
    assert req.full_url == "https://api.openai.com/v1/chat/completions"
    assert req.get_method() == "POST"
    assert req.get_header("Authorization") == "Bearer sk-test"
    body = json.loads(req.data.decode("utf-8"))
    assert body["tools"] == [工具]
    assert body["tool_choice"] == "auto"
    assert body["stream"] is False
    assert body["temperature"] == 0.3
    assert body["messages"] == [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "北京天气"},
    ]


def test_openai_工具响应解析():
    """arguments 的 JSON 字符串应解码为 dict，usage/finish_reason/raw 正常填充。"""
    provider = OpenAIProvider(api_key="sk-test")
    payload = {
        "id": "chatcmpl-1",
        "model": "gpt-4o-mini-2024",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "正在查询",
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "查询天气",
                                "arguments": '{"城市": "北京"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))):
        resp = provider.chat_with_tools(ChatRequest(messages=[user("hi")], tools=[_查询天气工具()]))

    assert resp.content == "正在查询"
    assert resp.model == "gpt-4o-mini-2024"
    assert resp.finish_reason == "tool_calls"
    assert resp.usage.prompt_tokens == 10
    assert resp.usage.total_tokens == 15
    assert resp.raw == payload
    assert resp.tool_calls == [
        {"id": "call_abc", "name": "查询天气", "arguments": {"城市": "北京"}}
    ]
    assert resp.to_dict()["工具调用"] == [
        {"编号": "call_abc", "名称": "查询天气", "参数": {"城市": "北京"}}
    ]


def test_openai_多工具调用与缺id兜底():
    """多个 tool_calls 全部保留；缺少 id 时按位置生成 call_N。"""
    provider = OpenAIProvider(api_key="sk-test")
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"function": {"name": "工具甲", "arguments": "{}"}},
                        {"id": "固定编号", "function": {"name": "工具乙", "arguments": "{}"}},
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))):
        resp = provider.chat_with_tools(ChatRequest(messages=[user("hi")], tools=[_查询天气工具()]))

    assert resp.content == ""
    assert resp.tool_calls == [
        {"id": "call_0", "name": "工具甲", "arguments": {}},
        {"id": "固定编号", "name": "工具乙", "arguments": {}},
    ]


def test_openai_参数非法JSON回退空字典():
    """arguments 不是合法 JSON 对象时回退为空字典，原始响应仍保留在 raw。"""
    provider = OpenAIProvider(api_key="sk-test")
    payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"id": "c1", "function": {"name": "工具", "arguments": "不是JSON"}},
                        {"id": "c2", "function": {"name": "工具", "arguments": "[1,2]"}},
                        {"id": "c3", "function": {"name": "工具", "arguments": {"a": 1}}},
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))):
        resp = provider.chat_with_tools(ChatRequest(messages=[user("hi")], tools=[_查询天气工具()]))

    assert [调用["arguments"] for 调用 in resp.tool_calls] == [{}, {}, {"a": 1}]
    assert resp.raw == payload


def test_openai_无tools委托chat():
    """未提供 tools 时应直接委托给 chat，行为完全一致。"""
    provider = OpenAIProvider(api_key="sk-test")
    request = ChatRequest(messages=[user("你好")])
    哨兵 = ChatResponse(content="来自 chat")
    with patch.object(provider, "chat", return_value=哨兵) as mock:
        resp = provider.chat_with_tools(request)
    mock.assert_called_once_with(request)
    assert resp is 哨兵


def test_openai_HTTP错误抛ProviderError():
    """HTTP 错误应转成中文 ProviderError，而不是被吞掉。"""
    provider = OpenAIProvider(api_key="sk-test")
    错误 = urllib.error.HTTPError("http://example.com", 500, "Server Error", {}, None)
    with (
        patch("urllib.request.urlopen", side_effect=错误),
        pytest.raises(ProviderError) as exc,
    ):
        provider.chat_with_tools(ChatRequest(messages=[user("hi")], tools=[_查询天气工具()]))
    assert "500" in str(exc.value)


def test_openai_缺api_key抛ConfigError():
    """未传 api_key 且无环境变量时应抛 ConfigError。"""
    with patch.dict(os.environ, {}, clear=True), pytest.raises(ConfigError):
        OpenAIProvider()


# ----------------------------- Anthropic -----------------------------


def test_anthropic_工具请求体拼装():
    """OpenAI 风格工具应转成 Anthropic 的 name/description/input_schema 结构。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    request = ChatRequest(
        messages=[system("你是助手"), user("北京天气")],
        tools=[_查询天气工具()],
        max_tokens=2048,
    )
    payload = {"content": [], "stop_reason": "end_turn", "usage": {}}
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))) as mock:
        provider.chat_with_tools(request)

    req = mock.call_args.args[0]
    assert req.full_url == "https://api.anthropic.com/v1/messages"
    assert req.get_method() == "POST"
    头 = dict(req.header_items())
    assert 头["X-api-key"] == "sk-ant-test"
    assert 头["Anthropic-version"] == "2023-06-01"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "claude-3-5-haiku-latest"
    assert body["max_tokens"] == 2048
    assert body["system"] == "你是助手"
    assert body["messages"] == [{"role": "user", "content": "北京天气"}]
    assert body["tools"] == [
        {
            "name": "查询天气",
            "description": "查询指定城市的天气",
            "input_schema": {
                "type": "object",
                "properties": {"城市": {"type": "string", "description": "城市名"}},
                "required": ["城市"],
            },
        }
    ]


def test_anthropic_工具响应解析():
    """tool_use 块归一为统一结构，text 块拼接为 content，usage/stop_reason 正确。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    payload = {
        "id": "msg_1",
        "model": "claude-test",
        "content": [
            {"type": "text", "text": "好的，"},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "查询天气",
                "input": {"城市": "上海"},
            },
            {"type": "text", "text": "已提交查询。"},
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 12, "output_tokens": 8},
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))):
        resp = provider.chat_with_tools(
            ChatRequest(messages=[user("hi")], tools=[_查询天气工具()])
        )

    assert resp.content == "好的，已提交查询。"
    assert resp.model == "claude-test"
    assert resp.role == "assistant"
    assert resp.finish_reason == "tool_use"
    assert resp.usage.prompt_tokens == 12
    assert resp.usage.completion_tokens == 8
    assert resp.usage.total_tokens == 20
    assert resp.raw == payload
    assert resp.tool_calls == [
        {"id": "toolu_1", "name": "查询天气", "arguments": {"城市": "上海"}}
    ]
    assert resp.to_dict()["工具调用"] == [
        {"编号": "toolu_1", "名称": "查询天气", "参数": {"城市": "上海"}}
    ]


def test_anthropic_多工具调用与缺id兜底():
    """多个 tool_use 块全部归一；缺少 id 时按出现顺序生成 call_N。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    payload = {
        "content": [
            {"type": "tool_use", "name": "工具甲", "input": {}},
            {"type": "tool_use", "id": "原始编号", "name": "工具乙", "input": {"x": 1}},
        ],
        "stop_reason": "tool_use",
        "usage": {},
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))):
        resp = provider.chat_with_tools(
            ChatRequest(messages=[user("hi")], tools=[_另一个工具()])
        )

    assert resp.content == ""
    assert resp.tool_calls == [
        {"id": "call_0", "name": "工具甲", "arguments": {}},
        {"id": "原始编号", "name": "工具乙", "arguments": {"x": 1}},
    ]


def test_anthropic_工具参数JSON字符串解析():
    """input 为 JSON 字符串时解码为 dict；非对象 json 回退空字典。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    payload = {
        "content": [
            {"type": "tool_use", "id": "c1", "name": "工具", "input": '{"a": 1}'},
            {"type": "tool_use", "id": "c2", "name": "工具", "input": "坏数据"},
            {"type": "tool_use", "id": "c3", "name": "工具", "input": [1, 2]},
        ],
        "usage": {},
    }
    with patch("urllib.request.urlopen", return_value=假响应(json.dumps(payload))):
        resp = provider.chat_with_tools(
            ChatRequest(messages=[user("hi")], tools=[_另一个工具()])
        )

    assert [调用["arguments"] for 调用 in resp.tool_calls] == [{"a": 1}, {}, {}]


def test_anthropic_无tools委托chat():
    """未提供 tools 时应直接委托给 chat，行为完全一致。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    request = ChatRequest(messages=[user("你好")])
    哨兵 = ChatResponse(content="来自 chat")
    with patch.object(provider, "chat", return_value=哨兵) as mock:
        resp = provider.chat_with_tools(request)
    mock.assert_called_once_with(request)
    assert resp is 哨兵


def test_anthropic_HTTP错误抛ProviderError():
    """HTTP 错误应转成中文 ProviderError，而不是被吞掉。"""
    provider = AnthropicProvider(api_key="sk-ant-test")
    错误 = urllib.error.HTTPError("http://example.com", 400, "Bad Request", {}, None)
    with (
        patch("urllib.request.urlopen", side_effect=错误),
        pytest.raises(ProviderError) as exc,
    ):
        provider.chat_with_tools(
            ChatRequest(messages=[user("hi")], tools=[_查询天气工具()])
        )
    assert "400" in str(exc.value)


def test_anthropic_缺api_key抛ConfigError():
    """未传 api_key 且无环境变量时应抛 ConfigError。"""
    with patch.dict(os.environ, {}, clear=True), pytest.raises(ConfigError):
        AnthropicProvider()
