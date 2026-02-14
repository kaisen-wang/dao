"""
语句执行混入
===========

包含所有 exec_* 方法，负责执行"道"语言的语句节点。
通过 Python mixin 模式，在运行时与 Interpreter 组合。
"""

from ..ast_nodes import *
from ..builtins import (
    BoundMethod,
    BuiltinFunction,
    DaoClass,
    DaoFunction,
    DaoInstance,
    InterpreterBuiltin,
    SuperProxy,
    get_builtins,
    get_interpreter_builtins,
)
from ..builtins.oop_types import DaoError, DaoTrait
from ..environment import Environment
from ..errors import (
    产出信号,
    名称错误,
    断言失败,
    类型错误,
    继续信号,
    跳出信号,
    运行时错误,
    返回信号,
)


class DaoEnum:
    """枚举类型"""

    def __init__(self, name: str, values: list[str]):
        self.name = name
        self.values = values
        self.value_indices = {v: i for i, v in enumerate(values)}

    def __getitem__(self, value: str):
        """获取枚举值的索引"""
        if value not in self.value_indices:
            raise 运行时错误(f"枚举 '{self.name}' 中不存在值 '{value}'")
        return self.value_indices[value]

    def __contains__(self, value: str) -> bool:
        """检查值是否在枚举中"""
        return value in self.value_indices

    def __repr__(self) -> str:
        return f"<枚举 {self.name}>"


class StatementExecutor:
    """语句执行方法集（混入类）"""

    def _has_yield(self, statements: list) -> bool:
        """检测语句列表中是否包含产出语句"""
        from ..ast_nodes import (
            ForInStmt,
            ForRangeStmt,
            IfStmt,
            TryStmt,
            WhileStmt,
            YieldStmt,
        )

        for stmt in statements:
            if isinstance(stmt, YieldStmt):
                return True
            elif isinstance(stmt, ForInStmt) or isinstance(stmt, ForRangeStmt):
                if self._has_yield(stmt.body):
                    return True
            elif isinstance(stmt, WhileStmt):
                if self._has_yield(stmt.body):
                    return True
            elif isinstance(stmt, IfStmt):
                if self._has_yield(stmt.body):
                    return True
                for _, elif_body in stmt.elif_clauses:
                    if self._has_yield(elif_body):
                        return True
                if stmt.else_body and self._has_yield(stmt.else_body):
                    return True
            elif isinstance(stmt, TryStmt):
                if self._has_yield(stmt.try_body):
                    return True
                if stmt.catch_body and self._has_yield(stmt.catch_body):
                    return True
                if stmt.finally_body and self._has_yield(stmt.finally_body):
                    return True
        return False

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
            case AsyncFunctionDecl():
                return self.exec_async_function_decl(stmt, env)
            case ReturnStmt():
                return self.exec_return(stmt, env)
            case YieldStmt():
                return self.exec_yield(stmt, env)
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
            case AbstractDecl():
                return self.exec_abstract_decl(stmt, env)
            case EnumDecl():
                return self.exec_enum_decl(stmt, env)
            case TraitDecl():
                return self.exec_trait_decl(stmt, env)
            case ExportStmt():
                return self.exec_export(stmt, env)
            case MatchStmt():
                return self.exec_match(stmt, env)
            case ImportStmt():
                return self.exec_import(stmt, env)
            case DestructureAssign():
                return self.exec_destructure(stmt, env)
            case ParallelStmt():
                return self.exec_parallel_stmt(stmt, env)
            case SendStmt():
                return self.exec_send_stmt(stmt, env)
            case SelectStmt():
                return self.exec_select_stmt(stmt, env)
            case SyncStmt():
                return self.exec_sync_stmt(stmt, env)
            case LogicBlock():
                return self.exec_logic_block(stmt, env)
            case _:
                raise 运行时错误(
                    f"未知的语句类型: {type(stmt).__name__}",
                    stmt.line,
                    stmt.column,
                    self.source,
                )

    # ========================
    # 基础语句
    # ========================

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
                # 先检查是否有 property setter
                setter_name = f"设置{stmt.target.member}"
                setter = obj.klass.find_method(setter_name)
                if setter and setter.is_setter:
                    self._call_method(obj, setter, [value], {}, stmt)
                    return

                obj.set_field(stmt.target.member, value)
            elif isinstance(obj, dict):
                obj[stmt.target.member] = value
            elif hasattr(obj, "set_field"):
                # 处理 ErrorInstanceWrapper 类型的对象
                obj.set_field(stmt.target.member, value)
            elif hasattr(obj, "__setattr__"):
                # 处理其他具有 __setattr__ 方法的对象
                setattr(obj, stmt.target.member, value)
            else:
                raise 类型错误(
                    f"无法给类型 '{type(obj).__name__}' 设置属性",
                    stmt.line,
                    stmt.column,
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
                    f"无法给类型 '{type(obj, 0, 0, self.source).__name__}' 设置索引",
                    stmt.line,
                    stmt.column,
                )
        else:
            raise 运行时错误("无效的赋值目标", stmt.line, stmt.column, self.source)

    def exec_function_decl(self, stmt: FunctionDecl, env: Environment) -> None:
        """执行函数声明"""
        func = DaoFunction(
            name=stmt.name,
            params=stmt.params,
            default_values={
                k: self.eval_expression(v, env) for k, v in stmt.default_values.items()
            },
            body=stmt.body,
            closure_env=env,
            is_generator=self._has_yield(stmt.body),
        )
        env.define(stmt.name, func)

    def exec_async_function_decl(
        self, stmt: AsyncFunctionDecl, env: Environment
    ) -> None:
        """执行异步函数声明"""
        from ..builtins.callables import DaoAsyncFunction

        func = DaoAsyncFunction(
            name=stmt.name,
            params=stmt.params,
            body=stmt.body,
            closure_env=env,
            default_values={
                k: self.eval_expression(v, env) for k, v in stmt.default_values.items()
            },
            is_static=stmt.is_static,
            is_private=stmt.is_private,
        )
        env.define(stmt.name, func)

    def exec_return(self, stmt: ReturnStmt, env: Environment) -> None:
        """执行返回语句"""
        value = None
        if stmt.value is not None:
            value = self.eval_expression(stmt.value, env)
        raise 返回信号(value)

    def exec_yield(self, stmt: YieldStmt, env: Environment) -> None:
        """执行产出语句"""
        value = None
        if stmt.value is not None:
            value = self.eval_expression(stmt.value, env)
        raise 产出信号(value)

    # ========================
    # 控制流
    # ========================

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
        if not hasattr(iterable, "__iter__"):
            raise 类型错误(
                f"类型 '{type(iterable).__name__}' 不可遍历",
                stmt.line,
                stmt.column,
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

    # ========================
    # 错误处理
    # ========================

    def exec_try(self, stmt: TryStmt, env: Environment) -> object:
        """执行尝试-捕获-最终"""
        try:
            return self._exec_block(stmt.try_body, env)
        except Exception as e:
            # 检查每个捕获块
            for catch in stmt.catches:
                should_catch = False
                error_type = catch.get("error_type")
                catch_var = catch.get("catch_var")
                catch_body = catch.get("catch_body")

                # 如果指定了错误类型，检查异常是否匹配
                if error_type:
                    if error_type == "异常":
                        # '异常' 类型表示捕获所有类型的错误
                        should_catch = True
                    else:
                        # 其他类型需要在环境中查找
                        error_class = env.get(error_type)
                        # 对于 DaoError 类型，检查 e.类型 == error_class
                        if isinstance(e, DaoError):
                            should_catch = e.类型 == error_class
                        else:
                            # 对于 Python 异常，检查 isinstance
                            should_catch = isinstance(e, error_class)
                else:
                    # 没有指定错误类型，捕获所有异常
                    should_catch = True

                if should_catch and catch_body:
                    catch_env = env.create_child()
                    if catch_var:
                        # 对于 DaoError 及其子类，使用异常对象本身
                        if isinstance(e, DaoError):
                            catch_env.define(catch_var, e)
                        else:
                            # 对于 Python 异常，创建错误信息字典
                            catch_env.define(
                                catch_var,
                                {
                                    "信息": str(e),
                                    "行": getattr(e, "line", 0),
                                    "列": getattr(e, "column", 0),
                                },
                            )
                    return self._exec_block(catch_body, catch_env)

            # 没有匹配到任何捕获块，重新抛出异常
            raise
        finally:
            if stmt.finally_body:
                self._exec_block(stmt.finally_body, env)

    def exec_throw(self, stmt: ThrowStmt, env: Environment) -> None:
        """执行抛出语句"""
        value = self.eval_expression(stmt.expression, env)
        if isinstance(value, str):
            raise 运行时错误(value, stmt.line, stmt.column, self.source)
        # 检查是否是 DaoError 子类的实例
        from ..builtins.oop_types import DaoError

        if isinstance(value, DaoError):
            raise value
        else:
            raise 运行时错误(str(value), stmt.line, stmt.column, self.source)

    def exec_assert(self, stmt: AssertStmt, env: Environment) -> None:
        """执行断言语句"""
        condition = self.eval_expression(stmt.condition, env)
        if not self._is_truthy(condition):
            msg = "断言失败"
            if stmt.message:
                msg = str(self.eval_expression(stmt.message, env))
            raise 断言失败(msg, stmt.line, stmt.column, self.source)

    # ========================
    # OOP 执行
    # ========================

    def exec_enum_decl(self, stmt: EnumDecl, env: Environment) -> None:
        """执行枚举声明"""
        enum_obj = DaoEnum(stmt.name, stmt.values)
        env.define(stmt.name, enum_obj)

    def exec_trait_decl(self, stmt: TraitDecl, env: Environment) -> None:
        """执行特征声明"""
        methods = {}
        static_methods = {}
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
                    is_generator=self._has_yield(s.body),
                )
                if s.is_static:
                    static_methods[s.name] = func
                else:
                    methods[s.name] = func

        trait = DaoTrait(name=stmt.name, methods=methods, static_methods=static_methods)
        env.define(stmt.name, trait)

    def exec_abstract_decl(self, stmt: AbstractDecl, env: Environment) -> None:
        """执行抽象类型声明"""
        # 将 AbstractDecl 转换为 ClassDecl 并执行
        class_stmt = ClassDecl(
            name=stmt.name,
            parent_name=stmt.parent_name,
            implemented_traits=[],
            body=stmt.body,
            line=stmt.line,
            column=stmt.column,
            is_error_class=False,
            is_abstract=True,
        )
        self.exec_class_decl(class_stmt, env)

    def exec_class_decl(self, stmt: ClassDecl, env: Environment) -> None:
        """执行类型声明"""
        from ..builtins.oop_types import DaoError

        parent = None
        is_error_class = False
        if stmt.parent_name:
            # 检查是否继承自 DaoError（自定义异常类型）
            if stmt.parent_name == "错误":
                is_error_class = True
                parent = DaoError
            else:
                parent = env.get(stmt.parent_name)
                # 检查是否继承自 DaoError（自定义异常类型）
                # 需要检查 parent 是否是 DaoClass 且继承自 DaoError，或者本身就是 DaoError
                if isinstance(parent, DaoClass):
                    # 检查继承链是否包含 DaoError
                    check_parent = parent
                    while check_parent:
                        if check_parent == DaoError:
                            is_error_class = True
                            break
                        check_parent = check_parent.parent
                elif parent == DaoError:
                    is_error_class = True
                elif not isinstance(parent, DaoClass):
                    raise 类型错误(
                        f"'{stmt.parent_name}' 不是一个类型，无法继承",
                        stmt.line,
                        stmt.column,
                        self.source,
                    )

        methods = {}
        static_methods = {}
        private_names = set()
        abstract_methods = set()
        for s in stmt.body:
            if isinstance(s, FunctionDecl):
                if s.is_abstract:
                    # 抽象方法不需要定义体
                    abstract_methods.add(s.name)
                    func = DaoFunction(
                        name=s.name,
                        params=s.params,
                        default_values={
                            k: self.eval_expression(v, env)
                            for k, v in s.default_values.items()
                        },
                        body=[],  # 抽象方法没有方法体
                        closure_env=env,
                        is_generator=False,
                    )
                else:
                    func = DaoFunction(
                        name=s.name,
                        params=s.params,
                        default_values={
                            k: self.eval_expression(v, env)
                            for k, v in s.default_values.items()
                        },
                        body=s.body,
                        closure_env=env,
                        is_generator=self._has_yield(s.body),
                        is_getter=s.is_getter,
                        is_setter=s.is_setter,
                    )
                if s.is_private:
                    private_names.add(s.name)
                if s.is_static:
                    static_methods[s.name] = func
                else:
                    methods[s.name] = func

        # 检查是否必须实现父类的所有抽象方法（仅对具体类进行检查）
        if parent and isinstance(parent, DaoClass) and not stmt.is_abstract:
            for abstract_method in parent.abstract_methods:
                if abstract_method not in methods:
                    raise 类型错误(
                        f"类型 '{stmt.name}' 必须实现父类 '{parent.name}' 的抽象方法 '{abstract_method}'",
                        stmt.line,
                        stmt.column,
                        self.source,
                    )

        implemented_traits = []
        for trait_name in stmt.implemented_traits:
            trait_obj = env.get(trait_name)
            if not isinstance(trait_obj, DaoTrait):
                raise 类型错误(
                    f"'{trait_name}' 不是一个特征",
                    stmt.line,
                    stmt.column,
                    self.source,
                )

            for method_name in trait_obj.methods:
                if method_name not in methods and (
                    not parent or not parent.find_method(method_name)
                ):
                    raise 类型错误(
                        f"类型 '{stmt.name}' 必须实现特征 '{trait_name}' 中的方法 '{method_name}'",
                        stmt.line,
                        stmt.column,
                        self.source,
                    )

            implemented_traits.append(trait_obj)

        # 如果是错误类，创建 DaoError 的子类
        if is_error_class:
            # 所有错误类都创建为普通的 DaoClass，这样它们可以被正常继承
            klass = DaoClass(
                name=stmt.name,
                parent=DaoError,
                methods=methods,
                static_methods=static_methods,
                private_names=private_names,
                implemented_traits=implemented_traits,
                is_abstract=stmt.is_abstract,
                abstract_methods=abstract_methods,
            )
            env.define(stmt.name, klass)
        else:
            klass = DaoClass(
                name=stmt.name,
                parent=parent,
                methods=methods,
                static_methods=static_methods,
                private_names=private_names,
                implemented_traits=implemented_traits,
                is_abstract=stmt.is_abstract,
                abstract_methods=abstract_methods,
            )
            env.define(stmt.name, klass)

    # ========================
    # 模式匹配
    # ========================

    def exec_match(self, stmt: MatchStmt, env: Environment) -> object:
        """执行匹配语句"""
        subject = self.eval_expression(stmt.subject, env)

        for case in stmt.cases:
            # 为每个 case 创建子环境，避免变量冲突
            case_env = env.create_child()

            # 通配符匹配任何值（应该在最后作为默认分支）
            if case.is_wildcard:
                if case.guard:
                    if not self._is_truthy(self.eval_expression(case.guard, case_env)):
                        continue
                return self._exec_block(case.body, case_env)

            # 检查模式是否匹配
            match_result = self._match_pattern(case.pattern, subject, case_env)
            if match_result:
                if case.guard:
                    if not self._is_truthy(self.eval_expression(case.guard, case_env)):
                        continue
                return self._exec_block(case.body, case_env)

        return None

    def _match_pattern(self, pattern, subject, env: Environment) -> bool:
        """匹配模式与主体"""
        from ..ast_nodes import DictPattern, Identifier, ListPattern

        # 列表模式
        if isinstance(pattern, ListPattern):
            if not isinstance(subject, list):
                return False

            if len(pattern.elements) > len(subject):
                return False

            # 处理展开操作符 ...rest
            if pattern.has_spread:
                # 最后一个元素是展开变量，不参与前面的匹配
                num_fixed = len(pattern.elements) - 1
                if len(subject) < num_fixed:
                    return False

                # 匹配前面的固定元素
                for i in range(num_fixed):
                    elem = pattern.elements[i]
                    if isinstance(elem, Identifier) and elem.name == "_":
                        continue  # 通配符，跳过
                    elif isinstance(elem, Identifier):
                        env.define(elem.name, subject[i])
                    else:
                        # 字面量比较
                        pattern_val = self.eval_expression(elem, env)
                        if pattern_val != subject[i]:
                            return False

                # 将剩余元素绑定到展开变量
                rest = subject[num_fixed:]
                spread_var = pattern.elements[-1]
                if isinstance(spread_var, Identifier):
                    rest_name = spread_var.name
                    if rest_name != "_":
                        env.define(rest_name, rest)
                return True
            else:
                # 匹配所有元素
                for i, elem in enumerate(pattern.elements):
                    if isinstance(elem, Identifier) and elem.name == "_":
                        continue  # 通配符，跳过
                    elif isinstance(elem, Identifier):
                        env.define(elem.name, subject[i])
                    else:
                        # 字面量比较
                        pattern_val = self.eval_expression(elem, env)
                        if pattern_val != subject[i]:
                            return False

                if len(subject) != len(pattern.elements):
                    return False

                return True

        # 字典模式
        elif isinstance(pattern, DictPattern):
            if not isinstance(subject, dict):
                return False

            for key_expr, value_expr in pattern.pairs:
                key = self.eval_expression(key_expr, env)
                if key not in subject:
                    return False

                if isinstance(value_expr, Identifier) and value_expr.name == "_":
                    continue  # 通配符
                elif isinstance(value_expr, Identifier):
                    env.define(value_expr.name, subject[key])
                else:
                    # 字面量比较
                    pattern_val = self.eval_expression(value_expr, env)
                    if pattern_val != subject[key]:
                        return False

            return True

        # 简单值模式（字面量或标识符）
        else:
            if isinstance(pattern, Identifier) and pattern.name == "_":
                return True  # 通配符匹配任何值
            elif isinstance(pattern, Identifier):
                env.define(pattern.name, subject)
                return True
            else:
                pattern_val = self.eval_expression(pattern, env)
                return pattern_val == subject

    # ========================
    # 导入和导出
    # ========================

    def exec_export(self, stmt: ExportStmt, env: Environment) -> None:
        """执行导出语句：标记要导出的变量名"""
        env.exports = stmt.names

    def exec_import(self, stmt: ImportStmt, env: Environment) -> None:
        """执行导入语句"""
        import os

        module_path = stmt.module_path.replace(".", os.sep) + ".道"

        if not os.path.exists(module_path):
            raise 运行时错误(
                f"模块 '{stmt.module_path}' 不存在 (找不到文件: {module_path}, 0, 0, self.source)",
                stmt.line,
                stmt.column,
            )

        with open(module_path, "r", encoding="utf-8") as f:
            source = f.read()

        from ..lexer import Lexer
        from ..parser import Parser

        lexer = Lexer(source, module_path)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        module_env = Environment()
        for name, func in get_builtins().items():
            module_env.define(name, func)
        for name, func in get_interpreter_builtins().items():
            func.interpreter = self
            module_env.define(name, func)

        self.execute(ast, module_env)

        # 根据导出列表过滤变量
        if module_env.exports:
            # 如果模块有导出列表，只导出指定的变量
            exported_vars = {}
            for name in module_env.exports:
                if name in module_env.values:
                    exported_vars[name] = module_env.values[name]
            module_env.values = exported_vars

        if stmt.is_from_import:
            # "从 模块 导入 {项}" 语法：直接将项导入当前环境
            for name in stmt.names:
                if name not in module_env.values:
                    raise 运行时错误(
                        f"模块 '{stmt.module_path}' 中没有导出 '{name}'",
                        stmt.line,
                        stmt.column,
                        self.source,
                    )
                env.define(name, module_env.values[name])
        else:
            # 普通 "导入 模块" 语法：将模块作为字典导入
            alias = stmt.alias or stmt.module_path.split(".")[-1]
            module_dict = {}
            for name, value in module_env.values.items():
                if not isinstance(value, (BuiltinFunction, InterpreterBuiltin)):
                    module_dict[name] = value

            env.define(alias, module_dict)

    # ========================
    # 解构赋值
    # ========================

    def exec_logic_block(self, stmt: LogicBlock, env: Environment) -> None:
        """执行逻辑块：创建知识库并添加事实和规则"""
        from ..logic.core import KnowledgeBase, LogicStruct, normalize_term
        from ..logic.solver import Solver

        # 创建知识库
        kb = KnowledgeBase(stmt.name)

        # 添加事实
        for fact in stmt.facts:
            # 求值事实的参数
            evaluated_args = [self.eval_expression(arg, env) for arg in fact.arguments]
            # 标准化为逻辑项
            normalized_args = [normalize_term(arg) for arg in evaluated_args]
            # 创建逻辑结构
            logic_fact = LogicStruct(fact.predicate, normalized_args)
            kb.add_fact(logic_fact)

        # 添加规则
        for rule in stmt.rules:
            # 求值规则头的参数
            head_args = [self.eval_expression(arg, env) for arg in rule.head.arguments]
            normalized_head_args = [normalize_term(arg) for arg in head_args]
            rule_head = LogicStruct(rule.head.predicate, normalized_head_args)

            # 解析规则体，不进行求值
            rule_body = []
            for body_expr in rule.body:
                if isinstance(body_expr, FunctionCall):
                    # 解析函数调用作为逻辑事实
                    predicate = body_expr.callee.name
                    body_args = []
                    for arg in body_expr.arguments:
                        if isinstance(arg, Identifier) and arg.name.startswith("?"):
                            from ..logic.core import LogicVariable

                            body_args.append(LogicVariable(arg.name))
                        elif isinstance(arg, StringLiteral):
                            from ..logic.core import LogicAtom

                            body_args.append(LogicAtom(arg.value))
                        elif isinstance(arg, NumberLiteral):
                            from ..logic.core import LogicAtom

                            body_args.append(LogicAtom(arg.value))
                        elif isinstance(arg, BooleanLiteral):
                            from ..logic.core import LogicAtom

                            body_args.append(LogicAtom(arg.value))
                        elif isinstance(arg, ListLiteral):
                            from ..logic.core import LogicAtom

                            elements = [
                                self.eval_expression(e, env) for e in arg.elements
                            ]
                            body_args.append(LogicAtom(elements))
                        elif isinstance(arg, DictLiteral):
                            from ..logic.core import LogicAtom

                            pairs = {
                                self.eval_expression(k, env): self.eval_expression(
                                    v, env
                                )
                                for k, v in arg.pairs
                            }
                            body_args.append(LogicAtom(pairs))
                    rule_body.append(LogicStruct(predicate, body_args))
                elif isinstance(body_expr, LogicFact):
                    body_args = []
                    for arg in body_expr.arguments:
                        if isinstance(arg, Identifier) and arg.name.startswith("?"):
                            from ..logic.core import LogicVariable

                            body_args.append(LogicVariable(arg.name))
                        elif isinstance(arg, StringLiteral):
                            from ..logic.core import LogicAtom

                            body_args.append(LogicAtom(arg.value))
                        elif isinstance(arg, NumberLiteral):
                            from ..logic.core import LogicAtom

                            body_args.append(LogicAtom(arg.value))
                        elif isinstance(arg, BooleanLiteral):
                            from ..logic.core import LogicAtom

                            body_args.append(LogicAtom(arg.value))
                        elif isinstance(arg, ListLiteral):
                            from ..logic.core import LogicAtom

                            elements = [
                                self.eval_expression(e, env) for e in arg.elements
                            ]
                            body_args.append(LogicAtom(elements))
                        elif isinstance(arg, DictLiteral):
                            from ..logic.core import LogicAtom

                            pairs = {
                                self.eval_expression(k, env): self.eval_expression(
                                    v, env
                                )
                                for k, v in arg.pairs
                            }
                            body_args.append(LogicAtom(pairs))
                    rule_body.append(LogicStruct(body_expr.predicate, body_args))

            kb.add_rule(rule_head, rule_body)

        # 将知识库和求解器存入环境中
        solver = Solver(kb)
        env.define(stmt.name, kb)
        env.define(f"{stmt.name}_求解器", solver)

    def exec_destructure(self, stmt, env: Environment) -> None:
        """执行解构赋值"""
        value = self.eval_expression(stmt.value, env)

        if isinstance(value, (list, tuple)):
            if len(stmt.targets) != len(value):
                raise 运行时错误(
                    f"解构赋值：目标数量({len(stmt.targets)})与值的数量({len(value)})不匹配",
                    stmt.line,
                    stmt.column,
                    self.source,
                )
            for name, val in zip(stmt.targets, value):
                if stmt.is_declaration:
                    env.define(name, val)
                elif env.has(name):
                    env.set(name, val)
                else:
                    env.define(name, val)
        elif isinstance(value, dict):
            for name in stmt.targets:
                if name not in value:
                    raise 运行时错误(
                        f"解构赋值：字典中不存在键 '{name}'",
                        stmt.line,
                        stmt.column,
                        self.source,
                    )
                if stmt.is_declaration:
                    env.define(name, value[name])
                elif env.has(name):
                    env.set(name, value[name])
                else:
                    env.define(name, value[name])
        else:
            raise 类型错误(
                f"无法对类型 '{type(value).__name__}' 进行解构赋值",
                stmt.line,
                stmt.column,
                self.source,
            )
