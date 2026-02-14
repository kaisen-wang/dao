from dao.ast_nodes import MacroCall
from dao.lexer import Lexer
from dao.macros.ast_ops import ASTOperations
from dao.parser import Parser

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

lexer = Lexer(code)
tokens = list(lexer.tokenize())

parser = Parser(tokens, code)
ast = parser.parse()

# 找到宏定义
macro_def = None
for stmt in ast.statements:
    from dao.ast_nodes import MacroDefinition

    if isinstance(stmt, MacroDefinition):
        macro_def = stmt
        break

# 找到宏调用
macro_call = None
for stmt in ast.statements:
    if hasattr(stmt, "expression") and isinstance(stmt.expression, MacroCall):
        macro_call = stmt.expression

print("=== Parameters ===")
print(f"Macro parameters: {macro_def.parameters}")
print(f"Call arguments: {[type(arg).__name__ for arg in macro_call.arguments]}")

# 尝试替换变量
if len(macro_def.parameters) == len(macro_call.arguments):
    replacements = dict(zip(macro_def.parameters, macro_call.arguments))

    print("\n=== Replacements ===")
    for k, v in replacements.items():
        print(f"  {k}: {type(v).__name__}")

        if hasattr(v, "body"):
            print(f"    Block body: {len(v.body)} statements")
            for s in v.body:
                print(f"      {type(s).__name__}")

    print("\n=== Replacing variables ===")
    result = ASTOperations.replace_variables(macro_def.body, replacements)
    print("Success!")

else:
    print(
        f"Error: Parameters count {len(macro_def.parameters)}, Arguments count {len(macro_call.arguments)}"
    )
