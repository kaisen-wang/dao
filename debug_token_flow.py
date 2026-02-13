#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试发送语句和函数调用解析冲突问题
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import TokenType


def trace_send_parse():
    """追踪发送语句的解析过程"""
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

    lexer = Lexer(source_code, "追踪调试.道")
    tokens = lexer.tokenize()

    print("=== 第18行周围的 Token 序列 ===")

    # 寻找第18行的 Token
    line18_tokens = []
    for i, token in enumerate(tokens):
        if token.line == 18:
            line18_tokens.append((i, token))
            if len(line18_tokens) > 10:
                break
        elif len(line18_tokens) > 0:
            line18_tokens.append((i, token))
            if len(line18_tokens) > 20:
                break

    if line18_tokens:
        print(f"找到第18行及后续 Token:")
        for i, token in line18_tokens:
            token_info = f"{i:4d} {token.type.name:<20} '{token.value}'"
            token_info += f" (行:{token.line}, 列:{token.column})"
            print(f"  {token_info}")

    try:
        parser = Parser(tokens)
        ast = parser.parse()
        print("\n✅ 成功解析到AST")

    except Exception as e:
        print(f"\n❌ 解析错误: {e}")
        import traceback

        print("\n" + traceback.format_exc())


def trace_parsers():
    """追踪解析器在遇到发送时的行为"""
    print("=== 解析器在第18行的行为 ===")
    print("parse_statement 首先检查 TokenType.发送")
    print("→ 然后调用 parse_send_stmt")
    print("parse_send_stmt 尝试解析 channel 表达式")
    print("→ parse_send_stmt: channel = parse_expression()")
    print("→ parse_expression 调用 parse_pipe()")
    print("→ parse_pipe() 调用 parse_or()")
    print("→ parse_or() 调用 parse_and()")
    print("→ parse_and() 调用 parse_not()")
    print("→ parse_not() 调用 parse_comparison()")
    print("→ parse_comparison() 调用 parse_addition()")
    print("→ parse_addition() 调用 parse_multiplication()")
    print("→ parse_multiplication() 调用 parse_power()")
    print("→ parse_power() 调用 parse_unary()")
    print("→ parse_unary() 调用 parse_call()")
    print("→ parse_call 调用 parse_primary()")
    print("parse_primary 在 parse_primary 方法中寻找左括号")
    print("→ 找到 Token.左括号，期望匹配右括号")
    print("→ 失败，引发 '括号表达式需要 )' 错误")


if __name__ == "__main__":
    print("=== 道语言解析器调试 ===")
    print("测试发送语句 vs 函数调用的解析冲突")

    print("\n" + "-" * 60 + "\n")
    trace_send_parse()

    print("\n" + "-" * 60 + "\n")
    trace_parsers()
