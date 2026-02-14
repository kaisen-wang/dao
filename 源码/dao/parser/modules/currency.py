"""
并发编程解析混入
===================

解析并发编程相关的语法：
- 异步/等待
- 协程和通道
- 同步原语
"""

from ...ast_nodes import (
    AsyncFunctionDecl,
    AwaitAllExpr,
    AwaitExpr,
    AwaitRaceExpr,
    ChannelExpr,
    Expression,
    ParallelStmt,
    ReceiveExpr,
    SelectCase,
    SelectStmt,
    SendStmt,
    Statement,
    SyncStmt,
)
from ...errors import 语法错误
from ...tokens import TokenType


class ConcurrencyParser:
    """并发编程解析方法集"""

    def parse_async_function_decl(self) -> AsyncFunctionDecl:
        """解析异步函数声明：异步 函数 名字(参数) ..."""
        token = self.advance()  # 消费 异步

        # 检查修饰符
        is_static = False
        is_private = False
        if self.current.type == TokenType.静态:
            is_static = True
            self.advance()
        if self.current.type == TokenType.私有:
            is_private = True
            self.advance()

        # 期望函数关键字
        self.expect(TokenType.函数, "异步函数声明需要 '函数' 关键字")

        # 解析函数名
        name_token = self.expect_identifier_or_keyword("异步函数声明需要函数名")
        self.expect(TokenType.左括号, "异步函数声明需要 '('")

        # 解析参数列表
        params, default_values = self._parse_param_list()

        self.expect(TokenType.右括号, "异步函数声明需要 ')'")

        # 跳过所有后续的换行符，但保留第一个 INDENT 作为函数体的开始
        # 只跳过换行符，不跳过缩进
        while self.current.type == TokenType.换行:
            self.advance()

        # 解析函数体
        body = self.parse_block()

        return AsyncFunctionDecl(
            name=name_token.value,
            params=params,
            default_values=default_values,
            body=body,
            is_static=is_static,
            is_private=is_private,
            line=token.line,
            column=token.column,
        )

    def parse_await_expr(self) -> AwaitExpr:
        """解析等待表达式：等待 表达式"""
        token = self.advance()  # 消费 等待

        # 解析等待的表达式
        expression = self.parse_expression()

        return AwaitExpr(
            expression=expression,
            line=token.line,
            column=token.column,
        )

    def parse_await_all_expr(self) -> AwaitAllExpr:
        """解析全部等待表达式：全部(任务1, 任务2, ...)"""
        token = self.advance()  # 消费 全部

        self.expect(TokenType.左括号, "全部() 需要 '('")

        expressions = []
        while self.current.type != TokenType.右括号:
            expr = self.parse_expression()
            expressions.append(expr)

            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右括号, "全部() 需要 ')'")

        return AwaitAllExpr(
            expressions=expressions,
            line=token.line,
            column=token.column,
        )

    def parse_await_race_expr(self) -> AwaitRaceExpr:
        """解析竞速等待表达式：竞速(任务1, 任务2, ...)"""
        token = self.advance()  # 消费 竞速

        self.expect(TokenType.左括号, "竞速() 需要 '('")

        expressions = []
        while self.current.type != TokenType.右括号:
            expr = self.parse_expression()
            expressions.append(expr)

            if not self.match(TokenType.逗号):
                break

        self.expect(TokenType.右括号, "竞速() 需要 ')'")

        return AwaitRaceExpr(
            expressions=expressions,
            line=token.line,
            column=token.column,
        )

    def parse_parallel_stmt(self) -> ParallelStmt:
        """解析并行块：并行 { ... }"""
        token = self.advance()  # 消费 并行

        self.expect(TokenType.换行, "并行块后需要换行")

        # 解析并行块体
        body = self.parse_block()

        return ParallelStmt(
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_channel_expr(self) -> ChannelExpr:
        """解析通道表达式：通道() 或 通道(容量)"""
        token = self.advance()  # 消费 通道

        self.expect(TokenType.左括号, "通道() 需要 '('")

        capacity = None
        if self.current.type != TokenType.右括号:
            # 解析容量参数
            capacity_token = self.expect(TokenType.数值, "通道容量必须是数值")
            capacity = int(capacity_token.value)

        self.expect(TokenType.右括号, "通道() 需要 ')'")

        return ChannelExpr(
            capacity=capacity,
            line=token.line,
            column=token.column,
        )

    def parse_send_stmt(self) -> SendStmt:
        """解析发送语句：发送 通道 数据"""
        token = self.advance()  # 消费 发送

        # 解析通道表达式
        channel = self.parse_expression()

        # 可选的逗号分隔符
        self.match(TokenType.逗号)

        # 解析要发送的值
        value = self.parse_expression()

        self.match(TokenType.换行)

        return SendStmt(
            channel=channel,
            value=value,
            line=token.line,
            column=token.column,
        )

    def parse_receive_expr(self) -> ReceiveExpr:
        """解析接收表达式：接收 通道"""
        token = self.advance()  # 消费 接收

        # 解析通道表达式
        channel = self.parse_expression()

        return ReceiveExpr(
            channel=channel,
            line=token.line,
            column=token.column,
        )

    def parse_select_stmt(self) -> SelectStmt:
        """解析选择语句：选择 ..."""
        token = self.advance()  # 消费 选择

        # 道语言不支持花括号语法，只支持缩进块语法
        has_braces = False

        cases = []

        # 解析所有情况语句
        while True:
            self.skip_newlines()

            if has_braces and self.current.type == TokenType.右花括号:
                break
            elif not has_braces and (
                self.current.type == TokenType.文件结束
                or (
                    self.current.type == TokenType.回退
                    and self.current.value == str(token.column - 1)
                )
            ):
                break

            if self.current.type == TokenType.情况:
                # 新语法风格：情况 接收 通道 作为 变量:
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
                # 可选的换行，接受缩进或直接解析
                if not self.match(TokenType.换行):
                    self.skip_newlines()

                # 如果没有 INDENT token，尝试解析单个语句作为块
                # 这将允许选择语句在没有明确缩进的情况下工作
                if self.current.type == TokenType.缩进:
                    body = self.parse_block()
                else:
                    # 解析单个语句作为块
                    body = []
                    stmt = self.parse_statement()
                    if stmt:
                        body.append(stmt)

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

            elif self.current.type == TokenType.当:
                # 语法风格支持两种：
                # 1. 当 变量 = 接收 通道 （接收消息）
                # 2. 当 条件 （直接条件判断）
                self.advance()  # 消费 当

                # 检查是否是 "当 超时(秒数)" 语法
                if (
                    self.current.type == TokenType.超时
                    and self.peek().type == TokenType.左括号
                ):
                    # 语法3：当 超时(秒数)
                    case_type = "timeout"
                    variable = None
                    channel = None

                    self.advance()  # 消费 超时
                    self.expect(TokenType.左括号, "超时() 需要 '('")
                    timeout_value = self.parse_expression()
                    self.expect(TokenType.右括号, "超时() 需要 ')'")
                elif (
                    self.current.type == TokenType.标识符
                    and self.peek().type == TokenType.赋值
                    and self.peek(2).type == TokenType.接收
                ):
                    # 语法1：当 变量 = 接收 通道
                    case_type = "receive"

                    # 解析变量 = 接收 通道
                    var_token = self.expect(TokenType.标识符, "需要变量名")
                    variable = var_token.value

                    self.expect(TokenType.赋值, "需要 '='")

                    self.expect(TokenType.接收, "需要 '接收'")

                    channel = self.parse_expression()
                else:
                    # 语法2：当 条件
                    case_type = "condition"
                    variable = None
                    channel = None
                    condition = self.parse_expression()

                self.skip_newlines()

                # 解析分支体（缩进块）
                if self.current.type == TokenType.缩进:
                    body = self.parse_block()
                else:
                    # 解析单个语句作为块
                    body = []
                    stmt = self.parse_statement()
                    if stmt:
                        body.append(stmt)

                # 创建 SelectCase 节点
                select_case = SelectCase(
                    type=case_type,
                    channel=channel,
                    variable=variable,
                    timeout_value=timeout_value
                    if "timeout_value" in locals()
                    else None,
                    body=body,
                    line=token.line,
                    column=token.column,
                )
                # 如果是条件判断，我们需要存储条件信息
                if case_type == "condition":
                    setattr(select_case, "condition", condition)

                cases.append(select_case)

            elif self.current.type == TokenType.默认:
                # 旧语法风格：默认
                self.advance()  # 消费 默认

                case_type = "timeout"
                variable = None
                channel = None
                timeout_value = None  # 无限超时

                self.skip_newlines()

                # 解析分支体（缩进块）
                if self.current.type == TokenType.缩进:
                    body = self.parse_block()
                else:
                    # 解析单个语句作为块
                    body = []
                    stmt = self.parse_statement()
                    if stmt:
                        body.append(stmt)

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
                # 如果是回退 token，说明选择语句块结束
                if self.current.type == TokenType.回退:
                    break
                else:
                    raise 语法错误(
                        f"选择分支必须是 '情况'、'当' 或 '默认'，但得到 {self.current.type.name}",
                        self.current.line,
                        self.current.column,
                        self.source,
                    )

        # 匹配可选的右花括号
        if has_braces:
            self.expect(TokenType.右花括号, "选择语句需要 '}'")

        return SelectStmt(
            cases=cases,
            line=token.line,
            column=token.column,
        )

    def parse_sync_stmt(self) -> SyncStmt:
        """解析同步块：同步 锁 ..."""
        token = self.advance()  # 消费 同步

        # 解析互斥锁表达式
        mutex = self.parse_expression()

        self.expect(TokenType.换行, "同步块后需要换行")

        # 解析同步块体
        body = self.parse_block()

        return SyncStmt(
            mutex=mutex,
            body=body,
            line=token.line,
            column=token.column,
        )

    def _parse_param_list(self) -> tuple:
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
