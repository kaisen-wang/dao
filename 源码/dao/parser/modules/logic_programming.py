"""逻辑编程解析混入"""

from ...tokens import TokenType
from ...ast_nodes import (
    LogicBlock,
    LogicFact,
    LogicRule,
    Identifier,
    FunctionCall,
)


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
            else:
                # 跳过其他内容或换行
                if self.current.type != TokenType.换行:
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

        # 解析谓词
        predicate_expr = self.parse_expression()
        predicate = ""
        arguments = []

        if isinstance(predicate_expr, Identifier):
            predicate = predicate_expr.name
        elif isinstance(predicate_expr, CallExpr):
            if isinstance(predicate_expr.callee, Identifier):
                predicate = predicate_expr.callee.name
            arguments = predicate_expr.arguments

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

        # 解析规则头
        head = self.parse_logic_fact()

        # 检查是否有"如果"
        body = []
        if self.match(TokenType.如果):
            # 解析规则体
            while not self.current.type in (TokenType.换行, TokenType.右花括号):
                if self.current.type == TokenType.标识符:
                    body.append(self.parse_expression())
                    self.match(TokenType.并且)

        return LogicRule(
            head=head,
            body=body,
            line=token.line,
            column=token.column,
        )

