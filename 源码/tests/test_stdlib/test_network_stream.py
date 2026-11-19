"""流式请求原语与打印刷新的单元测试。

用假的 urlopen 响应逐行吐出 NDJSON，验证「流式请求」的回调机制、
提前终止、错误降级，以及「打印」新增的「刷新」命名参数。
"""

import io
import json
import os
import sys
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.builtins.functions import _builtin_打印
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


class _流式响应:
    """支持 readline() 的假 HTTP 响应。"""

    def __init__(self, 行):
        self.status = 200
        self.headers = {}
        self._队列 = list(行)

    def readline(self):
        if not self._队列:
            return b""
        文本 = self._队列.pop(0)
        return 文本.encode("utf-8") if isinstance(文本, str) else 文本

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _计数缓冲(io.StringIO):
    """记录 flush 调用次数的输出缓冲。"""

    def __init__(self):
        super().__init__()
        self.刷新次数 = 0

    def flush(self):
        self.刷新次数 += 1
        super().flush()


def _运行(源码, 处理器):
    输出 = io.StringIO()
    with patch("urllib.request.urlopen", side_effect=处理器), redirect_stdout(输出):
        tokens = Lexer(源码).tokenize()
        ast = Parser(tokens).parse()
        Interpreter().execute(ast)
    return 输出.getvalue()


class Test流式请求:
    def test_逐行回调并跳过空行(self):
        行 = [
            json.dumps({"message": {"content": "甲"}, "done": False}, ensure_ascii=False),
            "\n",  # 真实 HTTP 流的空行是 b"\n"，只有 EOF 才是 b""
            json.dumps({"message": {"content": "乙"}, "done": False}, ensure_ascii=False),
            json.dumps({"message": {"content": ""}, "done": True,
                        "eval_count": 9}, ensure_ascii=False),
        ]

        def 处理器(req, **kwargs):
            return _流式响应(行)

        源码 = """
从 网络 导入 流式请求
从 编码 导入 JSON

定义 片段 = []

函数 收到(行)
    定义 块 = JSON.解码(行)
    追加(片段, 块["message"]["content"])
    返回 真

定义 行数 = 流式请求("http://localhost:11434/api/chat", {"方法": "POST"}, 收到)
打印(`行数={行数}`)
打印(`片段={片段}`)
"""
        输出 = _运行(源码, 处理器)
        assert "行数=3" in 输出  # 空行被跳过
        assert "甲" in 输出
        assert "乙" in 输出

    def test_回调返回假提前终止(self):
        行 = [json.dumps({"序号": i}) for i in range(1, 6)]

        def 处理器(req, **kwargs):
            return _流式响应(行)

        源码 = """
从 网络 导入 流式请求

定义 状态 = {"计数": 0}

函数 收到(行)
    状态["计数"] = 状态["计数"] + 1
    如果 状态["计数"] >= 2
        返回 假
    返回 真

定义 行数 = 流式请求("http://x/api", {}, 收到)
打印(`行数={行数}`)
打印(`计数={状态["计数"]}`)
"""
        输出 = _运行(源码, 处理器)
        assert "行数=2" in 输出
        assert "计数=2" in 输出

    def test_选项按中文键传递(self):
        记录 = {}

        def 处理器(req, **kwargs):
            记录["方法"] = req.get_method()
            记录["数据"] = req.data.decode("utf-8")
            记录["超时"] = kwargs.get("timeout")
            return _流式响应([])

        源码 = """
从 网络 导入 流式请求
定义 行数 = 流式请求("http://x/api", {"方法": "POST", "数据": "abc", "超时": 9}, 函数(行) => 真)
打印(`行数={行数}`)
"""
        输出 = _运行(源码, 处理器)
        assert "行数=0" in 输出
        assert 记录["方法"] == "POST"
        assert 记录["数据"] == "abc"
        assert 记录["超时"] == 9

    def test_连接失败抛中文错误(self):
        def 处理器(req, **kwargs):
            raise urllib.error.URLError("Connection refused")

        源码 = """
从 网络 导入 流式请求
尝试
    流式请求("http://x/api", {}, 函数(行) => 真)
捕获 错误
    打印(`捕获={文本(错误)}`)
"""
        输出 = _运行(源码, 处理器)
        assert "流式请求失败" in 输出
        assert "Connection refused" in 输出

    def test_HTTP错误抛中文错误(self):
        错误 = urllib.error.HTTPError(
            "http://x/api", 404, "Not Found", {},
            io.BytesIO(b'{"error": "model not found"}'),
        )

        def 处理器(req, **kwargs):
            raise 错误

        源码 = """
从 网络 导入 流式请求
尝试
    流式请求("http://x/api", {}, 函数(行) => 真)
捕获 错误
    打印(`捕获={文本(错误)}`)
"""
        输出 = _运行(源码, 处理器)
        assert "流式请求失败: HTTP 404" in 输出

    def test_处理函数不是函数时报类型错误(self):
        def 处理器(req, **kwargs):
            pytest.fail("参数校验应在发起请求之前失败")

        源码 = """
从 网络 导入 流式请求
尝试
    流式请求("http://x/api", {}, 123)
捕获 错误
    打印(`捕获={文本(错误)}`)
"""
        输出 = _运行(源码, 处理器)
        assert "必须是函数" in 输出


class Test打印刷新:
    def test_刷新为真时调用flush(self):
        缓冲 = _计数缓冲()
        with redirect_stdout(缓冲):
            _builtin_打印("甲", 结尾="", 刷新=True)
            _builtin_打印("乙", 结尾="")
            _builtin_打印("丙", 刷新=True)
        assert 缓冲.getvalue() == "甲乙丙\n"
        assert 缓冲.刷新次数 == 2

    def test_默认不刷新(self):
        缓冲 = _计数缓冲()
        with redirect_stdout(缓冲):
            _builtin_打印("甲", 结尾="")
        assert 缓冲.getvalue() == "甲"
        assert 缓冲.刷新次数 == 0
