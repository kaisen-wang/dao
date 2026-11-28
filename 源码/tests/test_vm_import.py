"""VM 模式（``--mode vm``）导入/导出语句的回归测试。

覆盖精确导入、通配符、别名、模块属性访问、本地模块、导出过滤、函数体内
导入、中文报错、JIT 回退路径，以及 AST / VM 两种模式的输出一致性。
"""

import hashlib
import os
import subprocess
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dao.bytecode.compiler import BytecodeCompiler
from dao.bytecode.disassembler import Disassembler
from dao.bytecode.opcodes import OpCode
from dao.errors import 道错误
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.core import VirtualMachine


def _compile(source: str):
    return BytecodeCompiler().compile(Parser(Lexer(source).tokenize()).parse())


def vm_output(source: str, *, jit: bool = False, vm=None, search_paths=None) -> str:
    """在 VM 中执行源码，返回捕获的标准输出。"""
    code = _compile(source)
    vm = vm or VirtualMachine()
    if search_paths is not None:
        vm.module_search_paths = list(search_paths)
    if jit:
        vm.enable_jit()
    buf = StringIO()
    with redirect_stdout(buf):
        vm.run(code)
    return buf.getvalue()


def ast_output(source: str) -> str:
    """在 AST 解释器中执行同一源码，返回捕获的标准输出。"""
    buf = StringIO()
    with redirect_stdout(buf):
        Interpreter().execute(Parser(Lexer(source).tokenize()).parse(), source=source)
    return buf.getvalue()


def write_module(tmp_path: Path, name: str, code: str) -> Path:
    """在 tmp_path 下写入一个 .道 模块文件。"""
    path = tmp_path / (name.replace(".", os.sep) + ".道")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    return path


@pytest.fixture
def local_module(tmp_path, monkeypatch):
    """创建一个带显式导出列表的本地模块，并把 cwd 切到其所在目录。"""
    write_module(
        tmp_path,
        "工具",
        "定义 值 = 42\n"
        "函数 加(x)\n"
        "  返回 x + 1\n"
        "导出 值, 加\n"
        "定义 隐藏 = 99\n",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---------- 字节码与反汇编 ----------


def test_compiler_and_disassembler_support_import_export():
    """导入/导出语句应编译成新 opcode，且反汇编可读。"""
    code = _compile("从 数学 导入 向上取整\n导出 向上取整\n")
    ops = [inst.opcode for inst in code.instructions]
    assert OpCode.IMPORT_STMT in ops
    assert OpCode.EXPORT_STMT in ops
    text = Disassembler().disassemble(code)
    assert "IMPORT_STMT" in text
    assert "EXPORT_STMT" in text
    assert "数学" in text  # 常量操作数以模块名展示，而非裸索引
    assert code.stack_size == 1  # 仅 LOAD_CONST None 需要一个槽，语句本身零栈效应


# ---------- 标准库导入 ----------


def test_stdlib_exact_import():
    assert vm_output("从 数学 导入 向上取整\n打印(向上取整(3.2))") == "4\n"


def test_stdlib_import_with_alias():
    assert vm_output(
        "从 数学 导入 向上取整 作为 取整\n打印(取整(3.2))"
    ) == "4\n"


def test_stdlib_alias_module_name():
    """``加密`` 是 ``密码`` 的直觉别名，与 AST 模式一致。"""
    digest = hashlib.sha256(b"abc").hexdigest()
    assert digest in vm_output('从 加密 导入 SHA256\n打印(SHA256("abc"))')


def test_wildcard_stdlib_import():
    digest = hashlib.sha256(b"abc").hexdigest()
    assert digest in vm_output('从 密码 导入 *\n打印(SHA256("abc"))')


# ---------- 本地模块 ----------


def test_import_module_then_attribute_access(local_module):
    """``导入 模块`` 后可用点号访问模块成员。"""
    assert vm_output("导入 工具\n打印(工具.值)") == "42\n"


def test_import_module_alias(local_module):
    assert vm_output("导入 工具 作为 t\n打印(t.值)") == "42\n"


def test_from_import_alias(local_module):
    assert vm_output("从 工具 导入 值 作为 v\n打印(v)") == "42\n"


def test_local_module_via_module_search_paths(tmp_path):
    """不必切 cwd：通过 VM.module_search_paths 也能定位本地模块。"""
    write_module(tmp_path, "工具", "定义 值 = 7\n导出 值\n")
    assert vm_output(
        "从 工具 导入 值\n打印(值)", search_paths=[str(tmp_path)]
    ) == "7\n"


def test_import_calls_module_function(local_module):
    """从本地模块导入的函数可在 VM 中调用（DaoFunction 由解释器代管）。"""
    assert vm_output(
        "从 工具 导入 加\n打印(加(1))"
    ) == "2\n"


def test_wildcard_local_module_import(local_module):
    assert vm_output(
        "从 工具 导入 *\n打印(值)\n打印(加(2))"
    ) == "42\n3\n"


def test_export_list_filters_named_import(local_module):
    with pytest.raises(道错误, match="没有导出"):
        vm_output("从 工具 导入 隐藏")


def test_export_list_filters_wildcard_import(local_module):
    with pytest.raises(道错误, match="未定义的变量"):
        vm_output("从 工具 导入 *\n打印(隐藏)")


def test_import_inside_function_body(local_module):
    assert vm_output(
        "函数 f()\n  从 工具 导入 加\n  返回 加(3)\n打印(f())"
    ) == "4\n"


def test_module_cache_reused_on_same_vm(local_module):
    """同一 VM 实例重复导入应复用解释器持有的模块缓存。"""
    vm = VirtualMachine()
    assert vm_output("从 工具 导入 值\n打印(值)", vm=vm) == "42\n"
    assert vm_output("导入 工具\n打印(工具.值)", vm=vm) == "42\n"
    assert "工具" in vm._import_interpreter.module_cache


# ---------- 中文报错 ----------


def test_unknown_module_chinese_error():
    with pytest.raises(道错误, match="模块 '不存在的模块' 不存在"):
        vm_output("导入 不存在的模块")


def test_unknown_name_chinese_error():
    with pytest.raises(道错误, match="模块 '数学' 中没有导出 '不存在'"):
        vm_output("从 数学 导入 不存在")


# ---------- JIT 与模式一致性 ----------


def test_jit_mode_import(local_module):
    source = "从 工具 导入 加\n打印(加(1))"
    assert vm_output(source, jit=True) == vm_output(source) == "2\n"


@pytest.mark.parametrize(
    "source",
    [
        "从 数学 导入 向上取整\n打印(向上取整(3.2))",
        "导入 工具\n打印(工具.值)",
        "从 工具 导入 值, 加\n打印(值)\n打印(加(1))",
        "从 工具 导入 *\n打印(加(2))",
    ],
)
def test_ast_and_vm_output_consistent(local_module, source):
    assert vm_output(source) == ast_output(source)


# ---------- 真实 main.py 子进程 ----------


def subprocess_run(source: str, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    script = cwd / "prog.道"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--mode", "vm", *args, str(script)],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )


def test_subprocess_vm_stdlib_import(tmp_path):
    result = subprocess_run(
        "从 数学 导入 向上取整\n打印(向上取整(3.2))\n", tmp_path
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "4"


def test_subprocess_vm_jit_local_module_import(tmp_path):
    write_module(tmp_path, "工具", "定义 值 = 42\n导出 值\n")
    result = subprocess_run(
        "导入 工具\n打印(工具.值)\n", tmp_path, "--jit"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "42"
