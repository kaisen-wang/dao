import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.bytecode.compiler import BytecodeCompiler
from dao.vm.core import VirtualMachine


def run_vm(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    compiler = BytecodeCompiler()
    code = compiler.compile(ast)
    vm = VirtualMachine()
    return vm.run(code)


class TestVirtualMachine:
    def test_arithmetic(self):
        assert run_vm("定义 x = 1 + 2\nx") == 3

    def test_subtraction(self):
        assert run_vm("定义 x = 5 - 3\nx") == 2

    def test_multiplication(self):
        assert run_vm("定义 x = 3 * 4\nx") == 12

    def test_division(self):
        assert run_vm("定义 x = 10 / 2\nx") == 5.0

    def test_variable_access(self):
        assert run_vm("定义 x = 42\nx") == 42

    def test_if_true(self):
        assert run_vm("定义 x = 0\n如果 1\n  x = 10\nx") == 10

    def test_while_loop(self):
        result = run_vm("定义 x = 0\n定义 i = 0\n当 i < 3\n  x = x + 1\n  i = i + 1\nx")
        assert result == 3

    def test_function_call(self):
        result = run_vm("函数 f(x)\n  返回 x + 1\n\nf(5)")
        assert result == 6

    def test_list_literal(self):
        result = run_vm("定义 x = [1, 2, 3]\nx")
        assert result == [1, 2, 3]

    def test_dict_literal(self):
        result = run_vm("定义 x = {1: 2}\nx")
        assert result == {1: 2}

    def test_comparison(self):
        assert run_vm("定义 x = 1 < 2\nx") == True

    def test_string_concat(self):
        assert run_vm('定义 x = "hello" + " world"\nx') == "hello world"