import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def run_capture(source: str) -> str:
    """运行代码并捕获输出"""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    try:
        Interpreter().execute(ast)
        return captured.getvalue()
    finally:
        sys.stdout = old_stdout


def test_simple_generator():
    source = """
函数 gen()
    产出 1
    产出 2
    产出 3

定义 g = gen()
遍历 x 在 g
    打印(x)
"""
    output = run_capture(source).strip().split("\n")
    assert output == ["1", "2", "3"], f"Expected ['1', '2', '3'], got {output}"
    print("✓ Simple generator test passed")


def test_generator_with_logic():
    source = """
函数 count_to(n)
    遍历 i 从 1 到 n
        产出 i

定义 evens = count_to(10)
遍历 x 在 evens
    如果 x % 2 == 0
        打印(x)
"""
    output = run_capture(source).strip().split("\n")
    assert output == ["2", "4", "6", "8", "10"], (
        f"Expected ['2', '4', '6', '8', '10'], got {output}"
    )
    print("✓ Generator with logic test passed")


def test_generator_in_expression():
    source = """
函数 gen()
    产出 1
    产出 2
    产出 3

定义 sum = 0
遍历 x 在 gen()
    sum = sum + x

打印(sum)
"""
    output = run_capture(source).strip()
    assert output == "6", f"Expected '6', got {output}"
    print("✓ Generator in expression test passed")


def test_empty_generator():
    # Test a generator that yields nothing
    source = """
函数 empty_gen()
    定义 n = 0
    如果 n > 0
        产出 n

定义 count = 0
定义 found = 假
遍历 x 在 [1]
    如果 x == 1
        遍历 y 在 empty_gen()
            count = count + 1
            found = 真

打印(count)
打印(found)
"""
    output = run_capture(source).strip().split("\n")
    assert output == ["0", "假"], f"Expected ['0', '假'], got {output}"
    print("✓ Empty generator test passed")


def test_generator_with_return():
    source = """
函数 gen_with_return(n)
    遍历 i 从 1 到 n
        产出 i
    返回 "Done"

定义 count = 0
遍历 x 在 gen_with_return(5)
    count = count + 1

打印(count)
"""
    output = run_capture(source).strip()
    assert output == "5", f"Expected '5', got {output}"
    print("✓ Generator with return test passed")


def test_nested_generator():
    source = """
函数 inner()
    产出 1
    产出 2

函数 outer()
    产出 0
    遍历 x 在 inner()
        产出 x

遍历 x 在 outer()
    打印(x)
"""
    output = run_capture(source).strip().split("\n")
    assert output == ["0", "1", "2"], f"Expected ['0', '1', '2'], got {output}"
    print("✓ Nested generator test passed")


def test_generator_in_list():
    source = """
函数 gen()
    产出 1
    产出 2
    产出 3

定义 lst = []
遍历 x 在 gen()
    lst.追加(x)

打印(长度(lst))
"""
    output = run_capture(source).strip()
    assert output == "3", f"Expected '3', got {output}"
    print("✓ Generator in list test passed")


if __name__ == "__main__":
    print("Running generator tests...")
    test_simple_generator()
    test_generator_with_logic()
    test_generator_in_expression()
    test_empty_generator()
    test_generator_with_return()
    test_nested_generator()
    test_generator_in_list()
    print("\n✅ All generator tests passed!")
