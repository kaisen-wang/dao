# -*- coding: utf-8 -*-
from typing import Any, Dict, Generator, List, Optional

from .backtracking import Backtracker, TrailStack
from .core import (
    KnowledgeBase,
    LogicAtom,
    LogicStruct,
    LogicVariable,
    Substitution,
    normalize_term,
)
from .exceptions import CircularRuleError, QueryError, UnificationError
from .unification import apply_substitution, unify


class QueryResult:
    def __init__(self, substitution, variables: list[str] = None):
        self.substitution = substitution
        self.variables = variables or []

    def get_binding(self, var_name: str) -> Any:
        value = self.substitution.get(var_name)
        if value is None:
            return var_name
        return value

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.variables:
            for var_name in self.variables:
                result[var_name] = self._format_value(self.get_binding(var_name))
        else:
            for var_name in self.substitution.keys():
                if var_name.startswith("?"):
                    result[var_name] = self._format_value(self.get_binding(var_name))
        return result

    def _format_value(self, value: Any) -> Any:
        if isinstance(value, LogicStruct):
            return str(value)
        elif isinstance(value, LogicVariable):
            return value.name
        elif isinstance(value, LogicAtom):
            return value.value
        else:
            return value

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{{{items}}}"

    def __str__(self) -> str:
        items = ", ".join(f"{k}={v}" for k, v in self.to_dict().items())
        return f"{{{items}}}"


class Solver:
    def __init__(
        self, knowledge_base: KnowledgeBase, constraints: Optional[List] = None
    ):
        self.kb = knowledge_base
        from .backtracking import Backtracker

        self.backtracker = Backtracker(knowledge_base, constraints)
        from .constraints.core import ConstraintSolver

        self.constraint_solver = ConstraintSolver(constraints or [])
        self._cut_active = False

    def solve(
        self, goal: Any, variables: list[str] = None, max_solutions: int = 0
    ) -> list[QueryResult]:
        goal = normalize_term(goal)
        results = []
        count = 0
        for substitution in self.backtracker.search(goal):
            # 应用约束传播
            propagated_subst = self.constraint_solver.propagate_constraints(
                substitution
            )
            if self.constraint_solver.check_constraints(propagated_subst):
                result = QueryResult(propagated_subst, variables)
                results.append(result)
                count += 1
                if max_solutions > 0 and count >= max_solutions:
                    break
        return results

    def solve_one(
        self, goal: Any, variables: list[str] = None
    ) -> Optional[QueryResult]:
        results = self.solve(goal, variables, max_solutions=1)
        return results[0] if results else None

    def exists(self, goal: Any) -> bool:
        return self.solve_one(goal) is not None

    def solve_generator(
        self, goal: Any, variables: list[str] = None
    ) -> Generator[QueryResult, None, None]:
        goal = normalize_term(goal)
        for substitution in self.backtracker.search(goal):
            # 应用约束传播
            propagated_subst = self.constraint_solver.propagate_constraints(
                substitution
            )
            if self.constraint_solver.check_constraints(propagated_subst):
                yield QueryResult(propagated_subst, variables)

    def solve_negation(self, goal: Any) -> bool:
        new_solver = Solver(self.kb)
        result = new_solver.solve_one(goal)
        return result is None

    def solve_negation_with_subst(self, goal: Any, substitution: Substitution) -> bool:
        goal = apply_substitution(goal, substitution)
        return not self.exists(goal)

    def add_constraint(self, constraint):
        """添加约束"""
        self.constraint_solver.add_constraint(constraint)
        from .backtracking import Backtracker

        self.backtracker = Backtracker(self.kb, self.constraint_solver.constraints)

    def remove_constraint(self, constraint):
        """移除约束"""
        self.constraint_solver.remove_constraint(constraint)
        from .backtracking import Backtracker

        self.backtracker = Backtracker(self.kb, self.constraint_solver.constraints)

    def clear_constraints(self):
        """清除所有约束"""
        self.constraint_solver.clear_constraints()
        from .backtracking import Backtracker

        self.backtracker = Backtracker(self.kb, [])

    def get_constraints(self):
        """获取所有约束"""
        return self.constraint_solver.constraints

    def has_constraints(self):
        """检查是否有约束"""
        return self.constraint_solver.has_constraints()

    def solve_conjunction(
        self, goals: list[Any], variables: list[str] = None
    ) -> list[QueryResult]:
        if not goals:
            return [QueryResult(Substitution(), variables)]
        first = goals[0]
        rest = goals[1:]
        if not rest:
            return self.solve(first, variables)
        results = []
        for result in self.solve(first):
            for rest_result in self._solve_with_subst(
                rest, result.substitution, variables
            ):
                results.append(rest_result)
        return results

    def _solve_with_subst(
        self, goals: list[Any], substitution: Substitution, variables: list[str] = None
    ) -> list[QueryResult]:
        if not goals:
            return [QueryResult(substitution, variables)]
        first = goals[0]
        rest = goals[1:]
        first = apply_substitution(first, substitution)
        results = []
        for subst in self.backtracker.search(first, substitution):
            merged_subst = Substitution()
            merged_subst.update(substitution)
            merged_subst.update(subst)
            if rest:
                for result in self._solve_with_subst(rest, merged_subst, variables):
                    results.append(result)
            else:
                results.append(QueryResult(merged_subst, variables))
        return results

    def solve_disjunction(
        self, goals: list[Any], variables: list[str] = None
    ) -> list[QueryResult]:
        all_results = []
        for goal in goals:
            results = self.solve(goal, variables)
            all_results.extend(results)
        return all_results

    def count_solutions(self, goal: Any, max_count: int = 1000) -> int:
        count = 0
        for _ in self.solve_generator(goal):
            count += 1
            if count >= max_count:
                break
        return count

    def explain_solution(self, result: QueryResult, goal: Any) -> str:
        lines = []
        lines.append(f"Query: {goal}")
        lines.append(f"Solution: {result}")
        if result.to_dict():
            lines.append("Variable bindings:")
            for var_name, value in result.to_dict().items():
                lines.append(f"  {var_name} = {value}")
        else:
            lines.append("No variable bindings (constant query)")
        result_str = ""
        for line in lines:
            result_str += line + " "
        return result_str


def solve(
    knowledge_base: KnowledgeBase, goal: Any, variables: list[str] = None
) -> list[QueryResult]:
    solver = Solver(knowledge_base)
    return solver.solve(goal, variables)


def query(knowledge_base: KnowledgeBase, goal_str: str) -> list[Dict[str, Any]]:
    """
    解析并执行逻辑查询

    Args:
        knowledge_base: 知识库
        goal_str: 查询字符串，支持格式如 "父母(?x, 小明)"

    Returns:
        查询结果的字典列表
    """
    from dao.ast_nodes import FunctionCall

    # 这里我们需要解析查询字符串，但由于没有完整的解析器上下文
    # 我们实现一个简单的解析器来处理基本查询格式
    def parse_simple_query(query_str):
        import re

        # 匹配格式如 "谓词(参数1, 参数2)" 的查询
        match = re.match(r"^(\w+)\((.*)\)$", query_str.strip())
        if not match:
            raise ValueError(f"无效的查询格式: {query_str}")

        predicate = match.group(1)
        args_str = match.group(2)

        # 解析参数
        args = []
        if args_str.strip():
            # 简单的参数解析（不处理嵌套结构）
            arg_tokens = args_str.split(",")
            for token in arg_tokens:
                token = token.strip()
                # 检查是否是变量（以?开头）
                if token.startswith("?"):
                    from dao.logic.core import LogicVariable

                    args.append(LogicVariable(token))
                # 检查是否是字符串字面量（带引号）
                elif (token.startswith("'") and token.endswith("'")) or (
                    token.startswith('"') and token.endswith('"')
                ):
                    from dao.logic.core import LogicAtom

                    args.append(LogicAtom(token[1:-1]))
                # 检查是否是数值
                elif token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
                    from dao.logic.core import LogicAtom

                    args.append(LogicAtom(int(token)))
                # 检查是否是布尔值
                elif token.lower() == "真" or token.lower() == "true":
                    from dao.logic.core import LogicAtom

                    args.append(LogicAtom(True))
                elif token.lower() == "假" or token.lower() == "false":
                    from dao.logic.core import LogicAtom

                    args.append(LogicAtom(False))
                # 其他情况作为原子
                else:
                    from dao.logic.core import LogicAtom

                    args.append(LogicAtom(token))

        from dao.logic.core import LogicStruct

        return LogicStruct(predicate, tuple(args))

    try:
        # 解析查询
        goal = parse_simple_query(goal_str)
        solver = Solver(knowledge_base)
        results = solver.solve(goal)
        return [result.to_dict() for result in results]
    except Exception as e:
        raise QueryError(f"查询解析或执行失败: {e}")
