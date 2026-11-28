"""@ 注解功能端到端集成测试（主代理独占，用于集成阶段统一验证）。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from contextlib import redirect_stdout
from io import StringIO

from dao.interpreter.core import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_source(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


def capture(source: str) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        run_source(source)
    return buf.getvalue()


class TestAnnotationIntegration:
    """端到端验证注解的完整语义（规格 §1.2）。"""

    def test_function_annotation_wrap_and_replace(self):
        """注解包装函数：返回新函数替换原函数。"""
        src = """\
函数 日志(原函数)
  函数 包装(x)
    打印("调用前")
    结果 = 原函数(x)
    打印("调用后")
    返回 结果
  返回 包装

@日志
函数 加一(x)
  返回 x + 1

加一(5)
"""
        out = capture(src)
        assert "调用前" in out and "调用后" in out

    def test_annotation_replace_value(self):
        """注解返回非 None 时替换目标值。"""
        src = """\
函数 翻倍(f)
  函数 包装(x)
    返回 f(x) * 2
  返回 包装

@翻倍
函数 原值(x)
  返回 x + 1

原值(3)
"""
        # (3+1)*2 = 8；但需通过语句块返回，用变量承接
        result = run_source(src.replace("原值(3)", "定义 r = 原值(3)\nr"))
        assert result == 8

    def test_annotation_returning_none_keeps_original(self):
        """注解返回 None 时保留原对象。"""
        src = """\
函数 无操作(f)
  返回 空

@无操作
函数 原值(x)
  返回 x + 1

定义 r = 原值(4)
r
"""
        assert run_source(src) == 5

    def test_multiple_annotations_order(self):
        """多注解从下往上依次应用。"""
        src = """\
函数 甲(f)
  函数 包装(x)
    返回 "甲(" + f(x) + ")"
  返回 包装

函数 乙(f)
  函数 包装(x)
    返回 "乙(" + f(x) + ")"
  返回 包装

@甲
@乙
函数 名字(x)
  返回 x

定义 r = 名字("中")
r
"""
        assert run_source(src) == "甲(乙(中))"

    def test_class_annotation(self):
        """类注解可应用且类仍可实例化。"""
        src = """\
函数 标记(c)
  打印("已注解")
  返回 空

@标记
类型 人
  函数 问候()
    返回 "你好"

定义 p = 人()
p.问候()
"""
        out = capture(src)
        assert "已注解" in out
        assert run_source(src).strip().endswith("你好")

    def test_undefined_annotation_error(self):
        """未定义的注解抛中文运行时错误。"""
        import pytest
        src = """\
@不存在
函数 f(x)
  返回 x
"""
        with pytest.raises(Exception, match="注解"):
            run_source(src)
