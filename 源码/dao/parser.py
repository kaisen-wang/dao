"""
语法分析器 (Parser)
==================

将Token流转换为抽象语法树（AST）。

采用递归下降（Recursive Descent）解析策略：
- 每个语法规则对应一个解析方法
- 自顶向下解析，从 program() 开始
- 运算符优先级通过方法调用层级实现

优先级（从低到高）：
1. 管道 (|>)
2. 或者
3. 并且
4. 不是
5. 比较 (==, !=, <, >, <=, >=, 在, 不在)
6. 加减 (+, -)
7. 乘除余 (*, /, %, //)
8. 幂 (**)
9. 一元 (-, 不是)
10. 调用/成员访问 (f(), obj.x, list[0])
11. 基本 (字面量, 标识符, 括号表达式)
"""

from .tokens import Token, TokenType
from .ast_nodes import *
from .errors import 语法错误


class Parser:
    """
    语法分析器

    使用方法：
        parser = Parser(token_list)
        ast = parser.parse()
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    @property
    def current(self) -> Token:
        """获取当前Token"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def peek(self, offset: int = 1) -> Token:
        """向前查看"""
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.tokens[-1]

    def advance(self) -> Token:
        """消费当前Token并返回"""
        token = self.current
        self.pos += 1
        return token

    def expect(self, token_type: TokenType, message: str = "") -> Token:
        """期望当前Token为指定类型，否则报错"""
        if self.current.type != token_type:
            msg = message or f"期望 {token_type.name}，但得到 {self.current.type.name} ('{self.current.value}')"
            raise 语法错误(msg, self.current.line, self.current.column)
        return self.advance()

    def match(self, *types: TokenType) -> Token | None:
        """如果当前Token是指定类型之一，消费并返回；否则返回None"""
        if self.current.type in types:
            return self.advance()
        return None

    def skip_newlines(self):
        """跳过所有换行Token"""
        while self.current.type == TokenType.换行:
            self.advance()

    def _error(self, message: str) -> 语法错误:
        return 语法错误(message, self.current.line, self.current.column)

    # ========================
    # 顶层解析
    # ========================

    def parse(self) -> Program:
        """解析整个程序"""
        program = Program(statements=[])
        self.skip_newlines()

        while self.current.type != TokenType.文件结束:
            stmt = self.parse_statement()
            if stmt:
                program.statements.append(stmt)
            self.skip_newlines()

        return program

    # ========================
    # 语句解析
    # ========================

    def parse_statement(self) -> Statement:
        """解析一条语句"""
        token = self.current

        match token.type:
            case TokenType.定义:
                return self.parse_variable_decl(is_constant=False)
            case TokenType.常量:
                return self.parse_variable_decl(is_constant=True)
            case TokenType.函数:
                return self.parse_function_decl()
            case TokenType.返回:
                return self.parse_return_stmt()
            case TokenType.如果:
                return self.parse_if_stmt()
            case TokenType.当:
                return self.parse_while_stmt()
            case TokenType.遍历:
                return self.parse_for_stmt()
            case TokenType.跳出:
                return self.parse_break_stmt()
            case TokenType.继续:
                return self.parse_continue_stmt()
            case TokenType.尝试:
                return self.parse_try_stmt()
            case TokenType.抛出:
                return self.parse_throw_stmt()
            case TokenType.断言:
                return self.parse_assert_stmt()
            case TokenType.类型:
                return self.parse_class_decl()
            case TokenType.匹配:
                return self.parse_match_stmt()
            case TokenType.导入:
                return self.parse_import_stmt()
            case _:
                return self.parse_expression_or_assignment()

    def parse_variable_decl(self, is_constant: bool) -> VariableDecl:
        """解析变量/常量声明：定义 x = 值"""
        token = self.advance()  # 消费 定义/常量
        name_token = self.expect(TokenType.标识符, "变量声明需要一个变量名")
        self.expect(TokenType.赋值, "变量声明需要 '=' 赋值")
        value = self.parse_expression()
        self.expect(TokenType.换行, "语句末尾需要换行")
        return VariableDecl(
            name=name_token.value,
            value=value,
            is_constant=is_constant,
            line=token.line,
            column=token.column,
        )

    def parse_function_decl(self) -> FunctionDecl:
        """解析函数声明：函数 名字(参数) ..."""
        token = self.advance()  # 消费 函数

        # 在类体外部：函数 名字(参数)
        name_token = self.expect(TokenType.标识符, "函数声明需要函数名")
        self.expect(TokenType.左括号, "函数声明需要 '('")

        params, default_values = self._parse_param_list()

        self.expect(TokenType.右括号, "函数声明需要 ')'")
        self.expect(TokenType.换行, "函数头部后需要换行")
        body = self.parse_block()

        return FunctionDecl(
            name=name_token.value,
            params=params,
            default_values=default_values,
            body=body,
            line=token.line,
            column=token.column,
        )

    def _parse_param_list(self) -> tuple[list[str], dict]:
        """解析参数列表"""
        params = []
        default_values = {}
        while self.current.type != TokenType.右括号:
            param = self.expect(TokenType.标识符, "期望参数名")
            params.append(param.value)
            # 检查默认值
            if self.match(TokenType.赋值):
                default_values[param.value] = self.parse_expression()
            if not self.match(TokenType.逗号):
                break
        return params, default_values

    def parse_return_stmt(self) -> ReturnStmt:
        """解析返回语句"""
        token = self.advance()  # 消费 返回
        value = None
        if self.current.type != TokenType.换行 and self.current.type != TokenType.文件结束:
            value = self.parse_expression()
        self.match(TokenType.换行)
        return ReturnStmt(value=value, line=token.line, column=token.column)

    def parse_if_stmt(self) -> IfStmt:
        """解析条件语句"""
        token = self.advance()  # 消费 如果
        condition = self.parse_expression()
        self.expect(TokenType.换行, "条件后需要换行")
        body = self.parse_block()

        elif_clauses = []
        else_body = []

        self.skip_newlines()
        while self.match(TokenType.否则如果):
            elif_cond = self.parse_expression()
            self.expect(TokenType.换行, "条件后需要换行")
            elif_body = self.parse_block()
            elif_clauses.append((elif_cond, elif_body))
            self.skip_newlines()

        if self.match(TokenType.否则):
            self.expect(TokenType.换行, "'否则' 后需要换行")
            else_body = self.parse_block()

        return IfStmt(
            condition=condition,
            body=body,
            elif_clauses=elif_clauses,
            else_body=else_body,
            line=token.line,
            column=token.column,
        )

    def parse_while_stmt(self) -> WhileStmt:
        """解析当循环"""
        token = self.advance()  # 消费 当
        condition = self.parse_expression()
        self.expect(TokenType.换行, "条件后需要换行")
        body = self.parse_block()
        return WhileStmt(
            condition=condition,
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_for_stmt(self) -> ForInStmt | ForRangeStmt:
        """解析遍历循环（遍历...在... 或 遍历...从...到...）"""
        token = self.advance()  # 消费 遍历
        var_token = self.expect(TokenType.标识符, "遍历需要一个循环变量名")

        if self.match(TokenType.在):
            # 遍历 x 在 集合
            iterable = self.parse_expression()
            self.expect(TokenType.换行, "遍历语句后需要换行")
            body = self.parse_block()
            return ForInStmt(
                variable=var_token.value,
                iterable=iterable,
                body=body,
                line=token.line,
                column=token.column,
            )
        elif self.match(TokenType.从):
            # 遍历 i 从 1 到 10 [步长 2]
            start = self.parse_expression()
            self.expect(TokenType.到, "范围循环需要 '到'")
            end = self.parse_expression()
            step = None
            if self.match(TokenType.步长):
                step = self.parse_expression()
            self.expect(TokenType.换行, "遍历语句后需要换行")
            body = self.parse_block()
            return ForRangeStmt(
                variable=var_token.value,
                start=start,
                end=end,
                step=step,
                body=body,
                line=token.line,
                column=token.column,
            )
        else:
            raise self._error("遍历后需要 '在' 或 '从'")

    def parse_break_stmt(self) -> BreakStmt:
        token = self.advance()
        self.match(TokenType.换行)
        return BreakStmt(line=token.line, column=token.column)

    def parse_continue_stmt(self) -> ContinueStmt:
        token = self.advance()
        self.match(TokenType.换行)
        return ContinueStmt(line=token.line, column=token.column)

    def parse_try_stmt(self) -> TryStmt:
        """解析尝试-捕获-最终"""
        token = self.advance()  # 消费 尝试
        self.expect(TokenType.换行, "'尝试' 后需要换行")
        try_body = self.parse_block()

        catch_var = None
        catch_body = []
        finally_body = []

        self.skip_newlines()
        if self.match(TokenType.捕获):
            if self.current.type == TokenType.标识符:
                catch_var = self.advance().value
            self.expect(TokenType.换行, "'捕获' 后需要换行")
            catch_body = self.parse_block()

        self.skip_newlines()
        if self.match(TokenType.最终):
            self.expect(TokenType.换行, "'最终' 后需要换行")
            finally_body = self.parse_block()

        return TryStmt(
            try_body=try_body,
            catch_var=catch_var,
            catch_body=catch_body,
            finally_body=finally_body,
            line=token.line,
            column=token.column,
        )

    def parse_throw_stmt(self) -> ThrowStmt:
        token = self.advance()  # 消费 抛出
        expr = self.parse_expression()
        self.match(TokenType.换行)
        return ThrowStmt(expression=expr, line=token.line, column=token.column)

    def parse_assert_stmt(self) -> AssertStmt:
        token = self.advance()  # 消费 断言
        condition = self.parse_expression()
        message = None
        if self.match(TokenType.逗号):
            message = self.parse_expression()
        self.match(TokenType.换行)
        return AssertStmt(
            condition=condition,
            message=message,
            line=token.line,
            column=token.column,
        )

    # ========================
    # OOP 解析
    # ========================

    def parse_class_decl(self) -> ClassDecl:
        """解析类型声明：类型 名字 [继承自 父类] ..."""
        token = self.advance()  # 消费 类型
        name_token = self.expect(TokenType.标识符, "类型声明需要一个类名")

        parent_name = None
        if self.match(TokenType.继承自):
            parent_token = self.expect(TokenType.标识符, "'继承自' 后需要父类名")
            parent_name = parent_token.value

        self.expect(TokenType.换行, "类型声明后需要换行")
        body = self.parse_class_body()

        return ClassDecl(
            name=name_token.value,
            parent_name=parent_name,
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_class_body(self) -> list[Statement]:
        """解析类体（缩进块，包含构造函数和方法）"""
        self.expect(TokenType.缩进, "类型体需要缩进")
        statements = []

        while self.current.type not in (TokenType.回退, TokenType.文件结束):
            self.skip_newlines()
            if self.current.type in (TokenType.回退, TokenType.文件结束):
                break

            if self.current.type == TokenType.初始化:
                # 构造函数：初始化(参数) ...
                statements.append(self.parse_constructor())
            elif self.current.type == TokenType.函数:
                # 方法：函数 名字(参数) ...
                statements.append(self.parse_function_decl())
            else:
                # 其他语句（如类级别的属性声明）
                statements.append(self.parse_statement())

        self.match(TokenType.回退)
        return statements

    def parse_constructor(self) -> FunctionDecl:
        """解析构造函数：初始化(参数) ..."""
        token = self.advance()  # 消费 初始化
        self.expect(TokenType.左括号, "构造函数需要 '('")
        params, default_values = self._parse_param_list()
        self.expect(TokenType.右括号, "构造函数需要 ')'")
        self.expect(TokenType.换行, "构造函数头部后需要换行")
        body = self.parse_block()

        return FunctionDecl(
            name="初始化",
            params=params,
            default_values=default_values,
            body=body,
            line=token.line,
            column=token.column,
        )

    # ========================
    # 模式匹配解析
    # ========================

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
            pattern = self.parse_expression()

        # 守卫条件
        guard = None
        if self.match(TokenType.当):
            guard = self.parse_expression()

        self.expect(TokenType.冒号, "匹配分支需要 ':'")
        self.skip_newlines()

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

    # ========================
    # 模块解析
    # ========================

    def parse_import_stmt(self) -> ImportStmt:
        """解析导入语句：导入 模块 / 从 模块 导入 名字"""
        token = self.advance()  # 消费 导入
        module_token = self.expect(TokenType.标识符, "导入需要模块名")
        module_path = module_token.value

        # 点分路径：工具.数学
        while self.match(TokenType.点):
            next_name = self.expect(TokenType.标识符, "模块路径需要名称")
            module_path += "." + next_name.value

        alias = None
        if self.match(TokenType.作为):
            alias_token = self.expect(TokenType.标识符, "'作为' 后需要别名")
            alias = alias_token.value

        self.match(TokenType.换行)
        return ImportStmt(
            module_path=module_path,
            alias=alias,
            line=token.line,
            column=token.column,
        )

    # ========================
    # 赋值与表达式语句
    # ========================

    def parse_expression_or_assignment(self) -> Statement:
        """解析表达式语句或赋值语句"""
        expr = self.parse_expression()

        # 检查是否为赋值
        if self.match(TokenType.赋值):
            value = self.parse_expression()
            self.match(TokenType.换行)
            return Assignment(
                target=expr,
                value=value,
                line=expr.line,
                column=expr.column,
            )

        self.match(TokenType.换行)
        return ExpressionStmt(
            expression=expr,
            line=expr.line,
            column=expr.column,
        )

    # ========================
    # 代码块解析
    # ========================

    def parse_block(self) -> list[Statement]:
        """解析缩进代码块"""
        self.expect(TokenType.缩进, "期望缩进的代码块")
        statements = []

        while self.current.type != TokenType.回退 and self.current.type != TokenType.文件结束:
            self.skip_newlines()
            if self.current.type == TokenType.回退 or self.current.type == TokenType.文件结束:
                break
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)

        self.match(TokenType.回退)
        return statements

    # ========================
    # 表达式解析（按优先级从低到高）
    # ========================

    def parse_expression(self) -> Expression:
        """解析表达式（入口）"""
        return self.parse_pipe()

    def parse_pipe(self) -> Expression:
        """解析管道表达式：甲 |> 乙"""
        left = self.parse_or()
        while self.match(TokenType.管道):
            right = self.parse_or()
            left = PipeExpr(left=left, right=right,
                            line=left.line, column=left.column)
        return left

    def parse_or(self) -> Expression:
        """解析 或者 表达式"""
        left = self.parse_and()
        while self.match(TokenType.或者):
            right = self.parse_and()
            left = BinaryOp(left=left, operator="或者", right=right,
                            line=left.line, column=left.column)
        return left

    def parse_and(self) -> Expression:
        """解析 并且 表达式"""
        left = self.parse_not()
        while self.match(TokenType.并且):
            right = self.parse_not()
            left = BinaryOp(left=left, operator="并且", right=right,
                            line=left.line, column=left.column)
        return left

    def parse_not(self) -> Expression:
        """解析 不是 表达式"""
        if self.match(TokenType.不是):
            operand = self.parse_not()
            return UnaryOp(operator="不是", operand=operand,
                           line=operand.line, column=operand.column)
        return self.parse_comparison()

    def parse_comparison(self) -> Expression:
        """解析比较表达式（含 在/不在 成员运算符）"""
        left = self.parse_addition()

        compare_ops = {
            TokenType.等于, TokenType.不等于,
            TokenType.大于, TokenType.小于,
            TokenType.大于等于, TokenType.小于等于,
            TokenType.在, TokenType.不在,
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
                return BinaryOp(left=operands[0], operator=operators[0],
                                right=operands[1],
                                line=left.line, column=left.column)
            else:
                return CompareOp(operands=operands, operators=operators,
                                 line=left.line, column=left.column)

        return left

    def parse_addition(self) -> Expression:
        """解析加减法"""
        left = self.parse_multiplication()
        while self.current.type in (TokenType.加, TokenType.减):
            op = self.advance()
            right = self.parse_multiplication()
            left = BinaryOp(left=left, operator=op.value, right=right,
                            line=left.line, column=left.column)
        return left

    def parse_multiplication(self) -> Expression:
        """解析乘除取余"""
        left = self.parse_power()
        while self.current.type in (TokenType.乘, TokenType.除, TokenType.取余):
            op = self.advance()
            right = self.parse_power()
            left = BinaryOp(left=left, operator=op.value, right=right,
                            line=left.line, column=left.column)
        return left

    def parse_power(self) -> Expression:
        """解析幂运算（右结合）"""
        base = self.parse_unary()
        if self.match(TokenType.幂):
            exponent = self.parse_power()  # 右结合：递归调用自身
            return BinaryOp(left=base, operator="**", right=exponent,
                            line=base.line, column=base.column)
        return base

    def parse_unary(self) -> Expression:
        """解析一元运算符"""
        if self.current.type == TokenType.减:
            op = self.advance()
            operand = self.parse_unary()
            return UnaryOp(operator="-", operand=operand,
                           line=op.line, column=op.column)
        return self.parse_call()

    def parse_call(self) -> Expression:
        """解析函数调用和成员/索引访问"""
        expr = self.parse_primary()

        while True:
            if self.match(TokenType.左括号):
                # 函数调用
                args = []
                kwargs = {}
                while self.current.type != TokenType.右括号:
                    # 检查命名参数
                    if (self.current.type == TokenType.标识符 and
                            self.peek().type == TokenType.赋值):
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
                    callee=expr, arguments=args, keyword_args=kwargs,
                    line=expr.line, column=expr.column,
                )
            elif self.match(TokenType.点):
                # 成员访问（接受标识符和部分关键字作为成员名）
                member_name = self._expect_member_name()
                expr = MemberAccess(
                    object=expr, member=member_name,
                    line=expr.line, column=expr.column,
                )
            elif self.match(TokenType.左方括号):
                index = self.parse_expression()
                self.expect(TokenType.右方括号, "索引访问需要 ']'")
                expr = IndexAccess(
                    object=expr, index=index,
                    line=expr.line, column=expr.column,
                )
            else:
                break

        return expr

    def _expect_member_name(self) -> str:
        """期望一个成员名（标识符或允许作为成员名的关键字）"""
        # 允许某些关键字作为成员名（如 父对象.初始化()）
        MEMBER_KEYWORDS = {
            TokenType.初始化, TokenType.类型, TokenType.标识符,
        }
        if self.current.type in MEMBER_KEYWORDS:
            return self.advance().value
        raise self._error(f"成员访问需要属性名，但得到 '{self.current.value}'")

    def parse_primary(self) -> Expression:
        """解析基本表达式（最高优先级）"""
        token = self.current

        # 数值字面量
        if token.type == TokenType.数值:
            self.advance()
            return NumberLiteral(value=token.value, line=token.line, column=token.column)

        # 字符串字面量
        if token.type == TokenType.文本:
            self.advance()
            return StringLiteral(value=token.value, line=token.line, column=token.column)

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

        # 标识符
        if token.type == TokenType.标识符:
            self.advance()
            return Identifier(name=token.value, line=token.line, column=token.column)

        # 本对象 (this/self)
        if token.type == TokenType.本对象:
            self.advance()
            return SelfExpr(line=token.line, column=token.column)

        # 父对象 (super)
        if token.type == TokenType.父对象:
            self.advance()
            return SuperExpr(line=token.line, column=token.column)

        # 匿名函数：函数(x) => x * 2
        if token.type == TokenType.函数:
            return self.parse_lambda()

        # 括号表达式
        if token.type == TokenType.左括号:
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.右括号, "括号表达式需要 ')'")
            return expr

        # 列表字面量 [...]
        if token.type == TokenType.左方括号:
            return self.parse_list_literal()

        # 字典字面量 {...}
        if token.type == TokenType.左花括号:
            return self.parse_dict_literal()

        raise self._error(f"无法解析的表达式: '{token.value}' ({token.type.name})")

    def parse_lambda(self) -> LambdaExpr:
        """解析匿名函数"""
        token = self.advance()  # 消费 函数
        self.expect(TokenType.左括号, "匿名函数需要 '('")

        params = []
        while self.current.type != TokenType.右括号:
            param = self.expect(TokenType.标识符, "期望参数名")
            params.append(param.value)
            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右括号, "匿名函数需要 ')'")
        self.expect(TokenType.箭头, "匿名函数需要 '=>'")
        body = self.parse_expression()

        return LambdaExpr(
            params=params, body=body,
            line=token.line, column=token.column,
        )

    def parse_list_literal(self) -> ListLiteral:
        """解析列表字面量"""
        token = self.advance()  # 消费 [
        elements = []

        while self.current.type != TokenType.右方括号:
            elements.append(self.parse_expression())
            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右方括号, "列表需要 ']'")
        return ListLiteral(elements=elements, line=token.line, column=token.column)

    def parse_dict_literal(self) -> DictLiteral:
        """解析字典字面量"""
        token = self.advance()  # 消费 {
        pairs = []

        while self.current.type != TokenType.右花括号:
            key = self.parse_expression()
            self.expect(TokenType.冒号, "字典需要 ':'")
            value = self.parse_expression()
            pairs.append((key, value))
            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右花括号, "字典需要 '}'")
        return DictLiteral(pairs=pairs, line=token.line, column=token.column)
