"""模式匹配解析混入"""

from ...tokens import TokenType
from ...ast_nodes import MatchStmt, MatchCase, NullLiteral


class PatternMatchingParser:
    """模式匹配解析方法集"""

    def parse_match_stmt(self) -> MatchStmt:
        """解析匹配语句：匹配 表达式 ..."""
        token = self.advance()  # 消费 匹配
        subject = self.parse_expression()
        self.expect(TokenType.换行, "'匹配' 后需要换行")
        self.expect(TokenType.缩进, "匹配体需要缩进")

        cases = []
        while self.current.type not in (TokenType.回退, TokenType.文件结束):
            self.skip_newlines()
            if self.current.type in (TokenType.回退, TokenType.文件结束):
                break
            cases.append(self.parse_match_case())

        self.match(TokenType.回退)
        return MatchStmt(
            subject=subject,
            cases=cases,
            line=token.line,
            column=token.column,
        )


    def parse_match_case(self) -> MatchCase:
        """解析匹配分支：情况 模式 [当 条件]: 代码块"""
        self.expect(TokenType.情况, "匹配体中需要 '情况'")
        line, col = self.current.line, self.current.column

        # 通配符 _
        is_wildcard = False
        if self.current.type == TokenType.标识符 and self.current.value == "_":
            is_wildcard = True
            self.advance()
            pattern = NullLiteral(line=line, column=col)
        else:
            # 检查是否是列表模式 [...]
            if self.current.type == TokenType.左方括号:
                pattern = self.parse_list_pattern()
            # 检查是否是字典模式 {...}
            elif self.current.type == TokenType.左花括号:
                pattern = self.parse_dict_pattern()
            else:
                pattern = self.parse_expression()

        # 守卫条件
        guard = None
        if self.match(TokenType.当):
            guard = self.parse_expression()

        # 冒号是可选的，如果有换行+缩进
        if self.current.type != TokenType.换行 and self.current.type != TokenType.缩进:
            self.expect(TokenType.冒号, "匹配分支需要 ':'")
        # 只跳换行，不跳缩进（因为缩进表示多行块）
        while self.current.type == TokenType.换行:
            self.advance()

        # 单行或多行体
        if self.current.type == TokenType.缩进:
            body = self.parse_block()
        else:
            stmt = self.parse_statement()
            body = [stmt]

        return MatchCase(
            pattern=pattern,
            guard=guard,
            body=body,
            is_wildcard=is_wildcard,
            line=line,
            column=col,
        )

    # 模块解析



