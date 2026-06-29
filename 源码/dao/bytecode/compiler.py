from dataclasses import dataclass, field

from ..ast_nodes import (
    Assignment,
    BinaryOp,
    BooleanLiteral,
    BreakStmt,
    ClassDecl,
    CompareOp,
    ContinueStmt,
    DictLiteral,
    EnumDecl,
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
    MemberAccess,
    NullLiteral,
    NumberLiteral,
    Program,
    ReturnStmt,
    SetLiteral,
    StringLiteral,
    TraitDecl,
    TupleLiteral,
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

    def compile(self, program: Program) -> CodeObject:
        code = CodeObject(name="<module>")
        for i, stmt in enumerate(program.statements):
            is_last = (i == len(program.statements) - 1)
            if is_last and isinstance(stmt, ExpressionStmt):
                self._compile_expression(stmt.expression, code)
            else:
                self._compile_statement(stmt, code)
        code.emit(OpCode.RETURN_VALUE, line=0)
        code.local_names = list(self._scope_stack[-1].local_names)
        code.stack_size = self._calculate_stack_size(code)
        return code

    def _compile_statement(self, stmt, code: CodeObject):
        if isinstance(stmt, VariableDecl):
            self._compile_variable_decl(stmt, code)
        elif isinstance(stmt, FunctionDecl):
            self._compile_function_decl(stmt, code)
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

    def _compile_variable_decl(self, stmt: VariableDecl, code: CodeObject):
        self._compile_expression(stmt.value, code)
        scope = self._scope_stack[-1]
        if stmt.name not in scope.local_names:
            scope.local_names.append(stmt.name)
        idx = scope.local_names.index(stmt.name)
        code.emit(OpCode.STORE_LOCAL, idx, line=stmt.line)

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

    def _compile_if_stmt(self, stmt: IfStmt, code: CodeObject):
        self._compile_expression(stmt.condition, code)
        else_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, stmt.line)
        for s in stmt.body:
            self._compile_statement(s, code)
        exit_jump = self._emit_jump(OpCode.JUMP, code, stmt.line)
        self._patch_jump(else_jump, code)
        for cond, body in stmt.elif_clauses:
            self._compile_expression(cond, code)
            else_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, stmt.line)
            for s in body:
                self._compile_statement(s, code)
            exit_jump = self._emit_jump(OpCode.JUMP, code, stmt.line)
            self._patch_jump(else_jump, code)
        for s in stmt.else_body:
            self._compile_statement(s, code)
        self._patch_jump(exit_jump, code)

    def _compile_while_stmt(self, stmt: WhileStmt, code: CodeObject):
        loop_start = len(code.instructions)
        self._compile_expression(stmt.condition, code)
        exit_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, stmt.line)
        for s in stmt.body:
            self._compile_statement(s, code)
        code.emit(OpCode.LOOP, loop_start, line=stmt.line)
        self._patch_jump(exit_jump, code)

    def _compile_for_in_stmt(self, stmt: ForInStmt, code: CodeObject):
        self._compile_expression(stmt.iterable, code)
        code.emit(OpCode.GET_ITERATOR, line=stmt.line)
        scope = self._scope_stack[-1]
        if stmt.variable not in scope.local_names:
            scope.local_names.append(stmt.variable)
        var_idx = scope.local_names.index(stmt.variable)
        loop_start = len(code.instructions)
        code.emit(OpCode.FOR_ITER, var_idx, line=stmt.line)
        exit_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, stmt.line)
        for s in stmt.body:
            self._compile_statement(s, code)
        code.emit(OpCode.LOOP, loop_start, line=stmt.line)
        self._patch_jump(exit_jump, code)

    def _compile_for_range_stmt(self, stmt: ForRangeStmt, code: CodeObject):
        self._compile_expression(stmt.start, code)
        self._compile_expression(stmt.end, code)
        if stmt.step:
            self._compile_expression(stmt.step, code)
        scope = self._scope_stack[-1]
        if stmt.variable not in scope.local_names:
            scope.local_names.append(stmt.variable)
        var_idx = scope.local_names.index(stmt.variable)
        code.emit(OpCode.STORE_LOCAL, var_idx, line=stmt.line)
        loop_start = len(code.instructions)
        code.emit(OpCode.LOAD_LOCAL, var_idx, line=stmt.line)
        self._compile_expression(stmt.end, code)
        code.emit(OpCode.COMPARE_LT, line=stmt.line)
        exit_jump = self._emit_jump(OpCode.POP_JUMP_IF_FALSE, code, stmt.line)
        for s in stmt.body:
            self._compile_statement(s, code)
        code.emit(OpCode.LOAD_LOCAL, var_idx, line=stmt.line)
        code.emit(OpCode.LOAD_CONST, self._add_constant(1, code), line=stmt.line)
        code.emit(OpCode.BINARY_ADD, line=stmt.line)
        code.emit(OpCode.STORE_LOCAL, var_idx, line=stmt.line)
        code.emit(OpCode.LOOP, loop_start, line=stmt.line)
        self._patch_jump(exit_jump, code)

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
            self._compile_expression(expr.left, code)
            self._compile_expression(expr.right, code)
            op_map = {
                "+": OpCode.BINARY_ADD, "-": OpCode.BINARY_SUB,
                "*": OpCode.BINARY_MUL, "/": OpCode.BINARY_DIV,
                "%": OpCode.BINARY_MOD, "**": OpCode.BINARY_POW,
                "//": OpCode.BINARY_FLOOR_DIV,
                "并且": OpCode.LOGICAL_AND, "或者": OpCode.LOGICAL_OR,
            }
            if expr.operator in op_map:
                code.emit(op_map[expr.operator], line=expr.line)
            elif expr.operator in ("==", "!=", "<", ">", "<=", ">="):
                cmp_map = {
                    "==": OpCode.COMPARE_EQ, "!=": OpCode.COMPARE_NE,
                    "<": OpCode.COMPARE_LT, "<=": OpCode.COMPARE_LE,
                    ">": OpCode.COMPARE_GT, ">=": OpCode.COMPARE_GE,
                }
                code.emit(cmp_map[expr.operator], line=expr.line)
        elif isinstance(expr, UnaryOp):
            self._compile_expression(expr.operand, code)
            if expr.operator == "-":
                code.emit(OpCode.UNARY_NEGATIVE, line=expr.line)
            elif expr.operator in ("不是", "!"):
                code.emit(OpCode.UNARY_NOT, line=expr.line)
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
            if c is value:
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
                        OpCode.RETURN_VALUE):
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
            elif op == OpCode.DUP_TOP:
                current += 1
            elif op == OpCode.FOR_ITER:
                current += 1
            max_size = max(max_size, current)
        return max_size