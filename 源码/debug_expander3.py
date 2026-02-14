"""
调试宏展开过程
"""

import sys

sys.path.insert(0, "E:\\data\\code\\dao\\源码")

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.macros.expander import MacroExpander
from dao.macros.registry import get_registry, register_macro


def debug_expansion():
    """调试宏展开过程"""
    code = """
定义宏 可选参数(x, y=10) {
    返回 引述 {
        $x + $y
    }
}

设 结果1 = !可选参数(5)
"""

    # 词法分析
    lexer = Lexer(code, "<调试>")
    tokens = lexer.tokenize()

    # 语法分析
    parser = Parser(tokens, code)
    ast = parser.parse()

    print("=== 解析后的 AST ===")
    print(ast)

    # 找到宏定义并注册
    from dao.ast_nodes import MacroDefinition

    for stmt in ast.statements:
        if isinstance(stmt, MacroDefinition):
            print(f"\n=== 找到宏定义 {stmt.name} ===")
            print("尝试注册到注册表...")
            register_macro(stmt, code)

    # 检查注册表
    print("\n=== 宏注册表 ===")
    registry = get_registry()
    print(f"所有已注册的宏: {[name for name in registry.macros.keys()]}")

    macro_info = registry.find_macro("可选参数")
    print(f"找到宏: {macro_info}")

    if macro_info:
        print(f"宏参数: {macro_info.parameters}")
        print(f"宏体类型: {type(macro_info.body)}")
        print(f"宏体: {macro_info.body}")

    # 现在使用解释器执行
    interpreter = Interpreter()
    print("\n=== 执行程序 ===")
    try:
        result = interpreter.execute(ast, source=code)
        print(f"执行结果: {result}")
    except Exception as e:
        print(f"执行过程中出现异常: {type(e).__name__}: {e}")
        import traceback

        print(f"堆栈跟踪: {traceback.format_exc()}")

    # 再次检查注册表
    print("\n=== 执行后的注册表 ===")
    print(f"所有已注册的宏: {[name for name in get_registry().macros.keys()]}")

    # 检查全局环境
    print("\n=== 全局环境变量 ===")
    print(f"变量: {list(interpreter.global_env.values.keys())}")
    if "结果1" in interpreter.global_env.values:
        print(f"结果1: {interpreter.global_env.values['结果1']}")

    if '结果1' in interpreter.global_env.values:
        print(f"结果1: {interpreter.global_env.values['结果1']}")

if __name__ == "__main__":
    debug_expansion()
