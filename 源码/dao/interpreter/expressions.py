"""
表达式求值混入
=============

包含所有 eval_* 方法，负责求值"道"语言的表达式节点。
通过 Python mixin 模式，在运行时与 Interpreter 组合。
"""

from ..ast_nodes import *
from ..builtins import (
    BoundMethod,
    BuiltinFunction,
    DaoCallable,
    DaoClass,
    DaoFunction,
    DaoInstance,
    InterpreterBuiltin,
    SuperProxy,
)
from ..environment import Environment
from ..errors import 名称错误, 类型错误, 索引错误, 运行时错误

# 导入逻辑编程相关类型
from ..logic.core import LogicVariable


class ExpressionEvaluator:
    """表达式求值方法集（混入类）"""

    def eval_expression(self, expr: Expression, env: Environment) -> object:
        """分派并求值一个表达式"""
        # 先使用 isinstance 检查避免 match 语句作用域问题
        if type(expr).__name__ == "LogicVariable":
            from ..logic.core import LogicVariable

            return LogicVariable(expr.name)

        if isinstance(expr, Identifier):
            if expr.name.startswith("?"):
                from ..logic.core import LogicVariable

                return LogicVariable(expr.name)
            return env.get(expr.name)

        # 处理 ExpressionStmt 类型
        if isinstance(expr, ExpressionStmt):
            return self.eval_expression(expr.expression, env)

        # 处理语句类型
        from ..ast_nodes import (
            AssertStmt,
            Assignment,
            BreakStmt,
            ContinueStmt,
            ForInStmt,
            ForRangeStmt,
            IfStmt,
            MatchStmt,
            ReturnStmt,
            ThrowStmt,
            VariableDecl,
            WhileStmt,
            YieldStmt,
        )

        if isinstance(
            expr,
            (
                WhileStmt,
                IfStmt,
                ForInStmt,
                ForRangeStmt,
                BreakStmt,
                ContinueStmt,
                ReturnStmt,
                YieldStmt,
                ThrowStmt,
                AssertStmt,
                MatchStmt,
                VariableDecl,
                Assignment,
            ),
        ):
            return self.exec_statement(expr, env)

        match expr:
            case NumberLiteral():
                return expr.value
            case StringLiteral():
                return expr.value
            case TemplateLiteral():
                return self.eval_template(expr, env)
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
            case AwaitExpr():
                return self.eval_await(expr, env)
            case AwaitAllExpr():
                return self.eval_await_all(expr, env)
            case AwaitRaceExpr():
                return self.eval_await_race(expr, env)
            case ChannelExpr():
                return self.eval_channel(expr, env)
            case ReceiveExpr():
                return self.eval_receive(expr, env)
            case LogicQuery():
                return self.eval_logic_query(expr, env)

            case MacroCall():
                return self.eval_macro_call(expr, env)
            case QuoteBlock():
                return self.eval_quote_block(expr, env)
            case UnquoteExpr():
                return self.eval_unquote_expr(expr, env)
            case LogicPredicate():
                return self.eval_logic_predicate(expr, env)
            case LogicNegation():
                return self.eval_logic_negation(expr, env)
            case LogicCut():
                return self.eval_logic_cut(expr, env)
            case BlockExpr():
                # 执行块中的所有语句并返回最后一个值
                evaluated = None
                for stmt in expr.body:
                    if hasattr(stmt, "expression"):
                        evaluated = self.eval_expression(stmt.expression, env)
                    else:
                        evaluated = self.exec_statement(stmt, env)
                return evaluated
            case LogicConstraint():
                return self.eval_logic_constraint(expr, env)
            case _:
                raise 运行时错误(
                    f"未知的表达式类型: {type(expr).__name__}",
                    expr.line,
                    expr.column,
                    self.source,
                )

    # ========================
    # 模板字符串
    # ========================

    def eval_template(self, expr: TemplateLiteral, env: Environment) -> str:
        """求值模板字符串"""
        parts = expr.parts
        values = [self.eval_expression(e, env) for e in expr.expressions]
        result = []
        for i, part in enumerate(parts):
            result.append(part)
            if i < len(values):
                v = values[i]
                if v is None:
                    result.append("空")
                elif isinstance(v, bool):
                    result.append("真" if v else "假")
                else:
                    result.append(str(v))
        return "".join(result)

    # ========================
    # 成员与索引访问
    # ========================

    def eval_member_access(self, expr: MemberAccess, env: Environment) -> object:
        """求值成员访问"""
        obj = self.eval_expression(expr.object, env)

        if isinstance(obj, DaoInstance):
            # 检查私有访问
            if expr.member in obj.klass.private_names:
                # 检查是否在类方法内部（本对象可访问）
                if not self._in_method_context(env, obj.klass):
                    raise 运行时错误(
                        f"无法访问类型 '{obj.klass.name}' 的私有成员 '{expr.member}'",
                        expr.line,
                        expr.column,
                        self.source,
                    )
            # 先检查是否有 property getter
            getter_name = f"获取{expr.member}"
            getter = obj.klass.find_method(getter_name)
            if getter and getter.is_getter:
                return self._call_method(obj, getter, [], {}, expr)

            result = obj.get_field(expr.member)
            if result is not None:
                return result
            raise 名称错误(
                f"类型 '{obj.klass.name}' 的实例没有属性 '{expr.member}'",
                expr.line,
                expr.column,
                self.source,
            )

        # 处理所有错误类型实例的成员访问
        from ..builtins.oop_types import DaoError
        from ..errors import 道错误

        if isinstance(obj, (DaoError, 道错误)):
            # 检查对象是否直接有该属性
            if hasattr(obj, expr.member):
                return getattr(obj, expr.member)

            # 对于 道错误 子类（如运行时错误），直接返回属性
            if isinstance(obj, 道错误):
                # 道错误 有 message, line, column, source, stack 属性
                if expr.member in ["message", "行", "列", "source", "stack"]:
                    if expr.member == "行":
                        return obj.line
                    elif expr.member == "列":
                        return obj.column
                    elif expr.member == "信息":
                        return str(obj)  # 返回格式化的错误信息
                    return getattr(obj, expr.member)

            # 对于 DaoError 类型，也支持访问 '信息' 属性
            if isinstance(obj, DaoError):
                if expr.member == "信息":
                    return str(obj)  # 对于 DaoError 实例，信息就是其字符串表示
                if expr.member == "消息":
                    return obj.message  # 直接访问 message 属性

            # 检查错误类型是否有该属性的 getter 方法
            from ..builtins.oop_types import DaoClass

            if hasattr(obj, "类型") and isinstance(obj.类型, DaoClass):
                getter_name = f"获取{expr.member}"
                getter = obj.类型.find_method(getter_name)
                if getter and getter.is_getter:
                    # 我们需要创建一个临时的 DaoInstance 来调用方法
                    class ErrorInstanceWrapper:
                        def __init__(self, error_obj, klass):
                            self.error = error_obj
                            self.klass = klass
                            self.fields = {}

                        def get_field(self, name):
                            return getattr(self.error, name, None)

                        def set_field(self, name, value):
                            setattr(self.error, name, value)

                    temp_instance = ErrorInstanceWrapper(obj, obj.类型)
                    return self._call_method(temp_instance, getter, [], {}, expr)

            raise 名称错误(
                f"类型 '{obj.类型.name if hasattr(obj, '类型') and obj.类型 else type(obj).__name__}' 的实例没有属性 '{expr.member}'",
                expr.line,
                expr.column,
                self.source,
            )

        if isinstance(obj, SuperProxy):
            # 检查 parent_class 是否是 DaoClass 实例（即是否有 find_method 方法）
            if hasattr(obj.parent_class, "find_method"):
                method = obj.parent_class.find_method(expr.member)
                if method:
                    return BoundMethod(obj.instance, method)

            # 对于继承自 DaoError 的类型，处理特殊情况
            from ..builtins.oop_types import DaoError

            if obj.parent_class == DaoError:
                # DaoError 是 Python 类，不是 DaoClass 实例
                if expr.member == "初始化":
                    # 返回一个可以设置消息的内置方法
                    from ..builtins.callables import BuiltinFunction

                    def initialize_method(消息):
                        obj.instance.消息 = 消息

                    return BuiltinFunction("初始化", initialize_method)

                if (
                    expr.member == "消息"
                    or expr.member == "line"
                    or expr.member == "column"
                ):
                    # 直接返回属性值
                    if hasattr(obj.instance, expr.member):
                        return getattr(obj.instance, expr.member)

                raise 名称错误(
                    f"父类型 'DaoError' 没有方法 '{expr.member}'",
                    expr.line,
                    expr.column,
                    self.source,
                )

            raise 名称错误(
                f"父类型中没有方法 '{expr.member}'", expr.line, expr.column, self.source
            )

        from ..builtins.oop_types import DaoClass

        if isinstance(obj, DaoClass):
            # 先查找静态方法
            static_method = obj.find_static_method(expr.member)
            if static_method:
                return static_method
            method = obj.find_method(expr.member)
            if method:
                return method
            raise 名称错误(
                f"类型 '{obj.name}' 没有方法或静态方法 '{expr.member}'",
                expr.line,
                expr.column,
                self.source,
            )

        if isinstance(obj, dict) and expr.member in obj:
            return obj[expr.member]

        if isinstance(obj, str):
            return self._get_str_method(obj, expr.member, expr)
        if isinstance(obj, list):
            return self._get_list_method(obj, expr.member, expr)

        raise 名称错误(
            f"对象没有属性 '{expr.member}'", expr.line, expr.column, self.source
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
        raise 名称错误(f"文本没有方法 '{name}'", expr.line, expr.column, self.source)

    def _get_list_method(self, lst: list, name: str, expr) -> object:
        """获取列表的内置方法"""
        methods = {
            "长度": lambda: len(lst),
            "追加": BuiltinFunction("追加", lambda item: lst.append(item) or lst),
            "弹出": BuiltinFunction("弹出", lambda: lst.pop()),
            "插入": BuiltinFunction(
                "插入", lambda i, item: lst.insert(int(i), item) or lst
            ),
            "连接": BuiltinFunction(
                "连接", lambda sep="": sep.join(str(x) for x in lst)
            ),
        }
        if name in methods:
            result = methods[name]
            if callable(result) and not isinstance(result, DaoCallable):
                return result()
            return result
        raise 名称错误(f"列表没有方法 '{name}'", expr.line, expr.column, self.source)

    def eval_index_access(self, expr: IndexAccess, env: Environment) -> object:
        """求值索引访问"""
        obj = self.eval_expression(expr.object, env)
        index = self.eval_expression(expr.index, env)

        if isinstance(obj, list):
            idx = int(index)
            if idx < -len(obj) or idx >= len(obj):
                raise 索引错误(
                    f"列表索引 {idx} 超出范围 (长度 {len(obj, 0, 0, self.source)})",
                    expr.line,
                    expr.column,
                )
            return obj[idx]
        elif isinstance(obj, dict):
            if index not in obj:
                raise 名称错误(
                    f"字典中不存在键 '{index}'", expr.line, expr.column, self.source
                )
            return obj[index]
        elif isinstance(obj, str):
            idx = int(index)
            if idx < -len(obj) or idx >= len(obj):
                raise 索引错误(
                    f"字符串索引 {idx} 超出范围 (长度 {len(obj, 0, 0, self.source)})",
                    expr.line,
                    expr.column,
                )
            return obj[idx]
        else:
            raise 类型错误(
                f"类型 '{type(obj, 0, 0, self.source).__name__}' 不支持索引访问",
                expr.line,
                expr.column,
            )

    # ========================
    # 运算
    # ========================

    def eval_binary_op(self, expr: BinaryOp, env: Environment) -> object:
        """求值二元运算"""
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

        # 检查左操作数是否是 DaoInstance 并有运算符重载
        left = self.eval_expression(expr.left, env)

        # 对于运算符重载，只求值右操作数（避免重复求值左操作数）
        if isinstance(left, DaoInstance):
            operator_method_name = f"运算符{expr.operator}"
            method = left.klass.find_method(operator_method_name)
            if method:
                # 调用运算符重载方法
                right = self.eval_expression(expr.right, env)
                return self._call_method(left, method, [right], {}, expr)

        right = self.eval_expression(expr.right, env)

        match expr.operator:
            case "+":
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                if isinstance(left, list) and isinstance(right, list):
                    return left + right
                return left + right
            case "-":
                return left - right
            case "*":
                if isinstance(left, str) and isinstance(right, (int, float)):
                    return left * int(right)
                if isinstance(right, str) and isinstance(left, (int, float)):
                    return right * int(left)
                return left * right
            case "/":
                if right == 0:
                    raise 运行时错误("除零错误", expr.line, expr.column, self.source)
                return left / right
            case "%":
                return left % right
            case "**":
                return left**right
            case "==":
                return left == right
            case "!=":
                return left != right
            case ">":
                return left > right
            case "<":
                return left < right
            case ">=":
                return left >= right
            case "<=":
                return left <= right
            case "在":
                return left in right
            case "不在":
                return left not in right
            case _:
                raise 运行时错误(
                    f"未知的运算符: '{expr.operator}'",
                    expr.line,
                    expr.column,
                    self.source,
                )

    def eval_unary_op(self, expr: UnaryOp, env: Environment) -> object:
        """求值一元运算"""
        operand = self.eval_expression(expr.operand, env)

        match expr.operator:
            case "-":
                return -operand
            case "不是":
                return not self._is_truthy(operand)
            case _:
                raise 运行时错误(
                    f"未知的一元运算符: '{expr.operator}'",
                    expr.line,
                    expr.column,
                    self.source,
                )

    def eval_compare_op(self, expr: CompareOp, env: Environment) -> bool:
        """求值链式比较"""
        values = [self.eval_expression(op, env) for op in expr.operands]

        for i, op in enumerate(expr.operators):
            left, right = values[i], values[i + 1]
            match op:
                case "==":
                    result = left == right
                case "!=":
                    result = left != right
                case ">":
                    result = left > right
                case "<":
                    result = left < right
                case ">=":
                    result = left >= right
                case "<=":
                    result = left <= right
                case "在":
                    result = left in right
                case "不在":
                    result = left not in right
                case _:
                    result = False
            if not result:
                return False
        return True

    # ========================
    # 函数调用
    # ========================

    def eval_function_call(self, expr: FunctionCall, env: Environment) -> object:
        """求值函数调用"""
        callee = self.eval_expression(expr.callee, env)

        args = [self.eval_expression(arg, env) for arg in expr.arguments]
        kwargs = {k: self.eval_expression(v, env) for k, v in expr.keyword_args.items()}

        if isinstance(callee, DaoClass):
            return self._instantiate_class(callee, args, kwargs, expr)

        if isinstance(callee, BoundMethod):
            return self._call_method(callee.instance, callee.method, args, kwargs, expr)

        # 检查是否是 DaoError 子类（自定义异常类型）
        from ..builtins.oop_types import DaoError

        if isinstance(callee, type) and issubclass(callee, DaoError):
            # 调用错误类的构造函数创建异常实例
            error = callee(*args)
            raise error

        if not isinstance(callee, DaoCallable):
            raise 类型错误(
                f"'{callee}' 不是一个可调用的函数", expr.line, expr.column, self.source
            )

        if isinstance(callee, BuiltinFunction):
            return callee.call(args, kwargs)

        if isinstance(callee, InterpreterBuiltin):
            return callee.call(args, kwargs)

        if isinstance(callee, DaoFunction):
            return self._call_dao_function(callee, args, kwargs, expr)

        from ..builtins import CurriedFunction

        if isinstance(callee, CurriedFunction):
            return callee.call(args, kwargs)

        return callee.call(args, kwargs)

    # ========================
    # 宏系统相关表达式求值
    # ========================

    def eval_macro_call(self, expr: MacroCall, env: Environment) -> object:
        """求值宏调用：!宏名(参数)"""
        from ..ast_nodes import QuoteBlock
        from ..macros import MacroExpander
        from ..macros.ast_repr import DataToAST
        from ..macros.registry import find_macro

        # 检查是否有该名称的宏定义
        macro_info = find_macro(expr.name)
        if not macro_info:
            raise 运行时错误(
                f"未找到宏定义 '{expr.name}'",
                expr.line,
                expr.column,
                self.source,
            )

        # 保留参数的 AST 节点，不进行求值，以便在替换时保持节点类型
        evaluated_args = expr.arguments

        # 宏体可能是数据结构，需要先转换回 AST 节点
        if isinstance(macro_info.body, (list, dict)):
            body_ast = DataToAST.convert(macro_info.body)
        else:
            body_ast = macro_info.body

        # 应用宏展开
        expander = MacroExpander()
        expanded_body = expander._apply_macro_parameters(
            body_ast, macro_info.parameters, evaluated_args
        )

        # 递归展开结果中的宏调用
        expanded = expander.expand(expanded_body)

        # 调试输出
        print(f"宏展开后得到: {type(expanded).__name__}: {str(expanded)}")

        # 处理展开后的结果
        if isinstance(expanded, QuoteBlock):
            # 如果是 QuoteBlock，直接取其内容
            expanded = expanded.body

        if isinstance(expanded, list):
            # 如果是语句列表，需要检查是否包含表达式语句
            if len(expanded) == 1 and hasattr(expanded[0], "expression"):
                # 提取表达式
                expanded = expanded[0].expression

        # 求值展开后的表达式
        if isinstance(expanded, (list, dict)):
            # 如果是数据结构，先转换回 AST
            expanded = DataToAST.convert(expanded)

        # 处理列表返回值
        if isinstance(expanded, list):
            # 创建新的作用域来执行宏体，确保卫生宏
            macro_env = Environment(parent=env)

            evaluated = None

            for stmt in expanded:
                # 检查是否是返回语句
                if hasattr(stmt, "value") and stmt.__class__.__name__ == "ReturnStmt":
                    # 如果是返回语句，我们需要求值其 value 属性
                    return_value = self.eval_expression(stmt.value, macro_env)
                    # 如果返回值是 QuoteBlock 或其数据结构，需要执行其内容
                    from ..ast_nodes import QuoteBlock
                    from ..macros.ast_repr import ASTToData, DataToAST

                    if isinstance(return_value, list):
                        # 如果是数据结构列表，转换回 AST 并在新作用域中执行，确保卫生宏
                        for quote_stmt in return_value:
                            ast_stmt = DataToAST.convert(quote_stmt)
                            if hasattr(ast_stmt, "expression"):
                                evaluated = self.eval_expression(
                                    ast_stmt.expression, macro_env
                                )
                            else:
                                evaluated = self.exec_statement(ast_stmt, macro_env)
                    elif isinstance(stmt.value, QuoteBlock):
                        # 如果是 QuoteBlock，在新作用域中执行其内容，确保卫生宏
                        for quote_stmt in stmt.value.body:
                            if hasattr(quote_stmt, "expression"):
                                evaluated = self.eval_expression(
                                    quote_stmt.expression, macro_env
                                )
                            else:
                                evaluated = self.exec_statement(quote_stmt, macro_env)
                    else:
                        evaluated = return_value
                elif hasattr(stmt, "expression"):
                    evaluated = self.eval_expression(stmt.expression, macro_env)
                else:
                    # 如果不是表达式语句，直接执行
                    evaluated = self.exec_statement(stmt, macro_env)
        else:
            evaluated = self.eval_expression(expanded, env)

        # 确保我们对所有类型的结果进行全面求值
        while isinstance(evaluated, (list, dict)):
            if isinstance(evaluated, list):
                if len(evaluated) == 1:
                    evaluated = evaluated[0]
                else:
                    evaluated = evaluated[-1]
            elif isinstance(evaluated, dict) and "__type__" in evaluated:
                # 将数据结构转换回实际的 AST 并求值
                evaluated = DataToAST.convert(evaluated)
                evaluated = self.eval_expression(evaluated, env)

        print(f"表达式求值结果: {type(evaluated).__name__}: {evaluated}")

        return evaluated

    def eval_quote_block(self, expr: QuoteBlock, env: Environment) -> object:
        """求值引述块：引述 { 代码块 }"""
        from ..macros.ast_repr import ASTToData

        # 将引述块内容转换为数据结构，保持原样不执行
        return ASTToData.convert(expr.body)

    def eval_unquote_expr(self, expr: UnquoteExpr, env: Environment) -> object:
        """求值注入表达式：注入(表达式)"""
        from ..ast_nodes import Identifier

        # 如果 expr.expression 是标识符，我们需要检查它是否是宏参数
        # 如果是标识符，并且它在当前环境中没有找到，可能是一个未绑定的变量
        # 或者是一个在宏参数中应该被替换但没有被替换的变量
        if isinstance(expr.expression, Identifier):
            variable_name = expr.expression.name

            try:
                return self.eval_expression(expr.expression, env)
            except:
                # 如果无法找到变量，可能是因为在宏参数替换时没有正确处理
                # 或者是一个在作用域链中没有定义的变量
                print(f"变量 '{variable_name}' 在环境中未找到")
                return None

        return self.eval_expression(expr.expression, env)

    def eval_lambda(self, expr: LambdaExpr, env: Environment) -> DaoFunction:
        """求值匿名函数（创建闭包）"""
        return DaoFunction(
            name="<匿名>",
            params=expr.params,
            default_values={},
            body=[ReturnStmt(value=expr.body)]
            if isinstance(expr.body, Expression)
            else expr.body,
            closure_env=env,
        )

    def eval_pipe(self, expr: PipeExpr, env: Environment) -> object:
        """求值管道表达式：甲 |> 乙"""
        # 检查右侧是否是宏（通过标识符查找）
        if isinstance(expr.right, Identifier):
            from ..macros.registry import find_macro

            macro_info = find_macro(expr.right.name)
            if macro_info:
                # 对于宏，我们需要保留左侧的 AST 节点原样传递，不进行求值
                from ..ast_nodes import MacroCall

                macro_call = MacroCall(name=expr.right.name, arguments=[expr.left])
                return self.eval_macro_call(macro_call, env)

        # 对于其他情况，继续正常的求值流程
        left_val = self.eval_expression(expr.left, env)

        if isinstance(expr.right, FunctionCall):
            callee = self.eval_expression(expr.right.callee, env)
            args = [left_val] + [
                self.eval_expression(a, env) for a in expr.right.arguments
            ]
            kwargs = {
                k: self.eval_expression(v, env)
                for k, v in expr.right.keyword_args.items()
            }

            if isinstance(callee, DaoClass):
                return self._instantiate_class(callee, args, kwargs, expr)
            if isinstance(callee, BoundMethod):
                return self._call_method(
                    callee.instance, callee.method, args, kwargs, expr
                )
            if isinstance(callee, BuiltinFunction):
                return callee.call(args, kwargs)
            if isinstance(callee, InterpreterBuiltin):
                return callee.call(args, kwargs)
            if isinstance(callee, DaoFunction):
                return self._call_dao_function(callee, args, kwargs, expr)
            raise 类型错误("管道右侧必须是函数", expr.line, expr.column, self.source)

        # 检查右侧是否是宏（通过标识符查找）
        if isinstance(expr.right, Identifier):
            from ..macros.registry import find_macro

            macro_info = find_macro(expr.right.name)
            if macro_info:
                # 创建宏调用表达式
                from ..ast_nodes import MacroCall

                macro_call = MacroCall(name=expr.right.name, arguments=[left_val])
                return self.eval_macro_call(macro_call, env)

        callee = self.eval_expression(expr.right, env)
        if isinstance(callee, DaoCallable) or isinstance(callee, DaoClass):
            return self.call_function(callee, [left_val])

        raise 类型错误(
            "管道运算符 |> 右侧必须是函数", expr.line, expr.column, self.source
        )

    # ========================
    # 并发编程相关表达式求值
    # ========================

    def eval_await(self, expr: AwaitExpr, env: Environment) -> object:
        """求值等待表达式"""
        from ..builtins.callables import DaoAsyncFunction
        from ..interpreter.concurrency import ConcurrencyEvaluator

        value = self.eval_expression(expr.expression, env)

        # 如果是异步函数对象，直接调用
        if isinstance(value, DaoAsyncFunction):
            concurrency_eval = ConcurrencyEvaluator()
            return concurrency_eval.run_async(
                concurrency_eval.eval_async_function_call(value, [], {})
            )

        # 如果是可调用对象，先调用再等待
        if hasattr(value, "__call__"):
            result = value()
            return self._handle_await_result(result)

        return self._handle_await_result(value)

    def eval_await_all(self, expr: AwaitAllExpr, env: Environment) -> object:
        """求值全部等待表达式"""
        tasks = [self.eval_expression(e, env) for e in expr.expressions]

        # 返回 coroutine，让调用者来运行它
        return self._run_all(tasks)

    async def _run_all(self, tasks):
        """运行所有任务并返回结果（内部辅助方法）"""
        import asyncio
        from asyncio import gather

        coros = []
        for task in tasks:
            if hasattr(task, "__call__"):
                coros.append(task())
            elif hasattr(task, "__await__"):
                coros.append(task)
            else:
                coros.append(self._wrap_in_coroutine(task))
        return await gather(*coros)

    async def _wrap_in_coroutine(self, result):
        """将结果包装在协程中（内部辅助方法）"""
        import asyncio

        await asyncio.sleep(0)
        return result

    def eval_await_race(self, expr: AwaitRaceExpr, env: Environment) -> object:
        """求值竞速等待表达式"""
        tasks = [self.eval_expression(e, env) for e in expr.expressions]

        # 返回 coroutine，让调用者来运行它
        return self._run_race(tasks)

    async def _run_race(self, tasks):
        """运行所有任务，返回第一个完成的结果（内部辅助方法）"""
        import asyncio
        from asyncio import FIRST_COMPLETED, wait

        coros = []
        for task in tasks:
            if hasattr(task, "__call__"):
                coros.append(task())
            elif hasattr(task, "__await__"):
                coros.append(task)
            else:
                coros.append(self._wrap_in_coroutine(task))

        # 明确地创建任务对象
        task_objects = []
        loop = asyncio.get_running_loop()
        for coro in coros:
            task_objects.append(loop.create_task(coro))

        done, pending = await wait(task_objects, return_when=FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        return next(iter(done)).result()

    def eval_channel(self, expr: ChannelExpr, env: Environment) -> object:
        """求值通道表达式"""
        from ..interpreter.concurrency import BufferedChannel, Channel

        if expr.capacity:
            return BufferedChannel(int(expr.capacity))
        return Channel()

    def eval_receive(self, expr: ReceiveExpr, env: Environment) -> object:
        """求值接收表达式"""
        channel = self.eval_expression(expr.channel, env)
        from ..interpreter.concurrency import BufferedChannel, Channel

        if isinstance(channel, (Channel, BufferedChannel)):
            return channel.receive()
        raise 类型错误(
            f"对象 '{channel}' 不是一个有效的通道", expr.line, expr.column, self.source
        )

    def eval_logic_query(self, expr: LogicQuery, env: Environment) -> object:
        """求值逻辑查询：查询(知识库, 目标)"""
        from ..ast_nodes import FunctionCall
        from ..logic.core import LogicStruct, normalize_term
        from ..logic.solver import Solver

        # 获取知识库
        if isinstance(expr.knowledge_base, str):
            kb = env.get(expr.knowledge_base)
        else:
            kb = self.eval_expression(expr.knowledge_base, env)

        # 求值查询目标
        goal = expr.goal
        if isinstance(goal, FunctionCall):
            # 如果是函数调用，解析为逻辑谓词
            predicate_name = goal.callee.name
            evaluated_args = [self.eval_expression(arg, env) for arg in goal.arguments]
            normalized_args = [normalize_term(arg) for arg in evaluated_args]
            normalized_goal = LogicStruct(predicate_name, normalized_args)
        else:
            # 否则直接求值
            goal_value = self.eval_expression(goal, env)
            normalized_goal = normalize_term(goal_value)

        # 创建求解器
        solver = Solver(kb)
        # 求解查询
        results = solver.solve(normalized_goal)
        # 将结果转换为字典列表
        return [result.to_dict() for result in results]

    def eval_logic_variable(self, expr: LogicVariable, env: Environment) -> object:
        """求值逻辑变量：?变量名"""
        from ..logic.core import LogicVariable

        return LogicVariable(expr.name)

    def eval_logic_predicate(self, expr: LogicPredicate, env: Environment) -> object:
        """求值逻辑谓词：谓词(?x, ?y)"""
        from ..logic.core import LogicStruct, normalize_term

        # 求值谓词参数
        evaluated_args = [self.eval_expression(arg, env) for arg in expr.arguments]
        normalized_args = [normalize_term(arg) for arg in evaluated_args]
        return LogicStruct(expr.predicate, normalized_args)

    def eval_logic_negation(self, expr: LogicNegation, env: Environment) -> object:
        """求值逻辑否定：非 已封禁(?用户)"""
        from ..logic.core import normalize_term
        from ..logic.solver import Solver

        # 求值被否定的表达式
        negated_expr = self.eval_expression(expr.expression, env)
        normalized_negated = normalize_term(negated_expr)

        # 这里我们需要上下文信息来知道当前的知识库，
        # 暂时返回否定表达式本身，由求解器处理
        return ("非", normalized_negated)

    def eval_logic_cut(self, expr: LogicCut, env: Environment) -> object:
        """求值剪枝操作符：剪枝"""
        return "剪枝"

    def eval_logic_constraint(self, expr: LogicConstraint, env: Environment) -> object:
        """求值约束表达式：?x 在范围 1..10"""
        return ("约束", expr.variable, expr.operator, expr.bounds)

    def _handle_await_result(self, result):
        """处理等待的结果"""
        if hasattr(result, "__await__"):
            # 检查事件循环是否已经在运行
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                # 事件循环正在运行，直接返回 coroutine，让调用者来等待
                return result
            except RuntimeError:
                # 如果事件循环没有在运行，创建一个新的
                from ..interpreter.concurrency import ConcurrencyEvaluator

                concurrency_eval = ConcurrencyEvaluator()
                return concurrency_eval.run_async(result)
        return result
