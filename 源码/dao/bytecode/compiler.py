from dataclasses import dataclass, field

from ..ast_nodes import (
    Assignment,
    BinaryOp,
    BooleanLiteral,
    BreakStmt,
    ChannelExpr,
    ClassDecl,
    CompareOp,
    ConditionalExpr,
    ContinueStmt,
    DictLiteral,
    DictPattern,
    EnumDecl,
    EnumVariantPattern,
    ExportStmt,
    Expression,
    ExpressionStmt,
    ForInStmt,
    ForRangeStmt,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStmt,
    ImportStmt,
    IndexAccess,
    LambdaExpr,
    ListLiteral,
    ListPattern,
    MatchStmt,
    MemberAccess,
    NullLiteral,
    NumberLiteral,
    Program,
    ReceiveExpr,
    ReturnStmt,
    SendStmt,
    SetLiteral,
    StringLiteral,
    TraitDecl,
    TupleLiteral,
    TypeCheckPattern,
    UnaryOp,
    VariableDecl,
    WhileStmt,
)
from .code_object import CodeObject
from .opcodes import OpCode


@dataclass
class CompileScope:
    local_names: list[str] = field(default_factory=list)
    upvalue_names: list[str] = field(default_factory=list)
    parent: "CompileScope | None" = None


class BytecodeCompiler:
    def __init__(self):
        self._constant_cache: dict = {}
        self._scope_stack: list[CompileScope] = [CompileScope()]
        self._loop_stack: list[dict] = []  # 循环栈，存储 break/continue 跳转目标
        self._temp_counter: int = 0

    def compile(self, program: Program) -> CodeObject:
        code = CodeObject(name="<module>")
        leaves_value = False
        for i, stmt in enumerate(program.statements):
            is_last = (i == len(program.statements) - 1)
            if is_last and isinstance(stmt, ExpressionStmt):
                # 模块最后一个表达式的值作为整个程序的求值结果
                self._compile_expression(stmt.expression, code)
                leaves_value = True
            elif is_last and isinstance(stmt, VariableDecl):
                # 解释器把变量声明语句的值作为结果返回；复制一份留在栈顶
                self._compile_variable_decl(stmt, code, leave_value=True)
                leaves_value = True
            elif is_last and isinstance(stmt, IfStmt):
                # 条件语句则是分支体的值
                self._compile_if_stmt(stmt, code, leave_value=True)
                leaves_value = True
            else:
                self._compile_statement(stmt, code)
        if not leaves_value:
            # 语句本身不产生值（如赋值、循环、函数声明），RETURN_VALUE 仍需一个操作数
            code.emit(OpCode.LOAD_CONST, self._add_constant(None, code), line=0)
        code.emit(OpCode.RETURN_VALUE, line=0)
        code.local_names = list(self._scope_stack[-1].local_names)
        code.stack_size = self._calculate_stack_size(code)
        return code

    def _compile_statement(self, stmt, code: CodeObject):
        if isinstance(stmt, VariableDecl):
            self._compile_variable_decl(stmt, code)
        elif isinstance(stmt, EnumDecl):
            self._compile_enum_decl(stmt, code)
        elif isinstance(stmt, FunctionDecl):
            self._compile_function_decl(stmt, code)
        elif isinstance(stmt, MatchStmt):
            self._compile_match_stmt(stmt, code)
        elif isinstance(stmt, ImportStmt):
            # 导入/导出语句交由 VM 复用 AST 解释器执行，这里仅把原始节点
            # 放进常量池并发出对应 opcode，不产生任何栈效应。
            idx = self._add_constant(stmt, code)
            code.emit(OpCode.IMPORT_STMT, idx, line=stmt.line)
        elif isinstance(stmt, ExportStmt):
            idx = self._add_constant(stmt, code)
            code.emit(OpCode.EXPORT_STMT, idx, line=stmt.line)
        elif isinstance(stmt, SendStmt):
            self._compile_expression(stmt.channel, code)
            self._compile_expression(stmt.value, code)
            code.emit(OpCode.SEND_VALUE, line=stmt.line)
        elif isinstance(stmt, IfStmt):
            self._compile_if_stmt(stmt, code)
        elif isinstance(stmt, WhileStmt):
            self._compile_while_stmt(stmt, code)
        elif isinstance(stmt, ForInStmt):
            self._compile_for_in_stmt(stmt, code)
        elif isinstance(stmt, ForRangeStmt):
            self._compile_for_range_stmt(stmt, code)
        elif isinstance(stmt, ReturnStmt):
            self._compile_return_stmt(stmt, code)
        elif isinstance(stmt, ExpressionStmt):
            self._compile_expression(stmt.expression, code)
            code.emit(OpCode.POP_TOP, line=stmt.line)
        elif isinstance(stmt, Assignment):
            self._compile_assignment(stmt, code)
        elif isinstance(stmt, BreakStmt):
            if not self._loop_stack:
                return  # 不在循环中，忽略
            # 迭代器循环中，正常退出时 FOR_ITER 会弹出迭代器；break 路径
            # 需要先手动弹出，保证汇合处栈深度一致。
            for _ in range(self._loop_stack[-1].get("break_pops", 0)):
                code.emit(OpCode.POP_TOP, line=stmt.line)
            # break 跳转到循环出口，但出口偏移量在编译循环体时还不知道
            # 先发出 JUMP 指令，稍后回填
            break_jump = self._emit_jump(OpCode.JUMP, code, stmt.line)
            self._loop_stack[-1]["breaks"].append(break_jump)
        elif isinstance(stmt, ContinueStmt):
            if not self._loop_stack:
                return  # 不在循环中，忽略
            # continue 跳转回循环起始
            loop_start = self._loop_stack[-1]["start"]
            code.emit(OpCode.LOOP, loop_start, line=stmt.line)

    def _apply_annotations_to_local(self, stmt, name_idx: int, code: CodeObject):
        """为已存入 ``name_idx`` 局部槽的声明值生成注解应用指令。

        语义对齐《注解功能设计规格》§1.2：按书写顺序的逆序应用；注解以被装饰
        对象为第一个位置参数调用；返回值非 None 时替换、为 None 时保留原对象。
        仅复用现有指令（LOAD_NAME / LOAD_LOCAL / CALL_FUNCTION / STORE_LOCAL 等）。

        限制：现有 ``CALL_FUNCTION`` 指令只接受位置参数（VM 的 _call 不接收
        kwargs），无法表达 ``注解(T, *args, **kwargs)`` 中的关键字参数。
        当任一注解带关键字参数时整体降级——跳过该声明的全部注解，保证 VM
        不崩溃且声明本身正常生成字节码。若需完整支持 kwargs，需为 VM 增加
        带关键字参数的调用指令（见交付报告）。
        """
        annotations = getattr(stmt, "annotations", None) or []
        if not annotations:
            return
        if any(getattr(a, "kwargs", None) for a in annotations):
            # 降级：关键字参数无法用现有指令表达，忽略注解但保持声明可用
            return

        for ann in reversed(annotations):
            name = getattr(ann, "name", "")
            if not name:
                continue
            line = getattr(ann, "line", 0) or getattr(stmt, "line", 0)
            # 注解函数（未定义时由 VM 的 LOAD_NAME 抛中文错误）
            code.emit(OpCode.LOAD_NAME, self._add_constant(name, code), line=line)
            # 被装饰对象作为第一个位置参数
            code.emit(OpCode.LOAD_LOCAL, name_idx, line=line)
            args = getattr(ann, "args", None) or []
            for arg in args:
                self._compile_expression(arg, code)
            code.emit(OpCode.CALL_FUNCTION, 1 + len(args), line=line)

            # 返回值非 None 则替换，否则保留原对象。等价于：
            #   result = A(T, ...)
            #   T = result if result is not None else T
            # 栈：[result] -> DUP_TOP -> [result, result]
            code.emit(OpCode.DUP_TOP, line=line)
            code.emit(OpCode.LOAD_CONST, self._add_constant(None, code), line=line)
            code.emit(OpCode.COMPARE_EQ, line=line)
            # 弹出比较结果：result is not None 时跳到 keep（result 留在栈上）
            keep_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, line)
            # result is None：丢弃 result，重新加载原对象
            code.emit(OpCode.POP_TOP, line=line)
            code.emit(OpCode.LOAD_LOCAL, name_idx, line=line)
            self._patch_jump(keep_jump, code)
            # 栈顶为最终值，写回同名局部变量
            code.emit(OpCode.STORE_LOCAL, name_idx, line=line)

    def _compile_variable_decl(self, stmt: VariableDecl, code: CodeObject,
                               leave_value: bool = False):
        self._compile_expression(stmt.value, code)
        scope = self._scope_stack[-1]
        if stmt.name not in scope.local_names:
            scope.local_names.append(stmt.name)
        idx = scope.local_names.index(stmt.name)
        code.emit(OpCode.STORE_LOCAL, idx, line=stmt.line)
        # 注解应用：结果写回同名局部变量（顺序自下而上）
        self._apply_annotations_to_local(stmt, idx, code)
        if leave_value:
            # 与解释器一致：变量声明语句的结果是注解应用后的值
            code.emit(OpCode.LOAD_LOCAL, idx, line=stmt.line)

    def _compile_enum_decl(self, stmt: EnumDecl, code: CodeObject):
        """编译枚举声明：在运行时构造 DaoEnum 对象并存入局部变量。"""
        variants = [
            (getattr(v, "name", ""), list(getattr(v, "params", [])))
            for v in stmt.variants
        ]
        descriptor = (stmt.name, list(stmt.values), variants)
        idx = self._add_constant(descriptor, code)
        code.emit(OpCode.BUILD_ENUM, idx, line=stmt.line)
        scope = self._scope_stack[-1]
        if stmt.name not in scope.local_names:
            scope.local_names.append(stmt.name)
        local_idx = scope.local_names.index(stmt.name)
        code.emit(OpCode.STORE_LOCAL, local_idx, line=stmt.line)

    @staticmethod
    def _pattern_bindings(pattern) -> list[str]:
        """收集模式会绑定的变量名（排除通配符 '_'）。"""
        names: list[str] = []

        def add(expr):
            if isinstance(expr, Identifier) and expr.name != "_":
                names.append(expr.name)

        if isinstance(pattern, Identifier):
            add(pattern)
        elif isinstance(pattern, ListPattern):
            for elem in pattern.elements:
                add(elem)
        elif isinstance(pattern, DictPattern):
            for _, value in pattern.pairs:
                add(value)
        elif isinstance(pattern, EnumVariantPattern):
            if pattern.binding:
                names.append(pattern.binding)
        elif isinstance(pattern, FunctionCall) and isinstance(pattern.callee, MemberAccess):
            for arg in pattern.arguments:
                add(arg)
        return names

    def _compile_match_stmt(self, stmt: MatchStmt, code: CodeObject):
        """编译匹配语句为顺序的模式检查 + 跳转链。"""
        self._compile_expression(stmt.subject, code)
        self._temp_counter += 1
        temp_name = f"__匹配主体_{self._temp_counter}"
        scope = self._scope_stack[-1]
        if temp_name not in scope.local_names:
            scope.local_names.append(temp_name)
        subject_idx = scope.local_names.index(temp_name)
        code.emit(OpCode.STORE_LOCAL, subject_idx, line=stmt.line)

        # 预先把所有模式会绑定的名字加入当前作用域，供分支体读取
        for case in stmt.cases:
            for name in self._pattern_bindings(case.pattern):
                if name not in scope.local_names:
                    scope.local_names.append(name)

        pending_skips: list[int] = []
        end_jumps: list[int] = []

        for case in stmt.cases:
            for jump in pending_skips:
                self._patch_jump(jump, code)
            pending_skips = []

            # 模式检查：压入布尔结果
            code.emit(OpCode.LOAD_LOCAL, subject_idx, line=case.line)
            pattern_data = (case.pattern, bool(case.is_wildcard))
            const_idx = self._add_constant(pattern_data, code)
            code.emit(OpCode.MATCH_PATTERN, const_idx, line=case.line)
            pending_skips.append(
                self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, case.line)
            )

            # 守卫条件
            if case.guard is not None:
                self._compile_expression(case.guard, code)
                pending_skips.append(
                    self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, case.line)
                )

            # 分支体（内联编译，使 return/break/continue 能正确传播）
            for i, s in enumerate(case.body):
                is_last = i == len(case.body) - 1
                if is_last and isinstance(s, ExpressionStmt):
                    # 保留最后一个表达式的值作为匹配语句结果
                    self._compile_expression(s.expression, code)
                else:
                    self._compile_statement(s, code)
            end_jumps.append(self._emit_jump(OpCode.JUMP, code, case.line))

        # 所有分支都未命中时，压入 None 作为默认值
        for jump in pending_skips:
            self._patch_jump(jump, code)
        code.emit(OpCode.LOAD_CONST, self._add_constant(None, code), line=stmt.line)
        # 命中分支跳过默认值
        for jump in end_jumps:
            self._patch_jump(jump, code)

    def _compile_function_decl(self, stmt: FunctionDecl, code: CodeObject):
        func_code = CodeObject(name=stmt.name)
        self._scope_stack.append(CompileScope())
        scope = self._scope_stack[-1]
        for param in stmt.params:
            scope.local_names.append(param)
        for s in stmt.body:
            self._compile_statement(s, func_code)
        func_code.emit(OpCode.LOAD_CONST, self._add_constant(None, func_code), line=0)
        func_code.emit(OpCode.RETURN_VALUE, line=0)
        func_code.local_names = scope.local_names
        func_code.stack_size = self._calculate_stack_size(func_code)
        self._scope_stack.pop()
        code.child_codes.append(func_code)
        const_idx = self._add_constant(func_code, code)
        code.emit(OpCode.MAKE_CLOSURE, const_idx, line=stmt.line)
        scope = self._scope_stack[-1]
        if stmt.name not in scope.local_names:
            scope.local_names.append(stmt.name)
        idx = scope.local_names.index(stmt.name)
        code.emit(OpCode.STORE_LOCAL, idx, line=stmt.line)
        # 函数注解：按自下而上顺序包装函数并写回同名局部变量
        self._apply_annotations_to_local(stmt, idx, code)

    def _compile_block(self, statements: list, code: CodeObject,
                       leave_value: bool = False):
        """编译语句块；leave_value 为真时保证块结束时栈顶恰好留下一个值。"""
        if not statements:
            if leave_value:
                code.emit(OpCode.LOAD_CONST, self._add_constant(None, code),
                          line=0)
            return
        if leave_value and isinstance(statements[-1], ExpressionStmt):
            for s in statements[:-1]:
                self._compile_statement(s, code)
            self._compile_expression(statements[-1].expression, code)
            return
        if leave_value and isinstance(statements[-1], VariableDecl):
            for s in statements[:-1]:
                self._compile_statement(s, code)
            self._compile_variable_decl(statements[-1], code, leave_value=True)
            return
        for s in statements:
            self._compile_statement(s, code)
        if leave_value:
            code.emit(OpCode.LOAD_CONST, self._add_constant(None, code), line=0)

    def _compile_if_stmt(self, stmt: IfStmt, code: CodeObject,
                         leave_value: bool = False):
        self._compile_expression(stmt.condition, code)
        else_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, stmt.line)
        self._compile_block(stmt.body, code, leave_value)
        exit_jumps = [self._emit_jump(OpCode.JUMP, code, stmt.line)]
        self._patch_jump(else_jump, code)
        for cond, body in stmt.elif_clauses:
            self._compile_expression(cond, code)
            else_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, stmt.line)
            self._compile_block(body, code, leave_value)
            exit_jumps.append(self._emit_jump(OpCode.JUMP, code, stmt.line))
            self._patch_jump(else_jump, code)
        self._compile_block(stmt.else_body, code, leave_value)
        for jump in exit_jumps:
            self._patch_jump(jump, code)

    def _compile_while_stmt(self, stmt: WhileStmt, code: CodeObject):
        loop_start = len(code.instructions)
        self._compile_expression(stmt.condition, code)
        exit_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, stmt.line)
        # 记录循环信息用于 break/continue
        loop_info = {"start": loop_start, "exit_jump": exit_jump, "breaks": []}
        self._loop_stack.append(loop_info)
        for s in stmt.body:
            self._compile_statement(s, code)
        self._loop_stack.pop()
        code.emit(OpCode.LOOP, loop_start, line=stmt.line)
        self._patch_jump(exit_jump, code)
        # 回填 break 跳转
        for break_jump in loop_info["breaks"]:
            self._patch_jump(break_jump, code)

    def _compile_for_in_stmt(self, stmt: ForInStmt, code: CodeObject):
        # 解释器为每轮迭代创建子环境，循环变量不会泄漏到循环外。
        # CAPTURE_NAME 保存进入循环前的绑定，RESTORE_NAME 在循环结束后恢复。
        second_var = getattr(stmt, "second_variable", None)
        name_idx = self._add_constant(stmt.variable, code)
        code.emit(OpCode.CAPTURE_NAME, name_idx, line=stmt.line)
        second_idx = None
        if second_var:
            second_idx = self._add_constant(second_var, code)
            code.emit(OpCode.CAPTURE_NAME, second_idx, line=stmt.line)
        self._compile_expression(stmt.iterable, code)
        if second_var:
            # 保留可迭代对象本身，以便按键取到对应的值
            code.emit(OpCode.DUP_TOP, line=stmt.line)
        code.emit(OpCode.GET_ITERATOR, line=stmt.line)
        loop_start = len(code.instructions)
        # 成功时压入下一个值（或键值对），耗尽时弹出迭代器并跳到出口
        iter_op = OpCode.FOR_ITER_PAIR if second_var else OpCode.FOR_ITER
        exit_jump = self._emit_jump(iter_op, code, stmt.line)
        # 用按名存储写入当前栈帧，使循环变量遮蔽外层同名变量；
        # 不加入 local_names，循环结束恢复后 LOAD_NAME 可继续找到外层变量。
        if second_var:
            code.emit(OpCode.STORE_SCOPE_LOCAL, second_idx, line=stmt.line)
        code.emit(OpCode.STORE_SCOPE_LOCAL, name_idx, line=stmt.line)
        loop_info = {
            "start": loop_start,
            "exit_jump": exit_jump,
            "breaks": [],
            "break_pops": 2 if second_var else 1,
        }
        self._loop_stack.append(loop_info)
        for s in stmt.body:
            self._compile_statement(s, code)
        self._loop_stack.pop()
        code.emit(OpCode.LOOP, loop_start, line=stmt.line)
        self._patch_jump(exit_jump, code)
        for break_jump in loop_info["breaks"]:
            self._patch_jump(break_jump, code)
        if second_var:
            code.emit(OpCode.RESTORE_NAME, second_idx, line=stmt.line)
        code.emit(OpCode.RESTORE_NAME, name_idx, line=stmt.line)

    def _compile_for_range_stmt(self, stmt: ForRangeStmt, code: CodeObject):
        # 与解释器完全一致：range(start, end + 1, step)，起止与步长只求值一次，
        # 结束点包含在内，步长为负时也沿用 Python range 的语义。
        name_idx = self._add_constant(stmt.variable, code)
        code.emit(OpCode.CAPTURE_NAME, name_idx, line=stmt.line)
        self._compile_expression(stmt.start, code)
        self._compile_expression(stmt.end, code)
        arg_count = 2
        if stmt.step:
            self._compile_expression(stmt.step, code)
            arg_count = 3
        code.emit(OpCode.BUILD_RANGE, arg_count, line=stmt.line)
        code.emit(OpCode.GET_ITERATOR, line=stmt.line)
        loop_start = len(code.instructions)
        exit_jump = self._emit_jump(OpCode.FOR_ITER, code, stmt.line)
        code.emit(OpCode.STORE_SCOPE_LOCAL, name_idx, line=stmt.line)
        loop_info = {
            "start": loop_start,
            "exit_jump": exit_jump,
            "breaks": [],
            "break_pops": 1,
        }
        self._loop_stack.append(loop_info)
        for s in stmt.body:
            self._compile_statement(s, code)
        self._loop_stack.pop()
        code.emit(OpCode.LOOP, loop_start, line=stmt.line)
        self._patch_jump(exit_jump, code)
        for break_jump in loop_info["breaks"]:
            self._patch_jump(break_jump, code)
        code.emit(OpCode.RESTORE_NAME, name_idx, line=stmt.line)

    def _compile_return_stmt(self, stmt: ReturnStmt, code: CodeObject):
        if stmt.value:
            self._compile_expression(stmt.value, code)
        else:
            code.emit(OpCode.LOAD_CONST, self._add_constant(None, code), line=stmt.line)
        code.emit(OpCode.RETURN_VALUE, line=stmt.line)

    def _compile_assignment(self, stmt: Assignment, code: CodeObject):
        self._compile_expression(stmt.value, code)
        if isinstance(stmt.target, Identifier):
            scope = self._scope_stack[-1]
            if stmt.target.name in scope.local_names:
                idx = scope.local_names.index(stmt.target.name)
                code.emit(OpCode.STORE_LOCAL, idx, line=stmt.line)
            else:
                code.emit(OpCode.STORE_NAME, self._add_constant(stmt.target.name, code), line=stmt.line)

    def _compile_expression(self, expr: Expression, code: CodeObject):
        if isinstance(expr, NumberLiteral):
            idx = self._add_constant(expr.value, code)
            code.emit(OpCode.LOAD_CONST, idx, line=expr.line)
        elif isinstance(expr, StringLiteral):
            idx = self._add_constant(expr.value, code)
            code.emit(OpCode.LOAD_CONST, idx, line=expr.line)
        elif isinstance(expr, BooleanLiteral):
            idx = self._add_constant(expr.value, code)
            code.emit(OpCode.LOAD_CONST, idx, line=expr.line)
        elif isinstance(expr, NullLiteral):
            idx = self._add_constant(None, code)
            code.emit(OpCode.LOAD_CONST, idx, line=expr.line)
        elif isinstance(expr, Identifier):
            scope = self._scope_stack[-1]
            if expr.name in scope.local_names:
                idx = scope.local_names.index(expr.name)
                code.emit(OpCode.LOAD_LOCAL, idx, line=expr.line)
            else:
                code.emit(OpCode.LOAD_NAME, self._add_constant(expr.name, code), line=expr.line)
        elif isinstance(expr, BinaryOp):
            op_map = {
                "+": OpCode.BINARY_ADD, "-": OpCode.BINARY_SUB,
                "*": OpCode.BINARY_MUL, "/": OpCode.BINARY_DIV,
                "%": OpCode.BINARY_MOD, "**": OpCode.BINARY_POW,
                "//": OpCode.BINARY_FLOOR_DIV,
            }
            if expr.operator == "并且":
                # 短路求值：左值为假时直接返回左值，不求值右侧
                self._compile_expression(expr.left, code)
                code.emit(OpCode.DUP_TOP, line=expr.line)
                short_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, expr.line)
                code.emit(OpCode.POP_TOP, line=expr.line)
                self._compile_expression(expr.right, code)
                self._patch_jump(short_jump, code)
            elif expr.operator == "或者":
                # 短路求值：左值为真时直接返回左值，不求值右侧
                self._compile_expression(expr.left, code)
                code.emit(OpCode.DUP_TOP, line=expr.line)
                code.emit(OpCode.UNARY_NOT, line=expr.line)
                short_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, expr.line)
                code.emit(OpCode.POP_TOP, line=expr.line)
                self._compile_expression(expr.right, code)
                self._patch_jump(short_jump, code)
            else:
                # 算术与比较运算：先求值左右操作数
                self._compile_expression(expr.left, code)
                self._compile_expression(expr.right, code)
                if expr.operator in op_map:
                    code.emit(op_map[expr.operator], line=expr.line)
                elif expr.operator in ("==", "!=", "<", ">", "<=", ">="):
                    cmp_map = {
                        "==": OpCode.COMPARE_EQ, "!=": OpCode.COMPARE_NE,
                        "<": OpCode.COMPARE_LT, "<=": OpCode.COMPARE_LE,
                        ">": OpCode.COMPARE_GT, ">=": OpCode.COMPARE_GE,
                    }
                    code.emit(cmp_map[expr.operator], line=expr.line)
                elif expr.operator == "在":
                    code.emit(OpCode.CONTAINS, line=expr.line)
                elif expr.operator == "不在":
                    code.emit(OpCode.NOT_CONTAINS, line=expr.line)
        elif isinstance(expr, UnaryOp):
            self._compile_expression(expr.operand, code)
            if expr.operator == "-":
                code.emit(OpCode.UNARY_NEGATIVE, line=expr.line)
            elif expr.operator in ("不是", "!"):
                code.emit(OpCode.UNARY_NOT, line=expr.line)
        elif isinstance(expr, ConditionalExpr):
            # 条件表达式：先求值条件，再选择真/假分支
            self._compile_expression(expr.condition, code)
            else_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, expr.line)
            self._compile_expression(expr.true_value, code)
            end_jump = self._emit_jump(OpCode.JUMP, code, expr.line)
            self._patch_jump(else_jump, code)
            self._compile_expression(expr.false_value, code)
            self._patch_jump(end_jump, code)
        elif isinstance(expr, ChannelExpr):
            capacity_idx = self._add_constant(expr.capacity, code)
            code.emit(OpCode.BUILD_CHANNEL, capacity_idx, line=expr.line)
        elif isinstance(expr, ReceiveExpr):
            self._compile_expression(expr.channel, code)
            code.emit(OpCode.RECEIVE_VALUE, line=expr.line)
        elif isinstance(expr, FunctionCall):
            self._compile_expression(expr.callee, code)
            for arg in expr.arguments:
                self._compile_expression(arg, code)
            code.emit(OpCode.CALL_FUNCTION, len(expr.arguments), line=expr.line)
        elif isinstance(expr, ListLiteral):
            for elem in expr.elements:
                self._compile_expression(elem, code)
            code.emit(OpCode.BUILD_LIST, len(expr.elements), line=expr.line)
        elif isinstance(expr, DictLiteral):
            for k, v in expr.pairs:
                self._compile_expression(k, code)
                self._compile_expression(v, code)
            code.emit(OpCode.BUILD_DICT, len(expr.pairs), line=expr.line)
        elif isinstance(expr, TupleLiteral):
            for elem in expr.elements:
                self._compile_expression(elem, code)
            code.emit(OpCode.BUILD_TUPLE, len(expr.elements), line=expr.line)
        elif isinstance(expr, SetLiteral):
            for elem in expr.elements:
                self._compile_expression(elem, code)
            code.emit(OpCode.BUILD_SET, len(expr.elements), line=expr.line)
        elif isinstance(expr, MemberAccess):
            self._compile_expression(expr.object, code)
            idx = self._add_constant(expr.member, code)
            code.emit(OpCode.LOAD_ATTR, idx, line=expr.line)
        elif isinstance(expr, IndexAccess):
            self._compile_expression(expr.object, code)
            self._compile_expression(expr.index, code)
            code.emit(OpCode.LOAD_INDEX, line=expr.line)
        elif isinstance(expr, LambdaExpr):
            lambda_code = CodeObject(name="<lambda>")
            self._scope_stack.append(CompileScope())
            scope = self._scope_stack[-1]
            for param in expr.params:
                scope.local_names.append(param)
            if isinstance(expr.body, Expression):
                self._compile_expression(expr.body, lambda_code)
            else:
                self._compile_statement(expr.body, lambda_code)
            lambda_code.emit(OpCode.RETURN_VALUE, line=expr.line)
            lambda_code.local_names = scope.local_names
            lambda_code.stack_size = self._calculate_stack_size(lambda_code)
            self._scope_stack.pop()
            code.child_codes.append(lambda_code)
            const_idx = self._add_constant(lambda_code, code)
            code.emit(OpCode.MAKE_CLOSURE, const_idx, line=expr.line)

    def _add_constant(self, value, code: CodeObject) -> int:
        for i, c in enumerate(code.constants):
            # 类型必须一致：否则 True == 1、False == 0 会错误复用常量，
            # 导致 VM 把布尔字面量求值为整数（AST 与 VM 语义不一致）。
            if type(c) is type(value) and c == value:
                return i
        idx = len(code.constants)
        code.constants.append(value)
        return idx

    def _emit_jump(self, opcode: OpCode, code: CodeObject, line: int) -> int:
        code.emit(opcode, 0, line=line)
        return len(code.instructions) - 1

    def _patch_jump(self, offset: int, code: CodeObject):
        target = len(code.instructions)
        code.instructions[offset].operand = target

    def _calculate_stack_size(self, code: CodeObject) -> int:
        max_size = 0
        current = 0
        for inst in code.instructions:
            op = inst.opcode
            if op in (OpCode.LOAD_CONST, OpCode.LOAD_LOCAL, OpCode.LOAD_NAME,
                      OpCode.LOAD_UPVALUE, OpCode.LOAD_ATTR, OpCode.LOAD_INDEX):
                current += 1
            elif op in (OpCode.STORE_LOCAL, OpCode.STORE_NAME, OpCode.STORE_UPVALUE,
                        OpCode.STORE_ATTR, OpCode.STORE_INDEX, OpCode.POP_TOP,
                        OpCode.RETURN_VALUE, OpCode.STORE_SCOPE_LOCAL,
                        OpCode.RESTORE_NAME):
                current = max(0, current - 1)
            elif op in (OpCode.BINARY_ADD, OpCode.BINARY_SUB, OpCode.BINARY_MUL,
                        OpCode.BINARY_DIV, OpCode.BINARY_MOD, OpCode.BINARY_POW,
                        OpCode.BINARY_FLOOR_DIV, OpCode.COMPARE_EQ, OpCode.COMPARE_NE,
                        OpCode.COMPARE_LT, OpCode.COMPARE_LE, OpCode.COMPARE_GT,
                        OpCode.COMPARE_GE, OpCode.LOGICAL_AND, OpCode.LOGICAL_OR):
                current = max(0, current - 1)
            elif op == OpCode.CALL_FUNCTION:
                args = inst.operand or 0
                current = max(0, current - args)
            elif op in (OpCode.BUILD_LIST, OpCode.BUILD_DICT, OpCode.BUILD_SET, OpCode.BUILD_TUPLE):
                count = inst.operand or 0
                current = max(0, current - count) + 1
            elif op == OpCode.MAKE_CLOSURE:
                current += 1
            elif op in (OpCode.GET_ITERATOR, OpCode.UNARY_NEGATIVE, OpCode.UNARY_NOT):
                pass
            elif op in (OpCode.IMPORT_STMT, OpCode.EXPORT_STMT):
                # 语句级副作用，不改变栈深度
                pass
            elif op == OpCode.DUP_TOP:
                current += 1
            elif op == OpCode.FOR_ITER:
                # 成功迭代时压入一个值；耗尽时指令直接跳出，不计入峰值
                current += 1
            elif op == OpCode.FOR_ITER_PAIR:
                current += 2
            elif op == OpCode.CAPTURE_NAME:
                current += 1
            elif op == OpCode.BUILD_RANGE:
                current = max(0, current - (inst.operand or 0)) + 1
            max_size = max(max_size, current)
        return max_size