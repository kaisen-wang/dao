import operator
from types import SimpleNamespace

from ..ast_nodes import (
    AbstractDecl,
    BooleanLiteral,
    ClassDecl,
    DictPattern,
    EnumVariantPattern,
    FunctionCall,
    Identifier,
    ListPattern,
    MemberAccess,
    NullLiteral,
    NumberLiteral,
    StringLiteral,
    TraitDecl,
    TypeCheckPattern,
)
from ..bytecode.code_object import CodeObject
from ..bytecode.frame import MISSING, Frame
from ..bytecode.opcodes import OpCode
from ..builtins import BuiltinFunction, DaoCallable, get_builtins
from ..errors import (
    错误信息,
    道错误,
    名称错误,
    类型错误,
    索引错误,
    运行时错误,
)

# 二元运算 opcode → 道语言运算符文本（用于 AST 侧运算符重载方法名）
_BINARY_OP_SYMBOLS = {
    OpCode.BINARY_ADD: "+",
    OpCode.BINARY_SUB: "-",
    OpCode.BINARY_MUL: "*",
    OpCode.BINARY_DIV: "/",
    OpCode.BINARY_MOD: "%",
    OpCode.BINARY_POW: "**",
    OpCode.BINARY_FLOOR_DIV: "//",
    OpCode.COMPARE_EQ: "==",
    OpCode.COMPARE_NE: "!=",
    OpCode.COMPARE_LT: "<",
    OpCode.COMPARE_LE: "<=",
    OpCode.COMPARE_GT: ">",
    OpCode.COMPARE_GE: ">=",
    OpCode.CONTAINS: "在",
    OpCode.NOT_CONTAINS: "不在",
}


class VirtualMachine:
    def __init__(self):
        # 与 AST 解释器保持一致：注入基础内置函数（打印/长度/范围等）
        self.globals: dict[str, object] = {}
        # 全局常量名持久集合：桥接环境的 global 层别名到它，
        # 避免把全局常量误写到某个栈帧上。
        self._global_constants: set[str] = set()
        for name, func in get_builtins().items():
            self.globals[name] = func
        self._call_depth = 0
        self._max_call_depth = 1000
        self._jit_enabled = False
        self._hotspot_detector = None
        self._type_feedback = {}
        self._jit_compiler = None
        self._root_compiled = set()
        # 模块系统：惰性复用一个 AST 解释器执行导入/导出语句，
        # 直接复用其模块加载、导出过滤、通配符、别名与错误处理逻辑。
        self._import_interpreter = None
        # 与 AST 解释器一致的模块搜索路径（运行前可按需追加）
        self.module_search_paths: list[str] = []
        # 函数式内置（映射/筛选/折叠/排序等）由解释器包提供。此处提前建立
        # 桥接解释器并注入包装后的内置函数，避免纯 VM 程序在没有任何委托
        # 语句时出现「变量 '映射' 未定义」的语义差异。
        self._get_import_interpreter()

    def enable_jit(self, threshold: int = 100):
        from ..jit.hotspot import HotspotDetector
        from ..jit.compiler import JitCompiler
        self._jit_enabled = True
        self._hotspot_detector = HotspotDetector(threshold=threshold)
        self._jit_compiler = JitCompiler(self._hotspot_detector)

    @staticmethod
    def _invoke_native(native, vm, frame, code):
        """调用生成的专用函数；守卫失败抛出 ``_Deopt`` 交由调用方回退。"""
        return native[0](vm, frame, code.constants, code.local_names,
                         code.instructions, native[1])

    @staticmethod
    def _is_truthy(value) -> bool:
        """复用 AST 解释器的真值判断规则，避免 Python ``not`` 语义偏差。"""
        from ..interpreter.core import Interpreter

        return Interpreter._is_truthy(value)

    # JIT 原生代码生成的辅助调用（保持与解释执行同一套语义）。
    def _truthy(self, value) -> bool:
        return self._is_truthy(value)

    def _unary_not(self, value) -> bool:
        return not self._is_truthy(value)

    def _binary_op(self, symbol: str, left, right, line: int = 0):
        inst = SimpleNamespace(line=line, column=0)
        return self._binary_operation(symbol, left, right, inst, None)

    def run(self, code: CodeObject) -> object:
        frame = Frame(code=code)
        if self._jit_enabled and self._jit_compiler:
            from ..jit.native import _Deopt
            key = id(code)
            native = self._jit_compiler.get_native(key)
            if native is None and key not in self._root_compiled:
                self._root_compiled.add(key)
                if not self._jit_compiler.is_disabled(key):
                    self._jit_compiler.compile_hotspot(key, code, {})
                    native = self._jit_compiler.get_native(key)
            if native is not None:
                try:
                    return self._invoke_native(native, self, frame, code)
                except _Deopt:
                    self._jit_compiler.handle_deoptimization(key)
                    frame = Frame(code=code)
        return self._execute_frame(frame)

    def _execute_frame(self, frame: Frame) -> object:
        while frame.ip < len(frame.code.instructions):
            inst = frame.code.instructions[frame.ip]
            current_ip = frame.ip
            frame.ip += 1
            try:
                result = self._dispatch(inst, frame)
            except Exception as exc:
                if not self._dispatch_exception(exc, frame, current_ip):
                    raise
                continue
            if frame.pending_return is not MISSING and frame.finally_return_ready:
                value = frame.pending_return
                frame.pending_return = MISSING
                frame.finally_return_ready = False
                return value
            if result is not None:
                return result
        return frame.pop() if frame.stack else None

    def _active_handler(self, frame: Frame, ip: int, kind: str | None = None):
        """当前 ip 覆盖范围内的最内层处理器。"""
        for handler in reversed(frame.handlers):
            if handler["consumed"]:
                continue
            if kind is not None and handler["kind"] != kind:
                continue
            if handler["start"] <= ip < handler["end"]:
                return handler
        return None

    def _dispatch_exception(self, exc, frame: Frame, ip: int) -> bool:
        """把异常交给最内层处理器；返回 False 表示应继续向外抛出。"""
        from .exceptions import is_control_signal, wrap_python_exception

        if is_control_signal(exc):
            return False
        handler = self._active_handler(frame, ip)
        if handler is None:
            return False
        del frame.stack[handler["depth"]:]
        handler["consumed"] = True
        frame.pending_raw_exc = exc
        from ..builtins.oop_types import DaoError

        frame.pending_exc = (
            exc if isinstance(exc, 道错误)
            else wrap_python_exception(
                exc, self._bridge_environment(frame), source=""
            )
        )
        if isinstance(exc, DaoError):
            # 用户自定义错误对象直接绑定，保留 .信息/.类型 等属性
            frame.pending_catch_value = exc
        else:
            wrapped = frame.pending_exc
            # 与 AST exec_try 一致：其它异常（含道错误）绑定 错误信息 包装对象
            frame.pending_catch_value = 错误信息(
                信息=getattr(
                    wrapped, "信息",
                    f"{type(exc).__name__} {str(wrapped)}",
                ),
                类型=getattr(wrapped, "类型", type(exc).__name__),
                行=getattr(wrapped, "行", getattr(exc, "line", 0)),
                列=getattr(wrapped, "列", getattr(exc, "column", 0)),
                文件名=getattr(wrapped, "文件名", getattr(exc, "filename", "")),
                来源=getattr(wrapped, "来源", getattr(exc, "source", "")),
                堆栈=getattr(wrapped, "堆栈", ""),
            )
        frame.ip = handler["handler"]
        return True

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
                raise 名称错误(f"变量 '{name}' 未定义")
        elif op == OpCode.STORE_LOCAL:
            name = frame.code.local_names[operand]
            if name in frame.constants:
                raise 运行时错误(f"常量 '{name}' 不能被重新赋值")
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
                    raise 名称错误(f"变量 '{name}' 未定义")
        elif op == OpCode.STORE_NAME:
            name = frame.code.constants[operand]
            value = frame.pop()
            # 赋值应更新变量所在的实际作用域（可能在外层帧），而不是一律写入全局。
            # 与 AST 解释器的 Environment.set 保持一致：命中作用域若把该名字
            # 声明为常量，则拒绝重新赋值。
            scope = frame
            while scope is not None:
                if name in scope.locals:
                    if name in scope.constants:
                        raise 运行时错误(f"常量 '{name}' 不能被重新赋值")
                    scope.locals[name] = value
                    break
                scope = scope.parent
            else:
                if name in self._global_constants:
                    raise 运行时错误(f"常量 '{name}' 不能被重新赋值")
                self.globals[name] = value
        elif op in _BINARY_OP_SYMBOLS:
            right, left = frame.pop(), frame.pop()
            frame.push(self._binary_operation(
                _BINARY_OP_SYMBOLS[op], left, right, inst, frame
            ))
        elif op in (OpCode.JUMP, OpCode.LOOP):
            # 离开 finally 保护区时先执行 finally，再恢复原跳转目标
            current = frame.ip - 1
            handler = self._active_handler(frame, current, kind="finally")
            if handler is not None and not (handler["start"] <= operand < handler["end"]):
                handler["consumed"] = True
                del frame.stack[handler["depth"]:]
                frame.pending_jump = operand
                frame.ip = handler["handler"]
            else:
                frame.ip = operand
        elif op == OpCode.JUMP_FINALLY:
            frame.ip = operand
        elif op == OpCode.JUMP_IF_FALSE:
            cond = frame.pop()
            if not self._is_truthy(cond):
                frame.ip = operand
        elif op == OpCode.POP_JUMP_IF_FALSE:
            cond = frame.pop()
            if not self._is_truthy(cond):
                frame.ip = operand
        elif op == OpCode.CALL_FUNCTION:
            arg_count = operand
            args = [frame.pop() for _ in range(arg_count)][::-1]
            callee = frame.pop()
            result = self._call(callee, args)
            frame.push(result)
        elif op == OpCode.RETURN_VALUE:
            # 防御：语句型模块（如末行为赋值/循环）不产生值时返回 None，
            # 避免栈顶为空导致解释器崩溃。
            value = frame.pop() if frame.stack else None
            handler = self._active_handler(frame, frame.ip - 1, kind="finally")
            if handler is not None:
                handler["consumed"] = True
                del frame.stack[handler["depth"]:]
                frame.pending_return = value
                frame.ip = handler["handler"]
                return None
            return value
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
            # 栈是后进先出，逆序还原源码中的键顺序
            frame.push(dict(reversed(items)))
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
            elif self._is_delegated_member(obj):
                frame.push(self._eval_delegated_member(obj, name, frame, inst.line))
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
            elif hasattr(obj, "set_field"):
                obj.set_field(name, value)
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
            if isinstance(obj, dict):
                if index not in obj:
                    raise 名称错误(f"字典中不存在键 '{index}'")
            else:
                # 与 AST eval_index_access 一致：列表/文本下标先 int()。
                index = int(index)
                kind = "列表" if isinstance(obj, list) else "字符串"
                if index < -len(obj) or index >= len(obj):
                    raise 索引错误(
                        f"{kind}索引 {index} 超出范围 (长度 {len(obj)})"
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
            # 成功：迭代器保留在栈上并压入下一个值；
            # 耗尽：弹出迭代器并跳到循环出口（operand 由编译器回填）。
            iterator = frame.peek()
            try:
                value = next(iterator)
            except StopIteration:
                frame.pop()
                frame.ip = operand
            else:
                frame.push(value)
        elif op == OpCode.FOR_ITER_PAIR:
            # 栈上依次为可迭代对象、迭代器；成功时压入 (键, 值)
            iterator = frame.peek()
            try:
                item = next(iterator)
            except StopIteration:
                frame.pop()
                frame.pop()
                frame.ip = operand
            else:
                source = frame.peek(1)
                frame.push(item)
                frame.push(source[item] if isinstance(source, dict) else None)
        elif op == OpCode.POP_TOP:
            frame.pop()
        elif op == OpCode.DUP_TOP:
            frame.push(frame.peek())
        elif op == OpCode.UNARY_NEGATIVE:
            frame.push(-frame.pop())
        elif op == OpCode.UNARY_NOT:
            frame.push(not self._is_truthy(frame.pop()))
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
            pattern_data = frame.code.constants[operand]
            # 兼容旧二元组常量格式；新格式携带 force_bind 标志。
            if isinstance(pattern_data, tuple) and len(pattern_data) == 3:
                pattern, is_wildcard, force_bind = pattern_data
            else:
                pattern, is_wildcard = pattern_data
                force_bind = False
            subject = frame.pop()
            frame.push(
                self._match_pattern(pattern, subject, frame, is_wildcard, force_bind)
            )
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
        elif op == OpCode.BUILD_RANGE:
            # 与解释器 exec_for_range 一致：range(start, end + 1, step)
            if operand == 3:
                step = int(frame.pop())
                end = int(frame.pop())
                start = int(frame.pop())
            else:
                end = int(frame.pop())
                start = int(frame.pop())
                step = 1
            frame.push(list(range(start, end + 1, step)))
        elif op == OpCode.CAPTURE_NAME:
            name = frame.code.constants[operand]
            # 只关心当前栈帧的绑定：循环结束后恢复它，使外层同名变量重新可见
            frame.push((name in frame.locals, frame.locals.get(name)))
        elif op == OpCode.STORE_SCOPE_LOCAL:
            name = frame.code.constants[operand]
            if name in frame.constants:
                raise 运行时错误(f"常量 '{name}' 不能被重新赋值")
            frame.locals[name] = frame.pop()
        elif op == OpCode.RESTORE_NAME:
            name = frame.code.constants[operand]
            existed, old_value = frame.pop()
            if existed:
                frame.locals[name] = old_value
            else:
                frame.locals.pop(name, None)
        elif op in (OpCode.IMPORT_STMT, OpCode.EXPORT_STMT):
            self._exec_import_export(inst, frame)
        elif op in (OpCode.MACRO_DEF, OpCode.MACRO_CALL, OpCode.AST_DECL):
            self._exec_delegated_node(op, inst, frame)
        elif op == OpCode.APPLY_ANNOTATIONS:
            stmt, name_idx = frame.code.constants[inst.operand]
            name = frame.code.local_names[name_idx]
            target = frame.locals.get(name)
            annotations = getattr(stmt, "annotations", None) or []
            interpreter = self._get_import_interpreter()
            env = self._bridge_environment(frame)
            saved = self._wrap_vm_closures(frame)
            try:
                replacement = interpreter._apply_annotations(target, annotations, env)
            finally:
                self._restore_vm_closures(saved)
            frame.locals[name] = replacement
        elif op == OpCode.DELEGATE_STMT:
            # VM 未原生实现、但 AST 解释器已完整实现的语句：整条语句
            # 委托执行，操作数 = 常量池中的 AST 节点，无栈效应。
            from .bridge import sync_environment

            node = frame.code.constants[operand]
            interpreter = self._get_import_interpreter()
            env = self._bridge_environment(frame)
            saved = self._wrap_vm_closures(frame)
            try:
                interpreter.exec_statement(node, env)
            finally:
                self._restore_vm_closures(saved)
                sync_environment(env, frame)
        elif op == OpCode.DELEGATE_EXPR:
            expr = frame.code.constants[inst.operand]
            interpreter = self._get_import_interpreter()
            saved = self._wrap_vm_closures(frame)
            try:
                value = interpreter.eval_expression(
                    expr, self._bridge_environment(frame)
                )
            finally:
                self._restore_vm_closures(saved)
            frame.push(value)
        elif op in (OpCode.SETUP_TRY, OpCode.SETUP_FINALLY):
            frame.handlers.append({
                "kind": "try" if op == OpCode.SETUP_TRY else "finally",
                "start": frame.ip,
                "end": operand,
                "handler": operand,
                "depth": len(frame.stack),
                "base": len(frame.handlers),
                "consumed": False,
            })
        elif op == OpCode.POP_BLOCK:
            if frame.handlers:
                frame.handlers.pop()
        elif op == OpCode.LOAD_EXC:
            value = frame.pending_catch_value
            frame.push(
                value if value is not MISSING else (
                    frame.pending_exc if frame.pending_exc is not MISSING else None
                )
            )
        elif op == OpCode.MATCH_EXC:
            from .exceptions import matches_catch

            exc = frame.pop()
            raw = frame.pending_raw_exc
            frame.push(matches_catch(
                raw if raw is not MISSING else exc,
                frame.code.constants[operand],
                self._bridge_environment(frame),
            ))
        elif op == OpCode.CLEAR_EXC:
            frame.pending_exc = MISSING
            frame.pending_raw_exc = MISSING
            frame.pending_catch_value = MISSING
        elif op == OpCode.RAISE:
            from .exceptions import normalize_raise

            raise normalize_raise(frame.pop(), line=inst.line)
        elif op == OpCode.END_FINALLY:
            indices = [
                i for i, h in enumerate(frame.handlers)
                if h["kind"] == "finally"
            ]
            if indices:
                del frame.handlers[indices[-1]:]
            if frame.pending_exc is not MISSING:
                exc = frame.pending_exc
                frame.pending_exc = MISSING
                frame.pending_raw_exc = MISSING
                frame.pending_catch_value = MISSING
                raise exc
            if frame.pending_jump is not MISSING:
                frame.ip = frame.pending_jump
                frame.pending_jump = MISSING
            if frame.pending_return is not MISSING:
                frame.finally_return_ready = True
        return None

    def _binary_operation(self, symbol: str, left, right, inst, frame: Frame):
        """按 AST ``ExpressionEvaluator.eval_binary_op`` 的语义完成一次二元运算。

        左右操作数已由字节码各求值一次，这里只做运算（含运算符重载），
        不会重复求值右操作数。
        """
        from ..builtins import DaoInstance

        if isinstance(left, DaoInstance):
            method = left.klass.find_method(f"运算符{symbol}")
            if method is not None:
                interpreter = self._get_import_interpreter()
                call_expr = SimpleNamespace(
                    line=getattr(inst, "line", 0),
                    column=getattr(inst, "column", 0),
                    file=getattr(frame.code, "filename", "") if frame is not None else "",
                )
                saved = self._wrap_vm_closures(frame) if frame is not None else []
                try:
                    return interpreter._call_method(
                        left, method, [right], {}, call_expr
                    )
                finally:
                    self._restore_vm_closures(saved)

        if symbol == "+":
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return left + right
        if symbol == "-":
            return left - right
        if symbol == "*":
            # 与 AST 一致：文本乘数值时先取整，避免 "道" * 2.0 抛类型错误。
            if isinstance(left, str) and isinstance(right, (int, float)):
                return left * int(right)
            if isinstance(right, str) and isinstance(left, (int, float)):
                return right * int(left)
            return left * right
        if symbol in ("/", "//"):
            if right == 0:
                raise 运行时错误("除零错误")
            return left / right if symbol == "/" else left // right
        if symbol == "%":
            return left % right
        if symbol == "**":
            return left**right
        if symbol == "==":
            return left == right
        if symbol == "!=":
            return left != right
        if symbol == "<":
            return left < right
        if symbol == "<=":
            return left <= right
        if symbol == ">":
            return left > right
        if symbol == ">=":
            return left >= right
        if symbol in ("在", "不在"):
            try:
                result = left in right
            except TypeError:
                raise 类型错误(
                    f"类型 '{type(right).__name__}' 不支持成员检查"
                ) from None
            return result if symbol == "在" else not result
        # JIT 原生代码用符号直译 并且/或者；对齐 AST 的真值语义。
        if symbol == "and":
            return right if self._is_truthy(left) else left
        if symbol == "or":
            return left if self._is_truthy(left) else right
        raise 运行时错误(f"未知的运算符: '{symbol}'")

    def _exec_delegated_node(self, op: OpCode, inst, frame: Frame) -> None:
        """宏与类型声明复用内嵌 AST 解释器，保留其完整语义。"""
        from .bridge import sync_environment

        node = frame.code.constants[inst.operand]
        interpreter = self._get_import_interpreter()
        env = self._bridge_environment(frame)
        saved = self._wrap_vm_closures(frame)
        try:
            if op == OpCode.MACRO_DEF:
                interpreter.exec_macro_definition(node, env)
            elif op == OpCode.MACRO_CALL:
                frame.push(interpreter.eval_macro_call(node, env))
            elif isinstance(node, ClassDecl):
                interpreter.exec_class_decl(node, env)
            elif isinstance(node, TraitDecl):
                interpreter.exec_trait_decl(node, env)
            elif isinstance(node, AbstractDecl):
                interpreter.exec_abstract_decl(node, env)
        finally:
            self._restore_vm_closures(saved)
        sync_environment(env, frame)

    def _get_import_interpreter(self):
        """惰性构造并复用一个 AST 解释器，用于执行导入/导出语句。

        延迟导入避免 dao.vm 与 dao.interpreter 之间的循环导入；复用同一实例
        使其模块缓存在多次导入之间共享（与 AST 模式一致）。
        """
        if self._import_interpreter is None:
            from ..interpreter import Interpreter

            self._import_interpreter = Interpreter()
            # 错误报告会读取 source；AST 模式由 execute() 设置，这里补一个默认值。
            self._import_interpreter.source = ""
            # AST 模式在 execute() 中注册内置宏；VM 委托执行不经过 execute()，
            # 这里只注册一次，避免清空后续通过 MACRO_DEF 注册的用户宏。
            from ..macros.builtins import register_builtin_macros

            register_builtin_macros(self._import_interpreter.macro_registry)
            # AST 解释器的内置函数（折叠/映射等）默认不在 VM globals 中，
            # 委托执行的类方法需要通过桥接环境查到它们。
            from ..builtins import get_interpreter_builtins

            for name, func in get_interpreter_builtins().items():
                if name not in self.globals:
                    func.interpreter = self._import_interpreter

                    def _adapt(*args, _fn=func, **kwargs):
                        adapted = [self._as_ast_callable(a) for a in args]
                        return _fn.call(adapted, kwargs)

                    self.globals[name] = BuiltinFunction(name, _adapt)
        # 搜索路径可能在 VM 构造后才被修改，每次同步同一列表引用。
        self._import_interpreter.module_search_paths = self.module_search_paths
        return self._import_interpreter

    def _as_ast_callable(self, fn, name: str = "<闭包>"):
        """把 VM 闭包元组包装成 AST 解释器可调用的 BuiltinFunction。"""
        if not (isinstance(fn, tuple) and len(fn) in (2, 3)
                and isinstance(fn[0], CodeObject)):
            return fn

        def _call_vm_closure(*args, _fn=fn, **kwargs):
            positional = list(args)
            for param in _fn[0].local_names:
                if param in kwargs:
                    positional.append(kwargs[param])
            return self._call(_fn, positional)

        return BuiltinFunction(name, _call_vm_closure)

    def _wrap_vm_closures(self, frame: Frame) -> list:
        """临时把 VM 闭包包装成 AST 解释器可调用的 BuiltinFunction。"""
        saved: list = []
        for mapping in (frame.locals, self.globals):
            for name, fn in list(mapping.items()):
                wrapped = self._as_ast_callable(fn, name)
                if wrapped is fn:
                    continue
                saved.append((mapping, name, fn))
                mapping[name] = wrapped
        return saved

    @staticmethod
    def _restore_vm_closures(saved: list) -> None:
        for mapping, name, fn in saved:
            mapping[name] = fn

    def _bridge_environment(self, frame: Frame):
        """把当前栈帧链包装成 AST Environment，供委托执行与异常包装复用。"""
        from .bridge import frame_to_environment

        return frame_to_environment(
            frame,
            self.globals,
            source=self._get_import_interpreter().source or "",
            global_constants=self._global_constants,
        )

    def _exec_import_export(self, inst, frame: Frame) -> None:
        """执行导入/导出语句，把 AST 解释器绑定的名称写入当前栈帧。"""
        from ..environment import Environment

        stmt = frame.code.constants[inst.operand]
        interpreter = self._get_import_interpreter()
        env = Environment()
        if inst.opcode == OpCode.IMPORT_STMT:
            interpreter.exec_import(stmt, env)
        else:
            interpreter.exec_export(stmt, env)
        # 直接写字典而非 Environment.define：避免重复定义报错，
        # 后续 LOAD_NAME / LOAD_ATTR 即可从 frame.locals 找到这些名称。
        for name, value in env.values.items():
            frame.locals[name] = value

    # ========================
    # 枚举与模式匹配辅助
    # ========================

    @staticmethod
    def _is_delegated_member(obj) -> bool:
        from ..builtins.oop_types import DaoClass, DaoError, DaoInstance, SuperProxy

        return isinstance(obj, (DaoInstance, DaoClass, DaoError, SuperProxy, 道错误))

    def _eval_delegated_member(self, obj, name: str, frame: Frame, line: int):
        """OOP 对象的成员访问委托给持有其闭包环境的 AST 解释器。"""
        from ..builtins.oop_types import DaoClass, DaoError, SuperProxy

        node = SimpleNamespace(member=name, line=line, column=0)
        interpreter = self._get_import_interpreter()
        env = self._bridge_environment(frame)
        if isinstance(obj, SuperProxy):
            return interpreter._eval_super_member(obj, node, env)
        if isinstance(obj, (DaoError, 道错误)):
            return interpreter._eval_error_member(obj, node)
        if isinstance(obj, DaoClass):
            # 与 AST 解释器一致：先查静态方法（find_method 不覆盖 static_methods），
            # 再查普通方法；缺失时抛中文「类型没有方法或静态方法」错误。
            return interpreter._eval_class_member(obj, node)
        return interpreter._eval_instance_member(obj, node, env)

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

    def _match_pattern(
        self,
        pattern,
        subject,
        frame: Frame,
        is_wildcard: bool,
        force_bind: bool = False,
    ) -> bool:
        """模式匹配核心：与 AST 解释器 ``StatementExecutor._match_pattern`` 对齐。

        绑定变量直接写入 ``frame.locals``，供内联编译的分支体读取。
        """
        from ..interpreter.statements import DaoEnumVariant

        if is_wildcard:
            return True

        if isinstance(pattern, Identifier):
            if pattern.name == "_":
                return True
            # 带守卫的裸标识符模式强制绑定，使守卫能引用刚绑定的变量。
            if force_bind:
                frame.locals[pattern.name] = subject
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
            interpreter = self._get_import_interpreter()
            env = self._bridge_environment(frame)
            saved = self._wrap_vm_closures(frame)
            try:
                for key_expr, value_expr in pattern.pairs:
                    # 与 AST 一致：字典模式的键是表达式，经桥接环境求值。
                    key = interpreter.eval_expression(key_expr, env)
                    if key not in subject:
                        return False
                    if isinstance(value_expr, Identifier):
                        if value_expr.name != "_":
                            frame.locals[value_expr.name] = subject[key]
                    else:
                        ok, val = self._literal_value(value_expr)
                        if not ok or val != subject[key]:
                            return False
                return True
            finally:
                self._restore_vm_closures(saved)

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
                # 以 CodeObject 身份而非函数名为键，避免同名函数互相污染。
                key = id(func_code)
                native = None
                if self._jit_enabled and self._jit_compiler:
                    native = self._jit_compiler.get_native(key)

                # 不把捕获的变量复制为新帧的局部变量：它们通过 defining_frame 作用域链
                # 按引用访问，才能与 AST 解释器保持一致（捕获变量可被闭包内外共同修改）。
                if native is not None:
                    from ..jit.native import _Deopt
                    frame = Frame(code=func_code, parent=defining_frame)
                    for i, param in enumerate(func_code.local_names[:len(args)]):
                        frame.locals[param] = args[i] if i < len(args) else None
                    try:
                        return self._invoke_native(native, self, frame, func_code)
                    except _Deopt:
                        self._jit_compiler.handle_deoptimization(key)
                        frame = Frame(code=func_code, parent=defining_frame)
                        for i, param in enumerate(func_code.local_names[:len(args)]):
                            frame.locals[param] = args[i] if i < len(args) else None
                        return self._execute_frame(frame)

                if self._jit_enabled and self._hotspot_detector:
                    self._hotspot_detector.record_execution(key)
                    if (self._hotspot_detector.is_hot(key)
                            and not self._jit_compiler.is_disabled(key)):
                        specialized = self._jit_compiler.get_specialized(key)
                        if specialized is None:
                            self._jit_compiler.compile_hotspot(key, func_code, self._type_feedback)
                            specialized = self._jit_compiler.get_specialized(key)
                        if specialized is not None:
                            func_code = specialized

                frame = Frame(code=func_code, parent=defining_frame)
                for i, param in enumerate(func_code.local_names[:len(args)]):
                    frame.locals[param] = args[i] if i < len(args) else None
                    if self._jit_enabled:
                        from ..jit.type_feedback import TypeFeedbackEntry
                        feedback_key = f"{key}.{param}"
                        if feedback_key not in self._type_feedback:
                            self._type_feedback[feedback_key] = TypeFeedbackEntry(code_id=feedback_key)
                        self._type_feedback[feedback_key].record_type(args[i] if i < len(args) else None)
                return self._execute_frame(frame)
            elif isinstance(callee, BuiltinFunction):
                # 内置函数包装器只实现 .call()，不可直接 __call__
                return callee.call(args, {})
            elif isinstance(callee, DaoCallable):
                # 导入语句加载的模块函数等来自 AST 解释器，其闭包环境
                # 由同一个解释器实例持有，交还它统一调用（含方法、类、柯里化函数）。
                interpreter = self._get_import_interpreter()
                return interpreter.call_function(callee, args, {})
            elif callable(callee):
                return callee(*args)
            else:
                raise 运行时错误(f"不可调用的对象: {callee}")
        finally:
            self._call_depth -= 1