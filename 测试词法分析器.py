#!/usr/bin/env python3

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "源码")))

from dao.lexer import Lexer


def main():
    # 读取测试文件
    with open("简单异步测试.道", "r", encoding="utf-8") as f:
        source = f.read()

    print("原始源代码:")
    print("=" * 50)
    print(source)
    print("=" * 50)
    print()

    print("词法分析结果:")
    print("-" * 50)

    # 创建词法分析器
    lexer = Lexer(source, "简单异步测试.道")

    try:
        tokens = list(lexer.tokenize())

        print(f"共生成 {len(tokens)} 个 Token:")
        for i, token in enumerate(tokens):
            print(f"{i:3} | 类型: {token.type.name:<10} | 值: {repr(token.value):<20}")
            print(f"    | 位置: 行 {token.line}, 列 {token.column}")
            print()

        # 检查是否生成了正确的 INDENT 和 DEDENT
        print("缩进信息:")
        indent_levels = []
        for token in tokens:
            if hasattr(token.type, "name") and token.type.name == "缩进":
                indent_levels.append("缩进")
            elif hasattr(token.type, "name") and token.type.name == "回退":
                indent_levels.append("回退")

        print(" ".join(indent_levels))

    except Exception as e:
        print(f"词法分析错误: {e}")
        print()
        import traceback

        print("错误堆栈:")
        print(traceback.format_exc())


if __name__ == "__main__":
    main()
