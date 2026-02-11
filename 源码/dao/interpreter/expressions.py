"""
表达式求值混入
=============

包含所有 eval_* 方法，负责求值"道"语言的表达式节点。
通过 Python mixin 模式，在运行时与 Interpreter 组合。
"""

from ..ast_nodes import *
from ..environment import Environment
from ..builtins import (
    DaoCallable, DaoFunction, BuiltinFunction, InterpreterBuiltin,
    DaoClass, DaoInstance, BoundMethod, SuperProxy,
)
from ..errors import 运行时错误, 类型错误, 名称错误, 索引错误


class ExpressionEvaluator:
    """表达式求值方法集（混入类）"""

    def eval_expression(self, expr: Expression, env: Environment) -> object:
        """分派并求值一个表达式"""
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
                raise 运行时错误(f"未知的表达式类型: {type(expr).__name__}",
                    expr.line, expr.column,
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
        return ''.join(result)

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
                    raise 运行时错误(f"无法访问类型 '{obj.klass.name}' 的私有成员 '{expr.member}'",
                        expr.line, expr.column, self.source)
            result = obj.get_field(expr.member)
            if result is not None:
                return result
            raise 名称错误(f"类型 '{obj.klass.name}' 的实例没有属性 '{expr.member}'",
                expr.line, expr.column, self.source)

        if isinstance(obj, SuperProxy):
            method = obj.parent_class.find_method(expr.member)
            if method:
                return BoundMethod(obj.instance, method)
            raise 名称错误(f"父类型中没有方法 '{expr.member}'",
                expr.line, expr.column, self.source)

        if isinstance(obj, DaoClass):
            # 先查找静态方法
            static_method = obj.find_static_method(expr.member)
            if static_method:
                return static_method
            method = obj.find_method(expr.member)
            if method:
                return method
            raise 名称错误(f"类型 '{obj.name}' 没有方法或静态方法 '{expr.member}'",
                expr.line, expr.column, self.source)

        if isinstance(obj, dict) and expr.member in obj:
            return obj[expr.member]

        if isinstance(obj, str):
            return self._get_str_method(obj, expr.member, expr)
        if isinstance(obj, list):
            return self._get_list_method(obj, expr.member, expr)

        raise 名称错误(f"对象没有属性 '{expr.member}'",
            expr.line, expr.column, self.source)

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
            "插入": BuiltinFunction("插入", lambda i, item: lst.insert(int(i), item) or lst),
            "连接": BuiltinFunction("连接", lambda sep="": sep.join(str(x) for x in lst)),
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
                raise 索引错误(f"列表索引 {idx} 超出范围 (长度 {len(obj, 0, 0, self.source)})",
                    expr.line, expr.column,
                )
            return obj[idx]
        elif isinstance(obj, dict):
            if index not in obj:
                raise 名称错误(f"字典中不存在键 '{index}'", expr.line, expr.column, self.source)
            return obj[index]
        elif isinstance(obj, str):
            idx = int(index)
            if idx < -len(obj) or idx >= len(obj):
                raise 索引错误(f"字符串索引 {idx} 超出范围 (长度 {len(obj, 0, 0, self.source)})",
                    expr.line, expr.column,
                )
            return obj[idx]
        else:
            raise 类型错误(f"类型 '{type(obj, 0, 0, self.source).__name__}' 不支持索引访问",
                expr.line, expr.column,
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
                    raise 运行时错误("除零错误", expr.line, expr.column, self.source)
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
                 raise 运行时错误(f"未知的运算符: '{expr.operator}'",
                    expr.line, expr.column, self.source)

    def eval_unary_op(self, expr: UnaryOp, env: Environment) -> object:
        """求值一元运算"""
        operand = self.eval_expression(expr.operand, env)

        match expr.operator:
            case '-':
                return -operand
            case '不是':
                return not self._is_truthy(operand)
            case _:
                 raise 运行时错误(f"未知的一元运算符: '{expr.operator}'",
                    expr.line, expr.column, self.source)

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

        if not isinstance(callee, DaoCallable):
             raise 类型错误(f"'{callee}' 不是一个可调用的函数",
                expr.line, expr.column, self.source)

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
            raise 类型错误("管道右侧必须是函数", expr.line, expr.column, self.source)

        callee = self.eval_expression(expr.right, env)
        if isinstance(callee, DaoCallable) or isinstance(callee, DaoClass):
            return self.call_function(callee, [left_val])

        raise 类型错误("管道运算符 |> 右侧必须是函数",
            expr.line, expr.column, self.source)
