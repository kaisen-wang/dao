#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试 Python 错误初始化过程的脚本
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.ast_nodes import *
from dao.builtins.oop_types import DaoClass, DaoError, DaoFunction, DaoInstance
from dao.interpreter.core import Interpreter


def test_error_initialization():
    """直接在 Python 中测试错误初始化过程"""
    print("测试错误初始化过程...")
    print("=" * 50)

    try:
        # 创建一个简单的错误类定义（DaoClass）
        # 注意：这是模拟解析器解析道语言代码的过程
        error_class_methods = {
            "初始化": DaoFunction(
                name="初始化",
                params=["消息", "行号"],
                default_values={},
                body=[],  # 这里应该包含实际的初始化代码，但我们简化处理
                closure_env=None,
            )
        }

        # 模拟解析器解析出的 DaoClass 对象
        from dao.builtins.oop_types import DaoClass

        详细错误类 = DaoClass(
            name="详细错误",
            parent=DaoError,
            methods=error_class_methods,
            static_methods={},
        )

        print(f"创建的错误类: {详细错误类}")
        print(f"继承自: {详细错误类.parent}")
        print(f"有初始化方法: {'初始化' in 详细错误类.methods}")

        # 现在测试实例化
        print("\n测试实例化:")
        interpreter = Interpreter()

        # 模拟调用 详细错误类 构造函数
        try:
            # 在真实场景中，这是通过 self.eval_function_call 间接调用的
            # 但我们可以直接访问 _instantiate_class 方法
            error_instance = interpreter._instantiate_class(
                详细错误类, ["测试消息", 10], {}, None
            )

            print(f"实例类型: {type(error_instance)}")
            print(f"是否是 DaoError 实例: {isinstance(error_instance, DaoError)}")
            print(f"错误消息: {str(error_instance)}")

            print(f"\n错误实例属性:")
            print(f"  hasattr(行号): {hasattr(error_instance, '行号')}")
            if hasattr(error_instance, "行号"):
                print(f"  行号: {error_instance.行号}")
            print(f"  hasattr(时间): {hasattr(error_instance, '时间')}")
            if hasattr(error_instance, "时间"):
                print(f"  时间: {error_instance.时间}")
            print(f"  hasattr(类型): {hasattr(error_instance, '类型')}")
            if hasattr(error_instance, "类型"):
                print(f"  类型: {error_instance.类型}")

            print(f"\n所有属性: {dir(error_instance)}")

        except Exception as e:
            print(f"实例化过程出错: {type(e).__name__}: {e}")
            import traceback

            print(f"堆栈跟踪: {traceback.format_exc()}")

    except Exception as e:
        print(f"测试过程出错: {type(e).__name__}: {e}")
        import traceback

        print(f"堆栈跟踪: {traceback.format_exc()}")

    print("=" * 50)


if __name__ == "__main__":
    test_error_initialization()
