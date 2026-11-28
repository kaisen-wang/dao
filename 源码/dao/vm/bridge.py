"""VM 栈帧与 AST 解释器 Environment 之间的桥接。

VM 的 ``Frame.locals`` 与 AST 解释器的 ``Environment.values`` 都是
``dict[str, object]``。本模块让解释器直接在 VM 的局部变量字典上工作：
``Environment.values`` 与对应栈帧的 ``locals`` 是同一个字典对象（别名），
因此 ``env.get`` / ``env.set`` / ``env.define`` 以及直接写 ``env.values``
都会即时反映到 VM 帧中；沿 ``frame.parent`` 链构造的父 Environment 与最
外层的全局 Environment 同理，使解释器的作用域链与 VM 的静态链一致。
此外，VM 帧链会被转换成 ``Environment.call_stack``（格式与 AST 解释器的
``env.get_stack()`` 一致），供异常辅助函数生成道语言调用栈信息。
"""

from typing import Any

from ..bytecode.frame import Frame
from ..environment import Environment


def _frame_stack_entry(frame: Frame) -> dict:
    """把单个 VM 帧映射为 ``Environment.call_stack`` 的一条记录。"""
    code = getattr(frame, "code", None)
    function = getattr(code, "name", "") or "<匿名>"
    filename = getattr(code, "filename", "") or ""

    line = 0
    instructions = getattr(code, "instructions", ()) or ()
    if instructions:
        ip = getattr(frame, "ip", 0)
        idx = min(max(ip - 1, 0), len(instructions) - 1)
        # 执行中的 ip 指向下一条指令；回退查找最近一条带行号的指令。
        for i in range(idx, -1, -1):
            line = getattr(instructions[i], "line", 0) or 0
            if line:
                break
    return {"function": function, "file": filename, "line": line}


def frame_to_environment(
    frame: Frame,
    globals_map: dict[str, object],
    *,
    source: str = "",
) -> Environment:
    """把 VM 栈帧（及其父帧、全局变量）包装成 AST 解释器的 Environment。

    返回的 Environment 的 ``values`` 就是 ``frame.locals`` 本身；沿
    ``frame.parent`` 链生成的每个父 Environment 的 ``values`` 也分别是
    对应父帧的 ``locals``；最外层父 Environment 的 ``values`` 则是
    ``globals_map``。所有 Environment 的 ``source`` 都设为 source。

    各层 Environment 共享同一个 ``call_stack``（由 VM 帧链按最外层到最
    内层转换而成，形如 ``{"function", "file", "line"}`` 的列表），与 AST
    解释器 ``create_child`` 共享调用栈的行为一致；``current_frame`` 指向
    当前帧对应的记录。因此 ``env.get()`` 可以穿透父帧到全局查找，
    ``env.define()`` / ``env.set()`` / 直接写 ``env.values`` 都会同步回 VM
    帧，``env.get_stack()`` 也能给出道语言风格的调用栈。
    """
    global_env = Environment()
    global_env.values = globals_map
    global_env.source = source

    frames: list[Frame] = []
    scope: Frame | None = frame
    while scope is not None:
        frames.append(scope)
        scope = scope.parent

    call_stack = [_frame_stack_entry(f) for f in reversed(frames)]
    current_frame = call_stack[-1] if call_stack else None

    env = global_env
    env.call_stack = call_stack
    env.current_frame = current_frame
    for current in reversed(frames):
        wrapped = Environment(parent=env)
        wrapped.values = current.locals
        wrapped.source = source
        wrapped.call_stack = call_stack
        wrapped.current_frame = current_frame
        env = wrapped
    return env


def sync_environment(env: Environment, frame: Frame) -> None:
    """把 ``env.values`` 中的绑定写回 ``frame.locals``。

    由 :func:`frame_to_environment` 构造的 Environment 与帧共享同一个字典，
    此处无需操作；若调用方传入的是独立的 Environment，则把其中的绑定
    （包括新增名称）写入帧，使后续 VM 指令的 LOAD_NAME 能够找到它们。
    """
    if env.values is frame.locals:
        return
    for name, value in env.values.items():
        frame.locals[name] = value


def environment_for_interpreter(
    interpreter: Any,
    frame: Frame,
    globals_map: dict[str, object],
    source: str = "",
) -> Environment:
    """设置解释器的 ``source``，并返回桥接后的 Environment。"""
    interpreter.source = source
    return frame_to_environment(frame, globals_map, source=source)
