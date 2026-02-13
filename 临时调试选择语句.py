#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试选择语句的解析 - 包含解析器
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import TokenType


def debug_indentation():
    """调试词法分析器的缩进识别"""
    # 调试源代码
    source = """选择 {
        情况 接收 通道1 作为 消息:

            打印("通道1 获胜:", 消息)

        情况 接收 通道2 作为 消息:

            打印("通道2 获胜:", 消息)

        情况 超时(2000):

            打印("超时")
    }
    """.strip()

    print("源代码:")
    print("-" * 50)
    print(source)
    print("-" * 50)

    # 词法分析
    lexer = Lexer(source, "调试.道")
    tokens = lexer.tokenize()

    print("\n词法分析结果:")
    for i, token in enumerate(tokens):
        token_info = f"{i:3d} {token.type.name:<20} '{token.value}' (行:{token.line}, 列:{token.column})"

        # 检查是否有缩进相关的 token
        if token.type in (TokenType.缩进, TokenType.回退):
            token_info += " → 缩进/回退"
        elif token.type == TokenType.情况:
            token_info += " → 情况语句"
        elif token.type == TokenType.左花括号:
            token_info += " → 左花括号"
        elif token.type == TokenType.左括号:
            token_info += " → 左括号"
        elif token.type == TokenType.换行:
            token_info += " → 换行"

        print(token_info)

    print(f"\nToken 总数: {len(tokens)}")

    # 检查缩进是否正确生成
    indent_found = False
    after_case = False
    case_count = 0

    for token in tokens:
        if token.type == TokenType.情况:
            case_count += 1
            print(f"\n情况 {case_count} 在 行:{token.line}")
            after_case = True
            indent_found = False

        if after_case and token.type == TokenType.缩进:
            print(f"找到缩进: 行:{token.line} 列:{token.column}")
            indent_found = True
            after_case = False

        if after_case and token.type == TokenType.左括号:
            print(f"情况后直接有左括号 行:{token.line}")

    if case_count == 0:
        print("未找到情况语句")

    # 检查是否有未配对的括号
    open_braces = 0
    open_parens = 0

    for token in tokens:
        if token.type == TokenType.左花括号:
            open_braces += 1
        elif token.type == TokenType.右花括号:
            open_braces -= 1
        elif token.type == TokenType.左括号:
            open_parens += 1
        elif token.type == TokenType.右括号:
            open_parens -= 1

    print(f"\n括号平衡检查:")
    print(f"  左花括号: {open_braces}")
    print(f"  左括号: {open_parens}")
    print(f"  是否平衡: {open_braces == 0 and open_parens == 0}")

    # 尝试解析
    print("\n" + "-" * 50)
    print("语法分析:")

    parser = Parser(tokens)
    try:
        ast = parser.parse()
        print("✅ 解析成功")

        if hasattr(ast, "statements"):
            print(f"\n程序结构:")
            for i, stmt in enumerate(ast.statements):
                print(f"  语句 {i + 1}: {type(stmt).__name__}")
                if hasattr(stmt, "cases") and hasattr(stmt.cases, "__len__"):
                    print(f"    包含 {len(stmt.cases)} 个选择分支")
                    for case in stmt.cases:
                        print(f"      类型: {case.type}, 变量: {case.variable}")
                        if hasattr(case, "body") and hasattr(case.body, "__len__"):
                            print(f"      主体: {len(case.body)} 条语句")

    except Exception as e:
        print(f"❌ 解析失败: {e}")
        import traceback

        print("堆栈跟踪:")
        print(traceback.format_exc())


if __name__ == "__main__":
    debug_indentation()
