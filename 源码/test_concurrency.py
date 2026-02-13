#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
道语言并发编程功能测试脚本
==========================

测试异步函数、等待操作、协程和通道的功能。
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter.core import Interpreter
from dao.lexer.core import Lexer
from dao.parser.core import Parser


def 测试词法分析器():
    """测试词法分析器"""
    print("=== 测试词法分析器 ===")

    程序内容 = """异步 函数 测试()
    打印("测试词法分析")
    定义 结果 = 等待 异步 函数()
        睡眠(0.5)
        返回 42

    打印("结果:", 结果)

运行异步(测试())
"""

    lexer = Lexer(程序内容)
    print("程序内容:")
    print(程序内容)
    print()

    print("分词结果:")
    tokens = lexer.tokenize()
    for i, token in enumerate(tokens, 1):
        print(f"{i:2d} | {token}")

    print(f"共 {len(tokens)} 个词法单元")
    print("-" * 30)
    print()


def 测试解析器():
    """测试解析器"""
    print("=== 测试解析器 ===")

    程序内容 = """异步 函数 测试()
    打印("测试词法分析")
    定义 结果 = 等待 异步 函数()
        睡眠(0.5)
        返回 42

    打印("结果:", 结果)

运行异步(测试())
"""

    lexer = Lexer(程序内容)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    try:
        ast = parser.parse()
        print("解析成功!")

        print(f"\n根节点类型: {type(ast).__name__}")
        if hasattr(ast, "body"):
            print(f"主体语句数量: {len(ast.body)}")
            for i, stmt in enumerate(ast.body, 1):
                stmt_type = type(stmt).__name__
                print(f"语句 {i}: {stmt_type}")

    except Exception as e:
        print(f"解析失败: {type(e).__name__}: {e}")
        import traceback

        print("堆栈跟踪:")
        print(traceback.format_exc())

    print("-" * 30)
    print()


def 测试简单异步程序():
    """测试简单异步程序"""
    print("=== 测试简单异步程序 ===")

    程序内容 = """异步 函数 异步加法(x, y)
    睡眠(0.5)
    返回 x + y

异步 函数 异步乘法(x, y)
    睡眠(0.8)
    返回 x * y

异步 函数 主()
    定义 a = 等待 异步加法(2, 3)
    打印("异步加法结果:", a)

    定义 b = 等待 异步乘法(4, 5)
    打印("异步乘法结果:", b)

运行异步(主())
"""

    try:
        lexer = Lexer(程序内容)
        tokens = lexer.tokenize()

        parser = Parser(tokens)
        ast = parser.parse()

        interpreter = Interpreter()
        result = interpreter.execute(ast)
        print(f"程序执行完成，结果: {result}")

    except Exception as e:
        print(f"测试失败: {type(e).__name__}: {e}")
        import traceback

        print("堆栈跟踪:")
        print(traceback.format_exc())

    print("-" * 30)
    print()


def 测试全部等待():
    """测试全部等待功能"""
    print("=== 测试全部等待功能 ===")

    程序内容 = """异步 函数 任务1()
    睡眠(0.3)
    返回 "任务1 完成"

异步 函数 任务2()
    睡眠(0.5)
    返回 "任务2 完成"

异步 函数 任务3()
    睡眠(0.2)
    返回 "任务3 完成"

异步 函数 主()
    打印("开始全部等待...")
    定义 结果 = 等待 全部([任务1(), 任务2(), 任务3()])
    打印("全部等待结果:")
    遍历 项 在 结果
        打印(项)

运行异步(主())
"""

    try:
        lexer = Lexer(程序内容)
        tokens = lexer.tokenize()

        parser = Parser(tokens)
        ast = parser.parse()

        interpreter = Interpreter()
        result = interpreter.execute(ast)
        print(f"程序执行完成，结果: {result}")

    except Exception as e:
        print(f"测试失败: {type(e).__name__}: {e}")
        import traceback

        print("堆栈跟踪:")
        print(traceback.format_exc())

    print("-" * 30)
    print()


def 测试竞速等待():
    """测试竞速等待功能"""
    print("=== 测试竞速等待功能 ===")

    程序内容 = """异步 函数 任务1()
    睡眠(0.3)
    返回 "任务1 完成"

异步 函数 任务2()
    睡眠(0.5)
    返回 "任务2 完成"

异步 函数 任务3()
    睡眠(0.2)
    返回 "任务3 完成"

异步 函数 主()
    打印("开始竞速等待...")
    定义 结果 = 等待 竞速([任务1(), 任务2(), 任务3()])
    打印("竞速等待结果:", 结果)

运行异步(主())
"""

    try:
        lexer = Lexer(程序内容)
        tokens = lexer.tokenize()

        parser = Parser(tokens)
        ast = parser.parse()

        interpreter = Interpreter()
        result = interpreter.execute(ast)
        print(f"程序执行完成，结果: {result}")

    except Exception as e:
        print(f"测试失败: {type(e).__name__}: {e}")
        import traceback

        print("堆栈跟踪:")
        print(traceback.format_exc())

    print("-" * 30)
    print()


def 运行道程序(文件名):
    """运行道程序"""
    文件路径 = os.path.join(os.path.dirname(__file__), 文件名)

    if not os.path.exists(文件路径):
        print(f"错误: 文件 '{文件名}' 不存在")
        return False

    with open(文件路径, encoding="utf-8") as f:
        source = f.read()

    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        parser = Parser(tokens)
        ast = parser.parse()

        interpreter = Interpreter()
        result = interpreter.execute(ast)
        print(f"文件 '{文件名}' 执行完成，结果: {result}")
        return True

    except Exception as e:
        print(f"执行文件 '{文件名}' 失败: {type(e).__name__}: {e}")
        import traceback

        print("堆栈跟踪:")
        print(traceback.format_exc())
        return False


def 运行所有测试():
    """运行所有测试"""
    print("========================================")
    print("道语言并发编程功能测试")
    print("========================================")
    print()

    测试词法分析器()
    测试解析器()
    测试简单异步程序()
    测试全部等待()
    测试竞速等待()

    print("========================================")
    print("所有测试完成!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        文件名 = sys.argv[1]
        if 文件名.endswith(".道"):
            运行道程序(文件名)
        else:
            print("错误: 文件必须以 '.道' 结尾")
            sys.exit(1)
    else:
        运行所有测试()
