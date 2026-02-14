# -*- coding: utf-8 -*-
"""Backtracking Mechanism Implementation"""

from typing import Any, Callable, Generator, List, Optional

from .core import (
    KnowledgeBase,
    LogicStruct,
    LogicVariable,
    Substitution,
    normalize_term,
)
from .unification import apply_substitution, occurs_check, unify


class TrailStack:
    """Trail stack for backtracking"""

    def __init__(self):
        self._marks = []
        self._bindings = []

    def mark(self) -> int:
        mark_id = len(self._marks)
        self._marks.append(len(self._bindings))
        return mark_id

    def bind(self, var: LogicVariable, value: Any) -> None:
        old_value = var.bound_to
        self._bindings.append((var, old_value))
        var.bind(value)

    def unbind(self, var: LogicVariable) -> None:
        old_value = var.bound_to
        self._bindings.append((var, old_value))
        var.unbind()

    def backtrack(self, mark_id: int) -> None:
        if mark_id < 0 or mark_id >= len(self._marks):
            raise ValueError(f"Invalid mark ID: {mark_id}")
        target_length = self._marks[mark_id]
        while len(self._bindings) > target_length:
            var, old_value = self._bindings.pop()
            var.bound_to = old_value

    def get_mark_count(self) -> int:
        return len(self._marks)

    def get_binding_count(self) -> int:
        return len(self._bindings)

    def clear(self) -> None:
        self._marks.clear()
        self._bindings.clear()

    def __repr__(self) -> str:
        return f"TrailStack(marks={len(self._marks)}, bindings={len(self._bindings)})"


class Backtracker:
    """Depth-first search backtracker"""

    def __init__(
        self, knowledge_base: KnowledgeBase, constraints: Optional[List] = None
    ):
        self.kb = knowledge_base
        self.trail = TrailStack()
        from .constraints.core import ConstraintSolver

        self.constraint_solver = ConstraintSolver(constraints or [])

    def search(
        self, goal: Any, substitution: Optional[Substitution] = None
    ) -> Generator[Substitution, None, None]:
        if substitution is None:
            substitution = Substitution()
        mark = self.trail.mark()
        try:
            yield from self._dfs(goal, substitution)
        finally:
            self.trail.backtrack(mark)

    def _dfs(
        self, goal: Any, substitution: Substitution
    ) -> Generator[Substitution, None, None]:
        goal = apply_substitution(goal, substitution)

        # 检查约束是否满足
        if not self.constraint_solver.check_constraints(substitution):
            return

        if isinstance(goal, LogicStruct):
            yield from self._match_struct(goal, substitution)
        elif isinstance(goal, LogicVariable):
            if substitution.is_bound(goal):
                bound_value = substitution.get_value(goal)
                if bound_value == goal:
                    yield substitution
            else:
                yield substitution
        else:
            yield substitution

    def _match_struct(
        self, struct: LogicStruct, substitution: Substitution
    ) -> Generator[Substitution, None, None]:
        predicate = struct.predicate

        for fact in self.kb.get_facts(predicate):
            mark = self.trail.mark()
            try:
                new_subst = substitution.copy()
                unify(struct, fact, new_subst)
                # 检查新替换是否满足约束
                if self.constraint_solver.check_constraints(new_subst):
                    yield new_subst
            except Exception:
                self.trail.backtrack(mark)

        for head, body in self.kb.get_rules(predicate):
            mark = self.trail.mark()
            try:
                new_subst = substitution.copy()
                unify(struct, head, new_subst)
                # 检查统一化后的替换是否满足约束
                if self.constraint_solver.check_constraints(new_subst):
                    yield from self._solve_body(body, new_subst)
            except Exception:
                self.trail.backtrack(mark)

    def _solve_body(
        self, body: list, substitution: Substitution
    ) -> Generator[Substitution, None, None]:
        if not body:
            yield substitution
            return

        first = body[0]
        rest = body[1:]

        for subst in self._dfs(first, substitution):
            if rest:
                yield from self._solve_body(rest, subst)
            else:
                yield subst

    def find_one(
        self, goal: Any, substitution: Optional[Substitution] = None
    ) -> Optional[Substitution]:
        for solution in self.search(goal, substitution):
            return solution
        return None

    def find_all(
        self, goal: Any, substitution: Optional[Substitution] = None
    ) -> list[Substitution]:
        return list(self.search(goal, substitution))

    def count_solutions(
        self,
        goal: Any,
        substitution: Optional[Substitution] = None,
        max_count: int = 1000,
    ) -> int:
        count = 0
        for _ in self.search(goal, substitution):
            count += 1
            if count >= max_count:
                break
        return count


def cut() -> None:
    raise NotImplementedError("Cut operator needs integration with searcher")


def once(goal: Any, backtracker: Backtracker) -> Optional[Substitution]:
    return backtracker.find_one(goal)
