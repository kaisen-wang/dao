# -*- coding: utf-8 -*-
from typing import Any, List, Set, Dict
from .core import LogicVariable, LogicAtom, Substitution
from .exceptions import ConstraintError

class RangeConstraint:
    def __init__(self, var: LogicVariable, low: int, high: int):
        self.var = var
        self.low = low
        self.high = high

    def is_satisfied(self, substitution: Substitution) -> bool:
        value = substitution.get_value(self.var)
        if value is None or isinstance(value, LogicVariable):
            return True
        if isinstance(value, LogicAtom):
            val = value.value
        else:
            val = value
        return isinstance(val, int) and self.low <= val <= self.high

    def get_domain(self) -> Set[int]:
        return set(range(self.low, self.high + 1))

    def __repr__(self) -> str:
        return f"{self.var.name} in [{self.low}, {self.high}]"

class AllDifferentConstraint:
    def __init__(self, variables: List[LogicVariable]):
        self.variables = variables

    def is_satisfied(self, substitution: Substitution) -> bool:
        values = []
        for var in self.variables:
            val = substitution.get_value(var)
            if val is None or isinstance(val, LogicVariable):
                continue
            if isinstance(val, LogicAtom):
                val = val.value
            values.append(val)
        return len(values) == len(set(values))

    def __repr__(self) -> str:
        vars_str = ', '.join(v.name for v in self.variables)
        return f"all_different({vars_str})"

class ConstraintSolver:
    def __init__(self):
        self.constraints = []

    def add_constraint(self, constraint) -> None:
        self.constraints.append(constraint)

    def is_satisfied(self, substitution: Substitution) -> bool:
        for constraint in self.constraints:
            if not constraint.is_satisfied(substitution):
                return False
        return True

    def solve_with_back(
        self,
        variables: List[LogicVariable],
        domains: Dict[LogicVariable, Set[int]],
        substitution: Substitution = None,
        index: int = 0
    ) -> List[Substitution]:
        if substitution is None:
            substitution = Substitution()
        
        if index >= len(variables):
            if self.is_satisfied(substitution):
                return [substitution.copy()]
            return []
        
        var = variables[index]
        solutions = []
        
        for value in domains.get(var, set()):
            new_subst = substitution.copy()
            new_subst.bind(var, LogicAtom(value))
            
            if self.is_satisfied(new_subst):
                solutions.extend(
                    self.solve_with_back(variables, domains, new_subst, index + 1)
                )
        
        return solutions

    def solve_all(
        self,
        variables: List[LogicVariable],
        domains: Dict[LogicVariable, Set[int]]
    ) -> List[Substitution]:
        return self.solve_with_back(variables, domains)

    def solve_one(
        self,
        variables: List[LogicVariable],
        domains: Dict[LogicVariable, Set[int]]
    ) -> Substitution | None:
        solutions = self.solve_with_back(variables, domains)
        return solutions[0] if solutions else None

    def count_solutions(
        self,
        variables: List[LogicVariable],
        domains: Dict[LogicVariable, Set[int]]
    ) -> int:
        return len(self.solve_with_back(variables, domains))

def in_range(var: LogicVariable, low: int, high: int) -> RangeConstraint:
    return RangeConstraint(var, low, high)

def all_different(variables: List[LogicVariable]) -> AllDifferentConstraint:
    return AllDifferentConstraint(variables)
