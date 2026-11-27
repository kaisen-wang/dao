"""
Python 互操作桥测试
==================

覆盖：白名单内调用、白名单外拒绝、类型映射、错误处理、
不可序列化对象拦截以及"不能通过桥执行任意代码"的安全性。
"""

import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.builtins.functions import get_builtins
from dao.errors import 名称错误, 类型错误, 运行时错误
from dao.interop import (
    Python模块,
    列出可用模块,
    参数转Python,
    结果转道,
    调用模块函数,
    载入模块,
)
from dao.interop.whitelist import 允许模块, 允许的属性
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


@pytest.fixture(scope="module")
def 内置表():
    return get_builtins()


def 载入(名):
    return 载入模块(名)


def 运行道代码(源码):
    """执行一段道代码，返回执行后的全局环境。"""
    解释器 = Interpreter()
    解释器.execute(Parser(Lexer(源码).tokenize()).parse(), source=源码)
    return 解释器.global_env


# ==========================================================
# 白名单与模块加载
# ==========================================================
class Test白名单模块:
    def test_十二个规范模块全部可用(self):
        规范模块 = {
            "math", "json", "statistics", "collections", "itertools", "functools",
            "re", "datetime", "pathlib", "hashlib", "base64", "urllib.parse",
        }
        assert 规范模块 <= set(列出可用模块())

    def test_中文别名可用且指向同一模块(self):
        assert 载入("数学")._模块 is 载入("math")._模块
        assert 载入("正则")._模块 is 载入("re")._模块
        assert 载入("网址解析")._模块 is 载入("urllib.parse")._模块

    def test_列出模块排序且无重复(self, 内置表):
        结果 = 内置表["列出Python模块"].func()
        assert 结果 == sorted(set(结果))
        assert "math" in 结果 and "数学" in 结果
        assert 内置表["列出Python模块"].param_count == 0

    def test_载入模块返回不透明句柄(self, 内置表):
        句柄 = 内置表["载入Python模块"].func("math")
        assert isinstance(句柄, Python模块)
        assert "math" in repr(句柄)
        assert 内置表["载入Python模块"].param_count == 1

    @pytest.mark.parametrize("模块名", ["os", "subprocess", "sys", "builtins", "ctypes", "importlib"])
    def test_白名单外模块被拒绝(self, 模块名):
        with pytest.raises(运行时错误, match="不在白名单"):
            载入模块(模块名)

    @pytest.mark.parametrize("非法参数", [123, None, True, [], ["math"]])
    def test_模块名类型错误(self, 非法参数):
        with pytest.raises(类型错误, match="必须是文本"):
            载入模块(非法参数)

    def test_每个白名单模块都有非空属性白名单(self):
        for 名 in ("math", "json", "statistics", "collections", "itertools",
                   "functools", "re", "datetime", "pathlib", "hashlib",
                   "base64", "urllib.parse"):
            assert 允许的属性(名)
            assert all(not 属性.startswith("_") for 属性 in 允许的属性(名))


# ==========================================================
# 白名单内调用成功 + 返回值映射
# ==========================================================
class Test白名单内调用:
    def test_math函数(self, 内置表):
        句柄 = 载入("math")
        assert 调用模块函数(句柄, "sqrt", 16) == 4.0
        assert 内置表["调用Python函数"].func(句柄, "floor", 2.9) == 2

    def test_math常量(self):
        assert 调用模块函数(载入("math"), "pi") == pytest.approx(3.141592653589793)

    def test_json_loads返回字典(self):
        结果 = 调用模块函数(载入("json"), "loads", '{"甲": 1, "乙": [2, 3]}')
        assert isinstance(结果, dict)
        assert 结果 == {"甲": 1, "乙": [2, 3]}

    def test_json_dumps返回文本(self):
        结果 = 调用模块函数(载入("json"), "dumps", {"a": 1})
        assert isinstance(结果, str)
        assert '"a"' in 结果

    def test_statistics_mean返回数字(self):
        assert 调用模块函数(载入("statistics"), "mean", [1, 2, 3, 4]) == 2.5

    def test_re_findall返回列表(self):
        结果 = 调用模块函数(载入("re"), "findall", r"\d+", "a1b22c")
        assert isinstance(结果, list)
        assert 结果 == ["1", "22"]

    def test_itertools迭代器物化为列表(self):
        结果 = 调用模块函数(载入("itertools"), "product", [1, 2], ["a", "b"])
        assert isinstance(结果, list)
        assert 结果 == [(1, "a"), (1, "b"), (2, "a"), (2, "b")]

    def test_collections_Counter返回字典(self):
        结果 = 调用模块函数(载入("collections"), "Counter", "aba")
        assert isinstance(结果, dict)
        assert 结果 == {"a": 2, "b": 1}

    def test_collections_deque返回列表(self):
        assert 调用模块函数(载入("collections"), "deque", [1, 2]) == [1, 2]

    def test_datetime返回ISO文本(self):
        assert 调用模块函数(载入("datetime"), "date", 2024, 1, 2) == "2024-01-02"

    def test_hashlib返回十六进制摘要(self):
        结果 = 调用模块函数(载入("hashlib"), "md5", "abc")
        assert 结果 == "900150983cd24fb0d6963f7d28e17f72"

    def test_pathlib返回路径文本(self):
        assert 调用模块函数(载入("pathlib"), "Path", "/tmp/道") == "/tmp/道"

    def test_urllib_parse返回元组(self):
        结果 = 调用模块函数(载入("urllib.parse"), "urlparse", "https://a.com/x?y=1")
        assert isinstance(结果, tuple)
        assert 结果[0] == "https" and 结果[1] == "a.com"

    def test_base64编码返回字节(self):
        结果 = 调用模块函数(载入("base64"), "b64encode", "hi")
        assert isinstance(结果, bytes)
        assert 结果 == b"aGk="

    def test_命名参数透传(self):
        结果 = 调用模块函数(载入("urllib.parse"), "quote", "a b", safe="")
        assert 结果 == "a%20b"

    def test_functools在白名单中(self):
        assert "functools" in 允许模块
        assert "reduce" in 允许的属性("functools")


# ==========================================================
# 安全：任意代码执行与沙箱逃逸
# ==========================================================
class Test安全边界:
    @pytest.mark.parametrize("函数名", [
        "__import__", "eval", "exec", "open", "compile", "globals",
        "__builtins__", "__class__", "system", "Popen",
    ])
    def test_危险属性被拒绝(self, 函数名):
        with pytest.raises(运行时错误, match="不在互操作白名单"):
            调用模块函数(载入("math"), 函数名)

    def test_下划线属性一律被拒绝(self):
        with pytest.raises(运行时错误):
            调用模块函数(载入("json"), "_make_scanner")

    def test_不能用桥导入os模块(self):
        with pytest.raises(运行时错误):
            # 即使试图借 __import__ 逃逸，白名单也会先拦截。
            调用模块函数(载入("math"), "__import__", "os")

    def test_句柄无法被当作模块直接使用(self, 内置表):
        句柄 = 载入("math")
        with pytest.raises(类型错误):
            内置表["调用Python函数"].func(句柄._模块, "sqrt", 4)

    def test_句柄不暴露公开属性(self):
        句柄 = 载入("math")
        assert not hasattr(句柄, "sqrt")
        assert not hasattr(句柄, "__import__")

    def test_道语言中通过属性访问无法绕过桥(self):
        源码 = '定义 m = 载入Python模块("math")\n定义 r = m.sqrt(4)\n'
        with pytest.raises(名称错误):
            运行道代码(源码)

    def test_道语言中白名单外模块被拒绝(self):
        源码 = '定义 m = 载入Python模块("os")\n'
        with pytest.raises(运行时错误, match="不在白名单"):
            运行道代码(源码)

    def test_函数中不能夹带函数或模块对象(self):
        句柄 = 载入("math")
        with pytest.raises(类型错误):
            调用模块函数(句柄, "sqrt", 内置表函数())
        with pytest.raises(类型错误):
            调用模块函数(句柄, "sqrt", 载入("json"))


def 内置表函数():
    return get_builtins()["打印"].func


# ==========================================================
# 返回值转换的安全拦截
# ==========================================================
class Test返回值安全:
    def test_空值直通(self):
        assert 结果转道(None) is None

    def test_基本类型直通(self):
        for 值 in (True, False, 0, -1, 3.14, "文本", b"bytes"):
            assert 结果转道(值) == 值

    def test_集合转列表(self):
        assert 结果转道({3, 1, 2}) == [1, 2, 3]

    def test_字典递归转换(self):
        assert 结果转道({"a": (1, [2, 3])}) == {"a": (1, [2, 3])}

    def test_文件句柄被拒绝(self):
        文件 = io.StringIO("内容")
        try:
            with pytest.raises(运行时错误, match="不允许暴露"):
                结果转道(文件)
        finally:
            文件.close()

    def test_模块对象被拒绝(self):
        import math as _math
        with pytest.raises(运行时错误, match="不允许暴露"):
            结果转道(_math)

    def test_函数对象被拒绝(self):
        with pytest.raises(运行时错误, match="不允许暴露"):
            结果转道(lambda: 1)

    def test_无限迭代器被拒绝(self):
        import itertools
        with pytest.raises(运行时错误, match="超过"):
            结果转道(itertools.count())

    def test_不可转换参数被拒绝(self):
        with pytest.raises(类型错误, match="不接受"):
            参数转Python(object())

    def test_嵌套参数递归转换(self):
        assert 参数转Python([1, (2, {"a": 3})]) == [1, (2, {"a": 3})]


# ==========================================================
# 错误处理
# ==========================================================
class Test错误处理:
    def test_Python异常被包装为中文运行时错误(self):
        with pytest.raises(运行时错误, match="调用 Python 函数 math.sqrt"):
            调用模块函数(载入("math"), "sqrt", -1)

    def test_句柄类型错误(self):
        with pytest.raises(类型错误, match="模块句柄"):
            调用模块函数("math", "sqrt", 4)

    def test_函数名类型错误(self):
        with pytest.raises(类型错误, match="必须是文本"):
            调用模块函数(载入("math"), 123)

    def test_不存在的白名单属性(self, monkeypatch):
        import dao.interop.bridge as 桥

        monkeypatch.setattr(桥, "允许的属性", lambda 名: frozenset({"不存在"}))
        with pytest.raises(运行时错误, match="不存在属性"):
            调用模块函数(载入("math"), "不存在")

    def test_下划线命名参数被拒绝(self):
        with pytest.raises(运行时错误, match="命名参数"):
            调用模块函数(载入("json"), "dumps", {"a": 1}, _键=1)


# ==========================================================
# 道语言端到端
# ==========================================================
class Test道语言端到端:
    def test_完整调用流程(self):
        源码 = (
            '定义 m = 载入Python模块("math")\n'
            '定义 r = 调用Python函数(m, "sqrt", 144)\n'
        )
        环境 = 运行道代码(源码)
        assert 环境.get("r") == 12.0

    def test_json结果可在道语言中使用(self):
        源码 = (
            '定义 j = 载入Python模块("json")\n'
            '定义 d = 调用Python函数(j, "loads", "{\\"a\\": 7}")\n'
        )
        环境 = 运行道代码(源码)
        assert 环境.get("d")["a"] == 7

    def test_命名参数在道语言中透传(self):
        源码 = (
            '定义 u = 载入Python模块("urllib.parse")\n'
            '定义 r = 调用Python函数(u, "quote", "a b", safe="")\n'
        )
        环境 = 运行道代码(源码)
        assert 环境.get("r") == "a%20b"

    def test_内置函数数量扩展(self, 内置表):
        assert {"列出Python模块", "载入Python模块", "调用Python函数"} <= set(内置表)
