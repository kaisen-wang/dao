import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.bytecode.compiler import BytecodeCompiler
from dao.bytecode.disassembler import Disassembler
from dao.bytecode.opcodes import OpCode
from dao.ast_nodes import Program


def compile_source(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    compiler = BytecodeCompiler()
    return compiler.compile(ast)


class TestBytecodeCompiler:
    def test_variable_decl(self):
        code = compile_source("定义 x = 42\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.LOAD_CONST in opcodes
        assert OpCode.STORE_LOCAL in opcodes

    def test_function_decl(self):
        code = compile_source("函数 f(x)\n  返回 x\n")
        assert len(code.child_codes) == 1
        assert code.child_codes[0].name == "f"

    def test_if_stmt(self):
        code = compile_source("如果 1\n  定义 x = 1\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.POP_JUMP_IF_FALSE in opcodes

    def test_while_stmt(self):
        code = compile_source("当 1\n  定义 x = 1\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.LOOP in opcodes

    def test_binary_op(self):
        code = compile_source("定义 x = 1 + 2\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.BINARY_ADD in opcodes

    def test_function_call(self):
        code = compile_source("定义 x = f(1, 2)\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.CALL_FUNCTION in opcodes

    def test_list_literal(self):
        code = compile_source("定义 x = [1, 2, 3]\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.BUILD_LIST in opcodes

    def test_dict_literal(self):
        code = compile_source("定义 x = {1: 2}\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.BUILD_DICT in opcodes

    def test_member_access(self):
        code = compile_source("定义 x = obj.属性\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.LOAD_ATTR in opcodes

    def test_index_access(self):
        code = compile_source("定义 x = 列表[0]\n")
        opcodes = [inst.opcode for inst in code.instructions]
        assert OpCode.LOAD_INDEX in opcodes


class TestDisassembler:
    def test_disassemble_output(self):
        code = compile_source("定义 x = 42\n")
        disasm = Disassembler()
        output = disasm.disassemble(code)
        assert "LOAD_CONST" in output
        assert "STORE_LOCAL" in output
        assert "42" in output

    def test_disassemble_function(self):
        code = compile_source("函数 f(x)\n  返回 x\n")
        disasm = Disassembler()
        output = disasm.disassemble(code)
        assert "f" in output