from dataclasses import dataclass, field

from .opcodes import OpCode

# 异常控制流哨兵：None 本身是合法的返回值/异常值，不能用作「无待处理项」
MISSING = object()


class Frame:
    def __init__(self, code, parent=None):
        self.code = code
        self.parent = parent
        self.stack: list = []
        self.locals: dict[str, object] = {}
        # 常量名集合：桥接环境把它别名到 Environment.constants，
        # VM 原生存储指令写入前也据此拒绝重新赋值。
        self.constants: set[str] = set()
        self.ip = 0
        # 异常控制流：活跃处理器栈与待处理的返回值/跳转/异常
        self.handlers: list[dict] = []
        self.pending_exc: object = MISSING
        self.pending_raw_exc: object = MISSING
        self.pending_catch_value: object = MISSING
        self.pending_return: object = MISSING
        self.finally_return_ready: bool = False
        self.pending_jump: object = MISSING

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