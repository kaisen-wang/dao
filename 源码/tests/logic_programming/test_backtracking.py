"""
回溯求解器功能测试
====================

测试 Backtracker 和 TrailStack 的功能，包括：
- 回溯机制
- 搜索策略
- 标记和回溯操作
- 变量绑定管理
- 深度优先搜索

这些测试验证逻辑编程引擎的回溯和搜索功能。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

import pytest
from dao.logic.backtracking import Backtracker, TrailStack
from dao.logic.constraints.core import NumericRangeConstraint
from dao.logic.core import (
    KnowledgeBase,
    LogicAtom,
    LogicStruct,
    LogicVariable,
    Substitution,
)
from dao.logic.unification import unify


class TestTrailStack:
    """测试 TrailStack（回溯栈）"""

    def test_trail_stack_initialization(self):
        """测试 TrailStack 的初始化"""
        trail = TrailStack()
        assert trail.get_mark_count() == 0
        assert trail.get_binding_count() == 0
        assert repr(trail) == "TrailStack(marks=0, bindings=0)"

    def test_trail_stack_mark_and_backtrack(self):
        """测试标记和回溯操作"""
        trail = TrailStack()
        x = LogicVariable("?x")

        mark = trail.mark()
        trail.bind(x, LogicAtom("值1"))
        trail.bind(x, LogicAtom("值2"))

        assert trail.get_mark_count() == 1
        assert trail.get_binding_count() == 2

        trail.backtrack(mark)
        assert trail.get_binding_count() == 0
        assert x.bound_to is None

    def test_nested_marks(self):
        """测试嵌套的标记和回溯"""
        trail = TrailStack()
        x = LogicVariable("?x")

        mark1 = trail.mark()
        trail.bind(x, LogicAtom("值1"))

        mark2 = trail.mark()
        trail.bind(x, LogicAtom("值2"))

        assert trail.get_mark_count() == 2
        assert trail.get_binding_count() == 2

        trail.backtrack(mark2)
        assert x.bound_to == "值1"
        trail.backtrack(mark1)
        assert x.bound_to is None

    def test_invalid_mark_id(self):
        """测试无效的标记ID"""
        trail = TrailStack()
        with pytest.raises(ValueError):
            trail.backtrack(1)
        with pytest.raises(ValueError):
            trail.backtrack(-1)


class TestBacktrackerBasic:
    """测试 Backtracker 的基本功能"""

    def test_backtracker_initialization(self):
        """测试 Backtracker 的初始化"""
        kb = KnowledgeBase("测试知识库")
        backtracker = Backtracker(kb)
        assert backtracker is not None

    def test_simple_fact_search(self):
        """测试简单的事实搜索"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("父母", (LogicAtom("张三"), LogicAtom("小明"))))
        kb.add_fact(LogicStruct("父母", (LogicAtom("李四"), LogicAtom("小红"))))

        backtracker = Backtracker(kb)
        x = LogicVariable("?x")
        goal = LogicStruct("父母", (x, LogicAtom("小明")))

        solutions = list(backtracker.search(goal))
        assert len(solutions) == 1
        assert solutions[0].get_value(x).value == "张三"

    def test_multiple_solutions_search(self):
        """测试返回多个解的搜索"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("朋友", (LogicAtom("小明"), LogicAtom("小红"))))
        kb.add_fact(LogicStruct("朋友", (LogicAtom("小明"), LogicAtom("小刚"))))
        kb.add_fact(LogicStruct("朋友", (LogicAtom("小红"), LogicAtom("小刚"))))

        backtracker = Backtracker(kb)
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        goal = LogicStruct("朋友", (x, y))

        solutions = list(backtracker.search(goal))
        assert len(solutions) == 3

    def test_no_solution_search(self):
        """测试无解决方案的搜索"""
        kb = KnowledgeBase("测试知识库")

        backtracker = Backtracker(kb)
        x = LogicVariable("?x")
        goal = LogicStruct("不存在的谓词", (x,))

        solutions = list(backtracker.search(goal))
        assert len(solutions) == 0


class TestBacktrackerWithVariables:
    """测试涉及变量的搜索"""

    def test_variable_in_query(self):
        """测试查询中包含变量"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("学生", (LogicAtom("张三"), LogicAtom("数学"))))
        kb.add_fact(LogicStruct("学生", (LogicAtom("李四"), LogicAtom("语文"))))
        kb.add_fact(LogicStruct("学生", (LogicAtom("王五"), LogicAtom("数学"))))

        backtracker = Backtracker(kb)
        name = LogicVariable("?name")
        course = LogicVariable("?course")

        solutions = list(backtracker.search(LogicStruct("学生", (name, course))))
        assert len(solutions) == 3

        course_values = set()
        for solution in solutions:
            course_value = solution.get_value(course)
            course_values.add(course_value.value)

        assert "数学" in course_values
        assert "语文" in course_values


class TestBacktrackerWithConstraints:
    """测试包含约束的搜索"""

    def test_backtracker_with_range_constraint(self):
        """测试包含范围约束的搜索"""
        kb = KnowledgeBase("测试知识库")
        for i in range(10):
            kb.add_fact(LogicStruct("数字", (LogicAtom(i),)))

        x = LogicVariable("?x")
        constraints = [NumericRangeConstraint(x, 3, 7)]

        backtracker = Backtracker(kb, constraints)
        goal = LogicStruct("数字", (x,))

        solutions = list(backtracker.search(goal))
        assert len(solutions) == 5

        values = []
        for solution in solutions:
            values.append(solution.get_value(x).value)

        assert all(3 <= v <= 7 for v in values)

    def test_backtracker_with_type_constraint(self):
        """测试包含类型约束的搜索"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("数据", (LogicAtom("字符串"),)))
        kb.add_fact(LogicStruct("数据", (LogicAtom(123),)))
        kb.add_fact(LogicStruct("数据", (LogicAtom(True),)))

        x = LogicVariable("?x")
        constraints = [NumericRangeConstraint(x, 0, 200)]

        backtracker = Backtracker(kb, constraints)
        goal = LogicStruct("数据", (x,))

        solutions = list(backtracker.search(goal))
        # 只有123是数字且在0-100范围内，所以应该只有一个解
        assert len(solutions) == 1
        assert solutions[0].get_value(x).value == 123


class TestBacktrackerAdvanced:
    """测试 Backtracker 的高级功能"""

    def test_nested_query_search(self):
        """测试嵌套查询的搜索（虽然我们的实现没有直接支持）"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("父母", (LogicAtom("张三"), LogicAtom("小明"))))
        kb.add_fact(LogicStruct("父母", (LogicAtom("李四"), LogicAtom("小红"))))
        kb.add_fact(LogicStruct("父母", (LogicAtom("王五"), LogicAtom("小刚"))))
        kb.add_fact(LogicStruct("祖父母", (LogicAtom("赵六"), LogicAtom("张三"))))
        kb.add_fact(LogicStruct("祖父母", (LogicAtom("钱七"), LogicAtom("李四"))))

        # 添加规则：祖父母(X, Z) :- 父母(X, Y), 父母(Y, Z)
        grandparent_rule = (
            LogicStruct("祖父母", (LogicVariable("?X"), LogicVariable("?Z"))),
            [
                LogicStruct("父母", (LogicVariable("?X"), LogicVariable("?Y"))),
                LogicStruct("父母", (LogicVariable("?Y"), LogicVariable("?Z"))),
            ],
        )
        kb.add_rule(*grandparent_rule)

        backtracker = Backtracker(kb)
        x = LogicVariable("?x")
        z = LogicVariable("?z")
        solutions = list(backtracker.search(LogicStruct("祖父母", (x, z))))

        # 预期有两个祖父母关系：赵六是小明的祖父母，钱七是小红的祖父母
        assert len(solutions) == 2

    def test_empty_knowledge_base(self):
        """测试空知识库的搜索"""
        kb = KnowledgeBase("测试知识库")
        backtracker = Backtracker(kb)
        x = LogicVariable("?x")

        solutions = list(backtracker.search(LogicStruct("任何谓词", (x,))))
        assert len(solutions) == 0

    def test_query_with_no_variables(self):
        """测试不含变量的查询"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("问候", (LogicAtom("你好"),)))

        backtracker = Backtracker(kb)
        solutions = list(backtracker.search(LogicStruct("问候", (LogicAtom("你好"),))))

        assert len(solutions) == 1


class TestBacktrackerPerformance:
    """测试 Backtracker 的性能"""

    def test_backtracker_with_large_fact_base(self):
        """测试 Backtracker 处理大量事实的性能"""
        kb = KnowledgeBase("大型知识库")
        for i in range(1000):
            kb.add_fact(LogicStruct("数字", (LogicAtom(i),)))

        backtracker = Backtracker(kb)
        x = LogicVariable("?x")

        solutions = list(backtracker.search(LogicStruct("数字", (x,))))
        assert len(solutions) == 1000

    def test_backtracker_with_deep_recursion(self):
        """测试深度递归搜索的性能"""
        kb = KnowledgeBase("递归知识库")
        n = 50

        # 这不会创建深度递归，因为我们的知识库没有规则链
        for i in range(n):
            kb.add_fact(LogicStruct("数据", (LogicAtom(i),)))

        backtracker = Backtracker(kb)
        x = LogicVariable("?x")

        solutions = list(backtracker.search(LogicStruct("数据", (x,))))
        assert len(solutions) == n


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
