import operator

from ..bytecode.code_object import CodeObject
from ..bytecode.frame import Frame
from ..bytecode.opcodes import OpCode
from ..builtins import BuiltinFunction, get_builtins
from ..errors import 运行时错误


class VirtualMachine:
    def __init__(self):
        # 与 AST 解释器保持一致：注入基础内置函数（打印/长度/范围等）
        self.globals: dict[str, object] = {}
        for name, func in get_builtins().items():
            self.globals[name] = func
        self._call_depth = 0
        self._max_call_depth = 1000
        self._jit_enabled = False
        self._hotspot_detector = None
        self._type_feedback = {}
        self._jit_compiler = None

    def enable_jit(self, threshold: int = 100):
        from ..jit.hotspot import HotspotDetector
        from ..jit.compiler import JitCompiler
        self._jit_enabled = True
        self._hotspot_detector = HotspotDetector(threshold=threshold)
        self._jit_compiler = JitCompiler(self._hotspot_detector)

    def run(self, code: CodeObject) -> object:
        frame = Frame(code=code)
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
                raise 运行时错误(f"未定义的变量 '{name}'")
        elif op == OpCode.STORE_LOCAL:
            name = frame.code.local_names[operand]
            frame.locals[name] = frame.pop()
        elif op == OpCode.LOAD_NAME:
            name = frame.code.constants[operand]
            # 沿静态作用域链（定义时所在帧 -> 父帧 -> ...）查找，
            # 与 AST 解释器的 Environment.get 保持一致（支持闭包与递归）。
            scope = frame
            while scope is not None:
                if name in scope.locals:
                    frame.push(scope.locals[name])
                    break
                scope = scope.parent
            else:
                if name in self.globals:
                    frame.push(self.globals[name])
                else:
                    raise 运行时错误(f"未定义的变量 '{name}'")
        elif op == OpCode.STORE_NAME:
            name = frame.code.constants[operand]
            value = frame.pop()
            # 赋值应更新变量所在的实际作用域（可能在外层帧），而不是一律写入全局。
            # 与 AST 解释器的 Environment.set 保持一致。
            scope = frame
            while scope is not None:
                if name in scope.locals:
                    scope.locals[name] = value
                    break
                scope = scope.parent
            else:
                self.globals[name] = value
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
            # 闭包携带定义时所在的帧，变量通过父帧链按引用共享，
            # 与 AST 解释器的 Environment 作用域链一致（支持递归、前向引用、闭包写变量）。
            frame.push((func_code, dict(frame.locals), frame))
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
                if name in obj:
                    frame.push(obj[name])
                else:
                    raise 运行时错误(f"字典没有键 '{name}'")
            elif isinstance(obj, str):
                frame.push(self._builtin_str_member(obj, name))
            elif isinstance(obj, list):
                frame.push(self._builtin_list_member(obj, name))
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

    @staticmethod
    def _resolve_builtin_member(methods: dict, name: str, expr_name: str):
        """解析内置成员：无参属性直接求值，带参方法返回 BuiltinFunction。"""
        if name not in methods:
            raise 运行时错误(f"{expr_name}没有方法 '{name}'")
        result = methods[name]
        if callable(result) and not isinstance(result, BuiltinFunction):
            return result()
        return result

    def _builtin_str_member(self, s: str, name: str):
        methods = {
            "长度": lambda: len(s),
            "大写": lambda: s.upper(),
            "小写": lambda: s.lower(),
            "去空白": lambda: s.strip(),
            "分割": BuiltinFunction("分割", lambda sep=" ": s.split(sep)),
            "替换": BuiltinFunction("替换", lambda old, new: s.replace(old, new)),
            "包含": BuiltinFunction("包含", lambda sub: sub in s),
            "开头是": BuiltinFunction("开头是", lambda prefix: s.startswith(prefix)),
            "结尾是": BuiltinFunction("结尾是", lambda suffix: s.endswith(suffix)),
        }
        return self._resolve_builtin_member(methods, name, "文本")

    def _builtin_list_member(self, lst: list, name: str):
        methods = {
            "长度": lambda: len(lst),
            "追加": BuiltinFunction("追加", lambda item: lst.append(item) or lst),
            "弹出": BuiltinFunction("弹出", lambda: lst.pop()),
            "插入": BuiltinFunction("插入", lambda i, item: lst.insert(int(i), item) or lst),
            "连接": BuiltinFunction("连接", lambda sep="": sep.join(str(x) for x in lst)),
        }
        return self._resolve_builtin_member(methods, name, "列表")

    def _call(self, callee, args):
        self._call_depth += 1
        if self._call_depth > self._max_call_depth:
            raise 运行时错误("调用栈深度超限")
        try:
            if (isinstance(callee, tuple) and len(callee) in (2, 3)
                    and isinstance(callee[0], CodeObject)):
                func_code = callee[0]
                defining_frame = callee[2] if len(callee) == 3 else None
                if self._jit_enabled and self._hotspot_detector:
                    self._hotspot_detector.record_execution(func_code.name)
                    if self._hotspot_detector.is_hot(func_code.name):
                        specialized = self._jit_compiler.get_specialized(func_code.name)
                        if specialized is None:
                            self._jit_compiler.compile_hotspot(func_code.name, func_code, self._type_feedback)
                            specialized = self._jit_compiler.get_specialized(func_code.name)
                        if specialized is not None:
                            func_code = specialized
                # 不把捕获的变量复制为新帧的局部变量：它们通过 defining_frame 作用域链
                # 按引用访问，才能与 AST 解释器保持一致（捕获变量可被闭包内外共同修改）。
                frame = Frame(code=func_code, parent=defining_frame)
                for i, param in enumerate(func_code.local_names[:len(args)]):
                    frame.locals[param] = args[i] if i < len(args) else None
                    if self._jit_enabled:
                        from ..jit.type_feedback import TypeFeedbackEntry
                        key = f"{func_code.name}.{param}"
                        if key not in self._type_feedback:
                            self._type_feedback[key] = TypeFeedbackEntry(code_id=key)
                        self._type_feedback[key].record_type(args[i] if i < len(args) else None)
                return self._execute_frame(frame)
            elif isinstance(callee, BuiltinFunction):
                # 内置函数包装器只实现 .call()，不可直接 __call__
                return callee.call(args, {})
            elif callable(callee):
                return callee(*args)
            else:
                raise 运行时错误(f"不可调用的对象: {callee}")
        finally:
            self._call_depth -= 1