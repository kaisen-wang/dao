"""
调试宏参数替换脚本2
"""

import os
import sys

# 确保能导入dao包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.macros.expander import MacroExpander
from dao.parser import Parser


def debug_apply():
    """调试 _apply_macro_parameters 方法"""
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

    interpreter = Interpreter()

    # 1. 词法分析
    lexer = Lexer(code, "<调试>")
    tokens = lexer.tokenize()

    # 2. 语法分析
    parser = Parser(tokens, code)
    ast = parser.parse()

    # 获取宏定义
    macro_def = None
    call_stmt = None

    for stmt in ast.statements:
        if hasattr(stmt, "name") and stmt.name == "循环":
            macro_def = stmt
        elif hasattr(stmt, "expression") and hasattr(stmt.expression, "arguments"):
            call_stmt = stmt

    print(f"宏名称: {macro_def.name}")
    print(f"参数: {macro_def.parameters}")
    print(f"Body 语句数: {len(macro_def.body)}")
    for i, stmt in enumerate(macro_def.body):
        print(f"  语句 {i}: {type(stmt).__name__}")

        if hasattr(stmt, "value"):
            print(f"  值类型: {type(stmt.value).__name__}")
            if hasattr(stmt.value, "body"):
                print(f"  块体: {len(stmt.value.body)} 语句")
                for j, q_stmt in enumerate(stmt.value.body):
                    print(f"    块语句 {j}: {type(q_stmt).__name__}")

                    if hasattr(q_stmt, "body"):
                        print(f"    内部 Body: {len(q_stmt.body)} 语句")
                        for k, b_stmt in enumerate(q_stmt.body):
                            print(f"      子语句 {k}: {type(b_stmt).__name__}")
    print()

    # 获取调用参数
    arguments = call_stmt.expression.arguments
    print(f"实际调用参数: {len(arguments)} 个")
    for i, arg in enumerate(arguments):
        print(f"参数 {i} ({macro_def.parameters[i]}):")
        print(f"  类型: {type(arg).__name__}")
        if hasattr(arg, "body"):
            print(f"  Body: {len(arg.body)} 语句")
            for j, b_stmt in enumerate(arg.body):
                print(f"    语句 {j}: {type(b_stmt).__name__}")

    print()

    # 执行参数替换
    expander = MacroExpander()
    expanded_body = expander._apply_macro_parameters(
        macro_def.body, macro_def.parameters, arguments
    )

    print(f"=== 替换后 Body ===")
    if hasattr(expanded_body, "body"):
        print(f"Body: {len(expanded_body.body)} 语句")
        for i, stmt in enumerate(expanded_body.body):
            print(f"  语句 {i}: {type(stmt).__name__}")

            if hasattr(stmt, "value"):
                print(f"  值类型: {type(stmt.value).__name__}")
                if hasattr(stmt.value, "body"):
                    print(f"  块体: {len(stmt.value.body)} 语句")
                    for j, q_stmt in enumerate(stmt.value.body):
                        print(f"    块语句 {j}: {type(q_stmt).__name__}")

                        if hasattr(q_stmt, "body"):
                            print(f"    内部 Body: {len(q_stmt.body)} 语句")
                            for k, b_stmt in enumerate(q_stmt.body):
                                print(f"      子语句 {k}: {type(b_stmt).__name__}")
    print()

    print("=== 参数替换后 ===")
    return_stmt = expanded_body[0]
    quote_block = return_stmt.value
    print(f"QuoteBlock 语句数: {len(quote_block.body)}")

    for i, stmt in enumerate(quote_block.body):
        print(f"  语句 {i}: {type(stmt).__name__}")

        if hasattr(stmt, "condition"):
            print(f"  条件: {type(stmt.condition).__name__}")

        if hasattr(stmt, "body"):
            print(f"  Body: {len(stmt.body)} 语句")
            for j, b_stmt in enumerate(stmt.body):
                print(f"    语句 {j}: {type(b_stmt).__name__}")
                print(f"      内容: {b_stmt}")


debug_apply()
