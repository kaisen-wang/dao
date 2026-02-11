"""
语句解析混入
===========

包含所有语句解析方法：变量声明、函数声明、控制流、
OOP（类型/构造函数）、模式匹配、模块导入、解构赋值等。
通过 Python mixin 模式，在运行时与 Parser 组合。
"""

from ..tokens import TokenType, Token
from ..ast_nodes import (
    Statement,
    Expression,
    VariableDecl,
    Assignment,
    ExpressionStmt,
    FunctionDecl,
    ReturnStmt,
    YieldStmt,
    IfStmt,
    WhileStmt,
    ForInStmt,
    ForRangeStmt,
    BreakStmt,
    ContinueStmt,
    TryStmt,
    ThrowStmt,
    AssertStmt,
    ClassDecl,
    AbstractDecl,
    EnumDecl,
    TraitDecl,
    MatchStmt,
    MatchCase,
    ImportStmt,
    ExportStmt,
    DestructureAssign,
    NullLiteral,
    ListLiteral,
    ListPattern,
    DictPattern,
    Identifier,
)


class StatementParser:
    """语句解析方法集（混入类）"""

    # ========================
    # 语句分派
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
            case TokenType.抽象:
                return self.parse_abstract_decl()
            case TokenType.类型:
                return self.parse_class_decl()
            case TokenType.枚举:
                return self.parse_enum_decl()
            case TokenType.特征:
                return self.parse_trait_decl()
            case TokenType.返回:
                return self.parse_return_stmt()
            case TokenType.产出:
                return self.parse_yield_stmt()
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
            case TokenType.导出:
                return self.parse_export_stmt()
            case TokenType.从:
                self.advance()  # 消费 "从"
                return self.parse_import_stmt(is_from_import=True)
            case _:
                return self.parse_expression_or_assignment()

    # ========================
    # 变量/常量声明
    # ========================

    def parse_variable_decl(
        self, is_constant: bool
    ) -> VariableDecl | DestructureAssign:
        """解析变量/常量声明：定义 x = 值 或 定义 [甲, 乙] = 值"""
        token = self.advance()  # 消费 定义/常量

        # 检查是否是解构赋值：定义 [甲, 乙] = ...
        if self.current.type == TokenType.左方括号:
            return self._parse_destructure_decl(token, is_constant)

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

    def _parse_destructure_decl(self, token, is_constant: bool) -> DestructureAssign:
        """解析解构声明：定义 [甲, 乙] = [1, 2]"""
        self.advance()  # 消费 [
        targets = []
        while self.current.type != TokenType.右方括号:
            name = self.expect(TokenType.标识符, "解构赋值需要变量名")
            targets.append(name.value)
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右方括号, "解构赋值需要 ']'")
        self.expect(TokenType.赋值, "解构赋值需要 '='")
        value = self.parse_expression()
        self.expect(TokenType.换行, "语句末尾需要换行")
        return DestructureAssign(
            targets=targets,
            value=value,
            is_declaration=True,
            line=token.line,
            column=token.column,
        )

    # ========================
    # 函数声明
    # ========================

    def parse_function_decl(self) -> FunctionDecl:
        """解析函数声明：函数 名字(参数) ..."""
        token = self.advance()  # 消费 函数

        name_token = self.expect_identifier_or_keyword("函数声明需要函数名")
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

    def _parse_method_signature(self, token: Token) -> FunctionDecl:
        """解析方法签名（用于抽象方法，不需要函数关键字）：方法名(参数)"""
        name_token = self.expect_identifier_or_keyword("方法声明需要方法名")
        self.expect(TokenType.左括号, "方法声明需要 '('")

        params, default_values = self._parse_param_list()

        self.expect(TokenType.右括号, "方法声明需要 ')'")
        self.expect(TokenType.换行, "方法头部后需要换行")

        return FunctionDecl(
            name=name_token.value,
            params=params,
            default_values=default_values,
            body=[],  # 抽象方法没有方法体
            line=token.line,
            column=token.column,
        )

    def _parse_operator_overload(self, is_static: bool, is_private: bool) -> FunctionDecl:
        """解析运算符重载：运算符+(参数)"""
        token = self.advance()  # 消费 运算符

        # 期望运算符符号
        operator_token = self.current
        operator_symbol = ""

        # 支持的运算符符号
        operator_token_types = {
            TokenType.加: "+",
            TokenType.减: "-",
            TokenType.乘: "*",
            TokenType.除: "/",
            TokenType.取余: "%",
            TokenType.幂: "**",
            TokenType.等于: "==",
            TokenType.不等于: "!=",
            TokenType.小于: "<",
            TokenType.小于等于: "<=",
            TokenType.大于: ">",
            TokenType.大于等于: ">=",
        }

        if operator_token.type in operator_token_types:
            operator_symbol = operator_token_types[operator_token.type]
            self.advance()
        else:
            raise 语法错误(
                f"运算符重载需要一个有效的运算符符号 (+, -, *, /, %, **, ==, !=, <, <=, >, >=)",
                operator_token.line,
                operator_token.column,
                self.source,
            )

        # 解析参数列表
        self.expect(TokenType.左括号, "运算符重载需要 '('")
        params, default_values = self._parse_param_list()
        self.expect(TokenType.右括号, "运算符重载需要 ')'")

        # 运算符通常接受一个参数（右操作数）
        if len(params) != 1:
            raise 语法错误(
                f"运算符重载需要一个参数（右操作数），但得到 {len(params)} 个参数",
                token.line,
                token.column,
                self.source,
            )

        self.expect(TokenType.换行, "运算符重载后需要换行")

        # 解析方法体
        body = self.parse_block()

        return FunctionDecl(
            name=f"运算符{operator_symbol}",  # 使用特殊名称存储
            params=params,
            default_values=default_values,
            body=body,
            line=token.line,
            column=token.column,
            is_static=is_static,
            is_private=is_private,
            is_operator=True,
            operator_symbol=operator_symbol,
        )

    def _parse_property_accessor(self, is_static: bool, is_private: bool, is_getter: bool) -> FunctionDecl:
        """解析属性访问器：获取 属性名() 或 设置 属性名(值)"""
        token = self.advance()  # 消费 获取或设置

        # 获取属性名
        property_name_token = self.expect_identifier_or_keyword("属性访问器需要一个属性名")
        property_name = property_name_token.value

        # 解析参数列表
        self.expect(TokenType.左括号, "属性访问器需要 '('")
        params, default_values = self._parse_param_list()
        self.expect(TokenType.右括号, "属性访问器需要 ')'")

        # 验证参数
        if is_getter:
            # getter 不应该有参数
            if len(params) > 0:
                raise 语法错误(
                    f"属性 getter '{property_name}' 不应该有参数，但得到 {len(params)} 个参数",
                    token.line,
                    token.column,
                    self.source,
                )
        else:
            # setter 必须有一个参数
            if len(params) != 1:
                raise 语法错误(
                    f"属性 setter '{property_name}' 必须有一个参数，但得到 {len(params)} 个参数",
                    token.line,
                    token.column,
                    self.source,
                )

        self.expect(TokenType.换行, "属性访问器后需要换行")

        # 解析方法体
        body = self.parse_block()

        # 使用特殊名称存储属性访问器
        accessor_name = f"获取{property_name}" if is_getter else f"设置{property_name}"

        return FunctionDecl(
            name=accessor_name,
            params=params,
            default_values=default_values,
            body=body,
            line=token.line,
            column=token.column,
            is_static=is_static,
            is_private=is_private,
            is_getter=is_getter,
            is_setter=not is_getter,
        )


    def _parse_param_list(self) -> tuple[list[str], dict]:
        """解析参数列表"""
        params = []
        default_values = {}
        while self.current.type != TokenType.右括号:
            param = self.expect_identifier_or_keyword("期望参数名")
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
        if (
            self.current.type != TokenType.换行
            and self.current.type != TokenType.文件结束
        ):
            value = self.parse_expression()
        self.match(TokenType.换行)
        return ReturnStmt(value=value, line=token.line, column=token.column)

    def parse_yield_stmt(self) -> YieldStmt:
        """解析产出语句"""
        token = self.advance()  # 消费 产出
        value = None
        if (
            self.current.type != TokenType.换行
            and self.current.type != TokenType.文件结束
        ):
            value = self.parse_expression()
        self.match(TokenType.换行)
        return YieldStmt(value=value, line=token.line, column=token.column)

    # ========================
    # 控制流
    # ========================

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

    # ========================
    # 错误处理
    # ========================

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
            error_type = None
            # 检查是否是类型化捕获：捕获 异常: 错误类型
            if self.current.type == TokenType.标识符:
                catch_var = self.advance().value
                if self.match(TokenType.冒号):
                    error_type_token = self.expect(TokenType.标识符, "期望错误类型名称")
                    error_type = error_type_token.value
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
            error_type=error_type,
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

    def parse_enum_decl(self) -> EnumDecl:
        """解析枚举声明：枚举 名字 { 枚举值1, 枚举值2, ... }"""
        from ..ast_nodes import EnumDecl

        token = self.advance()  # 消费 枚举
        name_token = self.expect(TokenType.标识符, "枚举声明需要一个枚举名")

        self.expect(TokenType.左花括号, "枚举声明需要 '{'")

        values = []
        while not self.match(TokenType.右花括号):
            value_token = self.expect(TokenType.标识符, "枚举值需要是标识符")
            values.append(value_token.value)

            # 逗号是可选的
            self.match(TokenType.逗号)

        return EnumDecl(
            name=name_token.value,
            values=values,
            line=token.line,
            column=token.column,
        )

    def parse_abstract_decl(self) -> AbstractDecl:
        """解析抽象类型声明：抽象 类型 名字 [继承自 父类] ..."""
        token = self.advance()  # 消费 抽象
        self.expect(TokenType.类型, "'抽象' 后需要 '类型' 关键字")
        name_token = self.expect(TokenType.标识符, "抽象类型声明需要一个类名")

        parent_name = None
        if self.match(TokenType.继承自):
            parent_token = self.expect(TokenType.标识符, "'继承自' 后需要父类名")
            parent_name = parent_token.value

        self.expect(TokenType.换行, "抽象类型声明后需要换行")

        body = self.parse_class_body(indent_consumed=False)

        return AbstractDecl(
            name=name_token.value,
            parent_name=parent_name,
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_class_decl(self) -> ClassDecl:
        """解析类型声明：类型 名字 [继承自 父类] [实现 特征1, 特征2] ..."""
        token = self.advance()  # 消费 类型
        name_token = self.expect(TokenType.标识符, "类型声明需要一个类名")

        parent_name = None
        if self.match(TokenType.继承自):
            parent_token = self.expect(TokenType.标识符, "'继承自' 后需要父类名")
            parent_name = parent_token.value

        implemented_traits = []

        self.expect(TokenType.换行, "类型声明后需要换行")

        # 实现 clause can appear after newline/indent (in class body)
        # 检查是否是错误类型（继承自 DaoError）
        is_error_class = False
        is_abstract = False
        if parent_name == "错误":
            is_error_class = True

        # Skip INDENT if present and check for '实现'
        has_indent = self.match(TokenType.缩进)
        if has_indent:
            # Check if the first token in class body is '实现'
            if self.match(TokenType.实现):
                # 解析特征列表
                while True:
                    trait_token = self.expect(TokenType.标识符, "'实现' 后需要特征名")
                    implemented_traits.append(trait_token.value)
                    if not self.match(TokenType.逗号):
                        break
                # Skip newline after implements clause
                self.skip_newlines()
            elif not is_error_class:
                # 错误类型不需要类体，如果不是错误类型则放回缩进
                self.pos -= 1  # Undo the match(TokenType.缩进)

        # 错误类型不需要解析类体
        if is_error_class:
            body = []
        else:
            body = self.parse_class_body(indent_consumed=has_indent)

        return ClassDecl(
            name=name_token.value,
            parent_name=parent_name,
            implemented_traits=implemented_traits,
            body=body,
            line=token.line,
            column=token.column,
            is_error_class=is_error_class,
            is_abstract=is_abstract,
        )

    def parse_trait_decl(self) -> TraitDecl:
        """解析特征声明：特征 名字 ..."""
        token = self.advance()  # 消费 特征
        name_token = self.expect(TokenType.标识符, "特征声明需要一个特征名")

        self.expect(TokenType.换行, "特征声明后需要换行")
        body = self.parse_class_body()  # 特征体和类体结构相同

        return TraitDecl(
            name=name_token.value,
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_class_body(self, indent_consumed: bool = False) -> list[Statement]:
        """解析类体（缩进块，包含构造函数和方法）"""
        if not indent_consumed:
            self.expect(TokenType.缩进, "类型类体需要缩进")
        statements = []

        while self.current.type not in (TokenType.回退, TokenType.文件结束):
            self.skip_newlines()
            if self.current.type in (TokenType.回退, TokenType.文件结束):
                break

            # 修饰符
            is_static = False
            is_private = False
            if self.current.type == TokenType.私有:
                is_private = True
                self.advance()
            if self.current.type == TokenType.静态:
                is_static = True
                self.advance()

            # '实现' 子句已在 parse_class_decl 中处理，这里不再需要
            if self.current.type == TokenType.实现:
                raise 语法错误(
                    "'实现' 子句必须在类型声明的开始处",
                    self.current.line,
                    self.current.column,
                    self.source,
                )

            if self.current.type == TokenType.初始化:
                # 构造函数：初始化(参数) ...
                func = self.parse_constructor()
                func.is_private = is_private
                statements.append(func)
            elif self.current.type == TokenType.函数:
                # 方法：函数 名字(参数) ...
                func = self.parse_function_decl()
                func.is_static = is_static
                func.is_private = is_private
                statements.append(func)
            elif self.current.type == TokenType.抽象:
                # 抽象方法：抽象 方法名(参数)
                token = self.advance()  # 消费 抽象
                func = self._parse_method_signature(token)
                func.is_abstract = True
                func.is_static = is_static
                func.is_private = is_private
                statements.append(func)
            elif self.current.type == TokenType.运算符:
                # 运算符重载：运算符+(参数)
                func = self._parse_operator_overload(is_static, is_private)
                statements.append(func)
            elif self.current.type == TokenType.获取:
                # 属性 getter：获取 属性名()
                func = self._parse_property_accessor(is_static, is_private, is_getter=True)
                statements.append(func)
            elif self.current.type == TokenType.设置:
                # 属性 setter：设置 属性名(value)
                func = self._parse_property_accessor(is_static, is_private, is_getter=False)
                statements.append(func)
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

    # ========================
    # 模块解析
    # ========================



    def parse_export_stmt(self) -> ExportStmt:
        """解析导出语句：导出 名称 / 导出 {名称1, 名称2}"""
        token = self.advance()  # 消费 导出

        names = []

        # 检查是否是花括号语法：导出 {名称1, 名称2}
        if self.match(TokenType.左花括号):
            while self.current.type != TokenType.右花括号:
                name_token = self.expect(TokenType.标识符, "期望导出的名称")
                names.append(name_token.value)
                if not self.match(TokenType.逗号):
                    break

            self.expect(TokenType.右花括号, "导出语句需要 '}'")
        else:
            # 单个名称：导出 名称
            name_token = self.expect(TokenType.标识符, "导出语句需要名称")
            names.append(name_token.value)

        self.match(TokenType.换行)
        return ExportStmt(
            names=names,
            line=token.line,
            column=token.column,
        )

    def parse_import_stmt(self, is_from_import: bool = False) -> ImportStmt:
        """解析导入语句：导入 模块 / 从 模块 导入 {项}"""

        if is_from_import:
            # 已经在 parse_statement 中消费了 "从"
            token = self.current  # 当前 token 是模块名
            module_token = self.expect(TokenType.标识符, "导入需要模块名")
            module_path = module_token.value

            # 点分路径：工具.数学
            while self.match(TokenType.点):
                next_name = self.expect(TokenType.标识符, "模块路径需要名称")
                module_path += "." + next_name.value

            self.expect(TokenType.导入, "期望 '导入' 关键字")

            names = []
            # 检查是否是花括号语法：导入 {项1, 项2}
            if self.match(TokenType.左花括号):
                while self.current.type != TokenType.右花括号:
                    name_token = self.expect(TokenType.标识符, "期望导入的名称")
                    names.append(name_token.value)
                    if not self.match(TokenType.逗号):
                        break

                self.expect(TokenType.右花括号, "导入语句需要 '}'")
            else:
                # 单个名称
                name_token = self.expect(TokenType.标识符, "导入语句需要名称")
                names.append(name_token.value)

            self.match(TokenType.换行)
            return ImportStmt(
                module_path=module_path,
                names=names,
                alias=None,
                is_from_import=True,
                line=token.line,
                column=token.column,
            )
        else:
            # 普通 "导入 模块" 语法
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
                names=[],
                alias=alias,
                is_from_import=False,
                line=token.line,
                column=token.column,
            )

    # ========================
    # 赋值与表达式语句
    # ========================

    def parse_expression_or_assignment(self) -> Statement:
        """解析表达式语句或赋值语句"""
        expr = self.parse_expression()

        # 检查是否为解构赋值：[甲, 乙] = ...
        if self.match(TokenType.赋值):
            if isinstance(expr, ListLiteral):
                # 列表解构赋值
                targets = []
                for elem in expr.elements:
                    if not isinstance(elem, Identifier):
                        raise self._error("解构赋值的目标必须是变量名")
                    targets.append(elem.name)
                value = self.parse_expression()
                self.match(TokenType.换行)
                return DestructureAssign(
                    targets=targets,
                    value=value,
                    is_declaration=False,
                    line=expr.line,
                    column=expr.column,
                )
            # 普通赋值
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
