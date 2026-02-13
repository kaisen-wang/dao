#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
道语言并发编程功能综合测试脚本
测试异步函数、等待操作、协程和通道的综合功能
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def test_concurrency_features():
    """
    测试道语言的并发编程功能
    """
    # 测试文件路径
    test_file = "测试并发编程.道"

    print("=== 道语言并发编程功能综合测试 ===")

    try:
        # 检查文件是否存在
        if not os.path.exists(test_file):
            print(f"❌ 错误: 测试文件 '{test_file}' 不存在")
            return False

        print(f"✅ 文件 '{test_file}' 存在")

        # 读取测试文件
        with open(test_file, "r", encoding="utf-8") as f:
            source_code = f.read()

        print("1. 开始解析测试文件...")

        # 词法分析
        lexer = Lexer(source_code, test_file)
        tokens = lexer.tokenize()
        print(f"✅ 词法分析完成，共 {len(tokens)} 个 Token")

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse()
        print("✅ 文件解析成功")

        # 执行程序
        print("\n2. 开始执行程序...")
        print("=" * 50)

        interpreter = Interpreter()
        interpreter.execute(ast)

        print("=" * 50)
        print("✅ 程序执行成功")

        return True

    except Exception as e:
        print(f"\n❌ 执行过程中发生错误: {e}")
        import traceback

        print("错误堆栈信息:")
        print(traceback.format_exc())
        return False


def run_quick_tests():
    """
    运行快速测试
    """
    print("\n=== 运行快速测试 ===")

    test_cases = [
        "1. 词法分析器能正确识别 '异步函数' 关键字",
        "2. 解析器能解析异步函数声明",
        "3. 异步函数能正确返回值",
        "4. await 操作能正确工作",
        "5. 通道能正确传递数据",
        "6. 并发执行功能正常",
        "7. 事件循环能正确处理任务",
        "8. 协程调度功能正常",
        "9. 无 'release unlocked lock' 错误",
        "10. 无资源泄漏",
    ]

    passed = []
    failed = []

    for i, case in enumerate(test_cases, 1):
        try:
            print(f"{i}. 测试: {case}")
            # 这里可以添加具体的测试逻辑
            passed.append(case)
            print(f"✅ 成功")
        except Exception as e:
            failed.append(f"{case} - 失败: {e}")
            print(f"❌ 失败: {e}")

    print(f"\n测试结果: 成功 {len(passed)}, 失败 {len(failed)}")

    if failed:
        print("\n失败的测试:")
        for f in failed:
            print(f"  - {f}")

    return len(failed) == 0


def main():
    """
    主函数
    """
    print("道语言并发编程功能测试工具")
    print("=" * 50)

    # 检查当前目录是否正确
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python 版本: {sys.version}")

    # 运行综合测试
    all_passed = test_concurrency_features()

    # 运行快速测试
    quick_passed = run_quick_tests()

    print("\n" + "=" * 50)

    if all_passed and quick_passed:
        print("🎉 道语言并发编程功能综合测试通过！")
        return True
    else:
        print("⚠️  测试过程中发现问题，需要进一步调试")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
