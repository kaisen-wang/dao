from .code_object import CodeObject
from .opcodes import OpCode


class Disassembler:
    def disassemble(self, code: CodeObject) -> str:
        lines = []
        lines.append(f"=== {code.name} ===")
        lines.append(f"  常量池: {code.constants}")
        lines.append(f"  局部变量: {code.local_names}")
        lines.append(f"  栈大小: {code.stack_size}")
        for i, inst in enumerate(code.instructions):
            operand_str = self._format_operand(inst.opcode, inst.operand, code)
            lines.append(f"  {i:4d} {inst.opcode.name:<24s} {operand_str}")
        for child in code.child_codes:
            lines.append("")
            lines.append(self.disassemble(child))
        return "\n".join(lines)

    def _format_operand(self, opcode: OpCode, operand: int | None, code: CodeObject) -> str:
        if operand is None:
            return ""
        if opcode == OpCode.LOAD_CONST:
            if 0 <= operand < len(code.constants):
                return f"({operand}) {code.constants[operand]!r}"
            return f"({operand})"
        if opcode in (OpCode.LOAD_LOCAL, OpCode.STORE_LOCAL):
            if 0 <= operand < len(code.local_names):
                return f"({operand}) {code.local_names[operand]}"
            return f"({operand})"
        if opcode in (OpCode.LOAD_NAME, OpCode.STORE_NAME, OpCode.LOAD_ATTR):
            if 0 <= operand < len(code.constants):
                return f"({operand}) {code.constants[operand]!r}"
            return f"({operand})"
        if opcode in (OpCode.CALL_FUNCTION, OpCode.BUILD_LIST, OpCode.BUILD_DICT,
                      OpCode.BUILD_SET, OpCode.BUILD_TUPLE):
            return f"({operand})"
        if opcode in (OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.POP_JUMP_IF_FALSE, OpCode.LOOP):
            return f"-> {operand}"
        if opcode == OpCode.MAKE_CLOSURE:
            if 0 <= operand < len(code.constants) and isinstance(code.constants[operand], CodeObject):
                return f"({operand}) {code.constants[operand].name}"
            return f"({operand})"
        if opcode == OpCode.FOR_ITER:
            if 0 <= operand < len(code.local_names):
                return f"({operand}) {code.local_names[operand]}"
            return f"({operand})"
        return f"({operand})" if operand is not None else ""