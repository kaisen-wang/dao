#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试错误对象属性的调试脚本
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.builtins.oop_types import DaoError
from dao.errors import 运行时错误

print("调试错误对象属性访问...")
print("=" * 50)

# 测试 运行时错误 对象
print("1. 测试 运行时错误 对象:")
try:
    raise 运行时错误("测试消息", 10, 20, "源代码")
except Exception as e:
    print(f"   类型: {type(e).__name__}")
    print(f"   字符串表示: {e}")
    print(f"   message: {e.message}")
    print(f"   line: {e.line}")
    print(f"   column: {e.column}")
    print(f"   source: {e.source}")
    print(f"   stack: {e.stack}")
    print(f"   所有属性: {dir(e)}")
    print()

# 测试 DaoError 对象
print("2. 测试 DaoError 对象:")
try:
    raise DaoError("自定义错误")
except Exception as e:
    print(f"   类型: {type(e).__name__}")
    print(f"   字符串表示: {e}")
    print(f"   message: {e.message}")
    print(f"   line: {e.line}")
    print(f"   column: {e.column}")
    print(f"   所有属性: {dir(e)}")
    print()

# 测试属性访问映射
print("3. 属性访问映射:")
test_error = 运行时错误("属性访问测试", 5, 15, "测试代码")
print(f"   test_error.行 = {test_error.line}")
print(f"   test_error.列 = {test_error.column}")
print(f"   test_error.message = {test_error.message}")
print(f"   str(test_error) = {str(test_error)}")
print()

print("调试完成！")
print("=" * 50)
