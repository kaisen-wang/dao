from dao.ast_nodes import BlockExpr, MacroCall
from dao.lexer.core import Lexer
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

# 词法分析
lexer = Lexer(code)
tokens = list(lexer.tokenize())

# 创建解析器
parser = Parser(tokens, code)

print("=== Parsing Step by Step ===")
print()

# 解析第一个语句（定义宏）
print("Step 0: 定义宏")
parser.pos = 0
stmt = parser.parse_statement()
print(f"  Returned: {type(stmt).__name__}")
print(f"  New pos: {parser.pos}")

# 解析第二个语句（设 总和 = 0）
print()
print("Step 1: 设 总和 = 0")
stmt = parser.parse_statement()
print(f"  Returned: {type(stmt).__name__}")
print(f"  New pos: {parser.pos}")
if hasattr(stmt, "name") and hasattr(stmt, "value"):
    print(f"  Value: {type(stmt.value).__name__}")

# 解析第三个语句（!循环(5) { ... }）
print()
print("Step 2: !循环(5)")
stmt = parser.parse_statement()
print(f"  Returned: {type(stmt).__name__}")
print(f"  New pos: {parser.pos}")

if hasattr(stmt, "expression") and isinstance(stmt.expression, MacroCall):
    print(f"  Macro call: {stmt.expression.name}")
    print(f"  Arguments: {len(stmt.expression.arguments)}")

    for j, arg in enumerate(stmt.expression.arguments):
        print(f"    Arg {j}: {type(arg).__name__}")

        if isinstance(arg, BlockExpr):
            print(f"    Block body statements: {len(arg.body)}")
            for i, s in enumerate(arg.body):
                print(f"      Statement {i}: {type(s).__name__}")
                if hasattr(s, "name"):
                    print(f"        Name: {s.name}")
                if hasattr(s, "value"):
                    print(f"        Value: {type(s.value).__name__}")

print()
print("=== Parsing Complete ===")
