# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Any, Hashable
from .exceptions import UnificationError, CircularRuleError

@dataclass
class LogicVariable:
    name: str
    bound_to: Any = None

    def __post_init__(self):
        if not self.name.startswith('?'):
            raise ValueError(f"Logic variable must start with ?, got: {self.name}")

    def is_bound(self) -> bool:
        return self.bound_to is not None

    def bind(self, value: Any) -> None:
        self.bound_to = value

    def unbind(self) -> None:
        self.bound_to = None

    def __repr__(self) -> str:
        if self.is_bound():
            return f"{self.name}={self.bound_to!r}"
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, LogicVariable):
            return self.name == other.name
        return False

@dataclass
class LogicAtom:
    value: Any

    def __repr__(self) -> str:
        return repr(self.value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, LogicAtom):
            return self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        if isinstance(self.value, Hashable):
            return hash(self.value)
        return hash(id(self.value))

@dataclass
class LogicStruct:
    predicate: str
    args: tuple[Any, ...]

    def __repr__(self) -> str:
        args_str = ', '.join(repr(arg) for arg in self.args)
        return f"{self.predicate}({args_str})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, LogicStruct):
            return self.predicate == other.predicate and self.args == other.args
        return False

    def __hash__(self) -> int:
        return hash((self.predicate, self.args))

    def arity(self) -> int:
        return len(self.args)

class Substitution(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._trail = []

    def bind(self, var: LogicVariable, value: Any) -> None:
        if var in self:
            self._trail.append(('update', var, self[var]))
        else:
            self._trail.append(('add', var))
        self[var.name] = value

    def get_value(self, var: LogicVariable) -> Any:
        return self.get(var.name, None)

    def is_bound(self, var: LogicVariable) -> bool:
        return var.name in self

    def mark(self) -> int:
        return len(self._trail)

    def backtrack(self, mark: int) -> None:
        while len(self._trail) > mark:
            action, var, *rest = self._trail.pop()
            if action == 'update':
                self[var.name] = rest[0]
            elif action == 'add':
                del self[var.name]

    def copy(self) -> 'Substitution':
        new_subst = Substitution(self)
        new_subst._trail = self._trail.copy()
        return new_subst

    def __repr__(self) -> str:
        items = ', '.join(f"{k}={v!r}" for k, v in self.items())
        return f"{{{items}}}"

class KnowledgeBase:
    def __init__(self, name: str = ""):
        self.name = name
        self.facts: dict[str, list[LogicStruct]] = {}
        self.rules: dict[str, list[tuple[LogicStruct, list[Any]]]] = {}
        self._fact_index = {}

    def add_fact(self, fact: LogicStruct) -> None:
        if fact.predicate not in self.facts:
            self.facts[fact.predicate] = []
        self.facts[fact.predicate].append(fact)

    def add_rule(self, head: LogicStruct, body: list[Any]) -> None:
        if head.predicate not in self.rules:
            self.rules[head.predicate] = []
        self.rules[head.predicate].append((head, body))

    def get_facts(self, predicate: str) -> list[LogicStruct]:
        return self.facts.get(predicate, [])

    def get_rules(self, predicate: str) -> list[tuple[LogicStruct, list[Any]]]:
        return self.rules.get(predicate, [])

    def remove_fact(self, fact: LogicStruct) -> bool:
        if fact.predicate in self.facts:
            try:
                self.facts[fact.predicate].remove(fact)
                return True
            except ValueError:
                return False
        return False

    def clear(self) -> None:
        self.facts.clear()
        self.rules.clear()

    def __repr__(self) -> str:
        result = f"KnowledgeBase: {self.name}"
        if self.facts:
            result += " Facts:"
            for pred, facts in self.facts.items():
                for fact in facts:
                    result += f" {fact}"
        if self.rules:
            result += " Rules:"
            for pred, rules in self.rules.items():
                for head, body in rules:
                    result += f" {head} if {body}"
        return result

def normalize_term(term: Any) -> Any:
    if isinstance(term, (LogicAtom, LogicVariable, LogicStruct)):
        return term
    if isinstance(term, str) and term.startswith('?'):
        return LogicVariable(term)
    if isinstance(term, (str, int, float, bool)):
        return LogicAtom(term)
    if isinstance(term, dict) and 'predicate' in term and 'args' in term:
        args_tuple = tuple(normalize_term(arg) for arg in term['args'])
        return LogicStruct(term['predicate'], args_tuple)
    return LogicAtom(term)
