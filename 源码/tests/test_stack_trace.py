"""
栈追踪测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.errors import 运行时错误
from io import StringIO


def test_stack_trace():
    """测试错误时的调用栈显示"""
    source = """// 测试栈追踪
函数 divide(a, b)
    返回 a / b

函数 process(x)
    返回 divide(x, 0)

函数 main()
    返回 process(10)

main()
"""

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("❌ 栈追踪测试失败: 应该抛出错误")
        assert False
    except 运行时错误 as e:
        # 直接检查异常对象的stack属性
        assert hasattr(e, "stack"), "错误对象应包含stack属性"
        stack = e.stack

        # 验证调用栈内容
        assert len(stack) >= 3, f"调用栈应有至少3层，实际有{len(stack)}层"

        # 获取函数名列表（跳过<匿名>等情况）
        func_names = [frame.get("function", "") for frame in stack]

        # 验证调用顺序
        assert "main" in func_names, f"调用栈应包含'main', 实际: {func_names}"
        assert "process" in func_names, f"调用栈应包含'process', 实际: {func_names}"
        assert "divide" in func_names, f"调用栈应包含'divide', 实际: {func_names}"

        # 验证调用顺序（main在最外层，divide在最内层）
        main_idx = next((i for i, f in enumerate(func_names) if f == "main"), -1)
        process_idx = next((i for i, f in enumerate(func_names) if f == "process"), -1)
        divide_idx = next((i for i, f in enumerate(func_names) if f == "divide"), -1)

        assert main_idx < process_idx < divide_idx, f"调用顺序错误: {func_names}"

        print(f"栈追踪测试通过 - 调用栈: {func_names}")


def test_stack_trace_with_method():
    """测试方法调用时的栈追踪"""
    source = """// 测试方法栈追踪
类型 Calculator
    函数 divide(a, b)
        返回 a / b

函数 process(calc, x)
    返回 calc.divide(x, 0)

函数 main()
    定义 calc = Calculator()
    返回 process(calc, 10)

main()
"""

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("❌ 方法栈追踪测试失败: 应该抛出错误")
        assert False
    except 运行时错误 as e:
        # 直接检查异常对象的stack属性
        assert hasattr(e, "stack"), "错误对象应包含stack属性"
        stack = e.stack

        # 验证调用栈内容
        assert len(stack) >= 3, f"调用栈应有至少3层，实际有{len(stack)}层"

        func_names = [frame.get("function", "") for frame in stack]

        assert "main" in func_names, f"调用栈应包含'main', 实际: {func_names}"
        assert "process" in func_names, f"调用栈应包含'process', 实际: {func_names}"
        assert "Calculator.divide" in func_names, (
            f"调用栈应包含'Calculator.divide', 实际: {func_names}"
        )

        print(f"方法栈追踪测试通过 - 调用栈: {func_names}")


def test_no_error_no_stack():
    """测试正常执行时不显示栈追踪"""
    source = """// 测试正常执行
函数 add(a, b)
    返回 a + b

函数 process(x)
    返回 add(x, 5)

定义 result = process(10)
打印(result)
"""

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()

        # 重定向输出来捕获打印结果
        from contextlib import redirect_stdout

        f = StringIO()
        with redirect_stdout(f):
            interpreter.execute(ast)

        output = f.getvalue()
        assert "调用栈" not in output, "正常执行不应显示调用栈"
        assert "15" in output, "应输出正确结果"

        print("正常执行无栈追踪测试通过")
    except Exception as e:
        print(f"❌ 正常执行测试失败: {e}")


if __name__ == "__main__":
    print("测试错误时的调用栈追踪")
    test_stack_trace()

    print("\n测试方法调用时的栈追踪")
    test_stack_trace_with_method()

    print("\n测试正常执行时不显示栈追踪")
    test_no_error_no_stack()

    print("\n所有栈追踪测试通过！")
