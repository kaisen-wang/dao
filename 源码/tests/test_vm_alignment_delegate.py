"""DELEGATE_STMT 反汇编可读性测试（契约中的可选项）。

若 opcode 尚未落地则整体跳过；已落地时检查反汇编能显示 AST 节点类名，
便于定位委托语句对应的源码结构。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.bytecode.compiler import BytecodeCompiler
from dao.bytecode.disassembler import Disassembler
from dao.bytecode.opcodes import OpCode
from dao.lexer import Lexer
from dao.parser import Parser

pytestmark = pytest.mark.skipif(
    not hasattr(OpCode, "DELEGATE_STMT"),
    reason="DELEGATE_STMT opcode 尚未落地",
)


def _反汇编(source: str) -> str:
    code = BytecodeCompiler().compile(Parser(Lexer(source).tokenize()).parse())
    return Disassembler().disassemble(code)


class TestDelegateStmt反汇编:
    def test_断言显示节点类名(self):
        文本 = _反汇编('断言 假, "错了"\n打印("到此")')
        assert "DELEGATE_STMT" in 文本
        assert "AssertStmt" in 文本

    def test_默认参数函数显示节点类名(self):
        文本 = _反汇编("函数 f(a, b=2)\n    返回 a+b\nf(1)")
        assert "DELEGATE_STMT" in 文本
        assert "FunctionDecl" in 文本

    def test_常量声明显示节点类名(self):
        文本 = _反汇编("常量 X = 1\n打印(X)")
        assert "DELEGATE_STMT" in 文本
        assert "VariableDecl" in 文本

    def test_委托语句无栈效应说明(self):
        文本 = _反汇编("断言 真, \"ok\"")
        assert "DELEGATE_STMT" in 文本


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
