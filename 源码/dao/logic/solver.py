# -*- coding: utf-8 -*-
from typing import Any, Generator, Optional, Dict
from .core import LogicVariable, LogicStruct, KnowledgeBase, normalize_term, LogicAtom, Substitution
from .unification import unify, apply_substitution
from .backtracking import Backtracker, TrailStack
from .exceptions import QueryError, UnificationError, CircularRuleError

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
                if var_name.startswith('?'):
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
        items = ', '.join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{{{items}}}"

    def __str__(self) -> str:
        items = ', '.join(f"{k}={v}" for k, v in self.to_dict().items())
        return f"{{{items}}}"

class Solver:
    def __init__(self, knowledge_base: KnowledgeBase):
        self.kb = knowledge_base
        self.backtracker = Backtracker(knowledge_base)
        self._cut_active = False

    def solve(self, goal: Any, variables: list[str] = None, max_solutions: int = 0) -> list[QueryResult]:
        goal = normalize_term(goal)
        results = []
        count = 0
        for substitution in self.backtracker.search(goal):
            result = QueryResult(substitution, variables)
            results.append(result)
            count += 1
            if max_solutions > 0 and count >= max_solutions:
                break
        return results

    def solve_one(self, goal: Any, variables: list[str] = None) -> Optional[QueryResult]:
        results = self.solve(goal, variables, max_solutions=1)
        return results[0] if results else None

    def exists(self, goal: Any) -> bool:
        return self.solve_one(goal) is not None

    def solve_generator(self, goal: Any, variables: list[str] = None) -> Generator[QueryResult, None, None]:
        goal = normalize_term(goal)
        for substitution in self.backtracker.search(goal):
            yield QueryResult(substitution, variables)

    def solve_negation(self, goal: Any) -> bool:
        new_solver = Solver(self.kb)
        result = new_solver.solve_one(goal)
        return result is None

    def solve_negation_with_subst(self, goal: Any, substitution: Substitution) -> bool:
        goal = apply_substitution(goal, substitution)
        return not self.exists(goal)

    def solve_conjunction(self, goals: list[Any], variables: list[str] = None) -> list[QueryResult]:
        if not goals:
            return [QueryResult(Substitution(), variables)]
        first = goals[0]
        rest = goals[1:]
        if not rest:
            return self.solve(first, variables)
        results = []
        for result in self.solve(first):
            for rest_result in self._solve_with_subst(rest, result.substitution, variables):
                results.append(rest_result)
        return results

    def _solve_with_subst(self, goals: list[Any], substitution: Substitution, variables: list[str] = None) -> list[QueryResult]:
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

    def solve_disjunction(self, goals: list[Any], variables: list[str] = None) -> list[QueryResult]:
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

def solve(knowledge_base: KnowledgeBase, goal: Any, variables: list[str] = None) -> list[QueryResult]:
    solver = Solver(knowledge_base)
    return solver.solve(goal, variables)

def query(knowledge_base: KnowledgeBase, goal_str: str) -> list[Dict[str, Any]]:
    solver = Solver(knowledge_base)
    return []
