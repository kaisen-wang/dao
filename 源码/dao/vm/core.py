import operator

from ..ast_nodes import (
    BooleanLiteral,
    DictPattern,
    EnumVariantPattern,
    FunctionCall,
    Identifier,
    ListPattern,
    MemberAccess,
    NullLiteral,
    NumberLiteral,
    StringLiteral,
    TypeCheckPattern,
)
from ..bytecode.code_object import CodeObject
from ..bytecode.frame import Frame
from ..bytecode.opcodes import OpCode
from ..builtins import BuiltinFunction, get_builtins
from ..errors import 名称错误, 类型错误, 索引错误, 运行时错误


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
            elif self._is_enum(obj):
                frame.push(self._eval_enum_member(obj, name))
            elif self._is_enum_variant(obj):
                frame.push(self._eval_enum_variant_member(obj, name, frame))
            elif hasattr(obj, name):
                frame.push(getattr(obj, name))
            else:
                raise 名称错误(f"对象没有属性 '{name}'")
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
            # 与 AST 解释器保持一致：仅列表/字典/文本支持索引访问，
            # 元组等其它类型应抛类型错误而非依赖 Python 的 __getitem__。
            if not isinstance(obj, (list, dict, str)):
                raise 类型错误(
                    f"类型 '{type(obj).__name__}' 不支持索引访问"
                )
            if isinstance(obj, dict) and index not in obj:
                raise 名称错误(f"字典中不存在键 '{index}'")
            if isinstance(obj, (list, str)) and isinstance(index, int):
                if index < -len(obj) or index >= len(obj):
                    raise 索引错误(
                        f"索引 {index} 超出范围 (长度 {len(obj)})"
                    )
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
        elif op == OpCode.BUILD_ENUM:
            from ..ast_nodes import EnumVariant
            from ..interpreter.statements import DaoEnum

            name, values, variant_tuples = frame.code.constants[operand]
            variants = [EnumVariant(name=v, params=list(p)) for v, p in variant_tuples]
            frame.push(DaoEnum(name, values, variants))
        elif op == OpCode.MATCH_PATTERN:
            pattern, is_wildcard = frame.code.constants[operand]
            subject = frame.pop()
            frame.push(self._match_pattern(pattern, subject, frame, is_wildcard))
        elif op == OpCode.BUILD_CHANNEL:
            from ..concurrency.channels import BufferedChannel, Channel

            capacity = frame.code.constants[operand]
            frame.push(Channel() if capacity is None else BufferedChannel(capacity))
        elif op == OpCode.SEND_VALUE:
            value = frame.pop()
            channel = frame.pop()
            from ..concurrency.channels import BufferedChannel, Channel

            if not isinstance(channel, (Channel, BufferedChannel)):
                raise 类型错误("发送操作的目标必须是通道对象")
            channel.send(value)
        elif op == OpCode.RECEIVE_VALUE:
            channel = frame.pop()
            frame.push(channel.receive())
        return None

    # ========================
    # 枚举与模式匹配辅助
    # ========================

    @staticmethod
    def _is_enum(obj) -> bool:
        from ..interpreter.statements import DaoEnum
        return isinstance(obj, DaoEnum)

    @staticmethod
    def _is_enum_variant(obj) -> bool:
        from ..interpreter.statements import DaoEnumVariant
        return isinstance(obj, DaoEnumVariant)

    def _eval_enum_member(self, enum_obj, name: str):
        """求值枚举类型的成员：简单变体或带参变体构造器。"""
        from ..interpreter.statements import DaoEnumVariant

        if name not in enum_obj.values:
            raise 运行时错误(f"枚举 '{enum_obj.name}' 中不存在变体 '{name}'")
        if enum_obj.has_variant_params(name):
            return BuiltinFunction(
                name,
                lambda *args: DaoEnumVariant(enum_obj.name, name, tuple(args)),
            )
        return DaoEnumVariant(enum_obj.name, name)

    def _eval_enum_variant_member(self, variant, name: str, frame: Frame | None = None):
        """求值枚举变体实例：内建字段与按参数名访问的关联值。"""
        if name == "数据":
            return variant.data
        if name == "变体名":
            return variant.variant_name
        if name == "枚举名":
            return variant.enum_name

        # 关联值按变体参数名访问，例如 结果.成功(5).值
        enum_obj = None
        if frame is not None:
            scope = frame
            while scope is not None:
                if variant.enum_name in scope.locals:
                    enum_obj = scope.locals[variant.enum_name]
                    break
                scope = scope.parent
        if enum_obj is None:
            enum_obj = self.globals.get(variant.enum_name)
        if enum_obj is not None:
            for v in getattr(enum_obj, "variants", []):
                if getattr(v, "name", None) == variant.variant_name:
                    params = getattr(v, "params", [])
                    if name in params:
                        idx = params.index(name)
                        if idx < len(variant.data):
                            return variant.data[idx]
                    break

        raise 运行时错误(
            f"枚举 '{variant.enum_name}.{variant.variant_name}' 没有属性 '{name}'"
        )

    def _name_defined(self, name: str, frame: Frame) -> bool:
        """变量是否已在静态作用域链或全局作用域中定义。"""
        scope = frame
        while scope is not None:
            if name in scope.locals:
                return True
            scope = scope.parent
        return name in self.globals

    def _load_name_value(self, name: str, frame: Frame):
        scope = frame
        while scope is not None:
            if name in scope.locals:
                return scope.locals[name]
            scope = scope.parent
        return self.globals[name]

    @staticmethod
    def _literal_value(expr):
        """求值简单字面量模式；非字面量返回 (False, None)。"""
        if isinstance(expr, NullLiteral):
            return True, None
        if isinstance(expr, (NumberLiteral, StringLiteral, BooleanLiteral)):
            return True, expr.value
        return False, None

    def _match_pattern(self, pattern, subject, frame: Frame, is_wildcard: bool) -> bool:
        """模式匹配核心：与 AST 解释器 ``StatementExecutor._match_pattern`` 对齐。

        绑定变量直接写入 ``frame.locals``，供内联编译的分支体读取。
        """
        from ..interpreter.statements import DaoEnumVariant

        if is_wildcard:
            return True

        if isinstance(pattern, Identifier):
            if pattern.name == "_":
                return True
            if self._name_defined(pattern.name, frame):
                return self._load_name_value(pattern.name, frame) == subject
            frame.locals[pattern.name] = subject
            return True

        ok, value = self._literal_value(pattern)
        if ok:
            return value == subject

        if isinstance(pattern, EnumVariantPattern):
            if not isinstance(subject, DaoEnumVariant):
                return False
            if (
                subject.enum_name != pattern.enum_name
                or subject.variant_name != pattern.variant_name
            ):
                return False
            if pattern.binding:
                data = subject.data
                frame.locals[pattern.binding] = (
                    data[0] if len(data) == 1 else data if data else None
                )
            return True

        # 枚举变体模式：结果.成功(v) / 颜色.红
        if isinstance(pattern, FunctionCall) and isinstance(pattern.callee, MemberAccess):
            obj = pattern.callee.object
            if isinstance(obj, Identifier):
                if not isinstance(subject, DaoEnumVariant):
                    return False
                if (
                    subject.enum_name != obj.name
                    or subject.variant_name != pattern.callee.member
                ):
                    return False
                if pattern.arguments:
                    binding = pattern.arguments[0]
                    if isinstance(binding, Identifier) and binding.name != "_":
                        data = subject.data
                        frame.locals[binding.name] = (
                            data[0] if len(data) == 1 else data if data else None
                        )
                return True

        if isinstance(pattern, MemberAccess) and isinstance(pattern.object, Identifier):
            if not isinstance(subject, DaoEnumVariant):
                return False
            return (
                subject.enum_name == pattern.object.name
                and subject.variant_name == pattern.member
            )

        if isinstance(pattern, TypeCheckPattern):
            checks = {
                "列表": lambda v: isinstance(v, list),
                "字典": lambda v: isinstance(v, dict),
                "数值": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
                "文本": lambda v: isinstance(v, str),
                "布尔": lambda v: isinstance(v, bool),
                "函数": lambda v: callable(v),
            }
            checker = checks.get(pattern.type_name)
            return checker(subject) if checker else False

        if isinstance(pattern, ListPattern):
            if not isinstance(subject, list):
                return False
            elements = pattern.elements
            if pattern.has_spread:
                fixed = len(elements) - 1
                if len(subject) < fixed:
                    return False
                for i in range(fixed):
                    elem = elements[i]
                    if isinstance(elem, Identifier):
                        if elem.name == "_":
                            continue
                        frame.locals[elem.name] = subject[i]
                    else:
                        ok, val = self._literal_value(elem)
                        if not ok or val != subject[i]:
                            return False
                spread = elements[-1]
                if isinstance(spread, Identifier) and spread.name != "_":
                    frame.locals[spread.name] = subject[fixed:]
                return True
            if len(subject) != len(elements):
                return False
            for i, elem in enumerate(elements):
                if isinstance(elem, Identifier):
                    if elem.name == "_":
                        continue
                    frame.locals[elem.name] = subject[i]
                else:
                    ok, val = self._literal_value(elem)
                    if not ok or val != subject[i]:
                        return False
            return True

        if isinstance(pattern, DictPattern):
            if not isinstance(subject, dict):
                return False
            for key_expr, value_expr in pattern.pairs:
                ok, key = self._literal_value(key_expr)
                if not ok or key not in subject:
                    return False
                if isinstance(value_expr, Identifier):
                    if value_expr.name == "_":
                        continue
                    frame.locals[value_expr.name] = subject[key]
                else:
                    ok, val = self._literal_value(value_expr)
                    if not ok or val != subject[key]:
                        return False
            return True

        return False

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