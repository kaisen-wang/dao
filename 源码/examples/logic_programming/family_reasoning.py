# -*- coding: utf-8 -*-
"""
Family Relationship Reasoning Example
Using Dao language's logic programming engine
"""

from dao.logic.core import LogicVariable, LogicAtom, LogicStruct, KnowledgeBase
from dao.logic.solver import solve


def main():
    # Create a family knowledge base
    kb = KnowledgeBase("Family Relations")
    
    # Add facts
    kb.add_fact(LogicStruct("parent", ("ZhangSan", "XiaoMing")))
    kb.add_fact(LogicStruct("parent", ("LiSi", "XiaoMing")))
    kb.add_fact(LogicStruct("parent", ("ZhangSan", "XiaoHong")))
    kb.add_fact(LogicStruct("parent", ("XiaoMing", "LeLe")))
    
    # Add rule: grandparent
    # Rule: grandparent(?gp, ?gc) if parent(?gp, ?p) and parent(?p, ?gc)
    grandparent = LogicVariable("?grandparent")
    parent = LogicVariable("?parent")
    grandchild = LogicVariable("?grandchild")
    
    rule_head = LogicStruct("grandparent", (grandparent, grandchild))
    rule_body = [
        LogicStruct("parent", (grandparent, parent)),
        LogicStruct("parent", (parent, grandchild))
    ]
    kb.add_rule(rule_head, rule_body)
    
    print("=" * 60)
    print("Family Knowledge Base")
    print("=" * 60)
    print(kb)
    print()
    
    # Query 1: Who are ZhangSan's children?
    print("Query 1: Who are ZhangSan's children?")
    print("-" * 60)
    child = LogicVariable("?child")
    goal1 = LogicStruct("parent", ("ZhangSan", child))
    
    results = solve(kb, goal1)
    for result in results:
        bound = result.get_binding(child.name)
        if hasattr(bound, 'value'):
            print(f"  ZhangSan's child: {bound.value}")
    print()
    
    # Query 2: Who are ZhangSan's grandchildren?
    print("Query 2: Who are ZhangSan's grandchildren? (via rule)")
    print("-" * 60)
    grandchild_var = LogicVariable("?grandchild")
    goal2 = LogicStruct("grandparent", ("ZhangSan", grandchild_var))
    
    results = solve(kb, goal2)
    for result in results:
        bound = result.get_binding(grandchild_var.name)
        if hasattr(bound, 'value'):
            print(f"  ZhangSan's grandchild: {bound.value}")
    print()
    
    # Query 3: Who are XiaoMing's parents?
    print("Query 3: Who are XiaoMing's parents?")
    print("-" * 60)
    parent_var = LogicVariable("?parent")
    goal3 = LogicStruct("parent", (parent_var, "XiaoMing"))
    
    results = solve(kb, goal3)
    for result in results:
        bound = result.get_binding(parent_var.name)
        if hasattr(bound, 'value'):
            print(f"  {bound.value} is XiaoMing's parent")
    print()
    
    # Query 4: All parent relationships
    print("Query 4: All parent relationships")
    print("-" * 60)
    p1 = LogicVariable("?p1")
    p2 = LogicVariable("?p2")
    goal4 = LogicStruct("parent", (p1, p2))
    
    results = solve(kb, goal4)
    for result in results:
        bound1 = result.get_binding(p1.name)
        bound2 = result.get_binding(p2.name)
        if hasattr(bound1, 'value') and hasattr(bound2, 'value'):
            print(f"  {bound1.value} is parent of {bound2.value}")
    print()
    
    print("=" * 60)
    print("Query Complete!")
    print("=" * 60)
    
    # Demonstrate reasoning
    print()
    print("Reasoning Demonstration:")
    print("-" * 60)
    print("Although the knowledge base doesn't directly store")
    print("'ZhangSan is grandparent of LeLe',")
    print("the system can infer it via the rule:")
    print("  grandparent(?gp, ?gc) if parent(?gp, ?p) and parent(?p, ?gc)")
    print("Chain: ZhangSan -> XiaoMing -> LeLe")
    print("Therefore, ZhangSan is LeLe's grandparent!")
    print()


if __name__ == "__main__":
    main()
