# -*- coding: utf-8 -*-
"""
家庭关系推理示例
演示逻辑编程的基本功能：事实、规则和查询
"""

from dao.logic.core import LogicVariable, LogicAtom, LogicStruct, KnowledgeBase
from dao.logic.solver import solve

# 创建知识库
kb = KnowledgeBase("家庭关系")

# 添加事实
kb.add_fact(LogicStruct("父母", ("张三", "小明")))
kb.add_fact(LogicStruct("父母", ("李四", "小明")))
kb.add_fact(LogicStruct("父母", ("张三", "小红")))
kb.add_fact(LogicStruct("父母", ("小明", "乐乐")))

# 添加规则：祖父母
# 祖父母(?祖, ?孙) 如果 父母(?祖, ?父) 并且 父母(?父, ?孙)
grandparent_rule_head = LogicStruct("祖父母", ("?祖", "?孙"))
grandparent_rule_body = [
    LogicStruct("父母", ("?祖", "?父")),
    LogicStruct("父母", ("?父", "?孙"))
]
kb.add_rule(grandparent_rule_head, grandparent_rule_body)

# 添加规则：兄弟姐妹
# 兄弟姐妹(?甲, ?乙) 如果 父母(?父, ?甲) 并且 父母(?父, ?乙) 并且 ?甲 != ?乙
# Note: Not equal constraint would be implemented separately

print("=" * 50)
print("家庭关系知识库")
print("=" * 50)
print(kb)
print()

# 查询1：张三的子女
print("查询1：张三的子女")
x = LogicVariable("?x")
goal1 = LogicStruct("父母", ("张三", x))
results1 = solve(kb, goal1)

for result in results1:
    child = result.get_binding(x.name)
    print(f"  张三的孩子是: {child.value}")
print()

# 查询2：张三的孙辈
print("查询2：张三的孙辈")
y = LogicVariable("?y")
goal2 = LogicStruct("祖父母", ("张三", y))
results2 = solve(kb, goal2)

for result in results2:
    grandchild = result.get_binding(y.name)
    print(f"  张三的孙辈是: {grandchild.value}")
print()

# 查询3：小明的父母
谁 = LogicVariable("?谁")
goal3 = LogicStruct("父母", (谁, "小明"))
results3 = solve(kb, goal3)

print("查询3：小明的父母")
for result in results3:
    parent = result.get_binding(谁.name)
    print(f"  小明的父母是: {parent.value}")
print()

print("=" * 50)
print("查询完成！")
print("=" * 50)
