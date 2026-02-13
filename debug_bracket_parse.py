#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试括号表达式解析问题
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import TokenType


def debug_expression_parsing(code, filename, token_pos=0):
    """调试括号表达式解析问题"""
    print(f"调试文件名: {filename}")
    print("-" * 50)
    print(f"代码内容:\n{code}")
    print("-" * 50)

    # 词法分析
    lexer = Lexer(code, filename)
    tokens = lexer.tokenize()

    # 打印 Token 列表
    print(f"词法分析: {len(tokens)} 个 Token")
    for i, token in enumerate(tokens):
        if token_pos - 5 <= i <= token_pos + 5:
            token_info = f"{i + 1:3d} {token.type.name:<20} '{token.value}'"
            token_info += f" (行:{token.line}, 列:{token.column})"
            if i == token_pos:
                print(f"→ {token_info}")
            else:
                print(f"  {token_info}")

    if token_pos < len(tokens) - 1:
        print("\n当前 Token 和下一个 Token:")
        print(f"   位置: {token_pos} -> {token_pos + 1}")
        current = tokens[token_pos]
        next_token = tokens[token_pos + 1]
        print(
            f"   当前 : {current.type.name} '{current.value}' (行:{current.line}, 列:{current.column})"
        )
        print(
            f"   下一个: {next_token.type.name} '{next_token.value}' (行:{next_token.line}, 列:{next_token.column})"
        )

    return tokens


def debug_line_18():
    """调试第18行的问题"""
    source_code = """异步 函数 延迟执行(毫秒)
    打印("延迟执行:", 毫秒)
    返回 毫秒 * 2

异步 函数 发送(通道, 消息)
    发送 通道 消息
    打印("发送:", 消息)

异步 函数 接收(通道, 名称)
    定义 消息 = 接收 通道
    打印(名称, "收到:", 消息)
    返回 消息

异步 函数 主程序()
    定义 ch1 = 通道()
    定义 ch2 = 通道()

    定义 t1 = 启动 发送(ch1, "消息1")
    定义 t2 = 启动 发送(ch2, "消息2")

    定义 m1 = 等待 接收(ch1, "接收方1")
    定义 m2 = 等待 接收(ch2, "接收方2")

    打印("所有完成")

等待 主程序()
""".strip()

    print("=== 调试简单并发测试第18行 ===")
    tokens = debug_expression_parsing(source_code, "简单并发测试.道", 127)

    try:
        # 尝试解析完整程序
        parser = Parser(tokens)
        ast = parser.parse()
        print("✅ 解析成功")
        print(f"程序结构: {type(ast).__name__}")
        if hasattr(ast, "statements"):
            print(f"语句数量: {len(ast.statements)}")
            for i, stmt in enumerate(ast.statements):
                print(f"  语句{i + 1}: {type(stmt).__name__}")
                if hasattr(stmt, "name"):
                    print(f"    名称: {stmt.name}")

    except Exception as e:
        print(f"❌ 解析错误: {e}")
        import traceback

        print("\n" + traceback.format_exc())


def debug_specific_tokens():
    """调试第18行的特定 Token 序列"""
    line_18 = '    定义 t1 = 启动 发送(ch1, "消息1")'
    print(f"\n=== 调试第18行内容 ===")
    debug_expression_parsing(line_18, "行18.道")

    print(f"\n=== 调试第18行内容 ===")
    debug_expression_parsing(line_18, "行18.道")

if __name__ == "__main__":
    # 调试第18行的问题
    debug_line_18()

    # 单独调试第18行的内容
    debug_specific_tokens()
