"""「大模型」标准库模块的单元测试。

用测试内自定义的假 Provider（继承 dao.llm.base.Provider）覆盖全部桥接逻辑，
不依赖真实网络；另有一个端到端用例验证「从 大模型 导入 ...」语法。
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
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ProviderError,
    StreamChunk,
    Usage,
)
from dao.llm import factory as llm_factory
from dao.llm.base import Provider
from dao.parser import Parser
from dao.stdlib import registry as registry_mod
from dao.stdlib.llm import (
    _stdlib_列出模型,
    _stdlib_创建客户端,
    _stdlib_对话,
    _stdlib_消息,
    _流式对话实现,
    create_module_env,
)
from dao.stdlib.loader import StdlibLoader

导出名集合 = {"消息", "创建客户端", "对话", "流式对话", "列出模型"}


class 假Provider(Provider):
    """可控的假后端：记录请求、按预设吐出响应块，可注入错误。"""

    def __init__(self, 回复="默认回复", 块=None, 模型列表=None, 抛错=None, **配置):
        super().__init__(**配置)
        self.回复 = 回复
        self.块 = 块 or []
        self.模型列表 = 模型列表 or []
        self.抛错 = 抛错
        self.收到请求 = None
        self.回调次数 = 0

    def chat(self, request):
        self.收到请求 = request
        if self.抛错 is not None:
            raise self.抛错
        return ChatResponse(
            content=self.回复,
            model=request.model or "假模型",
            usage=Usage(prompt_tokens=3, completion_tokens=5, total_tokens=8),
        )

    def chat_stream(self, request, on_chunk):
        self.收到请求 = request
        if self.抛错 is not None:
            raise self.抛错
        片段 = []
        for 块 in self.块:
            self.回调次数 += 1
            片段.append(块.content)
            if on_chunk(块) is False:
                break
        return ChatResponse(content="".join(片段), model=request.model or "假模型")

    def list_models(self):
        if self.抛错 is not None:
            raise self.抛错
        return list(self.模型列表)


class 假解释器:
    """最小解释器替身：直接把回调收到的第一个参数转给 Python 函数。"""

    def __init__(self, 回调):
        self.回调 = 回调

    def call_function(self, func, args, kwargs=None):
        return self.回调(args[0])


class Test模块环境:
    def test_五个导出函数存在且参数个数正确(self):
        env = create_module_env()
        assert set(env.exports) == 导出名集合
        assert set(env.values) == 导出名集合
        assert env.values["消息"].param_count == 2
        assert env.values["创建客户端"].param_count == 2
        assert env.values["对话"].param_count == 3
        assert env.values["流式对话"].param_count == 4
        assert env.values["列出模型"].param_count == 1

    def test_工厂重复调用元数据稳定(self):
        env1 = create_module_env()
        env2 = create_module_env()
        for 名称 in 导出名集合:
            assert env1.values[名称].func is env2.values[名称].func
            assert env1.values[名称].name == 名称


class Test消息:
    def test_返回中文键字典(self):
        assert _stdlib_消息("user", "你好") == {"角色": "user", "内容": "你好"}


class Test创建客户端:
    def test_按名称创建并把配置传给provider(self, monkeypatch):
        monkeypatch.setitem(llm_factory._Providers, "测试端", 假Provider)
        客户端 = _stdlib_创建客户端("测试端", {"model": "m1", "timeout": 9})
        assert isinstance(客户端, 假Provider)
        assert 客户端.config == {"model": "m1", "timeout": 9}

    def test_未知提供者抛中文运行时错误(self):
        with pytest.raises(Exception, match="创建大模型客户端失败"):
            _stdlib_创建客户端("不存在的提供者", {})


class Test对话:
    def test_中文键消息与选项(self):
        客户端 = 假Provider(回复="这是回答")
        消息列表 = [{"角色": "user", "内容": "问题一"}]
        结果 = _stdlib_对话(客户端, 消息列表, {"模型": "假模型", "温度": 0.7, "最大token": 99})

        assert 结果["成功"] is True
        assert 结果["内容"] == "这是回答"
        assert 结果["模型"] == "假模型"
        请求 = 客户端.收到请求
        assert isinstance(请求, ChatRequest)
        assert 请求.messages[0].role == "user"
        assert 请求.messages[0].content == "问题一"
        assert 请求.model == "假模型"
        assert 请求.temperature == 0.7
        assert 请求.max_tokens == 99

    def test_英文键消息与选项也可用(self):
        客户端 = 假Provider(回复="英文键回答")
        消息列表 = [{"role": "system", "content": "你是助手"}]
        结果 = _stdlib_对话(客户端, 消息列表, {"model": "m2", "temperature": 0.1})

        assert 结果["内容"] == "英文键回答"
        assert 客户端.收到请求.messages[0].role == "system"
        assert 客户端.收到请求.messages[0].content == "你是助手"
        assert 客户端.收到请求.model == "m2"
        assert 客户端.收到请求.temperature == 0.1

    def test_已经是消息对象也可传入(self):
        客户端 = 假Provider()
        _stdlib_对话(客户端, [ChatMessage(role="user", content="直接传对象")], {})
        assert 客户端.收到请求.messages[0].content == "直接传对象"

    def test_provider抛错返回失败字典(self):
        客户端 = 假Provider(抛错=ProviderError("后端连接失败"))
        结果 = _stdlib_对话(客户端, [{"角色": "user", "内容": "你好"}], {})
        assert 结果["成功"] is False
        assert "后端连接失败" in 结果["错误"]


class Test流式对话:
    def test_逐块回调并累积(self):
        块列表 = [
            StreamChunk(content="你"),
            StreamChunk(content="好"),
            StreamChunk(content="！", done=True),
        ]
        客户端 = 假Provider(块=块列表)
        收到的块 = []

        def 回调(块):
            收到的块.append(块)
            return True

        解释器 = 假解释器(回调)
        回调对象 = BuiltinFunction("回调", 回调, 1)
        结果 = _流式对话实现(解释器, 客户端, [{"角色": "user", "内容": "你好"}], 回调对象, {"模型": "流式模型"})

        assert [块["内容"] for 块 in 收到的块] == ["你", "好", "！"]
        assert 收到的块[-1]["完成"] is True
        assert 客户端.回调次数 == 3
        assert 结果["成功"] is True
        assert 结果["内容"] == "你好！"
        assert 客户端.收到请求.model == "流式模型"

    def test_回调返回假提前终止(self):
        客户端 = 假Provider(块=[StreamChunk(content=str(i)) for i in range(5)])
        收到的块 = []

        def 回调(块):
            收到的块.append(块["内容"])
            return len(收到的块) < 2

        结果 = _流式对话实现(假解释器(回调), 客户端, [], BuiltinFunction("回调", 回调, 1), {})

        assert 收到的块 == ["0", "1"]
        assert 客户端.回调次数 == 2
        assert 结果["内容"] == "01"

    def test_provider抛错返回失败字典(self):
        客户端 = 假Provider(抛错=ProviderError("流式中断"))

        def 回调(块):
            return True

        结果 = _流式对话实现(
            假解释器(回调), 客户端, [], BuiltinFunction("回调", 回调, 1), {}
        )
        assert 结果["成功"] is False
        assert "流式中断" in 结果["错误"]

    def test_回调函数类型错误(self):
        with pytest.raises(Exception, match="必须是函数"):
            _流式对话实现(假解释器(lambda _: True), 假Provider(), [], 123, {})


class Test列出模型:
    def test_返回模型名列表(self):
        客户端 = 假Provider(模型列表=["gemma4:e4b", "qwen2:7b"])
        assert _stdlib_列出模型(客户端) == ["gemma4:e4b", "qwen2:7b"]

    def test_provider抛错返回失败字典(self):
        客户端 = 假Provider(抛错=ProviderError("无法列举模型"))
        结果 = _stdlib_列出模型(客户端)
        assert 结果["成功"] is False
        assert "无法列举模型" in 结果["错误"]


class Test端到端:
    def test_从大模型导入语法可用(self, monkeypatch):
        class 端到端Provider(Provider):
            def chat(self, request):
                return ChatResponse(
                    content=f"回答：{request.messages[0].content}",
                    model=request.model or "假模型",
                )

            def chat_stream(self, request, on_chunk):
                for 文本 in ("你", "好", "！"):
                    if on_chunk(StreamChunk(content=文本)) is False:
                        break
                return ChatResponse(content="你好！", model=request.model or "假模型")

            def list_models(self):
                return ["gemma4:e4b", "qwen2:7b"]

        monkeypatch.setitem(llm_factory._Providers, "假端", 端到端Provider)
        monkeypatch.setitem(registry_mod._STDLIB_REGISTRY, "大模型", create_module_env)
        monkeypatch.setattr(StdlibLoader, "STDLIB_NAMES", None)

        源码 = """
从 大模型 导入 消息, 创建客户端, 对话, 流式对话, 列出模型

定义 客户端 = 创建客户端("假端", {"model": "假模型"})
定义 单次 = 对话(客户端, [消息("user", "你好")], {"模型": "假模型"})
打印(`内容={单次["内容"]}`)
打印(`成功={单次["成功"]}`)

定义 状态 = {"块数": 0, "内容": ""}
函数 收到(块)
    状态["块数"] = 状态["块数"] + 1
    状态["内容"] = 状态["内容"] + 块["内容"]
    返回 真

定义 流式 = 流式对话(客户端, [{"role": "user", "content": "流式问题"}], 收到, {"模型": "假模型"})
打印(`流式内容={流式["内容"]}`)
打印(`块数={状态["块数"]}`)

定义 模型们 = 列出模型(客户端)
打印(`模型数量={长度(模型们)}`)
"""
        输出 = io.StringIO()
        with redirect_stdout(输出):
            tokens = Lexer(源码).tokenize()
            ast = Parser(tokens).parse()
            Interpreter().execute(ast)
        结果 = 输出.getvalue()

        assert "内容=回答：你好" in 结果
        assert "成功=真" in 结果
        assert "流式内容=你好！" in 结果
        assert "块数=3" in 结果
        assert "模型数量=2" in 结果
