import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter.core import Interpreter
from dao.bytecode.compiler import BytecodeCompiler
from dao.vm.core import VirtualMachine


def run_interpreter(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


def run_vm(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    compiler = BytecodeCompiler()
    code = compiler.compile(ast)
    vm = VirtualMachine()
    return vm.run(code)


class TestDualMode:
    def test_arithmetic(self):
        src = "1 + 2"
        assert run_interpreter(src) == run_vm(src)

    def test_variable(self):
        src = "定义 x = 42\nx"
        assert run_interpreter(src) == run_vm(src)

    def test_if_branch(self):
        src = "定义 x = 0\n如果 1\n  x = 10\nx"
        assert run_interpreter(src) == run_vm(src)

    def test_while_loop(self):
        src = "定义 x = 0\n定义 i = 0\n当 i < 3\n  x = x + 1\n  i = i + 1\nx"
        assert run_interpreter(src) == run_vm(src)

    def test_function(self):
        src = "函数 f(x)\n  返回 x + 1\n\nf(5)"
        assert run_interpreter(src) == run_vm(src)

    def test_list(self):
        src = "定义 x = [1, 2, 3]\nx"
        assert run_interpreter(src) == run_vm(src)

    def test_string(self):
        src = '定义 x = "hello"\nx'
        assert run_interpreter(src) == run_vm(src)

    def test_comparison(self):
        src = "1 < 2"
        assert run_interpreter(src) == run_vm(src)