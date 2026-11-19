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
    UnaryOp,
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
        block_indent = self.expect(TokenType.缩进, "逻辑块需要缩进").value

        # 解析逻辑块内容
        while self.current.type != TokenType.文件结束:
            # 回退值是被弹出的缩进层级：规则体结束（如 8→4）也会产生回退，
            # 不能当作整个逻辑块结束。只有回到/低于逻辑块缩进层级的回退才退出。
            if self.current.type == TokenType.回退:
                level = self.current.value
                self.advance()
                if (
                    not isinstance(level, int)
                    or not isinstance(block_indent, int)
                    or level <= block_indent
                ):
                    break
                continue

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
                    body.append(self.parse_logic_rule_body_expr())
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

    def parse_logic_rule_body_expr(self):
        """解析规则体中的单个表达式，支持中缀约束 ``?x 在范围 a..b``。

        ``在范围`` 属于中缀语法：调用本方法时变量名已被解析为 ``left``，
        检测到 ``在范围`` 后把变量名传给 :meth:`parse_logic_constraint`。
        """
        left = self.parse_pipe()
        if self.current.type == TokenType.在范围:
            return self.parse_logic_constraint(left)
        return left

    def parse_logic_constraint(self, variable="") -> LogicConstraint:
        """解析约束表达式：?x 在范围 1..10

        ``variable`` 为 ``在范围`` 左侧已解析出的变量（``Identifier`` /
        ``LogicVariable`` 节点，或变量名字符串）。调用方必须先解析出变量
        再传入，因为变量名位于 ``在范围`` 关键字之前。
        """
        token = self.advance()  # 消费 在范围

        # 解析下界与上界，并校验为整数
        low = self._parse_constraint_bound("下界")
        if self.current.type != TokenType.区间:
            raise 语法错误("约束范围需要区间运算符 '..'")
        self.advance()  # 消费 ..
        high = self._parse_constraint_bound("上界")

        return LogicConstraint(
            variable=self._constraint_variable_name(variable),
            operator="在范围",
            bounds=(low, high),
            line=token.line,
            column=token.column,
        )

    def _parse_constraint_bound(self, label: str) -> int:
        """解析并校验约束边界，返回整数值。

        仅解析一元级别，避免把后续的 ``并且`` 等中缀运算符吞入边界表达式。
        """
        expr = self.parse_unary()

        sign = 1
        if isinstance(expr, UnaryOp) and expr.operator in ("-", "减"):
            sign = -1
            expr = expr.operand

        if isinstance(expr, NumberLiteral) and not isinstance(expr.value, bool):
            value = expr.value
            if isinstance(value, (int, float)) and float(value).is_integer():
                return sign * int(value)

        raise 语法错误(f"约束{label}必须是整数，得到 {type(expr).__name__}")

    @staticmethod
    def _constraint_variable_name(variable) -> str:
        """从已解析的变量表达式中提取变量名"""
        if isinstance(variable, str):
            return variable
        name = getattr(variable, "name", None)
        return name if isinstance(name, str) else ""
