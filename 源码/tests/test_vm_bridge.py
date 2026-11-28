"""VM 栈帧 → AST Environment 桥接测试。

验证 ``Environment.values`` 与 ``Frame.locals`` 的别名关系、父帧/全局
作用域链穿透、写回同步、调用栈转换，以及真实 VM 执行后的帧集成。
"""

import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dao.bytecode.code_object import CodeObject, Instruction
from dao.bytecode.compiler import BytecodeCompiler
from dao.bytecode.frame import Frame
from dao.bytecode.opcodes import OpCode
from dao.environment import Environment
from dao.errors import 名称错误, 运行时错误
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.bridge import (
    environment_for_interpreter,
    frame_to_environment,
    sync_environment,
)
from dao.vm.core import VirtualMachine


def _frame(locals_map=None, parent=None):
    """构造一个不执行字节码、只带局部变量与父链的测试帧。"""
    frame = Frame(code=None, parent=parent)
    frame.locals.update(locals_map or {})
    return frame


def test_current_frame_values_is_alias_and_get():
    frame = _frame({"x": 1})
    env = frame_to_environment(frame, {}, source="测试源码")

    assert env.values is frame.locals
    assert env.get("x") == 1
    assert env.source == "测试源码"
    assert env.has("x")


def test_parent_frame_lookup():
    parent = _frame({"outer": "父"})
    child = _frame({"inner": "子"}, parent=parent)
    env = frame_to_environment(child, {})

    assert env.get("inner") == "子"
    assert env.get("outer") == "父"
    assert env.parent.values is parent.locals


def test_global_lookup_without_parent_frame():
    globals_map = {"g": 99}
    frame = _frame({})
    env = frame_to_environment(frame, globals_map)

    assert env.parent is not None
    assert env.parent.values is globals_map
    assert env.parent.parent is None
    assert env.get("g") == 99


def test_writes_sync_back_to_frames_and_globals():
    parent = _frame({"outer": 1})
    child = _frame({"inner": 2}, parent=parent)
    globals_map = {"g": 3}
    env = frame_to_environment(child, globals_map)

    env.set("inner", 20)
    env.set("outer", 10)
    env.set("g", 30)
    env.define("新增", 40)
    env.values["直接写入"] = 50

    assert child.locals == {"inner": 20, "新增": 40, "直接写入": 50}
    assert parent.locals["outer"] == 10
    assert globals_map["g"] == 30


def test_undefined_name_raises_when_no_parent_frame():
    env = frame_to_environment(_frame({}), {})

    with pytest.raises(名称错误):
        env.get("不存在")
    with pytest.raises(名称错误):
        env.set("不存在", 1)


def test_shadowing_current_frame_then_parent_then_global():
    globals_map = {"name": "global"}
    parent = _frame({"name": "parent"})
    child = _frame({"name": "child"}, parent=parent)
    env = frame_to_environment(child, globals_map)

    assert env.get("name") == "child"
    del child.locals["name"]
    assert env.get("name") == "parent"
    del parent.locals["name"]
    assert env.get("name") == "global"


def test_define_duplicate_still_raises():
    frame = _frame({"x": 1})
    env = frame_to_environment(frame, {})

    with pytest.raises(运行时错误, match="已经被定义"):
        env.define("x", 2)

    # 同名变量只存在于父帧时，当前帧是独立作用域，允许遮蔽定义。
    child = _frame({}, parent=_frame({"outer": 1}))
    child_env = frame_to_environment(child, {})
    child_env.define("outer", 2)
    assert child.locals["outer"] == 2


def test_multi_level_parent_chain_aliases_every_frame():
    grandparent = _frame({"level": "g"})
    parent = _frame({"level": "p"}, parent=grandparent)
    child = _frame({}, parent=parent)
    env = frame_to_environment(child, {})

    assert env.parent.values is parent.locals
    assert env.parent.parent.values is grandparent.locals
    assert env.get("level") == "p"
    del parent.locals["level"]
    assert env.get("level") == "g"


def test_sync_environment_with_independent_environment():
    frame = _frame({"existing": 1})
    env = Environment()
    env.values["existing"] = 100
    env.values["new"] = 2

    sync_environment(env, frame)

    assert frame.locals["existing"] == 100
    assert frame.locals["new"] == 2


def test_sync_environment_is_noop_for_aliased_environment():
    frame = _frame({"x": 1})
    env = frame_to_environment(frame, {})

    sync_environment(env, frame)

    assert frame.locals == {"x": 1}


def test_environment_for_interpreter_sets_source():
    interpreter = SimpleNamespace(source="")
    frame = _frame({"x": 1})
    globals_map = {"g": 2}

    env = environment_for_interpreter(
        interpreter, frame, globals_map, source="测试源码"
    )

    assert interpreter.source == "测试源码"
    assert env.source == "测试源码"
    assert env.values is frame.locals
    assert env.parent.values is globals_map
    assert env.get("g") == 2


def test_call_stack_from_vm_frame_chain():
    def make_frame(name, line, parent=None):
        frame = Frame(
            code=CodeObject(
                name=name,
                instructions=[Instruction(opcode=OpCode.LOAD_CONST, line=line)],
            ),
            parent=parent,
        )
        frame.ip = 1  # 指向指令之后，模拟正在执行该指令
        return frame

    root = make_frame("<module>", 1)
    func = make_frame("外层", 5, parent=root)
    current = make_frame("内层", 9, parent=func)
    env = frame_to_environment(current, {})

    expected = [
        {"function": "<module>", "file": "", "line": 1},
        {"function": "外层", "file": "", "line": 5},
        {"function": "内层", "file": "", "line": 9},
    ]
    assert env.get_stack() == expected
    assert env.current_frame == expected[-1]
    # 与 AST 的 create_child 一致：整条作用域链共享同一个调用栈列表。
    assert env.call_stack is env.parent.call_stack
    assert env.parent.call_stack is env.parent.parent.call_stack


def test_call_stack_without_code_or_instructions():
    env = frame_to_environment(_frame({}), {})

    assert env.get_stack() == [{"function": "<匿名>", "file": "", "line": 0}]


class _FrameCapturingVM(VirtualMachine):
    """记录执行过的帧，便于测试桥接真实 VM 帧。"""

    def __init__(self):
        super().__init__()
        self.frames: list[Frame] = []

    def _execute_frame(self, frame: Frame) -> object:
        self.frames.append(frame)
        return super()._execute_frame(frame)


def test_real_vm_frame_integration():
    source = "定义 x = 42\n打印(x)\n"
    code = BytecodeCompiler().compile(Parser(Lexer(source).tokenize()).parse())
    vm = _FrameCapturingVM()
    with redirect_stdout(StringIO()) as out:
        vm.run(code)
    assert out.getvalue().strip() == "42"

    frame = vm.frames[0]
    env = frame_to_environment(frame, vm.globals, source=source)

    assert env.values is frame.locals
    assert env.source == source
    assert env.get("x") == 42
    assert env.get("打印") is vm.globals["打印"]
    assert env.get_stack() == [{"function": "<module>", "file": "", "line": 2}]

    env.define("来自解释器", 7)
    assert frame.locals["来自解释器"] == 7
