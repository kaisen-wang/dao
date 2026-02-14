import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import TokenType


def debug_parse_macro_def():
    source = """
定义宏 加一(x) {
    返回 引述 { $x + 1 }
}
""".strip()

    print(f"调试 parse_macro_definition 方法")
    print("=" * 50)
    print(f"源: {repr(source)}")
    print()

    # 词法分析
    lexer = Lexer(source, "<调试>")
    tokens = lexer.tokenize()

    print("词法分析结果:")
    for i, token in enumerate(tokens):
        print(f"  {i}: {token}")
    print()

    # 语法分析
    parser = Parser(tokens, source)

    # 打印调试信息
    print("调用 parse_statement:")
    try:
        # 获取第一个语句（应该是宏定义）
        stmt = parser.parse_statement()

        print("  语句类型: ", type(stmt).__name__)

        if hasattr(stmt, "name"):
            print(f"  名称: {stmt.name}")

        if hasattr(stmt, "body"):
            print(f"  体类型: {type(stmt.body).__name__}")

            if isinstance(stmt.body, list):
                print(f"  体长度: {len(stmt.body)}")
                for i, s in enumerate(stmt.body):
                    print(f"  语句{i}: {type(s).__name__}: {s}")
            elif stmt.body is not None:
                print(f"  体: {stmt.body}")

        if hasattr(stmt, "parameters"):
            print(f"  参数: {', '.join(stmt.parameters)}")

    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback

        print(f"堆栈跟踪: {traceback.format_exc()}")

    print()
    print("剩余 Token 流:")
    while parser.current.type != TokenType.文件结束:
        print(f"  {parser.current}")
        parser.advance()


if __name__ == "__main__":
    debug_parse_macro_def()
