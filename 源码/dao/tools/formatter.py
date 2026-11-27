"""
道语言独立格式化器
==================

用法（在 ``源码`` 目录下运行）：

.. code-block:: bash

   ./.venv/bin/python -m dao.tools.formatter 文件.道        # 原地格式化
   ./.venv/bin/python -m dao.tools.formatter --check 文件.道  # 只检查，需格式化时退出码为 1
   ./.venv/bin/python -m dao.tools.formatter --stdout 文件.道 # 打印结果，不写文件

格式化规则与 LSP 的 ``textDocument/formatting`` 完全一致，均由
:func:`dao.lsp.formatting.format_source` 提供，确保编辑器与命令行结果一致。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..lsp.formatting import DEFAULT_INDENT_WIDTH, format_source


def format_text(text: str, indent_width: int = DEFAULT_INDENT_WIDTH) -> str:
    """格式化源码文本，供脚本或测试直接调用。"""
    return format_source(text, indent_width)


def format_file(path: Path, indent_width: int = DEFAULT_INDENT_WIDTH) -> tuple[str, str]:
    """读取文件并返回 ``(原文本, 格式化后文本)``，保留原始换行风格与编码。"""
    text = path.read_bytes().decode("utf-8")
    return text, format_text(text, indent_width)


def main(argv=None) -> int:
    """命令行入口，返回进程退出码。"""
    parser = argparse.ArgumentParser(
        prog="python -m dao.tools.formatter",
        description="道语言源码格式化器（统一缩进、行尾空白与空行，不动字符串内容）",
    )
    parser.add_argument("files", nargs="+", help="待处理的 .道 文件")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查是否需要格式化，不写文件；需要格式化时退出码为 1",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="把格式化结果写到标准输出，不修改文件（仅限单个文件）",
    )
    parser.add_argument(
        "--indent-width",
        type=int,
        default=DEFAULT_INDENT_WIDTH,
        help=f"一级缩进的空格数（默认 {DEFAULT_INDENT_WIDTH}）",
    )
    args = parser.parse_args(argv)

    if args.check and args.stdout:
        parser.error("--check 与 --stdout 不能同时使用")
    if args.stdout and len(args.files) != 1:
        parser.error("--stdout 只能用于单个文件")

    changed: list[str] = []
    for name in args.files:
        path = Path(name)
        if not path.is_file():
            print(f"错误：文件不存在或不是普通文件：{name}", file=sys.stderr)
            return 2
        try:
            text, formatted = format_file(path, args.indent_width)
        except (OSError, UnicodeError) as error:
            print(f"错误：无法读取文件「{name}」：{error}", file=sys.stderr)
            return 2

        if args.stdout:
            sys.stdout.write(formatted)
            return 0

        if text == formatted:
            continue
        changed.append(name)
        if not args.check:
            try:
                path.write_bytes(formatted.encode("utf-8"))
            except OSError as error:
                print(f"错误：无法写回文件「{name}」：{error}", file=sys.stderr)
                return 2

    if args.check:
        if changed:
            for name in changed:
                print(f"需要格式化：{name}")
            return 1
        print("所有文件均已符合格式规范。")
        return 0

    for name in changed:
        print(f"已格式化：{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
