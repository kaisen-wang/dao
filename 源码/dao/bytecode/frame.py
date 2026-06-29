from dataclasses import dataclass, field

from .opcodes import OpCode


class Frame:
    def __init__(self, code, parent=None):
        self.code = code
        self.parent = parent
        self.stack: list = []
        self.locals: dict[str, object] = {}
        self.ip = 0

    def push(self, value):
        self.stack.append(value)

    def pop(self):
        if not self.stack:
            raise RuntimeError("栈下溢：尝试从空栈弹出")
        return self.stack.pop()

    def peek(self, offset: int = 0):
        idx = len(self.stack) - 1 - offset
        if idx < 0:
            raise RuntimeError("栈下溢：尝试查看空栈")
        return self.stack[idx]