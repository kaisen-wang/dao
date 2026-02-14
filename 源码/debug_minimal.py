import sys

sys.path.insert(0, "E:\\data\\code\\dao\\源码")

from dao.ast_nodes import (
    BinaryOp,
    ExpressionStmt,
    Identifier,
    MacroCall,
    MacroDefinition,
    NumberLiteral,
    QuoteBlock,
    ReturnStmt,
    UnquoteExpr,
    VariableDecl,
)
from dao.macros.expander import MacroExpander

# 创建一个最小的宏定义和调用场景
macro_def = MacroDefinition(name="可选参数", parameters=["x", "y"])
# 构造宏体
macro_def.body = [
    ReturnStmt(
        value=QuoteBlock(
            body=[
                ExpressionStmt(
                    expression=BinaryOp(
                        left=UnquoteExpr(expression=Identifier(name="x")),
                        operator="+",
                        right=UnquoteExpr(expression=Identifier(name="y")),
                    )
                )
            ]
        )
    )
]
arguments = [NumberLiteral(value=5), NumberLiteral(value=10)]

expander = MacroExpander()

print("=== 测试参数 ===")
print("macro_def.body:", macro_def.body)
print("macro_def.parameters:", macro_def.parameters)
print("arguments:", arguments)

print("\n=== 调用 _apply_macro_parameters ===")
result = expander._apply_macro_parameters(
    macro_def.body, macro_def.parameters, arguments
)
print("\n=== 结果 ===")
print(result)

print("\n=== 结果属性 ===")
print(dir(result))
if isinstance(result, list):
    for i, item in enumerate(result):
        print(f"\n项目 {i}:")
        print(item)
        print(dir(item))
