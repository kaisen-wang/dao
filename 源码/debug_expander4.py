"""
调试宏参数替换
"""

import sys

sys.path.insert(0, "E:\\data\\code\\dao\\源码")

from dao.ast_nodes import MacroCall, ReturnStmt
from dao.lexer import Lexer
from dao.macros.expander import MacroExpander
from dao.macros.registry import get_registry, register_macro
from dao.parser import Parser


def debug_expansion():
    """调试宏参数替换"""
    code = """
定义宏 可选参数(x, y=10) {
    返回 引述 {
        $x + $y
    }
}

设 结果1 = !可选参数(5)
"""

    print("=== 正在解析代码 ===")
    lexer = Lexer(code, "<调试>")
    tokens = lexer.tokenize()

    parser = Parser(tokens, code)
    ast = parser.parse()

    registry = get_registry()

    for stmt in ast.statements:
        if stmt.__class__.__name__ == "MacroDefinition":
            print(f"=== 找到宏定义 {stmt.name} ===")
            register_macro(stmt, code)

    print("=== 注册表内容 ===")
    print(registry)

    expander = MacroExpander()

    call_node = None
    macro_def = None

    for stmt in ast.statements:
        if stmt.__class__.__name__ == "MacroDefinition":
            macro_def = stmt
        elif (
            stmt.__class__.__name__ == "VariableDecl"
            and hasattr(stmt, "value")
            and isinstance(stmt.value, MacroCall)
        ):
            call_node = stmt.value

    print(f"=== 宏调用 ===")
    print(f"  call_node: {call_node}")
    print(f"  宏参数: {call_node.arguments}")

    macro_info = registry.find_macro("可选参数")

    print("=== 宏体 ===")
    return_stmt = None

    if isinstance(macro_info.body, list) and len(macro_info.body) == 1:
        if isinstance(macro_info.body[0], ReturnStmt):
            return_stmt = macro_info.body[0]
            print(f"  ReturnStmt: {return_stmt}")
            print(f"  返回值: {return_stmt.value}")

    if return_stmt:
        print(f"\n=== body 分析 ===")
        print(f"  类型: {type(return_stmt)}")
        print(f"  返回值类型: {type(return_stmt.value)}")
        print(f"  返回值属性: {dir(return_stmt.value)}")

        if hasattr(return_stmt.value, "body"):
            print(f"\n=== 引号块内容 ===")
            for expr_stmt in return_stmt.value.body:
                print(f"  语句类型: {type(expr_stmt)}")
                print(f"  表达式: {expr_stmt}")
                print(f"  左操作数: {expr_stmt.expression.left}")
                print(f"  左.expression: {expr_stmt.expression.left.expression}")
                print(f"  右操作数: {expr_stmt.expression.right}")
                print(f"  右.expression: {expr_stmt.expression.right.expression}")

        param_names = macro_def.parameters
        arguments = call_node.arguments

        print("=== 传入 _apply_macro_parameters 的参数 ===")
        print(f"  参数: {param_names}")
        print(f"  参数: {arguments}")
        from dao.macros.expander import MacroExpander

        expander = MacroExpander()
        result = expander._apply_macro_parameters([return_stmt], param_names, arguments)
        print("=== 返回值 ===")
        print(f"  返回值类型: {type(result)}")
        print(f"  返回值: {result}")

        # 详细显示返回结果
        if hasattr(result, "__dict__"):
            print("=== 返回对象属性 ===")
            for attr_name in dir(result):
                if not attr_name.startswith("__"):
                    try:
                        value = getattr(result, attr_name)
                        print(f"  {attr_name}: {type(value)}, {value}")
                    except:
                        print(f"  {attr_name}: (无法访问)")


if __name__ == "__main__":
    debug_expansion()
