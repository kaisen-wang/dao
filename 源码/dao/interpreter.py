"""
树遍历解释器 (Tree-Walking Interpreter)
========================================

遍历AST并执行程序。这是第一阶段的核心模块。

执行流程：
1. 从 Program 根节点开始
2. 逐个执行语句
3. 表达式求值返回 Python 原生值
4. 使用 Environment 管理变量作用域

支持特性：
- 基础语句（变量、赋值、控制流、函数）
- 面向对象（类型、继承、多态、本对象/父对象）
- 函数式（高阶函数、管道运算符、Lambda）
- 模式匹配（匹配/情况/守卫）
"""

from .ast_nodes import *
from .environment import Environment
from .builtins import (
    DaoCallable, DaoFunction, BuiltinFunction, InterpreterBuiltin,
    DaoClass, DaoInstance, BoundMethod, SuperProxy,
    get_builtins, get_interpreter_builtins,
)
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

        # 注册基础内置函数
        for name, func in get_builtins().items():
            self.global_env.define(name, func)

        # 注册需要解释器引用的高阶内置函数
        for name, func in get_interpreter_builtins().items():
            func.interpreter = self
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

    def call_function(self, func, args, kwargs=None):
        """
        统一的函数调用接口（供高阶内置函数使用）

        参数：
            func   : 可调用对象（DaoFunction, BuiltinFunction, etc.）
            args   : 位置参数列表
            kwargs : 命名参数字典
        """
        kwargs = kwargs or {}

        if isinstance(func, BuiltinFunction):
            return func.call(args, kwargs)

        if isinstance(func, InterpreterBuiltin):
            return func.call(args, kwargs)

        if isinstance(func, DaoFunction):
            return self._call_dao_function(func, args, kwargs, None)

        if isinstance(func, BoundMethod):
            return self._call_method(func.instance, func.method, args, kwargs, None)

        if isinstance(func, DaoClass):
            return self._instantiate_class(func, args, kwargs, None)

        raise 类型错误(f"'{func}' 不是可调用的函数")

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
            case ClassDecl():
                return self.exec_class_decl(stmt, env)
            case MatchStmt():
                return self.exec_match(stmt, env)
            case ImportStmt():
                return self.exec_import(stmt, env)
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
            if isinstance(obj, DaoInstance):
                obj.set_field(stmt.target.member, value)
            elif isinstance(obj, dict):
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
    # OOP 执行
    # ========================

    def exec_class_decl(self, stmt: ClassDecl, env: Environment) -> None:
        """执行类型声明"""
        # 解析父类
        parent = None
        if stmt.parent_name:
            parent = env.get(stmt.parent_name)
            if not isinstance(parent, DaoClass):
                raise 类型错误(
                    f"'{stmt.parent_name}' 不是一个类型，无法继承",
                    stmt.line, stmt.column,
                )

        # 收集方法（在当前环境的子环境中创建，使类方法能访问外部变量）
        methods = {}
        for s in stmt.body:
            if isinstance(s, FunctionDecl):
                func = DaoFunction(
                    name=s.name,
                    params=s.params,
                    default_values={
                        k: self.eval_expression(v, env)
                        for k, v in s.default_values.items()
                    },
                    body=s.body,
                    closure_env=env,
                )
                methods[s.name] = func

        klass = DaoClass(name=stmt.name, parent=parent, methods=methods)
        env.define(stmt.name, klass)

    def _instantiate_class(self, klass: DaoClass, args: list,
                           kwargs: dict, call_expr) -> DaoInstance:
        """创建类型实例"""
        instance = DaoInstance(klass)

        # 调用构造函数
        init_method = klass.find_method("初始化")
        if init_method:
            self._call_method(instance, init_method, args, kwargs, call_expr)
        elif args:
            line = call_expr.line if call_expr else 0
            col = call_expr.column if call_expr else 0
            raise 运行时错误(
                f"类型 '{klass.name}' 没有构造函数，不接受参数",
                line, col,
            )

        return instance

    def _call_method(self, instance: DaoInstance, method: DaoFunction,
                     args: list, kwargs: dict, call_expr) -> object:
        """调用实例方法（绑定 本对象）"""
        func_env = method.closure_env.create_child()
        func_env.define("本对象", instance)

        # 如果有父类，绑定 父对象 代理
        if instance.klass.parent:
            func_env.define("父对象", SuperProxy(instance, instance.klass.parent))

        # 绑定参数
        self._bind_params(method, args, kwargs, func_env, call_expr)

        # 执行方法体
        try:
            self._exec_block(method.body, func_env)
        except 返回信号 as ret:
            return ret.value

        return None

    # ========================
    # 模式匹配执行
    # ========================

    def exec_match(self, stmt: MatchStmt, env: Environment) -> object:
        """执行匹配语句"""
        subject = self.eval_expression(stmt.subject, env)

        for case in stmt.cases:
            # 通配符 _ 匹配所有
            if case.is_wildcard:
                if case.guard:
                    if self._is_truthy(self.eval_expression(case.guard, env)):
                        return self._exec_block(case.body, env)
                    continue
                return self._exec_block(case.body, env)

            # 求值模式并比较
            pattern_val = self.eval_expression(case.pattern, env)

            if subject == pattern_val:
                # 检查守卫条件
                if case.guard:
                    if not self._is_truthy(self.eval_expression(case.guard, env)):
                        continue
                return self._exec_block(case.body, env)

        return None  # 无匹配

    # ========================
    # 导入执行
    # ========================

    def exec_import(self, stmt: ImportStmt, env: Environment) -> None:
        """执行导入语句（基础版）"""
        import os
        # 将模块路径转换为文件路径
        module_path = stmt.module_path.replace(".", os.sep) + ".道"

        if not os.path.exists(module_path):
            raise 运行时错误(
                f"模块 '{stmt.module_path}' 不存在 (找不到文件: {module_path})",
                stmt.line, stmt.column,
            )

        with open(module_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # 在新环境中执行模块
        from .lexer import Lexer
        from .parser import Parser

        lexer = Lexer(source, module_path)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        module_env = Environment()
        # 注入内置函数到模块环境
        for name, func in get_builtins().items():
            module_env.define(name, func)
        for name, func in get_interpreter_builtins().items():
            func.interpreter = self
            module_env.define(name, func)

        self.execute(ast, module_env)

        # 将模块内容导入到当前环境
        alias = stmt.alias or stmt.module_path.split(".")[-1]
        module_dict = {}
        for name, value in module_env.values.items():
            if not isinstance(value, (BuiltinFunction, InterpreterBuiltin)):
                module_dict[name] = value

        env.define(alias, module_dict)

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
            case SelfExpr():
                return env.get("本对象")
            case SuperExpr():
                return env.get("父对象")
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
            case PipeExpr():
                return self.eval_pipe(expr, env)
            case _:
                raise 运行时错误(
                    f"未知的表达式类型: {type(expr).__name__}",
                    expr.line, expr.column,
                )

    def eval_member_access(self, expr: MemberAccess, env: Environment) -> object:
        """求值成员访问"""
        obj = self.eval_expression(expr.object, env)

        # 实例成员访问
        if isinstance(obj, DaoInstance):
            result = obj.get_field(expr.member)
            if result is not None:
                return result
            raise 名称错误(
                f"类型 '{obj.klass.name}' 的实例没有属性 '{expr.member}'",
                expr.line, expr.column,
            )

        # 父对象代理的成员访问
        if isinstance(obj, SuperProxy):
            method = obj.parent_class.find_method(expr.member)
            if method:
                return BoundMethod(obj.instance, method)
            raise 名称错误(
                f"父类型中没有方法 '{expr.member}'",
                expr.line, expr.column,
            )

        # 类型的静态方法访问
        if isinstance(obj, DaoClass):
            method = obj.find_method(expr.member)
            if method:
                return method
            raise 名称错误(
                f"类型 '{obj.name}' 没有方法 '{expr.member}'",
                expr.line, expr.column,
            )

        # 字典成员访问
        if isinstance(obj, dict) and expr.member in obj:
            return obj[expr.member]

        # 字符串/列表方法（常用方法模拟）
        if isinstance(obj, str):
            return self._get_str_method(obj, expr.member, expr)
        if isinstance(obj, list):
            return self._get_list_method(obj, expr.member, expr)

        raise 名称错误(
            f"对象没有属性 '{expr.member}'",
            expr.line, expr.column,
        )

    def _get_str_method(self, s: str, name: str, expr) -> object:
        """获取字符串的内置方法"""
        methods = {
            "长度": lambda: len(s),
            "大写": lambda: s.upper(),
            "小写": lambda: s.lower(),
            "去空白": lambda: s.strip(),
            "分割": BuiltinFunction("分割", lambda sep=" ": s.split(sep)),
            "替换": BuiltinFunction("替换", lambda old, new: s.replace(old, new)),
            "包含": BuiltinFunction("包含", lambda sub: sub in s),
            "开头是": BuiltinFunction("开头是", lambda prefix: s.startswith(prefix)),
            "结尾是": BuiltinFunction("结尾是", lambda suffix: s.endswith(suffix)),
        }
        if name in methods:
            result = methods[name]
            if callable(result) and not isinstance(result, DaoCallable):
                return result()
            return result
        raise 名称错误(f"文本没有方法 '{name}'", expr.line, expr.column)

    def _get_list_method(self, lst: list, name: str, expr) -> object:
        """获取列表的内置方法"""
        methods = {
            "长度": lambda: len(lst),
            "追加": BuiltinFunction("追加", lambda item: lst.append(item) or lst),
            "弹出": BuiltinFunction("弹出", lambda: lst.pop()),
            "插入": BuiltinFunction("插入", lambda i, item: lst.insert(int(i), item) or lst),
            "连接": BuiltinFunction("连接", lambda sep="": sep.join(str(x) for x in lst)),
        }
        if name in methods:
            result = methods[name]
            if callable(result) and not isinstance(result, DaoCallable):
                return result()
            return result
        raise 名称错误(f"列表没有方法 '{name}'", expr.line, expr.column)

    def eval_index_access(self, expr: IndexAccess, env: Environment) -> object:
        """求值索引访问"""
        obj = self.eval_expression(expr.object, env)
        index = self.eval_expression(expr.index, env)

        if isinstance(obj, list):
            idx = int(index)
            if idx < -len(obj) or idx >= len(obj):
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
            if idx < -len(obj) or idx >= len(obj):
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
                if isinstance(left, list) and isinstance(right, list):
                    return left + right
                return left + right
            case '-':
                return left - right
            case '*':
                if isinstance(left, str) and isinstance(right, (int, float)):
                    return left * int(right)
                if isinstance(right, str) and isinstance(left, (int, float)):
                    return right * int(left)
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
            case '在':
                return left in right
            case '不在':
                return left not in right
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
                case '在':
                    result = left in right
                case '不在':
                    result = left not in right
                case _:
                    result = False
            if not result:
                return False
        return True

    def eval_function_call(self, expr: FunctionCall, env: Environment) -> object:
        """求值函数调用"""
        callee = self.eval_expression(expr.callee, env)

        args = [self.eval_expression(arg, env) for arg in expr.arguments]
        kwargs = {k: self.eval_expression(v, env) for k, v in expr.keyword_args.items()}

        # 类型实例化
        if isinstance(callee, DaoClass):
            return self._instantiate_class(callee, args, kwargs, expr)

        # 绑定方法调用
        if isinstance(callee, BoundMethod):
            return self._call_method(callee.instance, callee.method, args, kwargs, expr)

        if not isinstance(callee, DaoCallable):
            raise 类型错误(
                f"'{callee}' 不是一个可调用的函数",
                expr.line, expr.column,
            )

        if isinstance(callee, BuiltinFunction):
            return callee.call(args, kwargs)

        if isinstance(callee, InterpreterBuiltin):
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

    def eval_pipe(self, expr: PipeExpr, env: Environment) -> object:
        """求值管道表达式：甲 |> 乙"""
        left_val = self.eval_expression(expr.left, env)

        # 如果右侧是函数调用，把左侧值插入为第一个参数
        if isinstance(expr.right, FunctionCall):
            callee = self.eval_expression(expr.right.callee, env)
            args = [left_val] + [self.eval_expression(a, env) for a in expr.right.arguments]
            kwargs = {k: self.eval_expression(v, env) for k, v in expr.right.keyword_args.items()}

            if isinstance(callee, DaoClass):
                return self._instantiate_class(callee, args, kwargs, expr)
            if isinstance(callee, BoundMethod):
                return self._call_method(callee.instance, callee.method, args, kwargs, expr)
            if isinstance(callee, BuiltinFunction):
                return callee.call(args, kwargs)
            if isinstance(callee, InterpreterBuiltin):
                return callee.call(args, kwargs)
            if isinstance(callee, DaoFunction):
                return self._call_dao_function(callee, args, kwargs, expr)
            raise 类型错误("管道右侧必须是函数", expr.line, expr.column)

        # 如果右侧是标识符或其他表达式，作为函数调用
        callee = self.eval_expression(expr.right, env)
        if isinstance(callee, DaoCallable) or isinstance(callee, DaoClass):
            return self.call_function(callee, [left_val])

        raise 类型错误(
            "管道运算符 |> 右侧必须是函数",
            expr.line, expr.column,
        )

    # ========================
    # 辅助方法
    # ========================

    def _call_dao_function(self, func: DaoFunction, args: list,
                           kwargs: dict, call_expr) -> object:
        """调用用户自定义函数"""
        # 创建函数执行环境（基于闭包环境）
        func_env = func.closure_env.create_child()

        # 绑定参数
        self._bind_params(func, args, kwargs, func_env, call_expr)

        # 执行函数体
        try:
            self._exec_block(func.body, func_env)
        except 返回信号 as ret:
            return ret.value

        return None  # 无返回值的函数返回 空

    def _bind_params(self, func: DaoFunction, args: list, kwargs: dict,
                     env: Environment, call_expr) -> None:
        """绑定函数参数到环境"""
        for i, param in enumerate(func.params):
            if i < len(args):
                env.define(param, args[i])
            elif param in kwargs:
                env.define(param, kwargs[param])
            elif param in func.default_values:
                env.define(param, func.default_values[param])
            else:
                line = call_expr.line if call_expr else 0
                col = call_expr.column if call_expr else 0
                raise 运行时错误(
                    f"函数 '{func.name}' 缺少参数 '{param}'",
                    line, col,
                )

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
