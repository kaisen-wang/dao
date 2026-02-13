"""
临时解决方案：简化选择语句解析
"""

from ..ast_nodes import SelectCase, SelectStmt
from ..errors import 语法错误
from ..tokens import TokenType


def parse_select_stmt(self) -> SelectStmt:
    """解析选择语句：选择 { 情况 接收 ch as val: ... 情况 超时(秒数): ... }"""
    token = self.advance()  # 消费 选择

    self.expect(TokenType.左花括号, "选择语句需要 '{'")

    cases = []

    # 解析所有情况语句，直到找到右花括号
    while (
        self.current.type != TokenType.右花括号
        and self.current.type != TokenType.文件结束
    ):
        self.skip_newlines()

        if self.current.type == TokenType.情况:
            self.advance()  # 消费 情况

            case_type = None
            channel = None
            variable = None
            timeout_value = None

            if self.current.type == TokenType.接收:
                # 接收情况：情况 接收 通道 as 变量
                case_type = "receive"

                self.advance()  # 消费 接收
                channel = self.parse_expression()

                # 可选的 as 子句
                if self.match(TokenType.作为):
                    var_token = self.expect(TokenType.标识符, "'as' 后需要变量名")
                    variable = var_token.value

            elif self.current.type == TokenType.超时:
                # 超时情况：情况 超时(秒数)
                case_type = "timeout"

                self.advance()  # 消费 超时
                self.expect(TokenType.左括号, "超时() 需要 '('")
                timeout_value = self.parse_expression()
                self.expect(TokenType.右括号, "超时() 需要 ')'")

            else:
                raise 语法错误(
                    f"选择分支必须是 '接收' 或 '超时'，但得到 {self.current.type.name}",
                    self.current.line,
                    self.current.column,
                    self.source,
                )

            # 解析分支体
            self.expect(TokenType.冒号, "选择分支需要 ':'")
            self.expect(TokenType.换行, "选择分支后需要换行")

            body = self.parse_block()

            # 创建 SelectCase 节点
            select_case = SelectCase(
                type=case_type,
                channel=channel,
                variable=variable,
                timeout_value=timeout_value,
                body=body,
                line=token.line,
                column=token.column,
            )
            cases.append(select_case)

        else:
            # 跳过未知内容
            self.advance()

    self.expect(TokenType.右花括号, "选择语句需要 '}'")

    return SelectStmt(
        cases=cases,
        line=token.line,
        column=token.column,
    )
