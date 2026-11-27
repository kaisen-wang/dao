"""VM 语义修复的针对性回归测试。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.bytecode.compiler import BytecodeCompiler
from dao.errors import 道错误
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.core import VirtualMachine


def _compile(source: str):
    return BytecodeCompiler().compile(Parser(Lexer(source).tokenize()).parse())


def _vm_run(source: str):
    return VirtualMachine().run(_compile(source))


class TestConstantPoolTypeIdentity:
    def test_true_not_reusing_integer_one(self):
        """常量池必须区分布尔与整数，否则 真 会被求值为 1。"""
        code = _compile("定义 x = 1\n真")
        assert True in code.constants
        assert any(type(c) is bool and c is True for c in code.constants)
        result = _vm_run("定义 x = 1\n真")
        assert result is True
        assert type(result) is bool

    def test_false_not_reusing_integer_zero(self):
        code = _compile("定义 x = 0\n假")
        assert any(type(c) is bool and c is False for c in code.constants)
        assert _vm_run("定义 x = 0\n假") is False


class TestShortCircuitLogic:
    def test_and_does_not_evaluate_right_when_left_false(self):
        assert _vm_run("假 并且 不存在的变量") is False

    def test_or_does_not_evaluate_right_when_left_true(self):
        assert _vm_run("真 或者 不存在的变量") is True

    def test_and_returns_right_value_when_left_true(self):
        assert _vm_run("真 并且 5") == 5

    def test_or_returns_right_value_when_left_false(self):
        assert _vm_run("假 或者 7") == 7

    def test_comparison_combined_with_and(self):
        assert _vm_run("定义 x = 2\nx > 1 并且 x < 3") is True


class TestMemberAccessErrors:
    def test_missing_attribute_is_dao_error(self):
        with pytest.raises(道错误):
            _vm_run("定义 x = 5\nx.foo")


class TestIndexSemantics:
    def test_list_out_of_range_is_dao_error(self):
        with pytest.raises(道错误):
            _vm_run("[1][5]")

    def test_dict_missing_key_is_dao_error(self):
        with pytest.raises(道错误):
            _vm_run('{"a": 1}["b"]')

    def test_tuple_index_is_dao_error(self):
        with pytest.raises(道错误):
            _vm_run("(1, 2)[0]")


class TestMatchSemantics:
    def test_binding_visible_in_case_body(self):
        src = (
            "枚举 结果\n  成功(值)\n"
            "定义 r = 结果.成功(7)\n"
            "匹配 r\n  情况 结果.成功(v): v\n  情况 _: 0"
        )
        assert _vm_run(src) == 7

    def test_pattern_binding_is_not_leaked_to_failed_case(self):
        # 未命中的分支不应把绑定变量留在作用域中
        src = "定义 x = 2\n匹配 x\n  情况 1: a\n  情况 2: 42"
        assert _vm_run(src) == 42

    def test_return_inside_case_propagates_from_function(self):
        src = (
            "函数 f(x)\n  匹配 x\n    情况 1: 返回 10\n    情况 2: 返回 20\n"
            "  返回 0\nf(2)"
        )
        assert _vm_run(src) == 20


class TestEnumSemantics:
    def test_enum_variant_equality(self):
        src = "枚举 颜色\n  红\n  绿\n颜色.红 == 颜色.红"
        assert _vm_run(src) is True

    def test_enum_variant_distinct(self):
        src = "枚举 颜色\n  红\n  绿\n颜色.红 == 颜色.绿"
        assert _vm_run(src) is False
