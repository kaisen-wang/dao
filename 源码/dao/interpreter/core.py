"""
核心解释器
=========

Interpreter 类：组合 StatementExecutor 和 ExpressionEvaluator 混入，
提供初始化、执行入口和核心辅助方法。
"""

from ..ast_nodes import Program
from ..environment import Environment
from ..builtins import (
    DaoCallable,
    DaoFunction,
    BuiltinFunction,
    InterpreterBuiltin,
    DaoClass,
    DaoInstance,
    BoundMethod,
    SuperProxy,
    CurriedFunction,
    DaoGenerator,
    get_builtins,
    get_interpreter_builtins,
)
from ..errors import 运行时错误, 类型错误, 返回信号, 产出信号
from .statements import StatementExecutor
from .expressions import ExpressionEvaluator


class Interpreter(StatementExecutor, ExpressionEvaluator):
    """
    "道"语言树遍历解释器

    组合了 StatementExecutor（语句执行）和 ExpressionEvaluator（表达式求值），
    并提供核心辅助方法。

    使用方法：
        interpreter = Interpreter()
        interpreter.execute(ast)
    """

    def __init__(self):
        # 创建全局环境，注入内置函数
        self.global_env = Environment()

        for name, func in get_builtins().items():
            self.global_env.define(name, func)

        for name, func in get_interpreter_builtins().items():
            func.interpreter = self
            self.global_env.define(name, func)

    def execute(
        self, program: Program, env: Environment | None = None, source: str = ""
    ) -> object:
        """
        执行程序

        参数：
            program : AST 根节点
            env     : 执行环境（默认全局环境）
            source  : 原始源代码（用于错误报告）
        返回：最后一条语句的值
        """
        self.source = source
        env = env or self.global_env
        result = None
        try:
            for stmt in program.statements:
                result = self.exec_statement(stmt, env)
        except 运行时错误 as e:
            # 在全局层面，确保调用栈信息被保留
            if not hasattr(e, "stack") or not e.stack:
                e.stack = env.get_stack()
            raise
        return result

    def call_function(self, func, args, kwargs=None):
        """
        统一的函数调用接口（供高阶内置函数使用）
        """
        kwargs = kwargs or {}

        if isinstance(func, BuiltinFunction):
            return func.call(args, kwargs)

        if isinstance(func, InterpreterBuiltin):
            return func.call(args, kwargs)

        if isinstance(func, DaoFunction):
            return self._call_dao_function(func, args, kwargs, None)

        if isinstance(func, CurriedFunction):
            return func.call(args, kwargs)

        if isinstance(func, BoundMethod):
            return self._call_method(func.instance, func.method, args, kwargs, None)

        if isinstance(func, DaoClass):
            return self._instantiate_class(func, args, kwargs, None)

        raise 类型错误(f"'{func}' 不是可调用的函数", 0, 0, self.source)

    # ========================
    # OOP 核心方法
    # ========================

    def _instantiate_class(
        self, klass: DaoClass, args: list, kwargs: dict, call_expr
    ) -> DaoInstance:
        """创建类型实例"""
        instance = DaoInstance(klass)

        init_method = klass.find_method("初始化")
        if init_method:
            self._call_method(instance, init_method, args, kwargs, call_expr)
        elif args:
            line = call_expr.line if call_expr else 0
            col = call_expr.column if call_expr else 0
            raise 运行时错误(
                f"类型 '{klass.name}' 没有构造函数，不接受参数", line, col, self.source
            )

        return instance

    def _call_method(
        self,
        instance: DaoInstance,
        method: DaoFunction,
        args: list,
        kwargs: dict,
        call_expr,
    ) -> object:
        """调用实例方法（绑定 本对象）"""
        func_env = method.closure_env.create_child()
        func_env.define("本对象", instance)

        if instance.klass.parent:
            func_env.define("父对象", SuperProxy(instance, instance.klass.parent))

        self._bind_params(method, args, kwargs, func_env, call_expr)

        line = call_expr.line if call_expr else 0
        file = getattr(call_expr, "file", "") if call_expr else ""
        func_env.push_frame(f"{instance.klass.name}.{method.name}", file, line)

        try:
            self._exec_block(method.body, func_env)
        except 返回信号 as ret:
            func_env.pop_frame()
            return ret.value
        except 运行时错误 as e:
            # 如果错误已经有栈信息，直接重新抛出
            if hasattr(e, "stack") and e.stack:
                func_env.pop_frame()
                raise

            # 重新创建错误，包含调用栈信息
            new_error = 运行时错误(
                e.message,
                e.line,
                e.column,
                getattr(e, "source", getattr(self, "source", "")),
                func_env.get_stack(),
            )
            func_env.pop_frame()
            raise new_error
        except Exception as e:
            # 对于非道语言异常，创建运行时错误包装
            new_error = 运行时错误(
                str(e), 0, 0, getattr(self, "source", ""), func_env.get_stack()
            )
            func_env.pop_frame()
            raise new_error
        finally:
            if func_env.current_frame:
                func_env.pop_frame()

        return None

    # ========================
    # 辅助方法
    # ========================

    def _call_dao_function(
        self, func: DaoFunction, args: list, kwargs: dict, call_expr
    ) -> object:
        """调用用户自定义函数"""
        func_env = func.closure_env.create_child()
        self._bind_params(func, args, kwargs, func_env, call_expr)

        line = call_expr.line if call_expr else 0
        file = getattr(call_expr, "file", "") if call_expr else ""
        func_env.push_frame(func.name, file, line)

        try:
            self._exec_block(func.body, func_env)
        except 产出信号 as e:
            func_env.pop_frame()
            return DaoGenerator(func, args, kwargs, self)
        except 返回信号 as ret:
            func_env.pop_frame()
            return ret.value
        except 运行时错误 as e:
            # 如果错误已经有栈信息，说明是从下层传递上来的，直接重新抛出
            # 没有栈信息才创建新的错误并附加调用栈
            if hasattr(e, "stack") and e.stack:
                func_env.pop_frame()
                raise

            # 重新创建错误，包含调用栈信息
            new_error = 运行时错误(
                e.message,
                e.line,
                e.column,
                getattr(e, "source", getattr(self, "source", "")),
                func_env.get_stack(),
            )
            func_env.pop_frame()
            raise new_error
        except Exception as e:
            # 对于非道语言异常，创建运行时错误包装
            new_error = 运行时错误(
                str(e), 0, 0, getattr(self, "source", ""), func_env.get_stack()
            )
            func_env.pop_frame()
            raise new_error
        finally:
            if func_env.current_frame:
                func_env.pop_frame()

        return None

    def _bind_params(
        self, func: DaoFunction, args: list, kwargs: dict, env: Environment, call_expr
    ) -> None:
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
                    f"函数 '{func.name}' 缺少参数 '{param}'", line, col, self.source
                )

    def _exec_block(self, statements: list, env: Environment) -> object:
        """执行一个代码块"""
        result = None
        for stmt in statements:
            result = self.exec_statement(stmt, env)
        return result

    @staticmethod
    def _in_method_context(env: Environment, klass: DaoClass) -> bool:
        """检查当前是否在指定类的方法内部（通过是否有 本对象 绑定判断）"""
        try:
            self_obj = env.get("本对象")
            if isinstance(self_obj, DaoInstance):
                # 检查是否是同一个类或其子类
                k = self_obj.klass
                while k:
                    if k is klass:
                        return True
                    k = k.parent
            return False
        except Exception:
            return False

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
