"""运行时代码生成：把 ``CodeObject`` 直译为 Python 函数。

生成的函数用 ``frame.stack`` 作为操作数栈，但控制流按基本块分派、块内是
顺序的 Python 语句，避免了解释器逐指令 ``if/elif`` 链与 ``Frame.push/pop``
方法调用的开销。生成的函数携带基于类型反馈的守卫；守卫失败时抛出
``_Deopt``，由 VM 捕获后回退到普通解释执行路径。
"""

from itertools import pairwise

from ..bytecode.opcodes import OpCode
from ..errors import 运行时错误

_MISSING = object()


class _Deopt(Exception):
    """内部信号：专用代码不再适用于当前运行时状态，需要去优化。"""


def _load_local(local_map, name):
    if name in local_map:
        return local_map[name]
    raise 运行时错误(f"未定义的变量 '{name}'")


def _load_name(frame, global_map, name):
    scope = frame
    while scope is not None:
        if name in scope.locals:
            return scope.locals[name]
        scope = scope.parent
    if name in global_map:
        return global_map[name]
    raise 运行时错误(f"未定义的变量 '{name}'")


def _store_name(frame, global_map, name, value):
    scope = frame
    while scope is not None:
        if name in scope.locals:
            scope.locals[name] = value
            return
        scope = scope.parent
    global_map[name] = value


# 支持直译的操作码。其余操作码通过 ``vm._dispatch`` 回退，保证语义完全一致。
_JUMP_OPS = {
    OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.POP_JUMP_IF_FALSE,
    OpCode.LOOP, OpCode.FOR_ITER, OpCode.FOR_ITER_PAIR,
}
_TERMINATORS = {
    OpCode.JUMP, OpCode.LOOP, OpCode.RETURN_VALUE,
    OpCode.FOR_ITER, OpCode.FOR_ITER_PAIR,
}
_BINARY = {
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
    OpCode.LOGICAL_AND: "and",
    OpCode.LOGICAL_OR: "or",
}
_BUILD_SEQ = {
    OpCode.BUILD_LIST: "list",
    OpCode.BUILD_TUPLE: "tuple",
    OpCode.BUILD_SET: "set",
}


class NativeCodegen:
    """把一个 ``CodeObject`` 翻译成可直接调用的 Python 函数。"""

    def __init__(self, code, feedback, code_id):
        self.code = code
        self.feedback = feedback
        self.code_id = code_id

    def generate(self):
        """返回 ``(native_fn, ip_to_block)``，无法生成时返回 ``None``。"""
        code = self.code
        insts = code.instructions
        n = len(insts)
        if not insts:
            return self._build_guards_only()

        leaders = {0}
        for i, inst in enumerate(insts):
            if inst.opcode in _JUMP_OPS and inst.operand is not None:
                target = inst.operand
                if isinstance(target, int) and 0 <= target <= n:
                    leaders.add(target)
                leaders.add(i + 1)
            elif inst.opcode in (OpCode.RETURN_VALUE,):
                leaders.add(i + 1)
        leaders = sorted(x for x in leaders if 0 <= x <= n)
        if n not in leaders:
            leaders.append(n)

        blocks = list(pairwise(leaders))
        exit_id = len(blocks)
        ip_to_block = [exit_id] * (n + 1)
        for bid, (start, end) in enumerate(blocks):
            for ip in range(start, end):
                ip_to_block[ip] = bid

        lines = [
            "def _dao_native(vm, frame, consts, names, insts, ipmap):",
            "    st = frame.stack",
            "    L = frame.locals",
            "    G = vm.globals",
        ]
        lines.extend(f"    {line}" for line in self._guard_lines())
        lines.append("    _ip = 0")
        lines.append("    while True:")
        for bid, (start, end) in enumerate(blocks):
            lines.append(f"        {'if' if bid == 0 else 'elif'} _ip == {bid}:")
            has_terminator = False
            for ip in range(start, end):
                body, terminates = self._emit_inst(insts[ip], ip, ip_to_block)
                lines.extend(f"            {line}" for line in body)
                has_terminator = has_terminator or terminates
            if not has_terminator:
                lines.append(f"            _ip = {ip_to_block[end]}")
                lines.append("            continue")
        lines.append("        else:")
        lines.append("            return st.pop() if st else None")

        return self._compile_source("\n".join(lines) + "\n", ip_to_block)

    def _build_guards_only(self):
        """空函数体：只需要守卫和返回语义。"""
        lines = [
            "def _dao_native(vm, frame, consts, names, insts, ipmap):",
            "    st = frame.stack",
            "    L = frame.locals",
            "    G = vm.globals",
        ]
        lines.extend(f"    {line}" for line in self._guard_lines())
        lines.append("    _ip = 0")
        lines.append("    while True:")
        lines.append("        if _ip == 0:")
        lines.append("            return st.pop() if st else None")
        return self._compile_source("\n".join(lines) + "\n", [0])

    def _compile_source(self, source, ip_to_block):
        guards = self._collect_guards()
        env = {
            "_Deopt": _Deopt,
            "_MISSING": _MISSING,
            "运行时错误": 运行时错误,
            "_load_local": _load_local,
            "_load_name": _load_name,
            "_store_name": _store_name,
        }
        for idx, (_, typ) in enumerate(guards):
            env[f"_T{idx}"] = typ
        try:
            # 故意使用 compile/exec：这是 JIT 的代码生成入口，源码完全由本模块构造。
            exec(compile(source, f"<dao-jit:{self.code.name}>", "exec"), env)  # noqa: S102
        except SyntaxError:
            return None
        return env["_dao_native"], ip_to_block

    def _collect_guards(self):
        prefix = f"{self.code_id}."
        guards = []
        for key, entry in self.feedback.items():
            if not isinstance(key, str) or not key.startswith(prefix):
                continue
            param = key[len(prefix):]
            if not param.isidentifier():
                continue
            typ = entry.dominant_type()
            if typ is not None:
                guards.append((param, typ))
        return guards

    def _guard_lines(self):
        lines = []
        for idx, (param, typ) in enumerate(self._collect_guards()):
            lines.append(
                f"if type(L.get({param!r}, _MISSING)) is not _T{idx}: "
                "raise _Deopt()"
            )
        return lines

    def _emit_inst(self, inst, ip, ip_to_block):
        """返回 ``(源码行列表, 是否终结当前块)``。"""
        op = inst.opcode
        operand = inst.operand

        if op == OpCode.LOAD_CONST:
            return [f"st.append(consts[{operand}])"], False
        if op == OpCode.LOAD_LOCAL:
            return [f"st.append(_load_local(L, names[{operand}]))"], False
        if op == OpCode.STORE_LOCAL:
            return [f"L[names[{operand}]] = st.pop()"], False
        if op == OpCode.LOAD_NAME:
            return [f"st.append(_load_name(frame, G, consts[{operand}]))"], False
        if op == OpCode.STORE_NAME:
            return [
                f"_store_name(frame, G, consts[{operand}], st.pop())"
            ], False
        if op in _BINARY:
            symbol = _BINARY[op]
            lines = ["_b = st.pop()", "_a = st.pop()"]
            if op == OpCode.BINARY_DIV:
                lines.append("if _b == 0: raise 运行时错误('除零错误')")
            lines.append(f"st.append(_a {symbol} _b)")
            return lines, False
        if op == OpCode.UNARY_NEGATIVE:
            return ["st.append(-st.pop())"], False
        if op == OpCode.UNARY_NOT:
            return ["st.append(not st.pop())"], False
        if op in (OpCode.JUMP, OpCode.LOOP):
            return [f"_ip = {ip_to_block[operand]}", "continue"], True
        if op in (OpCode.JUMP_IF_FALSE, OpCode.POP_JUMP_IF_FALSE):
            return [
                "_c = st.pop()",
                f"if not _c: _ip = {ip_to_block[operand]}; continue",
            ], False
        if op == OpCode.CALL_FUNCTION:
            argc = operand or 0
            lines = []
            if argc:
                lines.append(f"_args = st[-{argc}:]")
                lines.append(f"del st[-{argc}:]")
            else:
                lines.append("_args = []")
            lines.append("_callee = st.pop()")
            lines.append("st.append(vm._call(_callee, _args))")
            return lines, False
        if op == OpCode.RETURN_VALUE:
            # VM 的 _execute_frame 把 None 视为“本条指令没有返回值”，会继续
            # 执行下一条指令；这里必须完全复刻这一行为。
            return [
                "_ret = st.pop() if st else None",
                "if _ret is not None: return _ret",
                f"_ip = {ip_to_block[ip + 1]}",
                "continue",
            ], True
        if op == OpCode.MAKE_CLOSURE:
            return [
                f"st.append((consts[{operand}], dict(L), frame))"
            ], False
        if op in _BUILD_SEQ:
            kind = _BUILD_SEQ[op]
            count = operand or 0
            return [
                f"_n = {count}",
                "_items = [st.pop() for _ in range(_n)]",
                "if _n: _items.reverse()",
                f"st.append({kind}(_items))",
            ], False
        if op == OpCode.BUILD_DICT:
            count = operand or 0
            return [
                f"_n = {count}",
                "_pairs = []",
                "for _ in range(_n):",
                "    _v = st.pop()",
                "    _k = st.pop()",
                "    _pairs.append((_k, _v))",
                "if _n: _pairs.reverse()",
                "st.append(dict(_pairs))",
            ], False
        if op == OpCode.POP_TOP:
            return ["st.pop()"], False
        if op == OpCode.DUP_TOP:
            return ["st.append(st[-1])"], False
        if op == OpCode.GET_ITERATOR:
            return ["st.append(iter(st.pop()))"], False
        if op == OpCode.FOR_ITER:
            return [
                "_it = st[-1]",
                "try:",
                "    _val = next(_it)",
                "except StopIteration:",
                "    st.pop()",
                f"    _ip = {ip_to_block[operand]}; continue",
                "else:",
                "    st.append(_val)",
            ], False
        if op == OpCode.FOR_ITER_PAIR:
            return [
                "_it = st[-1]",
                "try:",
                "    _item = next(_it)",
                "except StopIteration:",
                "    st.pop()",
                "    st.pop()",
                f"    _ip = {ip_to_block[operand]}; continue",
                "else:",
                "    _src = st[-2]",
                "    st.append(_item)",
                "    st.append(_src[_item] if isinstance(_src, dict) else None)",
            ], False
        if op == OpCode.BUILD_RANGE:
            if operand == 3:
                return [
                    "_step = int(st.pop())",
                    "_end = int(st.pop())",
                    "_start = int(st.pop())",
                    "st.append(list(range(_start, _end + 1, _step)))",
                ], False
            return [
                "_end = int(st.pop())",
                "_start = int(st.pop())",
                "st.append(list(range(_start, _end + 1, 1)))",
            ], False
        if op == OpCode.CAPTURE_NAME:
            return [
                f"_name = consts[{operand}]",
                "st.append((_name in L, L.get(_name, _MISSING)))",
            ], False
        if op == OpCode.STORE_SCOPE_LOCAL:
            return [f"L[consts[{operand}]] = st.pop()"], False
        if op == OpCode.RESTORE_NAME:
            return [
                f"_name = consts[{operand}]",
                "_existed, _old = st.pop()",
                "if _existed: L[_name] = _old",
                "else: L.pop(_name, None)",
            ], False

        # 兜底：走 VM 原有分派路径，逐字节保持语义一致。
        # 这些操作码都不会跳转，因此不需要修改 _ip，也不终结当前基本块。
        return [f"vm._dispatch(insts[{ip}], frame)"], False


__all__ = ["NativeCodegen", "_Deopt"]
