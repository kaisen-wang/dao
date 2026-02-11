# -*- coding: utf-8 -*-
"""Unification Algorithm Implementation"""

from typing import Any
from .core import LogicVariable, LogicAtom, LogicStruct, Substitution, normalize_term
from .exceptions import UnificationError, CircularRuleError


def occurs_check(var: LogicVariable, term: Any) -> bool:
    """Check if variable occurs in term"""
    if isinstance(term, LogicVariable):
        return var == term
    elif isinstance(term, LogicStruct):
        return any(occurs_check(var, arg) for arg in term.args)
    elif isinstance(term, list) or isinstance(term, tuple):
        return any(occurs_check(var, item) for item in term)
    elif isinstance(term, dict):
        return any(occurs_check(var, value) for value in term.values())
    else:
        return False


def apply_substitution(term: Any, substitution: Substitution) -> Any:
    """Apply substitution to term"""
    if isinstance(term, LogicVariable):
        bound = substitution.get_value(term)
        if bound is not None:
            return apply_substitution(bound, substitution)
        return term

    elif isinstance(term, LogicStruct):
        new_args = tuple(apply_substitution(arg, substitution) for arg in term.args)
        if new_args == term.args:
            return term
        return LogicStruct(term.predicate, new_args)

    elif isinstance(term, list):
        return [apply_substitution(item, substitution) for item in term]

    elif isinstance(term, tuple):
        return tuple(apply_substitution(item, substitution) for item in term)

    elif isinstance(term, dict):
        return {k: apply_substitution(v, substitution) for k, v in term.items()}

    else:
        return term


def unify(term1: Any, term2: Any, substitution: Substitution | None = None) -> Substitution:
    """Unify two terms"""
    if substitution is None:
        substitution = Substitution()

    term1 = apply_substitution(term1, substitution)
    term2 = apply_substitution(term2, substitution)

    if term1 == term2:
        return substitution

    if isinstance(term1, LogicVariable):
        return _unify_variable(term1, term2, substitution)

    if isinstance(term2, LogicVariable):
        return _unify_variable(term2, term1, substitution)

    if isinstance(term1, LogicStruct) and isinstance(term2, LogicStruct):
        return _unify_struct(term1, term2, substitution)

    if isinstance(term1, LogicAtom) and isinstance(term2, LogicAtom):
        if term1.value == term2.value:
            return substitution
        raise UnificationError(f"Cannot unify different atoms: {term1} != {term2}")

    if isinstance(term1, LogicAtom):
        term1_val = term1.value
    else:
        term1_val = term1

    if isinstance(term2, LogicAtom):
        term2_val = term2.value
    else:
        term2_val = term2

    if term1_val == term2_val:
        return substitution

    raise UnificationError(f"Cannot unify different types: {type(term1).__name__} vs {type(term2).__name__}")


def _unify_variable(var: LogicVariable, term: Any, substitution: Substitution) -> Substitution:
    """Unify variable with term"""
    if substitution.is_bound(var):
        bound_value = substitution.get_value(var)
        return unify(bound_value, term, substitution)

    if occurs_check(var, term):
        raise CircularRuleError(f"Circular binding: variable {var} occurs in term {term}")

    return substitution


def _unify_struct(struct1: LogicStruct, struct2: LogicStruct, substitution: Substitution) -> Substitution:
    """Unify two structures"""
    if struct1.predicate != struct2.predicate:
        raise UnificationError(f"Different predicates: {struct1.predicate} vs {struct2.predicate}")

    if len(struct1.args) != len(struct2.args):
        raise UnificationError(f"Different arities: {struct1.predicate} has {len(struct1.args)} vs {len(struct2.args)}")

    for arg1, arg2 in zip(struct1.args, struct2.args):
        substitution = unify(arg1, arg2, substitution)

    return substitution


def unify_list(list1: list, list2: list, substitution: Substitution | None = None) -> Substitution:
    """Unify two lists"""
    if substitution is None:
        substitution = Substitution()

    if len(list1) != len(list2):
        raise UnificationError(f"Different list lengths: {len(list1)} vs {len(list2)}")

    for item1, item2 in zip(list1, list2):
        substitution = unify(item1, item2, substitution)

    return substitution


def is_unifiable(term1: Any, term2: Any, substitution: Substitution | None = None) -> bool:
    """Check if two terms can be unified"""
    try:
        unify(term1, term2, substitution)
        return True
    except (UnificationError, CircularRuleError):
        return False
