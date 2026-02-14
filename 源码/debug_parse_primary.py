import sys

sys.path.append(".")

from dao.lexer import Lexer
from dao.parser import Parser


def debug_primary_parsing():
    """调试 $块 的解析过程"""
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

    print("\n=== 定位 parse_block ===")

    parser = Parser(tokens, code)

    # 重写 parse_block 以调试 $块 的解析过程
    original_parse_block = parser.parse_block

    def debug_parse_block():
        print("DEBUG parse_block: 开始调用 parse_block")
        print(f"DEBUG parse_block: 调用时 pos = {parser.pos}")

        result = original_parse_block()

        print(f"DEBUG parse_block: 返回时 pos = {parser.pos}")

        # 打印结果的语句类型
        for i, stmt in enumerate(result):
            print(f"DEBUG parse_block: 语句 {i}")
            print(f"DEBUG parse_block: 类型 {type(stmt).__name__}")

            if hasattr(stmt, "body"):
                print(f"DEBUG parse_block: 包含 {len(stmt.body)} 个内部语句")
                for j, b_stmt in enumerate(stmt.body):
                    print(f"DEBUG parse_block:   内部语句 {j}:")
                    print(f"DEBUG parse_block:   类型 {type(b_stmt).__name__}")

                    if hasattr(b_stmt, "expression"):
                        print(
                            f"DEBUG parse_block:   表达式类型 {type(b_stmt.expression).__name__}"
                        )

                    if hasattr(b_stmt, "body"):
                        print(
                            f"DEBUG parse_block:   包含 {len(b_stmt.body)} 个内部语句"
                        )

        return result

    parser.parse_block = debug_parse_block

    try:
        print("\n=== 语法分析 ===")
        ast = parser.parse()

        print("\n=== 解析后的 AST ===")
        print(f"程序语句数: {len(ast.statements)}")

        for i, stmt in enumerate(ast.statements):
            print(f"语句 {i}:")
            print(f"类型: {type(stmt).__name__}")

            if hasattr(stmt, "name"):
                print(f"名称: {stmt.name}")

            if hasattr(stmt, "parameters"):
                print(f"参数: {', '.join(stmt.parameters)}")

            if hasattr(stmt, "body"):
                print(f"包含 {len(stmt.body)} 个内部语句")

                for j, b_stmt in enumerate(stmt.body):
                    print(f"  内部语句 {j}:")
                    print(f"  类型: {type(b_stmt).__name__}")

                    if hasattr(b_stmt, "value"):
                        print(f"  值类型: {type(b_stmt.value).__name__}")

                        if hasattr(b_stmt.value, "body"):
                            print(f"  值包含 {len(b_stmt.value.body)} 个语句")

                            for k, q_stmt in enumerate(b_stmt.value.body):
                                print(f"    引号块语句 {k}:")
                                print(f"    类型: {type(q_stmt).__name__}")

                                if hasattr(q_stmt, "body"):
                                    print(f"    包含 {len(q_stmt.body)} 个内部语句")

                                    for l, qq_stmt in enumerate(q_stmt.body):
                                        print(f"      内部引号块语句 {l}:")
                                        print(f"      类型: {type(qq_stmt).__name__}")

    except Exception as e:
        print(f"\n解析错误: {type(e).__name__}: {e}")

        import traceback

        print(f"\n堆栈跟踪:")
        print(traceback.format_exc())
        print()

        # 打印位置信息
        if hasattr(parser, "pos"):
            print(f"当前 pos: {parser.pos}")

            if hasattr(parser, "current"):
                print(
                    f"当前 token: {parser.current.type.name} '{parser.current.value}'"
                )
                print(
                    f"当前 token: {parser.current.type.name} '{parser.current.value}'"
                )

            print()
            print("可用 tokens:")

            for i in range(parser.pos, min(parser.pos + 5, len(tokens))):
                print(f"pos {i:2d}: {tokens[i].type.name} '{tokens[i].value}'")


debug_primary_parsing()
