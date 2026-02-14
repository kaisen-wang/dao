import sys

sys.path.append(".")

from dao.lexer import Lexer
from dao.parser import Parser


def debug_parsing():
    """调试块解析过程"""
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

    # 词法分析
    lexer = Lexer(code, "<调试>")
    tokens = lexer.tokenize()

    print("=== 词法分析结果 ===")
    for i, token in enumerate(tokens):
        print(f"pos {i:2d}: {token.type.name} '{token.value}'")

    print("\n=== 语法分析 ===")
    parser = Parser(tokens, code)

    # 修改 Parser 以保存对 tokens 的引用
    parser._debug_tokens = tokens

    # 重写 parse_block 以打印调试信息
    original_parse_block = parser.parse_block

    def debug_parse_block():
        print(f"DEBUG parse_block: 调用时 pos = {parser.pos}")
        print(
            "DEBUG parse_block: 当前 token =",
            parser.current.type.name,
            repr(parser.current.value),
        )

        # 打印可用 tokens 的范围
        print(
            f"DEBUG parse_block: 可用 tokens: pos {parser.pos} 到 {len(parser.tokens) - 1}"
        )
        for i in range(parser.pos, min(parser.pos + 5, len(parser.tokens))):
            print(
                f"DEBUG parse_block: pos {i:2d}: {parser.tokens[i].type.name} '{parser.tokens[i].value}'"
            )

        # 调用原始方法
        result = original_parse_block()

        print(f"DEBUG parse_block: 返回时 pos = {parser.pos}")
        print(f"DEBUG parse_block: 返回 {len(result)} 条语句")
        for i, stmt in enumerate(result):
            print(f"DEBUG parse_block: 语句 {i}:")
            print(f"  类型: {type(stmt).__name__}")

        return result

    parser.parse_block = debug_parse_block

    try:
        ast = parser.parse()

        print("\n=== 解析后的 AST ===")

        macro_def = None
        for stmt in ast.statements:
            if hasattr(stmt, "name") and stmt.name == "循环":
                macro_def = stmt
                break

        if macro_def:
            print(f"宏定义: {macro_def.name}")
            print(f"参数: {macro_def.parameters}")
            print(f"Body: {len(macro_def.body)} 语句")

            return_stmt = macro_def.body[0]
            print(f"返回值类型: {type(return_stmt.value).__name__}")

            if hasattr(return_stmt.value, "body"):
                print(f"引号块体: {len(return_stmt.value.body)} 语句")

                for i, stmt in enumerate(return_stmt.value.body):
                    print(f"\n  块语句 {i}:")
                    print(f"  类型: {type(stmt).__name__}")
                    print(f"  内容: {stmt}")

                    if hasattr(stmt, "body"):
                        print(f"  内部块: {len(stmt.body)} 语句")

                        for j, sub_stmt in enumerate(stmt.body):
                            print(f"\n    内部语句 {j}:")
                            print(f"    类型: {type(sub_stmt).__name__}")
                            print(f"    内容: {sub_stmt}")

    except Exception as e:
        import traceback

        print(f"\n解析错误: {type(e).__name__}: {e}")
        print("堆栈跟踪:")
        print(traceback.format_exc())


debug_parsing()
