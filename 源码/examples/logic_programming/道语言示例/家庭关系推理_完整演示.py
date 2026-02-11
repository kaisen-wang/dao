# -*- coding: utf-8 -*-
"""
家庭关系推理示例
使用道语言的逻辑编程引擎

这个示例演示了：
1. 创建知识库
2. 添加事实
3. 定义规则
4. 执行查询
5. 自动推理（通过规则）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from dao.logic.core import LogicVariable, LogicAtom, LogicStruct, KnowledgeBase
from dao.logic.solver import solve


def print_section(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def main():
    # 创建家庭知识库
    kb = KnowledgeBase("家庭关系")
    
    # 添加事实（父母关系）
    parent_facts = [
        ("张三", "小明"),
        ("李四", "小明"),
        ("张三", "小红"),
        ("小明", "乐乐"),
    ]
    
    for parent, child in parent_facts:
        kb.add_fact(LogicStruct("父母", (parent, child)))
    
    # 添加规则：祖父母
    # 规则：祖父母(?祖, ?孙) 如果 父母(?祖, ?父) 并且 父母(?父, ?孙)
    grandparent_var = LogicVariable("?祖父")
    parent_var = LogicVariable("?父亲")
    grandchild_var = LogicVariable("?孙辈")
    
    rule_head = LogicStruct("祖父母", (grandparent_var, grandchild_var))
    rule_body = [
        LogicStruct("父母", (grandparent_var, parent_var)),
        LogicStruct("父母", (parent_var, grandchild_var))
    ]
    kb.add_rule(rule_head, rule_body)
    
    # 显示知识库
    print_section("家庭关系知识库")
    print(kb)
    
    # 查询1：张三的子女
    print_section("查询1：张三的子女")
    print("-" * 60)
    child_var = LogicVariable("?孩子")
    goal1 = LogicStruct("父母", ("张三", child_var))
    
    results = solve(kb, goal1)
    if results:
        for result in results:
            bound = result.get_binding(child_var.name)
            if hasattr(bound, 'value'):
                print(f"  张三的孩子是: {bound.value}")
    else:
        print("  没有找到结果")
    
    # 查询2：张三的孙辈（通过规则推理）
    print_section("查询2：张三的孙辈（通过规则推理）")
    print("-" * 60)
    print("虽然知识库中没有直接存储'张三是乐乐的祖父母'")
    print("但通过规则'祖父母(?祖, ?孙) 如果 父母(?祖, ?父) 并且 父母(?父, ?孙)'")
    print("系统能够自动推理出：张三 -> 小明 -> 乐乐")
    print()
    
    grandchild_query = LogicVariable("?孙子")
    goal2 = LogicStruct("祖父母", ("张三", grandchild_query))
    
    results = solve(kb, goal2)
    if results:
        for result in results:
            bound = result.get_binding(grandchild_query.name)
            if hasattr(bound, 'value'):
                print(f"  张三的孙辈是: {bound.value}")
                print(f"  因此，张三是{bound.value}的祖父母！")
    else:
        print("  没有找到结果")
    
    # 查询3：小明的父母
    print_section("查询3：小明的父母")
    print("-" * 60)
    parent_query = LogicVariable("?父母")
    goal3 = LogicStruct("父母", (parent_query, "小明"))
    
    results = solve(kb, goal3)
    if results:
        for result in results:
            bound = result.get_binding(parent_query.name)
            if hasattr(bound, 'value'):
                print(f"  小明的父母是: {bound.value}")
    else:
        print("  没有找到结果")
    
    # 查询4：所有的父母关系
    print_section("查询4：所有的父母关系")
    print("-" * 60)
    p1 = LogicVariable("?父")
    c1 = LogicVariable("?子")
    goal4 = LogicStruct("父母", (p1, c1))
    
    results = solve(kb, goal4)
    if results:
        for result in results:
            bound_p = result.get_binding(p1.name)
            bound_c = result.get_binding(c1.name)
            if hasattr(bound_p, 'value') and hasattr(bound_c, 'value'):
                print(f"  {bound_p.value} 是 {bound_c.value} 的父母")
    else:
        print("  没有找到结果")
    
    # 查询5：谁是乐乐的父母？
    print_section("查询5：谁是乐乐的父母？")
    print("-" * 60)
    lele_parent = LogicVariable("?谁是乐乐的父母")
    goal5 = LogicStruct("父母", (lele_parent, "乐乐"))
    
    results = solve(kb, goal5)
    if results:
        for result in results:
            bound = result.get_binding(lele_parent.name)
            if hasattr(bound, 'value'):
                print(f"  {bound.value} 是乐乐的父母")
    else:
        print("  没有找到结果")
    
    # 推理能力总结
    print_section("推理能力总结")
    print("-" * 60)
    print("逻辑编程引擎展示了强大的自动推理能力：")
    print()
    print("1. 事实查询：直接从知识库中查找事实")
    print("   例：查询'张三的子女' -> 返回'小明'和'小红'")
    print()
    print("2. 规则推理：通过规则自动推导新关系")
    print("   例：查询'张三的孙辈' -> 推理路径：")
    print("       张三 -> 小明（事实）")
    print("       小明 -> 乐乐（事实）")
    print("       结论：张三 -> 乐乐（通过祖父母规则）")
    print()
    print("3. 变量绑定：支持多解查询")
    print("   例：查询'所有父母关系' -> 返回所有父母-子女对")
    print()
    print("这是声明式编程的精髓：")
    print("只需要告诉计算机'是什么'（事实和规则），")
    print("而不需要告诉计算机'怎么做'（推理过程）！")
    
    print()
    print("=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
