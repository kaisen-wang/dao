from dao.interpreter.core import Interpreter
from dao.lexer.core import Lexer
from dao.macros.registry import get_registry
from dao.parser.core import Parser

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
"""

try:
    # 词法分析
    lexer = Lexer(code)
    tokens = list(lexer.tokenize())
    print("=== Tokenization ===")
    print("Token count:", len(tokens))
    print("\n".join([f"{t.type}: {t.value}" for t in tokens]))
    print()

    # 语法分析
    parser = Parser(tokens, code)
    ast = parser.parse()
    print("=== Parsing ===")
    print("AST type:", type(ast))
    print("Number of statements:", len(ast.statements))
    for i, stmt in enumerate(ast.statements):
        print(f"  Statement {i}: {type(stmt).__name__}")
        if hasattr(stmt, "name"):
            print(f"    Name: {stmt.name}")
        if hasattr(stmt, "parameters"):
            print(f"    Parameters: {stmt.parameters}")
        if hasattr(stmt, "body"):
            print(f"    Body type: {type(stmt.body)}")
            if isinstance(stmt.body, list):
                print(f"    Body statements: {len(stmt.body)}")
                for j, s in enumerate(stmt.body):
                    print(f"      Statement {j}: {type(s).__name__}")
                    if hasattr(s, "expression"):
                        print(f"        Expression: {type(s.expression).__name__}")
                    if hasattr(s, "value"):
                        print(f"        Value: {type(s.value).__name__}")
                        if type(s.value).__name__ == "MacroCall":
                            print(f"          Macro name: {s.value.name}")
                            print(
                                f"          Macro args count: {len(s.value.arguments)}"
                            )
                    # 打印引用的源代码，用于调试
                    if hasattr(stmt, "line"):
                        print(f"        Line: {stmt.line}")
    print()

    # 执行
    print("=== Execution ===")
    interpreter = Interpreter()
    result = interpreter.execute(ast, source=code)
    print("Execution result:", result)
    print("Global environment variables:", list(interpreter.global_env.values.keys()))
    if "总和" in interpreter.global_env.values:
        print("总和变量值:", interpreter.global_env.get("总和"))

    # 检查宏注册表
    registry = get_registry()
    print("\n=== Macro Registry ===")
    print(registry)

except Exception as e:
    print(f"\n=== Error ===")
    print(f"类型: {type(e).__name__}")
    print(f"信息: {e}")
    import traceback

    print(f"堆栈跟踪: {traceback.format_exc()}")
