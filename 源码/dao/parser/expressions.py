"""
表达式解析混入
=============

包含所有表达式解析方法，按运算符优先级从低到高排列。
通过 Python mixin 模式，在运行时与 Parser 组合。
"""

from ..ast_nodes import (
    BinaryOp,
    BooleanLiteral,
    CompareOp,
    ConditionalExpr,
    DictLiteral,
    DictPattern,
    Expression,
    FunctionCall,
    Identifier,
    IndexAccess,
    LambdaExpr,
    ListLiteral,
    ListPattern,
    LogicQuery,
    LogicVariable,
    MemberAccess,
    NullLiteral,
    NumberLiteral,
    PipeExpr,
    ReturnStmt,
    SelfExpr,
    SetLiteral,
    SpreadExpr,
    StringLiteral,
    SuperExpr,
    TemplateLiteral,
    TupleLiteral,
    UnaryOp,
)
from ..tokens import TokenType


class ExpressionParser:
    """表达式解析方法集（混入类）"""

    # ========================
    # 表达式入口
    # ========================

    def parse_expression(self) -> Expression:
        """解析表达式（入口）"""
        return self.parse_conditional()

    # ========================
    # 优先级 0: 条件表达式
    # ========================

    def parse_conditional(self) -> Expression:
        """解析条件表达式：值 如果 条件 否则 值"""
        expr = self.parse_pipe()
        if self.current.type == TokenType.如果:
            true_value = expr
            self.advance()  # 消费 如果
            condition = self.parse_pipe()
            self.expect(TokenType.否则, "条件表达式需要 '否则'")
            false_value = self.parse_conditional()  # 右结合
            return ConditionalExpr(
                true_value=true_value,
                condition=condition,
                false_value=false_value,
                line=true_value.line,
                column=true_value.column,
            )
        return expr

    # ========================
    # 优先级 1: 管道
    # ========================

    def parse_pipe(self) -> Expression:
        """解析管道表达式：甲 |> 乙"""
        left = self.parse_or()
        while self.match(TokenType.管道):
            right = self.parse_or()
            left = PipeExpr(left=left, right=right, line=left.line, column=left.column)
        return left

    # ========================
    # 优先级 2-4: 逻辑运算
    # ========================

    def parse_or(self) -> Expression:
        """解析 或者 表达式"""
        left = self.parse_and()
        while self.match(TokenType.或者):
            right = self.parse_and()
            left = BinaryOp(
                left=left,
                operator="或者",
                right=right,
                line=left.line,
                column=left.column,
            )
        return left

    def parse_and(self) -> Expression:
        """解析 并且 表达式"""
        left = self.parse_not()
        while self.match(TokenType.并且):
            right = self.parse_not()
            left = BinaryOp(
                left=left,
                operator="并且",
                right=right,
                line=left.line,
                column=left.column,
            )
        return left

    def parse_not(self) -> Expression:
        """解析 不是/! 表达式"""
        if self.match(TokenType.不是):
            operand = self.parse_not()
            return UnaryOp(
                operator="不是",
                operand=operand,
                line=operand.line,
                column=operand.column,
            )
        if self.current.type == TokenType.感叹号:
            # ! 作为逻辑非：检查后面是否紧跟标识符（宏调用）
            # 如果 ! 后面紧跟标识符，则是宏调用；否则是逻辑非
            if self.peek().type != TokenType.标识符:
                self.advance()  # 消费 !
                operand = self.parse_not()
                return UnaryOp(
                    operator="不是",
                    operand=operand,
                    line=operand.line,
                    column=operand.column,
                )
        return self.parse_comparison()

    # ========================
    # 优先级 5: 比较
    # ========================

    def parse_comparison(self) -> Expression:
        """解析比较表达式（含 在/不在 成员运算符）"""
        left = self.parse_addition()

        compare_ops = {
            TokenType.等于,
            TokenType.不等于,
            TokenType.大于,
            TokenType.小于,
            TokenType.大于等于,
            TokenType.小于等于,
            TokenType.在,
            TokenType.不在,
        }

        if self.current.type in compare_ops:
            operands = [left]
            operators = []
            while self.current.type in compare_ops:
                op = self.advance()
                right = self.parse_addition()
                operators.append(op.value)
                operands.append(right)

            if len(operators) == 1:
                return BinaryOp(
                    left=operands[0],
                    operator=operators[0],
                    right=operands[1],
                    line=left.line,
                    column=left.column,
                )
            else:
                return CompareOp(
                    operands=operands,
                    operators=operators,
                    line=left.line,
                    column=left.column,
                )

        return left

    # ========================
    # 优先级 6-8: 算术运算
    # ========================

    def parse_addition(self) -> Expression:
        """解析加减法"""
        left = self.parse_multiplication()
        while self.current.type in (TokenType.加, TokenType.减):
            op = self.advance()
            right = self.parse_multiplication()
            left = BinaryOp(
                left=left,
                operator=op.value,
                right=right,
                line=left.line,
                column=left.column,
            )
        return left

    def parse_multiplication(self) -> Expression:
        """解析乘除取余整除"""
        left = self.parse_power()
        while self.current.type in (TokenType.乘, TokenType.除, TokenType.取余, TokenType.整除):
            op = self.advance()
            right = self.parse_power()
            left = BinaryOp(
                left=left,
                operator=op.value,
                right=right,
                line=left.line,
                column=left.column,
            )
        return left

    def parse_power(self) -> Expression:
        """解析幂运算（右结合）"""
        base = self.parse_unary()
        if self.match(TokenType.幂):
            exponent = self.parse_power()  # 右结合：递归调用自身
            return BinaryOp(
                left=base,
                operator="**",
                right=exponent,
                line=base.line,
                column=base.column,
            )
        return base

    # ========================
    # 优先级 9: 一元运算
    # ========================

    def parse_unary(self) -> Expression:
        """解析一元运算符"""
        if self.current.type == TokenType.减:
            op = self.advance()
            operand = self.parse_unary()
            return UnaryOp(
                operator="-", operand=operand, line=op.line, column=op.column
            )
        return self.parse_call()

    # ========================
    # 优先级 10: 调用/成员/索引
    # ========================

    def parse_call(self) -> Expression:
        """解析函数调用和成员/索引访问"""
        expr = self.parse_primary()

        # 如果是逻辑变量，直接返回，不解析成函数调用
        if (
            isinstance(expr, Identifier)
            and expr.name.startswith("?")
            or isinstance(expr, LogicVariable)
        ):
            return expr

        while True:
            if self.match(TokenType.左括号):
                # 如果 expr 是逻辑变量，返回 expr，不解析函数调用
                if isinstance(expr, Identifier) and expr.name.startswith("?"):
                    return expr

                # 函数调用
                args = []
                kwargs = {}
                while self.current.type != TokenType.右括号:
                    # 检查命名参数
                    if (
                        self.current.type == TokenType.标识符
                        and self.peek().type == TokenType.赋值
                    ):
                        name = self.advance().value
                        self.advance()  # 消费 =
                        value = self.parse_expression()
                        kwargs[name] = value
                    else:
                        args.append(self.parse_expression())
                    if not self.match(TokenType.逗号):
                        break
                self.expect(TokenType.右括号, "函数调用需要 ')'")
                expr = FunctionCall(
                    callee=expr,
                    arguments=args,
                    keyword_args=kwargs,
                    line=expr.line,
                    column=expr.column,
                )
            elif self.match(TokenType.点):
                # 成员访问（接受标识符和部分关键字作为成员名）
                member_name = self._expect_member_name()
                expr = MemberAccess(
                    object=expr,
                    member=member_name,
                    line=expr.line,
                    column=expr.column,
                )
            elif self.match(TokenType.左方括号):
                index = self.parse_expression()
                self.expect(TokenType.右方括号, "索引访问需要 ']'")
                expr = IndexAccess(
                    object=expr,
                    index=index,
                    line=expr.line,
                    column=expr.column,
                )
            else:
                break

        return expr

    def _expect_member_name(self) -> str:
        """期望一个成员名（标识符或允许作为成员名的关键字）"""
        # 允许某些关键字作为成员名（如 父对象.初始化()）
        MEMBER_KEYWORDS = {
            TokenType.初始化,
            TokenType.类型,
            TokenType.查询,
            TokenType.标识符,
        }
        if self.current.type in MEMBER_KEYWORDS:
            return self.advance().value
        raise self._error(f"成员访问需要属性名，但得到 '{self.current.value}'")

    # ========================
    # 优先级 11: 基本表达式
    # ========================

    def parse_primary(self) -> Expression:
        """解析基本表达式（最高优先级）"""
        token = self.current

        # 宏系统相关表达式
        if token.type == TokenType.感叹号 and self.peek().type == TokenType.标识符:
            return self.parse_macro_call()
        if token.type == TokenType.引述 or token.type == TokenType.引用:
            return self.parse_quote_block()
        if token.type == TokenType.注入:
            return self.parse_unquote_expr()
        if token.type == TokenType.美元注入:
            from ..ast_nodes import UnquoteExpr

            self.advance()
            return UnquoteExpr(
                expression=Identifier(
                    line=token.line, column=token.column, name=token.value
                ),
                line=token.line,
                column=token.column,
            )

        # 检查是否是字典字面量（如 { "a": 1 } 或 { a: 1 }）或集合字面量（如 {1, 2, 3}）
        if token.type == TokenType.左花括号:
            # 检查下一个token是否是标识符、字符串或数字，且后面紧跟冒号 → 字典
            if (
                self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type
                in (TokenType.标识符, TokenType.文本, TokenType.数值)
                and self.pos + 2 < len(self.tokens)
                and self.tokens[self.pos + 2].type == TokenType.冒号
            ):
                return self.parse_dict_literal()

            # 检查是否是集合字面量：{expr, expr, ...}（无冒号）
            if (
                self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type != TokenType.右花括号
            ):
                # 尝试解析为集合字面量
                return self.parse_set_or_block_literal()

            # 空花括号 {} → 空字典
            self.advance()  # 消费左花括号
            if self.current.type == TokenType.右花括号:
                self.advance()  # 消费右花括号
                return DictLiteral(pairs=[], line=token.line, column=token.column)

            # 否则，解析为块表达式（如 { 语句 }）
            # 找到匹配的右花括号
            depth = 1
            block_end = self.pos
            while block_end < len(self.tokens):
                if self.tokens[block_end].type == TokenType.左花括号:
                    depth += 1
                elif self.tokens[block_end].type == TokenType.右花括号:
                    depth -= 1
                    if depth == 0:
                        break
                block_end += 1

            if block_end < len(self.tokens):
                from ..ast_nodes import BlockExpr

                block_body = []

                while self.pos < block_end:
                    stmt = self.parse_statement()
                    if stmt:
                        block_body.append(stmt)

                self.pos = block_end + 1  # 消费右花括号

                return BlockExpr(body=block_body)

        # 并发编程相关表达式
        if token.type == TokenType.等待:
            return self.parse_await_expr()
        if token.type == TokenType.全部:
            return self.parse_await_all_expr()
        if token.type == TokenType.竞速:
            return self.parse_await_race_expr()
        if token.type == TokenType.通道:
            # 只有后面跟着左括号时才是通道表达式
            if self.peek().type == TokenType.左括号:
                return self.parse_channel_expr()
            else:
                # 否则，'通道' 应该被视为标识符
                self.advance()
                return Identifier(name="通道", line=token.line, column=token.column)
        if token.type == TokenType.接收:
            # 只有后面直接跟通道表达式且不是左括号时才是接收表达式
            # 如果是左括号，说明是函数调用：接收(...)
            if (
                self.peek().type in (TokenType.标识符, TokenType.通道)
                and self.peek(2).type != TokenType.左括号
            ):
                return self.parse_receive_expr()
            else:
                # 否则，'接收' 应该被视为标识符
                self.advance()
                return Identifier(name="接收", line=token.line, column=token.column)
        if token.type == TokenType.发送:
            # '发送' 作为函数名时应被视为标识符
            self.advance()
            return Identifier(name="发送", line=token.line, column=token.column)

        # 数值字面量
        if token.type == TokenType.数值:
            self.advance()
            return NumberLiteral(
                value=token.value, line=token.line, column=token.column
            )

        # 字符串字面量
        if token.type == TokenType.文本:
            self.advance()
            return StringLiteral(
                value=token.value, line=token.line, column=token.column
            )

        # 模板字符串
        if token.type == TokenType.模板文本:
            return self.parse_template_literal()

        # 布尔字面量
        if token.type == TokenType.真:
            self.advance()
            return BooleanLiteral(value=True, line=token.line, column=token.column)
        if token.type == TokenType.假:
            self.advance()
            return BooleanLiteral(value=False, line=token.line, column=token.column)

        # 空值
        if token.type == TokenType.空:
            self.advance()
            return NullLiteral(line=token.line, column=token.column)

        # 标识符 (包括逻辑变量)
        if token.type == TokenType.标识符:
            self.advance()
            if token.value.startswith("?"):
                from ..ast_nodes import LogicVariable, UnquoteExpr

                if token.value.startswith("$"):
                    return UnquoteExpr(
                        expression=Identifier(
                            line=token.line, column=token.column, name=token.value[1:]
                        ),
                        line=token.line,
                        column=token.column,
                    )

                return LogicVariable(
                    name=token.value, line=token.line, column=token.column
                )
            if token.value.startswith("$"):
                from ..ast_nodes import UnquoteExpr

                return UnquoteExpr(
                    expression=Identifier(
                        line=token.line, column=token.column, name=token.value[1:]
                    ),
                    line=token.line,
                    column=token.column,
                )

            return Identifier(name=token.value, line=token.line, column=token.column)

        # 本对象 (this/self)
        if token.type == TokenType.本对象:
            self.advance()
            return SelfExpr(line=token.line, column=token.column)

        # 父对象 (super)
        if token.type == TokenType.父对象:
            self.advance()
            return SuperExpr(line=token.line, column=token.column)

        # 允许类型关键字作为标识符
        if token.type == TokenType.类型:
            self.advance()
            return Identifier(name="类型", line=token.line, column=token.column)

        # 匿名函数：函数(x) => x * 2
        if token.type == TokenType.函数:
            return self.parse_lambda()

        # 括号表达式 或 元组字面量
        if token.type == TokenType.左括号:
            self.advance()
            # 空括号 → 空元组
            if self.current.type == TokenType.右括号:
                self.advance()
                return TupleLiteral(elements=[], line=token.line, column=token.column)
            # 如果下一个 token 是标识符且是逻辑变量，直接返回该变量，不解析括号表达式
            if self.current.type == TokenType.标识符 and self.current.value.startswith(
                "?"
            ):
                expr = self.parse_primary()
                self.expect(TokenType.右括号, "括号表达式需要 ')'")
                return expr
            # 解析括号内的表达式
            first = self.parse_expression()
            # 如果后面有逗号，则是元组
            if self.current.type == TokenType.逗号:
                elements = [first]
                while self.match(TokenType.逗号):
                    if self.current.type == TokenType.右括号:
                        break
                    elements.append(self.parse_expression())
                self.expect(TokenType.右括号, "元组需要 ')'")
                return TupleLiteral(
                    elements=elements, line=token.line, column=token.column
                )
            # 单元素带尾逗号 → 单元素元组
            # 已在上方逗号分支处理
            # 普通括号表达式
            self.expect(TokenType.右括号, "括号表达式需要 ')'")
            return first

        # 列表字面量 [...]
        if token.type == TokenType.左方括号:
            return self.parse_list_literal()

        # 查询表达式
        if token.type == TokenType.查询:
            return self.parse_logic_query()

        # 字典字面量 {...}
        if token.type == TokenType.左花括号:
            # 只有当后面紧跟标识符和冒号时才解析为字典字面量
            if (
                self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].type == TokenType.标识符
                and self.pos + 2 < len(self.tokens)
                and self.tokens[self.pos + 2].type == TokenType.冒号
            ):
                return self.parse_dict_literal()

        raise self._error(f"无法解析的表达式: '{token.value}' ({token.type.name})")

    # ========================
    # 模板字符串
    # ========================

    def parse_logic_query(self) -> LogicQuery:
        """解析查询表达式：查询(知识库, 目标)"""
        token = self.advance()  # 消费 查询

        # 期望左括号
        self.expect(TokenType.左括号, "查询表达式需要左括号")

        # 解析知识库
        knowledge_base = self.parse_expression()

        # 期望逗号
        self.expect(TokenType.逗号, "查询表达式需要逗号")

        # 解析查询目标
        goal = self.parse_expression()

        # 期望右括号
        self.expect(TokenType.右括号, "查询表达式需要右括号")

        return LogicQuery(
            knowledge_base=knowledge_base,
            goal=goal,
            line=token.line,
            column=token.column,
        )

    def parse_template_literal(self) -> TemplateLiteral:
        """解析模板字符串：`你好 {名字}，{年龄}岁`"""
        token = self.advance()  # 消费 模板文本 Token
        data = token.value  # {'parts': [...], 'exprs': [...]}
        parts = data["parts"]
        expr_strings = data["exprs"]

        # 将每个表达式源码字符串解析为 AST 表达式
        # 延迟导入，避免循环引用
        from ..lexer import Lexer
        from .core import Parser

        expressions = []
        for expr_src in expr_strings:
            expr_lexer = Lexer(expr_src, "<模板表达式>")
            expr_tokens = expr_lexer.tokenize()
            expr_parser = Parser(expr_tokens)
            expr_node = expr_parser.parse_expression()
            expressions.append(expr_node)

        return TemplateLiteral(
            parts=parts,
            expressions=expressions,
            line=token.line,
            column=token.column,
        )

    # ========================
    # 匿名函数
    # ========================

    def parse_lambda(self) -> LambdaExpr:
        """解析匿名函数
        
        支持三种语法：
        1. 无参数：函数 => 表达式
        2. 有参数：函数(参数) => 表达式
        3. 代码块：函数(参数) => 缩进块
        """
        token = self.advance()  # 消费 函数
        
        params = []
        
        # 检查是否有参数列表
        if self.current.type == TokenType.左括号:
            # 有参数列表：函数(参数) => 表达式
            self.advance()  # 消费 (
            
            while self.current.type != TokenType.右括号:
                param = self.expect(TokenType.标识符, "期望参数名")
                params.append(param.value)
                if not self.match(TokenType.逗号):
                    break
            
            self.expect(TokenType.右括号, "匿名函数需要 ')'")
        
        # 无论是无参数还是有参数，都需要箭头
        self.expect(TokenType.箭头, "匿名函数需要 '=>'")

        if self.current.type == TokenType.换行:
            while self.current.type == TokenType.换行:
                self.advance()
            body = self.parse_block()
        else:
            body = self.parse_expression()

        return LambdaExpr(
            params=params,
            body=body,
            line=token.line,
            column=token.column,
        )

    # ========================
    # 集合字面量
    # ========================

    def parse_list_literal(self) -> ListLiteral:
        """解析列表字面量，支持展开运算符：[...列表, 新元素]"""
        token = self.advance()  # 消费 [
        elements = []

        while self.current.type != TokenType.右方括号:
            if self.current.type == TokenType.展开:
                self.advance()  # 消费 ...
                elements.append(SpreadExpr(expression=self.parse_expression()))
            else:
                elements.append(self.parse_expression())
            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右方括号, "列表需要 ']'")
        return ListLiteral(elements=elements, line=token.line, column=token.column)

    def parse_dict_literal(self) -> DictLiteral:
        """解析字典字面量，支持展开运算符：{...字典, "新键": 值}"""
        token = self.advance()  # 消费 {
        pairs = []

        while self.current.type != TokenType.右花括号:
            if self.current.type == TokenType.展开:
                self.advance()  # 消费 ...
                spread = SpreadExpr(expression=self.parse_expression())
                pairs.append((spread, None))
            else:
                key = self.parse_expression()
                self.expect(TokenType.冒号, "字典需要 ':'")
                value = self.parse_expression()
                pairs.append((key, value))
            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右花括号, "字典需要 '}'")
        return DictLiteral(pairs=pairs, line=token.line, column=token.column)

    def parse_set_or_block_literal(self) -> Expression:
        """解析集合字面量或块表达式：{1, 2, 3} 或 {语句}，支持字典展开"""
        token = self.advance()  # 消费 {

        if self.current.type == TokenType.展开:
            self.advance()  # 消费 ...
            spread = SpreadExpr(expression=self.parse_expression())
            pairs = [(spread, None)]
            while self.match(TokenType.逗号):
                if self.current.type == TokenType.右花括号:
                    break
                if self.current.type == TokenType.展开:
                    self.advance()
                    spread = SpreadExpr(expression=self.parse_expression())
                    pairs.append((spread, None))
                else:
                    key = self.parse_expression()
                    self.expect(TokenType.冒号, "字典需要 ':'")
                    value = self.parse_expression()
                    pairs.append((key, value))
            self.expect(TokenType.右花括号, "字典需要 '}'")
            return DictLiteral(pairs=pairs, line=token.line, column=token.column)

        first = self.parse_expression()

        # 如果第一个表达式后紧跟冒号，说明是字典（key: value 的 key 是表达式）
        if self.current.type == TokenType.冒号:
            pairs = []
            key = first
            self.advance()  # 消费冒号
            value = self.parse_expression()
            pairs.append((key, value))
            while self.match(TokenType.逗号):
                if self.current.type == TokenType.右花括号:
                    break
                if self.current.type == TokenType.展开:
                    self.advance()
                    spread = SpreadExpr(expression=self.parse_expression())
                    pairs.append((spread, None))
                else:
                    key = self.parse_expression()
                    self.expect(TokenType.冒号, "字典需要 ':'")
                    value = self.parse_expression()
                    pairs.append((key, value))
            self.expect(TokenType.右花括号, "字典需要 '}'")
            return DictLiteral(pairs=pairs, line=token.line, column=token.column)

        # 如果有逗号，则是集合字面量
        if self.current.type == TokenType.逗号:
            elements = [first]
            while self.match(TokenType.逗号):
                if self.current.type == TokenType.右花括号:
                    break
                elements.append(self.parse_expression())
            self.expect(TokenType.右花括号, "集合需要 '}'")
            return SetLiteral(elements=elements, line=token.line, column=token.column)

        # 单个表达式且无逗号 → 可能是集合（单元素）或块表达式
        # 这里将其解析为集合字面量（单元素集合）
        self.expect(TokenType.右花括号, "需要 '}'")
        return SetLiteral(elements=[first], line=token.line, column=token.column)

    # ========================
    # 模式解析
    # ========================

    def parse_list_pattern(self) -> ListPattern:
        """解析列表模式：[x, y, ...rest]"""
        token = self.advance()  # 消费 [
        elements = []
        has_spread = False
        spread_var = None

        while self.current.type != TokenType.右方括号:
            if self.match(TokenType.展开):
                has_spread = True
                spread_var = self.expect(TokenType.标识符, "展开操作符后需要变量名")
                elements.append(
                    Identifier(
                        name=spread_var.value,
                        line=spread_var.line,
                        column=spread_var.column,
                    )
                )
            else:
                elements.append(self.parse_expression())
            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右方括号, "列表模式需要 ']'")
        return ListPattern(
            elements=elements,
            has_spread=has_spread,
            line=token.line,
            column=token.column,
        )

    def parse_dict_pattern(self) -> DictPattern:
        """解析字典模式：{键: 变量}"""
        token = self.advance()  # 消费 {
        pairs = []

        while self.current.type != TokenType.右花括号:
            key = self.parse_expression()
            self.expect(TokenType.冒号, "字典模式需要 ':'")
            value = self.parse_expression()
            pairs.append((key, value))
            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右花括号, "字典模式需要 '}'")
        return DictPattern(pairs=pairs, line=token.line, column=token.column)
