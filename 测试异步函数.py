#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试异步函数解析和执行
"""

import os
import sys

# 添加项目目录到 Python 路径
sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def test_async_function_parsing():
    """测试异步函数解析"""
    print("=== 测试异步函数解析 ===")

    source_code = """
异步 函数 延迟执行(毫秒)
    打印("延迟执行:", 毫秒)
    返回 毫秒 * 2

异步 函数 主程序()
    结果 = 等待 延迟执行(1000)
    打印("结果:", 结果)
    """.strip()

    # 词法分析
    lexer = Lexer(source_code, "测试.道")
    tokens = lexer.tokenize()
    print(f"词法分析完成，共 {len(tokens)} 个 Token")

    # 语法分析
    parser = Parser(tokens)
    try:
        ast = parser.parse()
        print("语法分析完成")

        # 打印解析结果
        print(f"\n程序结构: {type(ast).__name__}")
        for i, stmt in enumerate(ast.statements):
            print(f"  语句{i + 1}: {type(stmt).__name__}")
            if hasattr(stmt, "name"):
                print(f"    名称: {stmt.name}")
            if hasattr(stmt, "params"):
                print(f"    参数: {stmt.params}")

    except Exception as e:
        print(f"解析错误: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


def test_async_function_execution():
    """测试异步函数执行"""
    print("\n=== 测试异步函数执行 ===")

    source_code = """
异步 函数 延迟执行(毫秒)
    打印("延迟执行:", 毫秒)
    返回 毫秒 * 2

异步 函数 主程序()
    打印("开始执行")
    结果 = 等待 延迟执行(1000)
    打印("结果:", 结果)
    打印("执行完成")

打印("程序初始化")
    """.strip()

    try:
        # 词法分析
        lexer = Lexer(source_code, "测试.道")
        tokens = lexer.tokenize()

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse()

        # 执行
        interpreter = Interpreter()
        interpreter.execute(ast)

        print("同步执行完成")

    except Exception as e:
        print(f"执行错误: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


def test_channel_communication():
    """测试通道通信"""
    print("\n=== 测试通道通信 ===")

    source_code = """
通道 = 通道(2)  // 创建缓冲通道

函数 发送者()
    打印("发送者启动")
    发送 通道 1
    发送 通道 2
    发送 通道 3
    打印("发送者完成")

函数 接收者()
    打印("接收者启动")
    值1 = 接收 通道
    打印("接收到值1:", 值1)
    值2 = 接收 通道
    打印("接收到值2:", 值2)
    值3 = 接收 通道
    打印("接收到值3:", 值3)
    打印("接收者完成")

打印("创建线程")
发送线程 = 线程(目标=发送者)
接收线程 = 线程(目标=接收者)

打印("启动线程")
发送线程.启动()
接收线程.启动()

打印("等待线程完成")
发送线程.等待()
接收线程.等待()

打印("所有操作完成")
    """.strip()

    try:
        # 词法分析
        lexer = Lexer(source_code, "测试.道")
        tokens = lexer.tokenize()

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse()

        # 执行
        interpreter = Interpreter()
        interpreter.execute(ast)

    except Exception as e:
        print(f"执行错误: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    print("道语言异步函数实现测试")
    print("=" * 50)

    # 运行测试
    parsing_ok = test_async_function_parsing()
    execution_ok = test_async_function_execution()

    print("\n" + "=" * 50)
    if parsing_ok and execution_ok:
        print("✅ 所有测试通过")
    else:
        print("❌ 测试失败")
