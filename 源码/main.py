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

import sys
import os
import argparse

# 确保能导入 dao 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.errors import 道错误


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
    from dao.macros.registry import MacroRegistry

    cmd = line.strip()

    if cmd == ':宏列表':
        registry = MacroRegistry()
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
        from dao.macros.expander import MacroExpander
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
        from dao.macros.expander import MacroExpander
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


def run_repl():
    """启动交互式命令行（REPL）"""
    print("═" * 50)
    print("  道（Dao）编程语言 v0.1.0")
    print("  交互式命令行 - 输入代码按回车执行")
    print("  输入 ':宏帮助' 查看宏调试命令")
    print("  输入 '退出' 或按 Ctrl+C 退出")
    print("═" * 50)
    print()

    interpreter = Interpreter()

    while True:
        try:
            # 读取输入
            line = input("道 > ")

            if line.strip() in ('退出', 'exit', 'quit'):
                print("再见！")
                break

            if not line.strip():
                continue

            # 处理宏调试命令
            if line.strip().startswith(':宏'):
                _handle_macro_debug_command(line, interpreter)
                continue

            # 处理多行输入（以冒号结尾的行表示有后续缩进块）
            source = line
            if line.rstrip().endswith((':', '：')) or any(
                line.strip().startswith(kw) for kw in
                ['函数', '如果', '否则', '当', '遍历', '尝试', '捕获', '最终']
            ):
                while True:
                    try:
                        continuation = input("...   ")
                        if continuation.strip() == '':
                            break
                        source += '\n' + continuation
                    except EOFError:
                        break

            # 执行
            result = run_source(source + '\n', interpreter)
            if result is not None:
                # 在REPL中显示表达式的值
                if isinstance(result, bool):
                    print("真" if result else "假")
                elif result is None:
                    pass
                else:
                    print(result)

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
