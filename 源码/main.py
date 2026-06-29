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
               mode: str = "interpreter", type_check: bool = False, disasm: bool = False) -> object:
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
        return vm.run(code)

    result = interpreter.execute(ast, source=source)
    return result


def run_file(filepath: str, mode: str = "interpreter", type_check: bool = False, disasm: bool = False):
    """执行一个 .道 文件"""
    if not os.path.exists(filepath):
        print(f"错误：文件 '{filepath}' 不存在")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    interpreter = Interpreter()

    try:
        run_source(source, interpreter, filepath, mode=mode, type_check=type_check, disasm=disasm)
    except 道错误 as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n程序被中断")
        sys.exit(130)


def run_repl():
    """启动交互式命令行（REPL）"""
    print("═" * 50)
    print("  道（Dao）编程语言 v0.1.0")
    print("  交互式命令行 - 输入代码按回车执行")
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
    args = arg_parser.parse_args()

    if args.file:
        run_file(args.file, mode=args.mode, type_check=args.type_check, disasm=args.disasm)
    else:
        run_repl()


if __name__ == "__main__":
    main()
