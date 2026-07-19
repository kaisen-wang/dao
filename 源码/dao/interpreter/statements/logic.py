"""逻辑编程执行混入"""

from ...ast_nodes import (
    BooleanLiteral, DictLiteral, FunctionCall, Identifier,
    ListLiteral, LogicBlock, LogicFact, NumberLiteral, StringLiteral,
)
from ...environment import Environment


class LogicExecutor:
    """逻辑编程执行方法集（混入类）"""

    def _parse_logic_args(self, arguments, env: Environment) -> list:
        """解析逻辑谓词的参数列表为逻辑项"""
        from ...ast_nodes import LogicVariable as ASTLogicVariable
        from ...logic.core import LogicAtom, LogicVariable

        args = []
        for arg in arguments:
            if isinstance(arg, Identifier) and arg.name.startswith("?"):
                args.append(LogicVariable(arg.name))
            elif isinstance(arg, ASTLogicVariable):
                args.append(LogicVariable(arg.name))
            elif isinstance(arg, StringLiteral):
                args.append(LogicAtom(arg.value))
            elif isinstance(arg, NumberLiteral):
                args.append(LogicAtom(arg.value))
            elif isinstance(arg, BooleanLiteral):
                args.append(LogicAtom(arg.value))
            elif isinstance(arg, ListLiteral):
                elements = [self.eval_expression(e, env) for e in arg.elements]
                args.append(LogicAtom(elements))
            elif isinstance(arg, DictLiteral):
                pairs = {
                    self.eval_expression(k, env): self.eval_expression(v, env)
                    for k, v in arg.pairs
                }
                args.append(LogicAtom(pairs))
        return args

    def exec_logic_block(self, stmt: LogicBlock, env: Environment) -> None:
        """执行逻辑块：创建知识库并添加事实和规则"""
        from ...logic.core import KnowledgeBase, LogicStruct, normalize_term
        from ...logic.solver import Solver

        kb = KnowledgeBase(stmt.name)

        for fact in stmt.facts:
            evaluated_args = [self.eval_expression(arg, env) for arg in fact.arguments]
            normalized_args = [normalize_term(arg) for arg in evaluated_args]
            logic_fact = LogicStruct(fact.predicate, normalized_args)
            kb.add_fact(logic_fact)

        for rule in stmt.rules:
            head_args = [self.eval_expression(arg, env) for arg in rule.head.arguments]
            normalized_head_args = [normalize_term(arg) for arg in head_args]
            rule_head = LogicStruct(rule.head.predicate, normalized_head_args)

            rule_body = []
            for body_expr in rule.body:
                if isinstance(body_expr, FunctionCall):
                    predicate = body_expr.callee.name
                    body_args = self._parse_logic_args(body_expr.arguments, env)
                    rule_body.append(LogicStruct(predicate, body_args))
                elif isinstance(body_expr, LogicFact):
                    body_args = self._parse_logic_args(body_expr.arguments, env)
                    rule_body.append(LogicStruct(body_expr.predicate, body_args))

            kb.add_rule(rule_head, rule_body)

        solver = Solver(kb)
        env.define(stmt.name, kb)
        env.define(f"{stmt.name}_求解器", solver)
        if stmt.is_exported:
            env.exports.append(stmt.name)
