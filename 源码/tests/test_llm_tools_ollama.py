"""OllamaProvider.chat_with_tools 工具调用单元测试。

全部通过 ``unittest.mock.patch`` 拦截 ``urllib.request.urlopen``，
不依赖真实 Ollama 服务，也不产生任何网络流量。
"""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.llm.providers.ollama import OllamaProvider
from dao.llm.types import ChatMessage, ChatRequest, ProviderError, ToolDefinition

_拦截地址 = "dao.llm.providers.ollama.urllib.request.urlopen"


class 假响应:
    """最小 HTTP 响应替身，支持 read/status/close。"""

    def __init__(self, body: bytes = b"", status: int = 200):
        self.body = body
        self.status = status
        self.closed = False

    def read(self) -> bytes:
        """返回完整响应体。"""
        return self.body

    def close(self) -> None:
        """记录关闭动作。"""
        self.closed = True


def 构造请求(**覆盖: object) -> ChatRequest:
    """构造一条单轮对话请求。"""
    return ChatRequest(messages=[ChatMessage(role="user", content="查天气")], **覆盖)


def 构造工具(**覆盖: object) -> list[dict]:
    """构造一个 OpenAI 风格 tool 字典列表。"""
    参数 = {
        "type": "object",
        "properties": {"城市": {"type": "string", "description": "城市名"}},
        "required": ["城市"],
    }
    return [
        {
            "type": "function",
            "function": {
                "name": "查天气",
                "description": "查询指定城市的天气",
                "parameters": 参数,
                **覆盖,
            },
        }
    ]


def 构造工具响应(**覆盖: object) -> bytes:
    """构造一个带 tool_calls 的典型 /api/chat 响应体。"""
    数据: dict[str, object] = {
        "model": "gemma4:e4b",
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_abc",
                    "function": {"name": "查天气", "arguments": {"城市": "深圳"}},
                }
            ],
        },
        "prompt_eval_count": 20,
        "eval_count": 8,
        "total_duration": 5000,
        "done": True,
        "done_reason": "tool_calls",
    }
    数据.update(覆盖)
    return json.dumps(数据, ensure_ascii=False).encode("utf-8")


def test_工具请求体正确携带tools并保留tool消息字段():
    """请求体 stream=False、tools 原样传递，且 tool 消息的调用编号保留。"""
    工具 = 构造工具()
    请求 = ChatRequest(
        messages=[
            ChatMessage(role="user", content="查天气"),
            ChatMessage(role="assistant", content="", tool_calls=[{"id": "call_abc"}]),
            ChatMessage(role="tool", content="晴", tool_call_id="call_abc"),
        ],
        tools=工具,
    )
    响应对象 = 假响应(body=构造工具响应())
    with patch(_拦截地址, return_value=响应对象) as 模拟:
        OllamaProvider().chat_with_tools(请求)

    请求对象 = 模拟.call_args[0][0]
    assert 请求对象.full_url == "http://localhost:11434/api/chat"
    assert 请求对象.get_method() == "POST"
    请求体 = json.loads(请求对象.data)
    assert 请求体["tools"] == 工具
    assert 请求体["stream"] is False
    assert 请求体["messages"][0] == {"role": "user", "content": "查天气"}
    assert 请求体["messages"][1]["tool_calls"] == [{"id": "call_abc"}]
    assert 请求体["messages"][2]["tool_call_id"] == "call_abc"
    assert 响应对象.closed is True


def test_ToolDefinition字典可直接作为tools传入():
    """ToolDefinition.to_dict() 的产物被原样塞入请求体 tools 字段。"""
    工具 = ToolDefinition(name="查天气", description="查询天气", parameters={"type": "object"}).to_dict()
    响应对象 = 假响应(body=构造工具响应())
    with patch(_拦截地址, return_value=响应对象) as 模拟:
        OllamaProvider().chat_with_tools(构造请求(tools=[工具]))
    请求体 = json.loads(模拟.call_args[0][0].data)
    assert 请求体["tools"] == [工具]


def test_有tool_calls响应_归一解析全部字段():
    """带 id 的 tool call 正确归一，同时解析内容、模型、用量与原始响应。"""
    响应对象 = 假响应(body=构造工具响应())
    with patch(_拦截地址, return_value=响应对象):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))

    assert 结果.tool_calls == [
        {"id": "call_abc", "name": "查天气", "arguments": {"城市": "深圳"}}
    ]
    assert 结果.content == ""
    assert 结果.model == "gemma4:e4b"
    assert 结果.finish_reason == "tool_calls"
    assert 结果.usage.prompt_tokens == 20
    assert 结果.usage.completion_tokens == 8
    assert 结果.usage.total_tokens == 28
    assert 结果.usage.extra == {"total_duration": 5000}
    assert 结果.raw["message"]["tool_calls"][0]["id"] == "call_abc"


def test_无tools时委托chat且不发起新请求():
    """request.tools 为空时直接返回 chat 的结果，不触碰 HTTP。"""
    预期 = object()
    提供者 = OllamaProvider()
    模拟聊天 = Mock(return_value=预期)
    请求 = 构造请求()
    with patch.object(提供者, "chat", 模拟聊天) as 模拟, patch(_拦截地址) as 模拟请求:
        结果 = 提供者.chat_with_tools(请求)

    模拟.assert_called_once_with(请求)
    assert 结果 is 预期
    模拟请求.assert_not_called()


def test_arguments为JSON字符串_解码为字典():
    """arguments 为 JSON 字符串时用 json.loads 解码为字典。"""
    响应体 = 构造工具响应(
        message={
            "role": "assistant",
            "content": "好的",
            "tool_calls": [
                {
                    "id": "call_json",
                    "function": {
                        "name": "查天气",
                        "arguments": '{"城市": "北京", "天数": 3}',
                    },
                }
            ],
        }
    )
    with patch(_拦截地址, return_value=假响应(body=响应体)):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))

    assert 结果.tool_calls == [
        {"id": "call_json", "name": "查天气", "arguments": {"城市": "北京", "天数": 3}}
    ]
    assert 结果.content == "好的"


def test_无id时按位置生成call编号():
    """后端不返回 id 时，按 tool_calls 位置生成 call_0、call_1。"""
    响应体 = 构造工具响应(
        message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "工具甲", "arguments": {"a": 1}}},
                {"function": {"name": "工具乙", "arguments": {"b": 2}}},
            ],
        }
    )
    with patch(_拦截地址, return_value=假响应(body=响应体)):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))

    assert 结果.tool_calls == [
        {"id": "call_0", "name": "工具甲", "arguments": {"a": 1}},
        {"id": "call_1", "name": "工具乙", "arguments": {"b": 2}},
    ]


def test_多工具调用混合有无id_全部归一():
    """一次响应中的多个 tool call 无论有无 id 都按顺序归一。"""
    响应体 = 构造工具响应(
        message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "真实编号", "function": {"name": "甲", "arguments": {"x": 1}}},
                {"function": {"name": "乙", "arguments": '{"y": 2}'}},
                {"function": {"name": "丙", "arguments": {}}},
            ],
        }
    )
    with patch(_拦截地址, return_value=假响应(body=响应体)):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))

    assert [调用["id"] for 调用 in (结果.tool_calls or [])] == [
        "真实编号",
        "call_1",
        "call_2",
    ]
    assert [调用["name"] for 调用 in (结果.tool_calls or [])] == ["甲", "乙", "丙"]
    assert [调用["arguments"] for 调用 in (结果.tool_calls or [])] == [
        {"x": 1},
        {"y": 2},
        {},
    ]


def test_arguments解码失败_当空字典且原文保留在raw():
    """JSON 解码失败时 arguments 为空字典，原始字符串仍保留在 raw 中。"""
    原文 = "{这不是合法 JSON"
    响应体 = 构造工具响应(
        message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_bad", "function": {"name": "查天气", "arguments": 原文}}
            ],
        }
    )
    with patch(_拦截地址, return_value=假响应(body=响应体)):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))

    assert 结果.tool_calls == [
        {"id": "call_bad", "name": "查天气", "arguments": {}}
    ]
    assert 结果.raw["message"]["tool_calls"][0]["function"]["arguments"] == 原文


def test_arguments为JSON非对象_按空字典处理():
    """JSON 字符串解码后不是对象（如数组/数字）时按空字典处理。"""
    响应体 = 构造工具响应(
        message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_arr", "function": {"name": "查天气", "arguments": "[1, 2, 3]"}}
            ],
        }
    )
    with patch(_拦截地址, return_value=假响应(body=响应体)):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))
    assert 结果.tool_calls == [{"id": "call_arr", "name": "查天气", "arguments": {}}]


def test_usage映射与后端total_tokens优先():
    """用量正常映射，后端显式 total_tokens 优先于相加值。"""
    响应体 = 构造工具响应(prompt_eval_count=2, eval_count=3, total_tokens=99)
    with patch(_拦截地址, return_value=假响应(body=响应体)):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))
    assert 结果.usage.prompt_tokens == 2
    assert 结果.usage.completion_tokens == 3
    assert 结果.usage.total_tokens == 99


def test_finish_reason保留后端原值():
    """finish_reason 直接取后端 done_reason，不做改写。"""
    响应体 = 构造工具响应(done_reason="length")
    with patch(_拦截地址, return_value=假响应(body=响应体)):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))
    assert 结果.finish_reason == "length"


def test_无tool_calls响应_tool_calls为空():
    """模型未发起工具调用时 tool_calls 为 None，to_dict 输出空列表。"""
    响应体 = json.dumps(
        {"model": "gemma4:e4b", "message": {"content": "无需工具"}, "done": True}
    ).encode("utf-8")
    with patch(_拦截地址, return_value=假响应(body=响应体)):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))
    assert 结果.tool_calls is None
    assert 结果.content == "无需工具"
    assert 结果.to_dict()["工具调用"] == []


def test_to_dict输出中文键工具调用():
    """ChatResponse.to_dict() 的「工具调用」为中文键，供道语言直接消费。"""
    with patch(_拦截地址, return_value=假响应(body=构造工具响应())):
        结果 = OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))
    assert 结果.to_dict()["工具调用"] == [
        {"编号": "call_abc", "名称": "查天气", "参数": {"城市": "深圳"}}
    ]


def test_后端error字段_抛ProviderError():
    """响应体携带 error 字段时转成 ProviderError。"""
    响应对象 = 假响应(body=json.dumps({"error": "model not found"}).encode("utf-8"))
    with patch(_拦截地址, return_value=响应对象), pytest.raises(ProviderError, match="model not found"):
        OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))


def test_非法JSON响应_抛ProviderError():
    """非 JSON 响应用统一 ProviderError 上报，不返回假响应。"""
    with patch(_拦截地址, return_value=假响应(body=b"not-json")), pytest.raises(
        ProviderError, match="JSON"
    ):
        OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))


def test_HTTP404_抛ProviderError():
    """HTTP 404 转成 ProviderError，且消息中包含状态码。"""
    错误 = urllib.error.HTTPError(
        "http://localhost:11434/api/chat", 404, "Not Found", {}, io.BytesIO(b"missing")
    )
    with patch(_拦截地址, side_effect=错误), pytest.raises(ProviderError, match="404"):
        OllamaProvider().chat_with_tools(构造请求(tools=构造工具()))
