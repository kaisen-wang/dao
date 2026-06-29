import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.bytecode.opcodes import OpCode
from dao.bytecode.code_object import CodeObject, Instruction
from dao.bytecode.frame import Frame


class TestOpCode:
    def test_opcodes_exist(self):
        assert OpCode.LOAD_CONST is not None
        assert OpCode.STORE_LOCAL is not None
        assert OpCode.BINARY_ADD is not None
        assert OpCode.RETURN_VALUE is not None
        assert OpCode.CALL_FUNCTION is not None
        assert OpCode.MAKE_CLOSURE is not None
        assert OpCode.BUILD_LIST is not None
        assert OpCode.BUILD_DICT is not None
        assert OpCode.JUMP is not None
        assert OpCode.POP_JUMP_IF_FALSE is not None

    def test_opcode_count(self):
        assert len(OpCode) >= 40


class TestCodeObject:
    def test_create_empty(self):
        code = CodeObject(name="test")
        assert code.name == "test"
        assert len(code.instructions) == 0

    def test_emit_instruction(self):
        code = CodeObject(name="test")
        code.emit(OpCode.LOAD_CONST, 0, line=1)
        assert len(code.instructions) == 1
        assert code.instructions[0].opcode == OpCode.LOAD_CONST
        assert code.instructions[0].operand == 0

    def test_constants(self):
        code = CodeObject(name="test", constants=[42, "hello"])
        assert code.constants[0] == 42
        assert code.constants[1] == "hello"


class TestFrame:
    def test_push_pop(self):
        frame = Frame(code=CodeObject())
        frame.push(42)
        frame.push("hello")
        assert frame.pop() == "hello"
        assert frame.pop() == 42

    def test_peek(self):
        frame = Frame(code=CodeObject())
        frame.push(1)
        frame.push(2)
        assert frame.peek() == 2
        assert frame.peek(1) == 1

    def test_pop_empty_error(self):
        frame = Frame(code=CodeObject())
        try:
            frame.pop()
            assert False, "应该抛出异常"
        except RuntimeError:
            pass