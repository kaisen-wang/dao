"""OllamaProvider 单元测试。

全部通过 ``unittest.mock.patch`` 拦截 ``urllib.request.urlopen``，
不依赖真实 Ollama 服务，也不产生任何网络流量。
"""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.llm.providers.ollama import OllamaProvider
from dao.llm.types import ChatMessage, ChatRequest, ProviderError

_拦截地址 = "dao.llm.providers.ollama.urllib.request.urlopen"


class 假响应:
    """最小 HTTP 响应替身，支持 read/readline/status/close。"""

    def __init__(self, body: bytes = b"", lines: list[bytes] | None = None, status: int = 200):
        self.body = body
        self.lines = list(lines or [])
        self.status = status
        self.headers: dict[str, str] = {}
        self.closed = False

    def read(self) -> bytes:
        """返回完整响应体。"""
        return self.body

    def readline(self) -> bytes:
        """逐行返回预置的 NDJSON 行，读尽后返回空字节。"""
        if self.lines:
            return self.lines.pop(0)
        return b""

    def close(self) -> None:
        """记录关闭动作。"""
        self.closed = True


def 构造聊天响应(**覆盖: object) -> bytes:
    """构造一个典型的非流式 /api/chat 响应体。"""
    数据: dict[str, object] = {
        "model": "gemma4:e4b",
        "message": {"role": "assistant", "content": "你好！", "thinking": "让我想想"},
        "prompt_eval_count": 12,
        "eval_count": 5,
        "total_duration": 123456,
        "load_duration": 1000,
        "done": True,
        "done_reason": "stop",
    }
    数据.update(覆盖)
    return json.dumps(数据).encode("utf-8")


def 构造请求(**覆盖: object) -> ChatRequest:
    """构造一条简单的单轮对话请求。"""
    return ChatRequest(messages=[ChatMessage(role="user", content="你好")], **覆盖)


def test_chat_成功校验请求并解析全部字段():
    """chat 正确设置 URL/方法/请求体，并解析内容、思考、用量与原始响应。"""
    响应对象 = 假响应(body=构造聊天响应())
    with patch(_拦截地址, return_value=响应对象) as 模拟:
        结果 = OllamaProvider().chat(构造请求())

    请求对象 = 模拟.call_args[0][0]
    assert 请求对象.full_url == "http://localhost:11434/api/chat"
    assert 请求对象.get_method() == "POST"
    请求体 = json.loads(请求对象.data)
    assert 请求体["model"] == "gemma4:e4b"
    assert 请求体["messages"] == [{"role": "user", "content": "你好"}]
    assert 请求体["stream"] is False
    assert 请求体["options"] == {}

    assert 结果.content == "你好！"
    assert 结果.thinking == "让我想想"
    assert 结果.model == "gemma4:e4b"
    assert 结果.finish_reason == "stop"
    assert 结果.usage.prompt_tokens == 12
    assert 结果.usage.completion_tokens == 5
    assert 结果.usage.total_tokens == 17
    assert 结果.usage.extra == {"total_duration": 123456, "load_duration": 1000}
    assert 结果.raw["done"] is True
    assert 响应对象.closed is True


def test_chat_后端total_tokens优先():
    """响应自带 total_tokens 时直接采用，不再把提示与生成token相加。"""
    响应对象 = 假响应(body=构造聊天响应(prompt_eval_count=2, eval_count=3, total_tokens=99))
    with patch(_拦截地址, return_value=响应对象):
        结果 = OllamaProvider().chat(构造请求())
    assert 结果.usage.total_tokens == 99


def test_chat_HTTP404_抛ProviderError():
    """HTTP 404 转成 ProviderError，且消息中包含状态码。"""
    错误 = urllib.error.HTTPError(
        "http://localhost:11434/api/chat", 404, "Not Found", {}, io.BytesIO(b"model not found")
    )
    with patch(_拦截地址, side_effect=错误), pytest.raises(ProviderError, match="404"):
        OllamaProvider().chat(构造请求())


def test_chat_非200状态码_抛ProviderError():
    """未抛出异常但状态码非 200 的响应同样转成 ProviderError。"""
    响应对象 = 假响应(body=b"", status=500)
    with patch(_拦截地址, return_value=响应对象), pytest.raises(ProviderError, match="500"):
        OllamaProvider().chat(构造请求())


def test_chat_网络URLError_抛ProviderError():
    """网络层 URLError 转成 ProviderError，消息包含原因。"""
    错误 = urllib.error.URLError("connection refused")
    with patch(_拦截地址, side_effect=错误), pytest.raises(ProviderError, match="connection refused"):
        OllamaProvider().chat(构造请求())


def test_chat_后端error字段_抛ProviderError():
    """响应体携带 error 字段时转成 ProviderError。"""
    响应对象 = 假响应(body=json.dumps({"error": "model not found"}).encode("utf-8"))
    with patch(_拦截地址, return_value=响应对象), pytest.raises(ProviderError, match="model not found"):
        OllamaProvider().chat(构造请求())


def test_chat_默认配置与环境变量兜底():
    """未显式配置时读取环境变量；环境变量缺失时回落到内置默认值。"""
    with patch.dict(os.environ, {"OLLAMA_HOST": "http://env-host:1111", "OLLAMA_MODEL": "env-model"}):
        提供者 = OllamaProvider()
    assert 提供者._host == "http://env-host:1111"
    assert 提供者._model == "env-model"
    assert 提供者._timeout == 120

    with patch.dict(os.environ, {}, clear=True):
        默认提供者 = OllamaProvider()
    assert 默认提供者._host == "http://localhost:11434"
    assert 默认提供者._model == "gemma4:e4b"


def test_chat_显式配置优先并去除主机尾部斜杠():
    """构造参数中的 host/model/timeout 优先于环境变量与默认值。"""
    with patch.dict(os.environ, {"OLLAMA_HOST": "http://env:1", "OLLAMA_MODEL": "env"}):
        提供者 = OllamaProvider(host="http://my-host:2222/", model="my-model", timeout=5)
    assert 提供者._host == "http://my-host:2222"
    assert 提供者._model == "my-model"
    assert 提供者._timeout == 5


def test_chat_request_model覆盖配置并映射options():
    """request.model 优先于配置模型；采样参数映射为 Ollama 的 options。"""
    响应对象 = 假响应(body=json.dumps({"message": {"content": "ok"}, "done": True}).encode())
    with patch(_拦截地址, return_value=响应对象) as 模拟:
        请求 = 构造请求(model="指定模型", temperature=0.7, top_p=0.9, max_tokens=50, options={"seed": 42})
        OllamaProvider(model="配置模型").chat(请求)
    请求体 = json.loads(模拟.call_args[0][0].data)
    assert 请求体["model"] == "指定模型"
    assert 请求体["options"] == {
        "seed": 42,
        "temperature": 0.7,
        "top_p": 0.9,
        "num_predict": 50,
    }


def test_chat_stream_逐块回调并累积全文与用量():
    """多行 NDJSON 被逐块回调，返回累积内容、思考与末行统计。"""
    行 = [
        json.dumps({"model": "gemma4:e4b", "message": {"content": "你", "thinking": "思1"}, "done": False}).encode(),
        json.dumps({"model": "gemma4:e4b", "message": {"content": "好", "thinking": "思2"}, "done": False}).encode(),
        json.dumps(
            {
                "model": "gemma4:e4b",
                "message": {"content": "", "thinking": ""},
                "prompt_eval_count": 3,
                "eval_count": 7,
                "total_duration": 999,
                "done": True,
                "done_reason": "stop",
            }
        ).encode(),
    ]
    响应对象 = 假响应(lines=行)
    收到: list[tuple[str, str, bool]] = []

    with patch(_拦截地址, return_value=响应对象) as 模拟:

        def 回调(块: object) -> None:
            收到.append((块.content, 块.thinking, 块.done))  # type: ignore[attr-defined]

        结果 = OllamaProvider().chat_stream(构造请求(), 回调)

    请求体 = json.loads(模拟.call_args[0][0].data)
    assert 请求体["stream"] is True
    assert 收到 == [("你", "思1", False), ("好", "思2", False), ("", "", True)]
    assert 结果.content == "你好"
    assert 结果.thinking == "思1思2"
    assert 结果.usage.prompt_tokens == 3
    assert 结果.usage.completion_tokens == 7
    assert 结果.usage.total_tokens == 10
    assert 结果.usage.extra == {"total_duration": 999}
    assert 结果.finish_reason == "stop"
    assert 结果.raw["done"] is True
    assert 响应对象.closed is True


def test_chat_stream_回调返回False提前终止():
    """回调返回 False 后停止读取，后续 NDJSON 行不再被处理。"""
    行 = [
        json.dumps({"message": {"content": "第一"}, "done": False}).encode(),
        json.dumps({"message": {"content": "第二"}, "done": False}).encode(),
        json.dumps({"message": {"content": "第三"}, "done": True}).encode(),
    ]
    响应对象 = 假响应(lines=行)
    收到: list[str] = []

    with patch(_拦截地址, return_value=响应对象):

        def 回调(块: object) -> bool:
            收到.append(块.content)  # type: ignore[attr-defined]
            return False

        结果 = OllamaProvider().chat_stream(构造请求(), 回调)

    assert 收到 == ["第一"]
    assert 结果.content == "第一"
    assert len(响应对象.lines) == 2
    assert 响应对象.closed is True


def test_chat_stream_回调异常原样上抛():
    """回调函数自身抛出的异常不被包装，原样向上传播。"""

    class 自定义异常(Exception):
        """测试用自定义异常。"""

    响应对象 = 假响应(lines=[json.dumps({"message": {"content": "x"}, "done": False}).encode()])

    with patch(_拦截地址, return_value=响应对象):

        def 回调(块: object) -> None:
            raise 自定义异常("回调炸了")

        with pytest.raises(自定义异常, match="回调炸了"):
            OllamaProvider().chat_stream(构造请求(), 回调)


def test_chat_stream_非法JSON行_抛ProviderError():
    """流式响应中出现非法 JSON 行时转成 ProviderError。"""
    响应对象 = 假响应(lines=[b"not-json"])
    with patch(_拦截地址, return_value=响应对象), pytest.raises(ProviderError, match="JSON"):
        OllamaProvider().chat_stream(构造请求(), lambda 块: None)


def test_list_models_解析模型名():
    """GET /api/tags 并返回各模型的 name 字段。"""
    响应对象 = 假响应(body=json.dumps({"models": [{"name": "gemma4:e4b"}, {"name": "qwen2:7b"}, {}]}).encode())
    with patch(_拦截地址, return_value=响应对象) as 模拟:
        名称 = OllamaProvider().list_models()
    assert 名称 == ["gemma4:e4b", "qwen2:7b"]
    请求对象 = 模拟.call_args[0][0]
    assert 请求对象.full_url == "http://localhost:11434/api/tags"
    assert 请求对象.get_method() == "GET"


def test_list_models_HTTP错误_抛ProviderError():
    """列出模型时发生 HTTP 错误转成 ProviderError。"""
    错误 = urllib.error.HTTPError("http://localhost:11434/api/tags", 503, "unavailable", {}, None)
    with patch(_拦截地址, side_effect=错误), pytest.raises(ProviderError, match="503"):
        OllamaProvider().list_models()
