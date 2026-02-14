import sys

sys.path.append(".")

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_test():
    """运行测试"""
    code = """
    定义宏 循环(n, 块) {
        返回 引述 {
            设 i = 0
            当 i < $n {
                $块
                i = i + 1
            }
        }
    }

    设 总和 = 0
    !循环(5) {
        总和 = 总和 + i
    }

    打印("总和:", 总和)
    """

    # 词法分析
    lexer = Lexer(code, "<测试>")
    tokens = lexer.tokenize()

    # 语法分析
    parser = Parser(tokens, code)
    ast = parser.parse()
    print("=== 解析后的 AST ===")
    print(ast)

    # 执行
    interpreter = Interpreter()
    try:
        interpreter.execute(ast, code)

        print("\n=== 解释器环境 ===")
        print(f"全局环境: {interpreter.global_env.values}")
        print(f"总和: {interpreter.global_env.get('总和')}")
        print(f"i: {interpreter.global_env.get('i')}")

    except Exception as e:
        import traceback

        print(f"\n执行错误: {e}")
        print("堆栈跟踪:")
        print(traceback.format_exc())


if __name__ == "__main__":
    run_test()
