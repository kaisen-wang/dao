"""多轮工具对话的消息序列化契约测试。

确保 stdlib「工具对话」追加的 assistant tool_calls 与 role=tool 消息，
在各 Provider 的请求体中不会被丢弃——这是真实多轮 Function Calling 的
必要条件（OpenAI 要求 tool_call_id，Anthropic 要求 tool_use/tool_result 块）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dao.llm import ChatMessage, ChatRequest
from dao.llm.providers.anthropic import AnthropicProvider
from dao.llm.providers.openai import OpenAIProvider


class TestOpenAI多轮消息:
    def test_assistant工具调用保留在请求体(self):
        请求 = ChatRequest(
            messages=[
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {"id": "call_0", "name": "查天气", "arguments": {"城市": "北京"}}
                    ],
                )
            ]
        )
        消息 = OpenAIProvider._消息列表(请求)
        assert 消息[0]["tool_calls"] == [
            {
                "id": "call_0",
                "type": "function",
                "function": {
                    "name": "查天气",
                    "arguments": json.dumps({"城市": "北京"}, ensure_ascii=False),
                },
            }
        ]

    def test_工具结果消息保留调用编号(self):
        请求 = ChatRequest(
            messages=[ChatMessage(role="tool", content="晴天", tool_call_id="call_0")]
        )
        消息 = OpenAIProvider._消息列表(请求)
        assert 消息[0] == {"role": "tool", "content": "晴天", "tool_call_id": "call_0"}

    def test_普通消息保持简化结构(self):
        请求 = ChatRequest(messages=[ChatMessage(role="user", content="你好")])
        assert OpenAIProvider._消息列表(请求) == [{"role": "user", "content": "你好"}]


class TestAnthropic多轮消息:
    def test_assistant工具调用转tool_use块(self):
        请求 = ChatRequest(
            messages=[
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {"id": "call_0", "name": "查天气", "arguments": {"城市": "北京"}}
                    ],
                )
            ]
        )
        系统, 消息 = AnthropicProvider._拆分消息(请求)
        assert 系统 == []
        assert 消息 == [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_0",
                        "name": "查天气",
                        "input": {"城市": "北京"},
                    }
                ],
            }
        ]

    def test_工具结果消息转user的tool_result块(self):
        请求 = ChatRequest(
            messages=[ChatMessage(role="tool", content="晴天", tool_call_id="call_0")]
        )
        _系统, 消息 = AnthropicProvider._拆分消息(请求)
        assert 消息 == [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_0", "content": "晴天"}
                ],
            }
        ]

    def test_带文本的助手工具消息含两个块(self):
        请求 = ChatRequest(
            messages=[
                ChatMessage(
                    role="assistant",
                    content="正在查询",
                    tool_calls=[{"id": "call_0", "name": "查天气", "arguments": {}}],
                )
            ]
        )
        _系统, 消息 = AnthropicProvider._拆分消息(请求)
        块 = 消息[0]["content"]
        assert [项["type"] for 项 in 块] == ["text", "tool_use"]
        assert 块[0]["text"] == "正在查询"

    def test_普通消息仍为字符串格式(self):
        请求 = ChatRequest(messages=[ChatMessage(role="user", content="你好")])
        _系统, 消息 = AnthropicProvider._拆分消息(请求)
        assert 消息 == [{"role": "user", "content": "你好"}]

    def test_系统消息抽到顶层(self):
        请求 = ChatRequest(
            messages=[
                ChatMessage(role="system", content="你是助手"),
                ChatMessage(role="user", content="你好"),
            ]
        )
        系统, 消息 = AnthropicProvider._拆分消息(请求)
        assert 系统 == ["你是助手"]
        assert 消息 == [{"role": "user", "content": "你好"}]
