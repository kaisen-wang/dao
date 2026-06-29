from dataclasses import dataclass, field

from .opcodes import OpCode


@dataclass
class Instruction:
    opcode: OpCode
    operand: int | None = None
    line: int = 0


@dataclass
class CodeObject:
    name: str = ""
    instructions: list[Instruction] = field(default_factory=list)
    constants: list = field(default_factory=list)
    local_names: list[str] = field(default_factory=list)
    upvalue_names: list[str] = field(default_factory=list)
    child_codes: list["CodeObject"] = field(default_factory=list)
    stack_size: int = 0

    def emit(self, opcode: OpCode, operand: int | None = None, line: int = 0):
        self.instructions.append(Instruction(opcode=opcode, operand=operand, line=line))