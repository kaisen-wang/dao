"""LLM 工具调用协议层核心测试：统一类型、抽象契约与道语言桥接。

用测试内假 Provider / 假解释器覆盖全部逻辑，不打外网；最后一个端到端
用例用真解释器验证「从 大模型 导入 工具定义, 工具对话」语法与自动回调。
"""

import io
import os
import sys
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.builtins.callables import BuiltinFunction
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.llm import (
    ChatRequest,
    ChatResponse,
    LLMError,
    ProviderError,
    ToolCall,
    ToolDefinition,
    UnsupportedError,
    Usage,
)
from dao.llm import factory as llm_factory
from dao.llm.base import Provider
from dao.parser import Parser
from dao.stdlib.llm import (
    _stdlib_工具定义,
    _stdlib_工具结果,
    _工具对话实现,
    create_module_env,
)

导出名集合 = {
    "消息",
    "创建客户端",
    "对话",
    "流式对话",
    "列出模型",
    "工具定义",
    "工具结果",
    "工具对话",
}


class 工具假Provider(Provider):
    """按预设响应序列吐出工具调用/最终答复的可控后端。"""

    def __init__(self, 响应序列=None, 抛错=None, **配置):
        super().__init__(**配置)
        self.响应序列 = list(响应序列 or [])
        self.抛错 = 抛错
        self.收到请求 = []

    def chat(self, request):
        return ChatResponse(content="普通回复")

    def chat_stream(self, request, on_chunk):
        return ChatResponse(content="")

    def list_models(self):
        return ["假模型"]

    def chat_with_tools(self, request):
        self.收到请求.append(request)
        if self.抛错 is not None:
            raise self.抛错
        if self.响应序列:
            return self.响应序列.pop(0)
        return ChatResponse(
            content="完成",
            usage=Usage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )


class 不支持工具Provider(Provider):
    """具体类但不覆写 chat_with_tools，用于验证基类默认行为。"""

    def chat(self, request):
        return ChatResponse(content="")

    def chat_stream(self, request, on_chunk):
        return ChatResponse(content="")

    def list_models(self):
        return []


class 假工具解释器:
    """最小解释器替身：把回调参数原样转给 Python 函数（名称、参数字典）。"""

    def __init__(self, 回调):
        self.回调 = 回调

    def call_function(self, func, args, kwargs=None):
        return self.回调(args[0], args[1])


class Test统一类型:
    def test_工具定义生成openai风格字典(self):
        定义 = ToolDefinition(
            name="查天气", description="查询城市天气", parameters={"type": "object"}
        )
        assert 定义.to_dict() == {
            "type": "function",
            "function": {
                "name": "查天气",
                "description": "查询城市天气",
                "parameters": {"type": "object"},
            },
        }

    def test_工具调用转中文键字典(self):
        调用 = ToolCall(id="call_0", name="查天气", arguments={"城市": "北京"})
        assert 调用.to_dict() == {"编号": "call_0", "名称": "查天气", "参数": {"城市": "北京"}}

    def test_响应无工具调用时输出空列表(self):
        响应 = ChatResponse(content="你好")
        assert 响应.to_dict()["工具调用"] == []

    def test_响应工具调用转中文键(self):
        响应 = ChatResponse(
            content="",
            tool_calls=[{"id": "call_1", "name": "查天气", "arguments": {"城市": "北京"}}],
        )
        assert 响应.to_dict()["工具调用"] == [
            {"编号": "call_1", "名称": "查天气", "参数": {"城市": "北京"}}
        ]

    def test_请求可携带工具列表(self):
        请求 = ChatRequest(messages=[], tools=[{"type": "function"}])
        assert len(请求.tools) == 1


class Test抽象契约:
    def test_默认不支持工具调用(self):
        供应器 = 不支持工具Provider()
        with pytest.raises(UnsupportedError, match="不支持工具调用"):
            供应器.chat_with_tools(ChatRequest(messages=[]))

    def test_不支持异常属于接口层异常(self):
        assert issubclass(UnsupportedError, LLMError)


class Test模块环境:
    def test_八个导出函数存在且参数个数正确(self):
        env = create_module_env()
        assert set(env.exports) == 导出名集合
        assert set(env.values) == 导出名集合
        assert env.values["工具定义"].param_count == -1
        assert env.values["工具结果"].param_count == 2
        assert env.values["工具对话"].param_count == 5

    def test_工厂重复调用元数据稳定(self):
        env1 = create_module_env()
        env2 = create_module_env()
        for 名称 in 导出名集合:
            assert env1.values[名称].func is env2.values[名称].func


class Test工具定义:
    def test_中文键参数模式转英文schema(self):
        结果 = _stdlib_工具定义(
            "查天气",
            "查询城市天气",
            {"属性": {"城市": {"类型": "string", "描述": "城市名"}}, "必填": ["城市"]},
        )
        assert 结果["type"] == "function"
        函数 = 结果["function"]
        assert 函数["name"] == "查天气"
        assert 函数["parameters"]["type"] == "object"
        assert 函数["parameters"]["properties"]["城市"] == {
            "type": "string",
            "description": "城市名",
        }
        assert 函数["parameters"]["required"] == ["城市"]

    def test_英文schema原样保留(self):
        schema = {"type": "object", "properties": {"城市": {"type": "string"}}}
        结果 = _stdlib_工具定义("查天气", "", schema)
        assert 结果["function"]["parameters"] is schema

    def test_参数模式为空时给默认对象schema(self):
        结果 = _stdlib_工具定义("无参数工具")
        assert 结果["function"]["parameters"] == {"type": "object", "properties": {}}

    def test_属性值为字符串时当作类型(self):
        结果 = _stdlib_工具定义("查天气", "", {"属性": {"城市": "string"}})
        assert 结果["function"]["parameters"]["properties"]["城市"] == {"type": "string"}

    def test_非法名称抛类型错误(self):
        with pytest.raises(Exception, match="名称"):
            _stdlib_工具定义("")


class Test工具结果:
    def test_构造tool消息字典(self):
        assert _stdlib_工具结果("call_0", "晴天") == {
            "角色": "tool",
            "内容": "晴天",
            "调用编号": "call_0",
        }

    def test_非法编号抛类型错误(self):
        with pytest.raises(Exception, match="调用编号"):
            _stdlib_工具结果(123, "晴天")

    def test_工具结果消息转换保留调用编号(self):
        from dao.stdlib.llm import _转消息列表

        消息列表 = _转消息列表([_stdlib_工具结果("call_0", "晴天")])
        assert 消息列表[0].role == "tool"
        assert 消息列表[0].tool_call_id == "call_0"


class Test工具对话:
    def test_自动多轮执行工具回调(self):
        响应序列 = [
            ChatResponse(
                content="",
                tool_calls=[
                    {"id": "call_0", "name": "查天气", "arguments": {"城市": "北京"}},
                    {"id": "call_1", "name": "查天气", "arguments": {"城市": "上海"}},
                ],
                usage=Usage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
            ),
            ChatResponse(
                content="北京晴天，上海多云",
                usage=Usage(prompt_tokens=1, completion_tokens=4, total_tokens=5),
            ),
        ]
        客户端 = 工具假Provider(响应序列=响应序列)
        调用记录 = []

        def 回调(名称, 参数):
            调用记录.append((名称, 参数["城市"]))
            return f"{参数['城市']}晴天"

        工具 = _stdlib_工具定义("查天气", "查询天气", {"属性": {"城市": "string"}})
        结果 = _工具对话实现(
            假工具解释器(回调),
            客户端,
            [{"角色": "user", "内容": "天气如何"}],
            [工具],
            BuiltinFunction("回调", 回调, 2),
            {"最大轮次": 3},
        )

        assert 结果["成功"] is True
        assert 结果["内容"] == "北京晴天，上海多云"
        assert 结果["轮次"] == 2
        assert 结果["工具调用记录"] == [
            {"名称": "查天气", "参数": {"城市": "北京"}, "结果": "北京晴天"},
            {"名称": "查天气", "参数": {"城市": "上海"}, "结果": "上海晴天"},
        ]
        assert 调用记录 == [("查天气", "北京"), ("查天气", "上海")]
        assert 结果["用量"] == {"提示token": 3, "生成token": 7, "总token": 10}
        assert len(客户端.收到请求) == 2
        assert 客户端.收到请求[0].tools == [工具]
        assert 客户端.收到请求[1].messages[-2].role == "tool"

    def test_达到最大轮次返回失败(self):
        响应序列 = [
            ChatResponse(
                content="",
                tool_calls=[{"id": f"call_{i}", "name": "查天气", "arguments": {}}],
            )
            for i in range(5)
        ]
        客户端 = 工具假Provider(响应序列=响应序列)

        def 回调(名称, 参数):
            return "晴天"

        结果 = _工具对话实现(
            假工具解释器(回调),
            客户端,
            [],
            [_stdlib_工具定义("查天气")],
            BuiltinFunction("回调", 回调, 2),
            {"最大轮次": 2},
        )
        assert 结果["成功"] is False
        assert "最大轮次" in 结果["错误"]
        assert 结果["轮次"] == 2

    def test_最大轮次非法返回失败字典(self):
        def 回调(名称, 参数):
            return ""

        结果 = _工具对话实现(
            假工具解释器(回调),
            工具假Provider(),
            [],
            [],
            BuiltinFunction("回调", 回调, 2),
            {"最大轮次": 0},
        )
        assert 结果["成功"] is False
        assert "正整数" in 结果["错误"]

    def test_提供者抛错返回失败字典(self):
        客户端 = 工具假Provider(抛错=ProviderError("工具后端断开"))

        def 回调(名称, 参数):
            return ""

        结果 = _工具对话实现(
            假工具解释器(回调),
            客户端,
            [],
            [],
            BuiltinFunction("回调", 回调, 2),
            {},
        )
        assert 结果["成功"] is False
        assert "工具后端断开" in 结果["错误"]

    def test_不支持工具调用的后端优雅降级(self):
        客户端 = 不支持工具Provider()  # 基类默认 chat_with_tools 抛 UnsupportedError

        def 回调(名称, 参数):
            return ""

        结果 = _工具对话实现(
            假工具解释器(回调),
            客户端,
            [],
            [],
            BuiltinFunction("回调", 回调, 2),
            {},
        )
        assert 结果["成功"] is False
        assert "不支持工具调用" in 结果["错误"]

    def test_工具回调异常转为错误文本且不中断(self):
        响应序列 = [
            ChatResponse(
                content="",
                tool_calls=[{"id": "call_0", "name": "坏工具", "arguments": {}}],
            ),
            ChatResponse(content="已继续", usage=Usage()),
        ]
        客户端 = 工具假Provider(响应序列=响应序列)

        def 回调(名称, 参数):
            raise ValueError("工具内部错误")

        结果 = _工具对话实现(
            假工具解释器(回调),
            客户端,
            [],
            [_stdlib_工具定义("坏工具")],
            BuiltinFunction("回调", 回调, 2),
            {"最大轮次": 3},
        )
        assert 结果["成功"] is True
        assert "工具内部错误" in 结果["工具调用记录"][0]["结果"]

    def test_回调函数类型错误(self):
        with pytest.raises(Exception, match="必须是函数"):
            _工具对话实现(假工具解释器(lambda a, b: ""), 工具假Provider(), [], [], 123, {})


class 端到端工具Provider(Provider):
    """供端到端道语言测试使用：首轮请求工具，次轮给出最终答复。"""

    def __init__(self, **配置):
        super().__init__(**配置)
        self.轮次 = 0

    def chat(self, request):
        return ChatResponse(content="普通回复")

    def chat_stream(self, request, on_chunk):
        return ChatResponse(content="")

    def list_models(self):
        return ["假模型"]

    def chat_with_tools(self, request):
        self.轮次 += 1
        if self.轮次 == 1:
            return ChatResponse(
                content="",
                tool_calls=[
                    {"id": "call_0", "name": "查天气", "arguments": {"城市": "北京"}}
                ],
                usage=Usage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
            )
        return ChatResponse(
            content="北京今天晴天",
            usage=Usage(prompt_tokens=1, completion_tokens=4, total_tokens=5),
        )


class Test端到端:
    def test_从大模型导入工具对话语法可用(self, monkeypatch):
        monkeypatch.setitem(llm_factory._Providers, "工具假端", 端到端工具Provider)
        源码 = """
从 大模型 导入 工具定义, 工具对话, 创建客户端

定义 工具 = 工具定义("查天气", "查询城市天气", {"属性": {"城市": "string"}, "必填": ["城市"]})
定义 记录 = []

函数 执行工具(名称, 参数)
    记录.追加(名称 + ":" + 参数["城市"])
    返回 "晴天"

定义 客户端 = 创建客户端("工具假端", {})
定义 结果 = 工具对话(客户端, [{"角色": "user", "内容": "北京天气"}], [工具], 执行工具, {"最大轮次": 3})
打印(`成功={结果["成功"]}`)
打印(`内容={结果["内容"]}`)
打印(`记录={记录}`)
"""
        输出 = io.StringIO()
        with redirect_stdout(输出):
            tokens = Lexer(源码).tokenize()
            ast = Parser(tokens).parse()
            Interpreter().execute(ast)
        文本 = 输出.getvalue()

        assert "成功=真" in 文本
        assert "内容=北京今天晴天" in 文本
        assert "查天气:北京" in 文本
