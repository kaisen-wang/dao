"""逻辑编程解析混入"""

from ...ast_nodes import (
    BooleanLiteral,
    FunctionCall,
    Identifier,
    LogicBlock,
    LogicConstraint,
    LogicCut,
    LogicFact,
    LogicNegation,
    LogicRule,
    NumberLiteral,
    StringLiteral,
)
from ...errors import 语法错误
from ...tokens import TokenType


class LogicProgrammingParser:
    """逻辑编程解析方法集"""

    def parse_logic_block(self) -> LogicBlock:
        """解析逻辑代码块：逻辑 名称（缩进块）"""
        token = self.advance()  # 消费 逻辑

        name_token = self.expect(TokenType.标识符, "逻辑块需要一个名称")
        name = name_token.value

        facts = []
        rules = []

        # 匹配换行或缩进
        if self.current.type == TokenType.换行:
            self.advance()
        self.expect(TokenType.缩进, "逻辑块需要缩进")

        # 解析逻辑块内容
        while not self.match(TokenType.回退):
            if self.current.type == TokenType.事实:
                fact = self.parse_logic_fact()
                facts.append(fact)
            elif self.current.type == TokenType.规则:
                rule = self.parse_logic_rule()
                rules.append(rule)
            elif self.current.type == TokenType.换行:
                self.advance()
            else:
                # 跳过其他内容
                self.advance()

        return LogicBlock(
            name=name,
            facts=facts,
            rules=rules,
            line=token.line,
            column=token.column,
        )

    def parse_logic_fact(self) -> LogicFact:
        """解析事实声明：事实: 父母("张三", "小明")"""
        token = self.advance()  # 消费 事实

        # 消费冒号
        self.match(TokenType.冒号)

        # 解析整个事实表达式（使用 parse_pipe 避免 如果 被当作条件表达式）
        fact_expr = self.parse_pipe()
        predicate = ""
        arguments = []

        if isinstance(fact_expr, Identifier):
            predicate = fact_expr.name
        elif isinstance(fact_expr, FunctionCall):
            if isinstance(fact_expr.callee, Identifier):
                # 确保谓词不是逻辑变量
                if fact_expr.callee.name.startswith("?"):
                    raise 语法错误(f"谓词不能是逻辑变量 '{fact_expr.callee.name}'")
                predicate = fact_expr.callee.name
            arguments = fact_expr.arguments
            # 检查参数是否有效
            for arg in arguments:
                if isinstance(arg, Identifier) and arg.name.startswith("?"):
                    continue  # 逻辑变量是有效的参数
                elif isinstance(arg, (StringLiteral, NumberLiteral, BooleanLiteral)):
                    continue  # 字面量是有效的参数
                else:
                    raise 语法错误(f"无效的参数类型: {type(arg).__name__}")

        return LogicFact(
            predicate=predicate,
            arguments=arguments,
            line=token.line,
            column=token.column,
        )

    def parse_logic_rule(self) -> LogicRule:
        """解析规则声明：规则: 祖父母(?祖, ?孙) 如果 父母(?祖, ?父) 并且 父母(?父, ?孙)"""
        token = self.advance()  # 消费 规则

        # 消费冒号
        self.match(TokenType.冒号)

        # 解析规则头（使用 parse_pipe 避免 如果 被当作条件表达式）
        head = self.parse_pipe()
        if not isinstance(head, FunctionCall):
            raise 语法错误("规则头必须是函数调用")

        # 解析规则体
        body = []
        if self.match(TokenType.如果):
            self.skip_newlines()
            self.match(TokenType.缩进)
            # 解析规则体
            while self.current.type not in (TokenType.回退, TokenType.文件结束):
                if self.current.type == TokenType.非:
                    body.append(self.parse_logic_negation())
                    if self.current.type == TokenType.并且:
                        self.advance()
                elif self.current.type == TokenType.剪枝:
                    body.append(self.parse_logic_cut())
                    if self.current.type == TokenType.并且:
                        self.advance()
                elif self.current.type == TokenType.标识符:
                    body.append(self.parse_pipe())
                    if self.current.type == TokenType.并且:
                        self.advance()
                elif self.current.type == TokenType.换行:
                    self.advance()
                elif self.current.type == TokenType.缩进:
                    self.advance()
                else:
                    break

        return LogicRule(
            head=LogicFact(
                predicate=head.callee.name,
                arguments=head.arguments,
                line=token.line,
                column=token.column,
            ),
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_logic_negation(self) -> LogicNegation:
        """解析逻辑否定：非 已封禁(?用户)"""
        token = self.advance()  # 消费 非
        negated_expr = self.parse_pipe()
        return LogicNegation(
            expression=negated_expr,
            line=token.line,
            column=token.column,
        )

    def parse_logic_cut(self) -> LogicCut:
        """解析剪枝操作符：剪枝"""
        token = self.advance()  # 消费 剪枝
        return LogicCut(line=token.line, column=token.column)

    def parse_logic_constraint(self) -> LogicConstraint:
        """解析约束表达式：?x 在范围 1..10"""
        token = self.advance()  # 消费 在范围

        # 解析下界
        low = self.parse_expression()

        # 期望区间运算符 ..
        if self.current.type != TokenType.区间:
            raise 语法错误("约束范围需要区间运算符 '..'")
        self.advance()  # 消费 ..

        # 解析上界
        high = self.parse_expression()

        # 获取变量名（从之前的上下文推断）
        # 这个方法由 parse_primary 中的 在范围 分支调用
        # 变量名在调用前已经确定
        return LogicConstraint(
            variable="",
            operator="在范围",
            bounds=(0, 0),
            line=token.line,
            column=token.column,
        )
