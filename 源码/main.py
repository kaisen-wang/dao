#!/usr/bin/env python3
"""
道（Dao）编程语言 - 主入口
=========================

提供两种运行模式：
1. REPL模式：交互式命令行（无参数启动）
2. 文件模式：执行 .道 文件（传入文件路径）

使用方法：
    python main.py                  # 启动 REPL
    python main.py 你好世界.道      # 执行文件
"""

import argparse
import os
import sys

# 确保能导入 dao 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.errors import 道错误
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_source(source: str, interpreter: Interpreter, filename: str = "<输入>",
               mode: str = "interpreter", type_check: bool = False, disasm: bool = False,
               jit: bool = False) -> object:
    lexer = Lexer(source, filename)
    tokens = lexer.tokenize()
    parser = Parser(tokens, source)
    ast = parser.parse()

    if type_check:
        from dao.types.checker import TypeInferenceEngine
        engine = TypeInferenceEngine()
        reports = engine.check(ast)
        for r in reports:
            print(f"类型警告: {r.message} (行{r.line})")

    if mode == "vm":
        from dao.bytecode.compiler import BytecodeCompiler
        from dao.bytecode.disassembler import Disassembler
        from dao.vm.core import VirtualMachine
        compiler = BytecodeCompiler()
        code = compiler.compile(ast)
        if disasm:
            disassembler = Disassembler()
            print(disassembler.disassemble(code))
        vm = VirtualMachine()
        if jit:
            vm.enable_jit()
        return vm.run(code)

    result = interpreter.execute(ast, source=source)
    return result


def run_file(filepath: str, mode: str = "interpreter", type_check: bool = False,
             disasm: bool = False, jit: bool = False):
    """执行一个 .道 文件"""
    if not os.path.exists(filepath):
        print(f"错误：文件 '{filepath}' 不存在")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    interpreter = Interpreter()

    try:
        run_source(source, interpreter, filepath, mode=mode, type_check=type_check,
                   disasm=disasm, jit=jit)
    except 道错误 as e:
        if not e.filename:
            e.filename = filepath
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n程序被中断")
        sys.exit(130)


def _handle_macro_debug_command(line: str, interpreter: Interpreter):
    """处理宏调试 REPL 命令

    支持的命令：
    - :宏列表 — 列出所有已注册的宏
    - :宏追踪 — 开启/关闭宏展开追踪
    - :宏追踪状态 — 查看追踪状态
    - :宏调用栈 — 显示当前宏展开调用栈
    - :宏帮助 — 显示宏调试帮助
    """

    cmd = line.strip()

    if cmd == ':宏列表':
        registry = interpreter.macro_registry
        macros = registry.get_all_macros()
        if not macros:
            print("当前无已注册的宏")
        else:
            print(f"已注册 {len(macros)} 个宏：")
            for m in macros:
                macro_type = "模式匹配" if m.is_pattern_macro else "普通"
                params = ", ".join(m.parameters)
                print(f"  !{m.name}({params}) [{macro_type}]")
        return True

    if cmd == ':宏追踪':
        # 切换追踪状态
        # 通过 interpreter 的内部状态控制追踪
        if not hasattr(interpreter, '_macro_trace'):
            interpreter._macro_trace = False
        interpreter._macro_trace = not interpreter._macro_trace
        state = "开启" if interpreter._macro_trace else "关闭"
        print(f"宏展开追踪已{state}")
        return True

    if cmd == ':宏追踪状态':
        state = "开启" if getattr(interpreter, '_macro_trace', False) else "关闭"
        print(f"宏展开追踪状态: {state}")
        return True

    if cmd == ':宏调用栈':
        # 调用栈在展开过程中才有内容，这里显示上一次展开的调用栈
        if hasattr(interpreter, '_last_macro_call_stack'):
            stack = interpreter._last_macro_call_stack
            if not stack:
                print("宏调用栈为空（无正在进行的宏展开）")
            else:
                print("宏展开调用栈:")
                for i, entry in enumerate(stack):
                    indent = "  " * i
                    name = entry.get("name", "?")
                    line = entry.get("line", 0)
                    depth = entry.get("depth", 0)
                    print(f"{indent}[{i}] !{name} (行 {line}, 深度 {depth})")
        else:
            print("宏调用栈为空（尚未执行过宏展开）")
        return True

    if cmd == ':宏帮助':
        print("宏调试命令：")
        print("  :宏列表       — 列出所有已注册的宏")
        print("  :宏追踪       — 开启/关闭宏展开追踪")
        print("  :宏追踪状态   — 查看追踪状态")
        print("  :宏调用栈     — 显示当前宏展开调用栈")
        print("  :宏帮助       — 显示此帮助信息")
        return True

    # 不是宏调试命令
    return False


# ---------------------------------------------------------------------------
# REPL 输入与多行判定辅助
# ---------------------------------------------------------------------------

# 出现在行首即可判定为「块开始」的关键字（后跟空白或行尾才算独立关键字）
_BLOCK_KEYWORDS = (
    '函数', '异步函数', '如果', '否则如果', '否则', '当', '遍历',
    '尝试', '捕获', '最终', '类型',
)

_prompt_session = None
_prompt_session_tried = False


def _get_prompt_session():
    """惰性创建 prompt_toolkit 的 PromptSession；导入失败返回 None。"""
    global _prompt_session, _prompt_session_tried
    if not _prompt_session_tried:
        _prompt_session_tried = True
        try:
            from prompt_toolkit import PromptSession
            _prompt_session = PromptSession()
        except Exception:  # noqa: BLE001 - 可选依赖缺失或环境不兼容时静默降级
            _prompt_session = None
    return _prompt_session


def _read_line(prompt: str) -> str:
    """读取一行输入。

    交互终端下优先使用 prompt_toolkit（提供历史与行编辑能力），
    非交互终端（如管道）或依赖缺失时优雅降级到内置 input()。
    """
    if sys.stdin.isatty():
        session = _get_prompt_session()
        if session is not None:
            return session.prompt(prompt)
    return input(prompt)


def _find_top_level_colon(line: str) -> tuple[int, bool]:
    """查找行内最后一个位于顶层（括号外、字符串外）的冒号。

    返回 ``(冒号位置, 冒号后是否还有非空代码)``；未找到返回 ``(-1, False)``。
    这样可避免把字符串、字典字面量里的冒号误判为块起始符。
    """
    depth = 0
    quote = None
    escaped = False
    last_colon = -1
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if quote:
            if ch == '\\':
                escaped = True
            elif ch == quote:
                # 三引号字符串：\"\"\" 或 '''
                if (quote in ('"', "'") and i + 2 < n
                        and line[i + 1] == quote and line[i + 2] == quote):
                    i += 3
                    quote = None
                    continue
                quote = None
            i += 1
            continue
        if ch in ('"', "'", '`'):
            if (ch in ('"', "'") and i + 2 < n
                    and line[i + 1] == ch and line[i + 2] == ch):
                quote = ch
                i += 3
                continue
            quote = ch
        elif ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth = max(0, depth - 1)
        elif ch in (':', '：') and depth == 0:
            last_colon = i
        i += 1

    has_code_after = last_colon >= 0 and bool(line[last_colon + 1:].strip())
    return last_colon, has_code_after


def _leading_block_keyword(line: str) -> str | None:
    """若行首是一个独立的块关键字，返回该关键字，否则返回 None。"""
    code = line.lstrip()
    for kw in _BLOCK_KEYWORDS:
        if code.startswith(kw):
            rest = code[len(kw):]
            if rest == '' or rest[0].isspace():
                return kw
    return None


def _needs_continuation(line: str) -> bool:
    """判断单行输入是否尚未写完，需要进入续行模式。

    判定规则（按优先级）：
    1. 空行与注释不触发续行；
    2. 顶层冒号后还有代码（如 ``如果 x: 语句``）视为单行语句；
    3. 顶层冒号结尾（如 ``如果 x:``）触发续行；
    4. 行首为块关键字（如 ``如果 x > 0``）触发续行。
    字符串与字典字面量内部的冒号不会被误判。
    """
    if not line.strip():
        return False
    stripped = line.lstrip()
    if stripped.startswith(('//', '注：', '注:')):
        return False

    colon_pos, has_code_after = _find_top_level_colon(line)
    if has_code_after:
        return False
    if colon_pos >= 0:
        return True
    return _leading_block_keyword(line) is not None


def _print_help():
    """打印 REPL 可用命令帮助。"""
    print("REPL 命令：")
    print("  :帮助             — 显示本帮助信息")
    print("  :粘贴 / :多行      — 进入多行粘贴模式，输入 '.' 或 ':结束' 完成，':取消' 放弃")
    print("  :宏列表           — 列出所有已注册的宏")
    print("  :宏追踪           — 开启/关闭宏展开追踪")
    print("  :宏追踪状态       — 查看宏展开追踪状态")
    print("  :宏调用栈         — 显示当前宏展开调用栈")
    print("  :宏帮助           — 显示宏调试帮助")
    print("  退出 / exit / quit — 退出 REPL")
    print("提示：输入块关键字（如 '如果 x > 0'）会自动进入续行，空行结束。")


def _read_paste_mode():
    """读取多行粘贴模式的内容。

    返回拼接后的源码字符串；用户取消或没有任何内容时返回 None。
    """
    print("已进入多行粘贴模式：输入 '.' 或 ':结束' 完成，':取消' 放弃。")
    lines = []
    while True:
        try:
            line = _read_line("...   ")
        except (EOFError, KeyboardInterrupt):
            break
        stripped = line.strip()
        if stripped in ('.', ':结束', ':完成'):
            break
        if stripped == ':取消':
            print("已取消多行输入")
            return None
        lines.append(line)
    if not lines:
        return None
    return '\n'.join(lines)


def _execute_repl_source(source: str, interpreter: Interpreter):
    """执行一段 REPL 源码并按既有规则显示结果。"""
    result = run_source(source + '\n', interpreter)
    if result is not None:
        if isinstance(result, bool):
            print("真" if result else "假")
        else:
            print(result)


def run_repl():
    """启动交互式命令行（REPL）"""
    print("═" * 50)
    print("  道（Dao）编程语言 v0.1.0")
    print("  交互式命令行 - 输入代码按回车执行")
    print("  输入 ':帮助' 查看所有命令")
    print("  输入 '退出' 或按 Ctrl+C 退出")
    print("═" * 50)
    print()

    interpreter = Interpreter()

    while True:
        try:
            line = _read_line("道 > ")
            cmd = line.strip()

            if cmd in ('退出', 'exit', 'quit'):
                print("再见！")
                break

            if not cmd:
                continue

            # REPL 通用命令
            if cmd == ':帮助':
                _print_help()
                continue

            if cmd in (':粘贴', ':多行'):
                source = _read_paste_mode()
                if source is not None:
                    _execute_repl_source(source, interpreter)
                continue

            # 宏调试命令（保留原有 :宏 系列行为）
            if cmd.startswith(':宏'):
                if _handle_macro_debug_command(line, interpreter):
                    continue
                print(f"未知命令：{cmd}（输入 ':帮助' 查看可用命令）")
                continue

            if cmd.startswith(':'):
                print(f"未知命令：{cmd}（输入 ':帮助' 查看可用命令）")
                continue

            # 多行输入：块关键字或顶层冒号结尾进入续行，空行结束
            source = line
            if _needs_continuation(line):
                while True:
                    try:
                        continuation = _read_line("...   ")
                    except EOFError:
                        break
                    if continuation.strip() == '':
                        break
                    source += '\n' + continuation

            _execute_repl_source(source, interpreter)

        except 道错误 as e:
            print(f"❌ {e}")
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except EOFError:
            print("\n再见！")
            break


def main():
    """主函数"""
    arg_parser = argparse.ArgumentParser(description="道（Dao）编程语言")
    arg_parser.add_argument("file", nargs="?", help="要执行的 .道 文件")
    arg_parser.add_argument("--mode", choices=["interpreter", "vm"], default="interpreter",
                            help="执行模式：interpreter（默认）或 vm")
    arg_parser.add_argument("--type-check", action="store_true", help="启用类型推断检查")
    arg_parser.add_argument("--disasm", action="store_true", help="输出字节码反汇编结果（仅 VM 模式）")
    arg_parser.add_argument("--jit", action="store_true", help="启用 JIT 编译（仅 VM 模式）")
    args = arg_parser.parse_args()

    if args.file:
        run_file(args.file, mode=args.mode, type_check=args.type_check, disasm=args.disasm, jit=args.jit)
    else:
        run_repl()


if __name__ == "__main__":
    main()
