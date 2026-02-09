"""
树遍历解释器 (Tree-Walking Interpreter)
========================================

遍历AST并执行程序。这是第一阶段的核心模块。

执行流程：
1. 从 Program 根节点开始
2. 逐个执行语句
3. 表达式求值返回 Python 原生值
4. 使用 Environment 管理变量作用域
"""

from .ast_nodes import *
from .environment import Environment
from .builtins import DaoCallable, DaoFunction, BuiltinFunction, get_builtins
from .errors import (
    运行时错误, 类型错误, 名称错误, 索引错误,
    断言失败, 跳出信号, 继续信号, 返回信号,
)


class Interpreter:
    """
    "道"语言树遍历解释器

    使用方法：
        interpreter = Interpreter()
        interpreter.execute(ast)
    """

    def __init__(self):
        # 创建全局环境，注入内置函数
        self.global_env = Environment()
        for name, func in get_builtins().items():
            self.global_env.define(name, func)

    def execute(self, program: Program, env: Environment | None = None) -> object:
        """
        执行程序

        参数：
            program : AST根节点
            env     : 执行环境（默认全局环境）
        返回：最后一条语句的值
        """
        env = env or self.global_env
        result = None
        for stmt in program.statements:
            result = self.exec_statement(stmt, env)
        return result

    # ========================
    # 语句执行
    # ========================

    def exec_statement(self, stmt: Statement, env: Environment) -> object:
        """分派并执行一条语句"""
        match stmt:
            case VariableDecl():
                return self.exec_variable_decl(stmt, env)
            case Assignment():
                return self.exec_assignment(stmt, env)
            case ExpressionStmt():
                return self.eval_expression(stmt.expression, env)
            case FunctionDecl():
                return self.exec_function_decl(stmt, env)
            case ReturnStmt():
                return self.exec_return(stmt, env)
            case IfStmt():
                return self.exec_if(stmt, env)
            case WhileStmt():
                return self.exec_while(stmt, env)
            case ForInStmt():
                return self.exec_for_in(stmt, env)
            case ForRangeStmt():
                return self.exec_for_range(stmt, env)
            case BreakStmt():
                raise 跳出信号()
            case ContinueStmt():
                raise 继续信号()
            case TryStmt():
                return self.exec_try(stmt, env)
            case ThrowStmt():
                return self.exec_throw(stmt, env)
            case AssertStmt():
                return self.exec_assert(stmt, env)
            case _:
                raise 运行时错误(
                    f"未知的语句类型: {type(stmt).__name__}",
                    stmt.line, stmt.column,
                )

    def exec_variable_decl(self, stmt: VariableDecl, env: Environment) -> None:
        """执行变量/常量声明"""
        value = self.eval_expression(stmt.value, env)
        env.define(stmt.name, value, is_constant=stmt.is_constant)

    def exec_assignment(self, stmt: Assignment, env: Environment) -> None:
        """执行赋值语句"""
        value = self.eval_expression(stmt.value, env)

        if isinstance(stmt.target, Identifier):
            env.set(stmt.target.name, value)
        elif isinstance(stmt.target, MemberAccess):
            obj = self.eval_expression(stmt.target.object, env)
            if isinstance(obj, dict):
                obj[stmt.target.member] = value
            else:
                raise 类型错误(
                    f"无法给类型 '{type(obj).__name__}' 设置属性",
                    stmt.line, stmt.column,
                )
        elif isinstance(stmt.target, IndexAccess):
            obj = self.eval_expression(stmt.target.object, env)
            index = self.eval_expression(stmt.target.index, env)
            if isinstance(obj, list):
                obj[int(index)] = value
            elif isinstance(obj, dict):
                obj[index] = value
            else:
                raise 类型错误(
                    f"无法给类型 '{type(obj).__name__}' 设置索引",
                    stmt.line, stmt.column,
                )
        else:
            raise 运行时错误("无效的赋值目标", stmt.line, stmt.column)

    def exec_function_decl(self, stmt: FunctionDecl, env: Environment) -> None:
        """执行函数声明"""
        func = DaoFunction(
            name=stmt.name,
            params=stmt.params,
            default_values={
                k: self.eval_expression(v, env)
                for k, v in stmt.default_values.items()
            },
            body=stmt.body,
            closure_env=env,
        )
        env.define(stmt.name, func)

    def exec_return(self, stmt: ReturnStmt, env: Environment) -> None:
        """执行返回语句"""
        value = None
        if stmt.value is not None:
            value = self.eval_expression(stmt.value, env)
        raise 返回信号(value)

    def exec_if(self, stmt: IfStmt, env: Environment) -> object:
        """执行条件语句"""
        if self._is_truthy(self.eval_expression(stmt.condition, env)):
            return self._exec_block(stmt.body, env)

        for elif_cond, elif_body in stmt.elif_clauses:
            if self._is_truthy(self.eval_expression(elif_cond, env)):
                return self._exec_block(elif_body, env)

        if stmt.else_body:
            return self._exec_block(stmt.else_body, env)

        return None

    def exec_while(self, stmt: WhileStmt, env: Environment) -> None:
        """执行当循环"""
        while self._is_truthy(self.eval_expression(stmt.condition, env)):
            try:
                self._exec_block(stmt.body, env)
            except 跳出信号:
                break
            except 继续信号:
                continue

    def exec_for_in(self, stmt: ForInStmt, env: Environment) -> None:
        """执行遍历循环"""
        iterable = self.eval_expression(stmt.iterable, env)
        if not hasattr(iterable, '__iter__'):
            raise 类型错误(
                f"类型 '{type(iterable).__name__}' 不可遍历",
                stmt.line, stmt.column,
            )

        for item in iterable:
            loop_env = env.create_child()
            loop_env.define(stmt.variable, item)
            try:
                self._exec_block(stmt.body, loop_env)
            except 跳出信号:
                break
            except 继续信号:
                continue

    def exec_for_range(self, stmt: ForRangeStmt, env: Environment) -> None:
        """执行范围循环"""
        start = int(self.eval_expression(stmt.start, env))
        end = int(self.eval_expression(stmt.end, env))
        step = int(self.eval_expression(stmt.step, env)) if stmt.step else 1

        for i in range(start, end + 1, step):
            loop_env = env.create_child()
            loop_env.define(stmt.variable, i)
            try:
                self._exec_block(stmt.body, loop_env)
            except 跳出信号:
                break
            except 继续信号:
                continue

    def exec_try(self, stmt: TryStmt, env: Environment) -> object:
        """执行尝试-捕获-最终"""
        try:
            return self._exec_block(stmt.try_body, env)
        except 运行时错误 as e:
            if stmt.catch_body:
                catch_env = env.create_child()
                if stmt.catch_var:
                    catch_env.define(stmt.catch_var, {
                        "信息": e.message,
                        "行": e.line,
                        "列": e.column,
                    })
                return self._exec_block(stmt.catch_body, catch_env)
        except Exception as e:
            if stmt.catch_body:
                catch_env = env.create_child()
                if stmt.catch_var:
                    catch_env.define(stmt.catch_var, {
                        "信息": str(e),
                    })
                return self._exec_block(stmt.catch_body, catch_env)
        finally:
            if stmt.finally_body:
                self._exec_block(stmt.finally_body, env)

    def exec_throw(self, stmt: ThrowStmt, env: Environment) -> None:
        """执行抛出语句"""
        value = self.eval_expression(stmt.expression, env)
        if isinstance(value, str):
            raise 运行时错误(value, stmt.line, stmt.column)
        raise 运行时错误(str(value), stmt.line, stmt.column)

    def exec_assert(self, stmt: AssertStmt, env: Environment) -> None:
        """执行断言语句"""
        condition = self.eval_expression(stmt.condition, env)
        if not self._is_truthy(condition):
            msg = "断言失败"
            if stmt.message:
                msg = str(self.eval_expression(stmt.message, env))
            raise 断言失败(msg, stmt.line, stmt.column)

    # ========================
    # 表达式求值
    # ========================

    def eval_expression(self, expr: Expression, env: Environment) -> object:
        """分派并求值一个表达式"""
        match expr:
            case NumberLiteral():
                return expr.value
            case StringLiteral():
                return expr.value
            case BooleanLiteral():
                return expr.value
            case NullLiteral():
                return None
            case ListLiteral():
                return [self.eval_expression(e, env) for e in expr.elements]
            case DictLiteral():
                return {
                    self.eval_expression(k, env): self.eval_expression(v, env)
                    for k, v in expr.pairs
                }
            case Identifier():
                return env.get(expr.name)
            case MemberAccess():
                return self.eval_member_access(expr, env)
            case IndexAccess():
                return self.eval_index_access(expr, env)
            case BinaryOp():
                return self.eval_binary_op(expr, env)
            case UnaryOp():
                return self.eval_unary_op(expr, env)
            case CompareOp():
                return self.eval_compare_op(expr, env)
            case FunctionCall():
                return self.eval_function_call(expr, env)
            case LambdaExpr():
                return self.eval_lambda(expr, env)
            case _:
                raise 运行时错误(
                    f"未知的表达式类型: {type(expr).__name__}",
                    expr.line, expr.column,
                )

    def eval_member_access(self, expr: MemberAccess, env: Environment) -> object:
        """求值成员访问"""
        obj = self.eval_expression(expr.object, env)
        if isinstance(obj, dict) and expr.member in obj:
            return obj[expr.member]
        if isinstance(obj, list) and expr.member.isdigit():
            return obj[int(expr.member)]
        raise 名称错误(
            f"对象没有属性 '{expr.member}'",
            expr.line, expr.column,
        )

    def eval_index_access(self, expr: IndexAccess, env: Environment) -> object:
        """求值索引访问"""
        obj = self.eval_expression(expr.object, env)
        index = self.eval_expression(expr.index, env)

        if isinstance(obj, list):
            idx = int(index)
            if idx < 0 or idx >= len(obj):
                raise 索引错误(
                    f"列表索引 {idx} 超出范围 (长度 {len(obj)})",
                    expr.line, expr.column,
                )
            return obj[idx]
        elif isinstance(obj, dict):
            if index not in obj:
                raise 名称错误(f"字典中不存在键 '{index}'", expr.line, expr.column)
            return obj[index]
        elif isinstance(obj, str):
            idx = int(index)
            if idx < 0 or idx >= len(obj):
                raise 索引错误(
                    f"字符串索引 {idx} 超出范围 (长度 {len(obj)})",
                    expr.line, expr.column,
                )
            return obj[idx]
        else:
            raise 类型错误(
                f"类型 '{type(obj).__name__}' 不支持索引访问",
                expr.line, expr.column,
            )

    def eval_binary_op(self, expr: BinaryOp, env: Environment) -> object:
        """求值二元运算"""
        # 短路求值
        if expr.operator == "并且":
            left = self.eval_expression(expr.left, env)
            if not self._is_truthy(left):
                return left
            return self.eval_expression(expr.right, env)

        if expr.operator == "或者":
            left = self.eval_expression(expr.left, env)
            if self._is_truthy(left):
                return left
            return self.eval_expression(expr.right, env)

        left = self.eval_expression(expr.left, env)
        right = self.eval_expression(expr.right, env)

        match expr.operator:
            case '+':
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                return left + right
            case '-':
                return left - right
            case '*':
                if isinstance(left, str) and isinstance(right, (int, float)):
                    return left * int(right)
                return left * right
            case '/':
                if right == 0:
                    raise 运行时错误("除零错误", expr.line, expr.column)
                return left / right
            case '%':
                return left % right
            case '**':
                return left ** right
            case '==':
                return left == right
            case '!=':
                return left != right
            case '>':
                return left > right
            case '<':
                return left < right
            case '>=':
                return left >= right
            case '<=':
                return left <= right
            case _:
                raise 运行时错误(
                    f"未知的运算符: '{expr.operator}'",
                    expr.line, expr.column,
                )

    def eval_unary_op(self, expr: UnaryOp, env: Environment) -> object:
        """求值一元运算"""
        operand = self.eval_expression(expr.operand, env)

        match expr.operator:
            case '-':
                return -operand
            case '不是':
                return not self._is_truthy(operand)
            case _:
                raise 运行时错误(
                    f"未知的一元运算符: '{expr.operator}'",
                    expr.line, expr.column,
                )

    def eval_compare_op(self, expr: CompareOp, env: Environment) -> bool:
        """求值链式比较"""
        values = [self.eval_expression(op, env) for op in expr.operands]

        for i, op in enumerate(expr.operators):
            left, right = values[i], values[i + 1]
            match op:
                case '==':
                    result = left == right
                case '!=':
                    result = left != right
                case '>':
                    result = left > right
                case '<':
                    result = left < right
                case '>=':
                    result = left >= right
                case '<=':
                    result = left <= right
                case _:
                    result = False
            if not result:
                return False
        return True

    def eval_function_call(self, expr: FunctionCall, env: Environment) -> object:
        """求值函数调用"""
        callee = self.eval_expression(expr.callee, env)

        if not isinstance(callee, DaoCallable):
            raise 类型错误(
                f"'{callee}' 不是一个可调用的函数",
                expr.line, expr.column,
            )

        args = [self.eval_expression(arg, env) for arg in expr.arguments]
        kwargs = {k: self.eval_expression(v, env) for k, v in expr.keyword_args.items()}

        if isinstance(callee, BuiltinFunction):
            return callee.call(args, kwargs)

        if isinstance(callee, DaoFunction):
            return self._call_dao_function(callee, args, kwargs, expr)

        return callee.call(args, kwargs)

    def eval_lambda(self, expr: LambdaExpr, env: Environment) -> DaoFunction:
        """求值匿名函数（创建闭包）"""
        return DaoFunction(
            name="<匿名>",
            params=expr.params,
            default_values={},
            body=[ReturnStmt(value=expr.body)] if isinstance(expr.body, Expression) else expr.body,
            closure_env=env,
        )

    # ========================
    # 辅助方法
    # ========================

    def _call_dao_function(self, func: DaoFunction, args: list,
                           kwargs: dict, call_expr: FunctionCall) -> object:
        """调用用户自定义函数"""
        # 创建函数执行环境（基于闭包环境）
        func_env = func.closure_env.create_child()

        # 绑定参数
        for i, param in enumerate(func.params):
            if i < len(args):
                func_env.define(param, args[i])
            elif param in kwargs:
                func_env.define(param, kwargs[param])
            elif param in func.default_values:
                func_env.define(param, func.default_values[param])
            else:
                raise 运行时错误(
                    f"函数 '{func.name}' 缺少参数 '{param}'",
                    call_expr.line, call_expr.column,
                )

        # 执行函数体
        try:
            self._exec_block(func.body, func_env)
        except 返回信号 as ret:
            return ret.value

        return None  # 无返回值的函数返回 空

    def _exec_block(self, statements: list[Statement], env: Environment) -> object:
        """执行一个代码块"""
        result = None
        for stmt in statements:
            result = self.exec_statement(stmt, env)
        return result

    @staticmethod
    def _is_truthy(value: object) -> bool:
        """判断值的真假（道语言的真值判断规则）"""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) > 0
        return True
