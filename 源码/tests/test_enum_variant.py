"""
带关联数据的枚举变体测试
======================
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def eval_env(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    interpreter.execute(ast)
    return interpreter.global_env


def capture_output(source: str) -> str:
    import io
    from contextlib import redirect_stdout
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    f = io.StringIO()
    with redirect_stdout(f):
        interpreter.execute(ast)
    return f.getvalue().strip()


class TestEnumVariants:
    def test_simple_enum_still_works(self):
        env = eval_env("枚举 方向\n    东, 南, 西, 北\n")
        from dao.interpreter.statements import DaoEnum
        d = env.get("方向")
        assert isinstance(d, DaoEnum)
        assert d.values == ["东", "南", "西", "北"]

    def test_enum_variant_with_params(self):
        env = eval_env("枚举 形状\n    圆形(半径)\n    矩形(宽, 高)\n")
        from dao.interpreter.statements import DaoEnum
        s = env.get("形状")
        assert isinstance(s, DaoEnum)
        assert s.has_variant_params("圆形")
        assert s.get_variant_params("圆形") == ["半径"]

    def test_enum_variant_constructor(self):
        output = capture_output(
            "枚举 形状\n    圆形(半径)\n    矩形(宽, 高)\n"
            "定义 c = 形状.圆形(5.0)\n"
            "打印(c)\n"
        )
        assert "圆形" in output

    def test_enum_variant_data(self):
        env = eval_env(
            "枚举 形状\n    圆形(半径)\n    矩形(宽, 高)\n"
            "定义 c = 形状.圆形(5.0)\n"
        )
        from dao.interpreter.statements import DaoEnumVariant
        c = env.get("c")
        assert isinstance(c, DaoEnumVariant)
        assert c.variant_name == "圆形"
        assert c.data == (5.0,)

    def test_enum_variant_multi_params(self):
        env = eval_env(
            "枚举 形状\n    圆形(半径)\n    矩形(宽, 高)\n"
            "定义 r = 形状.矩形(3, 4)\n"
        )
        from dao.interpreter.statements import DaoEnumVariant
        r = env.get("r")
        assert isinstance(r, DaoEnumVariant)
        assert r.variant_name == "矩形"
        assert r.data == (3, 4)

    def test_mixed_variants(self):
        env = eval_env(
            "枚举 结果\n    成功\n    失败(原因)\n"
        )
        from dao.interpreter.statements import DaoEnum, DaoEnumVariant
        r = env.get("结果")
        assert isinstance(r, DaoEnum)
        assert not r.has_variant_params("成功")
        assert r.has_variant_params("失败")

    def test_simple_variant_access(self):
        env = eval_env(
            "枚举 结果\n    成功\n    失败(原因)\n"
            "定义 s = 结果.成功\n"
        )
        from dao.interpreter.statements import DaoEnumVariant
        s = env.get("s")
        assert isinstance(s, DaoEnumVariant)
        assert s.variant_name == "成功"
        assert s.data == ()