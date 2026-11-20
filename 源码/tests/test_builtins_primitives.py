"""语言自举新增 IO/诊断原语与系统元数据导出的回归测试。"""

import io
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.builtins.functions import get_builtins  # noqa: E402
from dao.errors import 类型错误, 运行时错误  # noqa: E402
from dao.stdlib.system import create_module_env  # noqa: E402
from dao.tokens import KEYWORDS  # noqa: E402


@pytest.fixture(scope="module")
def 内置表():
    return get_builtins()


class Test读字节:
    def test_读取指定字节数(self, 内置表, monkeypatch):
        monkeypatch.setattr(
            sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO(b"abcdef"))
        )
        assert 内置表["读字节"].func(3) == b"abc"
        assert 内置表["读字节"].param_count == 1

    def test_非正整数抛运行时错误(self, 内置表):
        for n in (0, -1):
            with pytest.raises(运行时错误):
                内置表["读字节"].func(n)

    def test_类型错误(self, 内置表):
        for n in ("3", 1.5, True, None):
            with pytest.raises(类型错误):
                内置表["读字节"].func(n)


class Test字节长度:
    def test_中文按UTF8计字节(self, 内置表):
        assert 内置表["字节长度"].func("你好") == 6
        assert 内置表["字节长度"].param_count == 1

    def test_ASCII与空文本(self, 内置表):
        assert 内置表["字节长度"].func("abc") == 3
        assert 内置表["字节长度"].func("") == 0

    def test_非文本抛类型错误(self, 内置表):
        for value in (123, None, [1], b"abc"):
            with pytest.raises(类型错误):
                内置表["字节长度"].func(value)


class Test错误输出:
    def test_写入标准错误并支持中文转换(self, 内置表, capsys):
        内置表["错误输出"].func("错误", 1, True, None, 分隔符="-", 结尾="!")
        assert capsys.readouterr().err == "错误-1-真-空!"
        assert 内置表["错误输出"].param_count == -1

    def test_刷新参数(self, 内置表, capsys):
        内置表["错误输出"].func("刷新", 刷新=True)
        assert capsys.readouterr().err == "刷新\n"


class Test诊断源码:
    def test_正确源码返回空列表(self, 内置表):
        assert 内置表["诊断源码"].func("定义 x = 1") == []
        assert 内置表["诊断源码"].param_count == 1

    def test_词法错误(self, 内置表):
        result = 内置表["诊断源码"].func('"未闭合的字符串')
        assert len(result) == 1
        assert result[0]["行"] == 1
        assert result[0]["列"] >= 1
        assert result[0]["类型"] == "词法错误"
        assert "未闭合" in result[0]["消息"]

    def test_语法错误(self, 内置表):
        result = 内置表["诊断源码"].func("定义 x = ")
        assert len(result) == 1
        assert result[0]["行"] >= 1
        assert result[0]["列"] >= 1
        assert result[0]["类型"] == "语法错误"
        assert result[0]["消息"]

    def test_每项键为中文且完整(self, 内置表):
        for source in ('"未闭合的字符串', "定义 x = "):
            for item in 内置表["诊断源码"].func(source):
                assert set(item) == {"行", "列", "类型", "消息"}

    def test_非文本抛类型错误(self, 内置表):
        with pytest.raises(类型错误):
            内置表["诊断源码"].func(123)


class Test系统元数据导出:
    def test_关键字表与Python侧一致(self):
        from dao.stdlib.system import _stdlib_关键字表

        env = create_module_env()
        assert env.values["关键字表"].func() == list(KEYWORDS)
        assert _stdlib_关键字表() == list(KEYWORDS)

    def test_内置函数名与Python侧同口径(self):
        from dao.builtins.hof import get_interpreter_builtins
        from dao.stdlib.system import _stdlib_内置函数名

        expected = list(get_builtins()) + list(get_interpreter_builtins())
        env = create_module_env()
        assert env.values["内置函数名"].func() == expected
        assert _stdlib_内置函数名() == expected

    def test_标准库模块名与注册表一致(self):
        from dao.stdlib.registry import STDLIB_REGISTRY
        from dao.stdlib.system import _stdlib_标准库模块名

        env = create_module_env()
        assert env.values["标准库模块名"].func() == list(STDLIB_REGISTRY.keys())
        assert _stdlib_标准库模块名() == list(STDLIB_REGISTRY.keys())
