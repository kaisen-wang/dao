import operator

from ..bytecode.code_object import CodeObject
from ..bytecode.frame import Frame
from ..bytecode.opcodes import OpCode
from ..errors import 运行时错误


class VirtualMachine:
    def __init__(self):
        self.globals: dict[str, object] = {}
        self._call_depth = 0
        self._max_call_depth = 1000

    def run(self, code: CodeObject) -> object:
        frame = Frame(code=code)
        for i, name in enumerate(code.local_names):
            frame.locals[name] = i
        return self._execute_frame(frame)

    def _execute_frame(self, frame: Frame) -> object:
        while frame.ip < len(frame.code.instructions):
            inst = frame.code.instructions[frame.ip]
            frame.ip += 1
            result = self._dispatch(inst, frame)
            if result is not None:
                return result
        return frame.pop() if frame.stack else None

    def _dispatch(self, inst, frame: Frame):
        op = inst.opcode
        operand = inst.operand

        if op == OpCode.LOAD_CONST:
            frame.push(frame.code.constants[operand])
        elif op == OpCode.LOAD_LOCAL:
            name = frame.code.local_names[operand]
            if name in frame.locals:
                frame.push(frame.locals[name])
            else:
                frame.push(None)
        elif op == OpCode.STORE_LOCAL:
            name = frame.code.local_names[operand]
            frame.locals[name] = frame.pop()
        elif op == OpCode.LOAD_NAME:
            name = frame.code.constants[operand]
            if name in frame.locals:
                frame.push(frame.locals[name])
            elif name in self.globals:
                frame.push(self.globals[name])
            else:
                frame.push(None)
        elif op == OpCode.STORE_NAME:
            name = frame.code.constants[operand]
            self.globals[name] = frame.pop()
        elif op == OpCode.BINARY_ADD:
            right, left = frame.pop(), frame.pop()
            frame.push(left + right)
        elif op == OpCode.BINARY_SUB:
            right, left = frame.pop(), frame.pop()
            frame.push(left - right)
        elif op == OpCode.BINARY_MUL:
            right, left = frame.pop(), frame.pop()
            frame.push(left * right)
        elif op == OpCode.BINARY_DIV:
            right, left = frame.pop(), frame.pop()
            if right == 0:
                raise 运行时错误("除零错误")
            frame.push(left / right)
        elif op == OpCode.BINARY_MOD:
            right, left = frame.pop(), frame.pop()
            frame.push(left % right)
        elif op == OpCode.BINARY_POW:
            right, left = frame.pop(), frame.pop()
            frame.push(left ** right)
        elif op == OpCode.BINARY_FLOOR_DIV:
            right, left = frame.pop(), frame.pop()
            frame.push(left // right)
        elif op == OpCode.COMPARE_EQ:
            right, left = frame.pop(), frame.pop()
            frame.push(left == right)
        elif op == OpCode.COMPARE_NE:
            right, left = frame.pop(), frame.pop()
            frame.push(left != right)
        elif op == OpCode.COMPARE_LT:
            right, left = frame.pop(), frame.pop()
            frame.push(left < right)
        elif op == OpCode.COMPARE_LE:
            right, left = frame.pop(), frame.pop()
            frame.push(left <= right)
        elif op == OpCode.COMPARE_GT:
            right, left = frame.pop(), frame.pop()
            frame.push(left > right)
        elif op == OpCode.COMPARE_GE:
            right, left = frame.pop(), frame.pop()
            frame.push(left >= right)
        elif op == OpCode.JUMP:
            frame.ip = operand
        elif op == OpCode.JUMP_IF_FALSE:
            cond = frame.pop()
            if not cond:
                frame.ip = operand
        elif op == OpCode.POP_JUMP_IF_FALSE:
            cond = frame.pop()
            if not cond:
                frame.ip = operand
        elif op == OpCode.LOOP:
            frame.ip = operand
        elif op == OpCode.CALL_FUNCTION:
            arg_count = operand
            args = [frame.pop() for _ in range(arg_count)][::-1]
            callee = frame.pop()
            result = self._call(callee, args)
            frame.push(result)
        elif op == OpCode.RETURN_VALUE:
            return frame.pop()
        elif op == OpCode.MAKE_CLOSURE:
            func_code = frame.code.constants[operand]
            frame.push((func_code, dict(frame.locals)))
        elif op == OpCode.BUILD_LIST:
            count = operand
            elements = [frame.pop() for _ in range(count)][::-1]
            frame.push(elements)
        elif op == OpCode.BUILD_DICT:
            count = operand
            items = []
            for _ in range(count):
                v = frame.pop()
                k = frame.pop()
                items.append((k, v))
            frame.push(dict(items))
        elif op == OpCode.BUILD_TUPLE:
            count = operand
            elements = [frame.pop() for _ in range(count)][::-1]
            frame.push(tuple(elements))
        elif op == OpCode.BUILD_SET:
            count = operand
            elements = [frame.pop() for _ in range(count)][::-1]
            frame.push(set(elements))
        elif op == OpCode.LOAD_ATTR:
            obj = frame.pop()
            name = frame.code.constants[operand]
            if isinstance(obj, dict):
                frame.push(obj.get(name))
            elif hasattr(obj, name):
                frame.push(getattr(obj, name))
            else:
                frame.push(None)
        elif op == OpCode.STORE_ATTR:
            value = frame.pop()
            obj = frame.pop()
            name = frame.code.constants[operand]
            if isinstance(obj, dict):
                obj[name] = value
            else:
                setattr(obj, name, value)
        elif op == OpCode.LOAD_INDEX:
            index = frame.pop()
            obj = frame.pop()
            frame.push(obj[index])
        elif op == OpCode.STORE_INDEX:
            value = frame.pop()
            index = frame.pop()
            obj = frame.pop()
            obj[index] = value
        elif op == OpCode.GET_ITERATOR:
            obj = frame.pop()
            frame.push(iter(obj))
        elif op == OpCode.FOR_ITER:
            var_idx = operand
            iterator = frame.peek()
            try:
                value = next(iterator)
                name = frame.code.local_names[var_idx]
                frame.locals[name] = value
            except StopIteration:
                frame.pop()
                frame.ip = frame.code.instructions[frame.ip - 1].operand
        elif op == OpCode.POP_TOP:
            frame.pop()
        elif op == OpCode.DUP_TOP:
            frame.push(frame.peek())
        elif op == OpCode.UNARY_NEGATIVE:
            frame.push(-frame.pop())
        elif op == OpCode.UNARY_NOT:
            frame.push(not frame.pop())
        elif op == OpCode.LOGICAL_AND:
            right, left = frame.pop(), frame.pop()
            frame.push(left and right)
        elif op == OpCode.LOGICAL_OR:
            right, left = frame.pop(), frame.pop()
            frame.push(left or right)
        return None

    def _call(self, callee, args):
        self._call_depth += 1
        if self._call_depth > self._max_call_depth:
            raise 运行时错误("调用栈深度超限")
        try:
            if isinstance(callee, tuple) and len(callee) == 2 and isinstance(callee[0], CodeObject):
                func_code, closure_vars = callee
                frame = Frame(code=func_code, parent=None)
                frame.locals.update(closure_vars)
                for i, param in enumerate(func_code.local_names[:len(args)]):
                    frame.locals[param] = args[i] if i < len(args) else None
                return self._execute_frame(frame)
            elif callable(callee):
                return callee(*args)
            else:
                raise 运行时错误(f"不可调用的对象: {callee}")
        finally:
            self._call_depth -= 1