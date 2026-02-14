from dao.lexer import Lexer
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
"""

lexer = Lexer(code)
tokens = list(lexer.tokenize())

parser = Parser(tokens, code)
ast = parser.parse()

# 找到宏定义
from dao.ast_nodes import MacroDefinition

for stmt in ast.statements:
    if isinstance(stmt, MacroDefinition):
        macro_def = stmt

print("=== Macro Definition ===")
for i, body_stmt in enumerate(macro_def.body):
    print(f"  Stmt {i}: {type(body_stmt).__name__}")

    if hasattr(body_stmt, "value"):
        from dao.ast_nodes import QuoteBlock

        if isinstance(body_stmt.value, QuoteBlock):
            print(f"  QuoteBlock: {len(body_stmt.value.body)} statements")
            for j, q_stmt in enumerate(body_stmt.value.body):
                print(f"    Stmt {j}: {type(q_stmt).__name__}")

                # 检查是否包含 $块
                if hasattr(q_stmt, "body"):
                    for b_stmt in q_stmt.body:
                        print(f"      Block Stmt: {type(b_stmt).__name__}")

                        from dao.ast_nodes import Identifier

                        if hasattr(b_stmt, "target") and isinstance(
                            b_stmt.target, Identifier
                        ):
                            print(f"        Target: {b_stmt.target.name}")

                        if hasattr(b_stmt, "value"):
                            print(f"        Value: {type(b_stmt.value).__name__}")

                        if hasattr(b_stmt, "condition"):
                            print(
                                f"        Condition: {type(b_stmt.condition).__name__}"
                            )

                        if hasattr(b_stmt, "body"):
                            print(f"        Body: {len(b_stmt.body)} statements")
                            for c_stmt in b_stmt.body:
                                print(f"          Body Stmt: {type(c_stmt).__name__}")

                                # 查找包含 $块 的标识符
                                from dao.ast_nodes import Identifier

                                if hasattr(c_stmt, "__dict__"):
                                    for attr_name in dir(c_stmt):
                                        attr = getattr(c_stmt, attr_name)
                                        if isinstance(attr, Identifier):
                                            print(
                                                f"            Identifier: {attr.name}"
                                            )
