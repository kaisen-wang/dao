"""
求解器功能测试
================

测试 Solver 类的功能，包括：
- 查询执行
- 结果格式化
- 查询方法重载
- 约束集成
- 性能边界情况

这些测试确保逻辑编程引擎的求解器部分正常工作。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

import pytest
from dao.logic.constraints.core import NumericRangeConstraint
from dao.logic.core import KnowledgeBase, LogicAtom, LogicStruct, LogicVariable
from dao.logic.solver import Solver


class TestSolverBasicQueries:
    """测试求解器的基本查询功能"""

    def test_solve_one_simple_query(self):
        """测试 solve_one 方法的简单查询"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("父母", (LogicAtom("张三"), LogicAtom("小明"))))
        kb.add_fact(LogicStruct("父母", (LogicAtom("李四"), LogicAtom("小红"))))

        solver = Solver(kb)
        x = LogicVariable("?x")
        result = solver.solve_one(LogicStruct("父母", (x, LogicAtom("小明"))))

        assert result is not None
        assert result.to_dict()["?x"] == "张三"

    def test_solve_multiple_results(self):
        """测试 solve 方法返回多个结果"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("兄弟", (LogicAtom("小明"), LogicAtom("小红"))))
        kb.add_fact(LogicStruct("兄弟", (LogicAtom("小明"), LogicAtom("小刚"))))
        kb.add_fact(LogicStruct("兄弟", (LogicAtom("小红"), LogicAtom("小刚"))))

        solver = Solver(kb)
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        results = solver.solve(LogicStruct("兄弟", (x, y)))

        assert len(results) == 3
        assert any(
            result.to_dict()["?x"] == "小明" and result.to_dict()["?y"] == "小红"
            for result in results
        )
        assert any(
            result.to_dict()["?x"] == "小明" and result.to_dict()["?y"] == "小刚"
            for result in results
        )

    def test_solve_with_max_solutions(self):
        """测试 solve 方法的 max_solutions 参数"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("数字", (LogicAtom(1),)))
        kb.add_fact(LogicStruct("数字", (LogicAtom(2),)))
        kb.add_fact(LogicStruct("数字", (LogicAtom(3),)))

        solver = Solver(kb)
        x = LogicVariable("?x")
        results = solver.solve(LogicStruct("数字", (x,)), max_solutions=2)

        assert len(results) == 2

    def test_solve_generator(self):
        """测试 solve_generator 方法"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("颜色", (LogicAtom("红色"),)))
        kb.add_fact(LogicStruct("颜色", (LogicAtom("蓝色"),)))

        solver = Solver(kb)
        x = LogicVariable("?x")
        generator = solver.solve_generator(LogicStruct("颜色", (x,)))

        results = list(generator)
        assert len(results) == 2
        assert any(result.to_dict()["?x"] == "红色" for result in results)
        assert any(result.to_dict()["?x"] == "蓝色" for result in results)


class TestSolverQueryMethods:
    """测试求解器的查询方法重载"""

    def test_exists_query(self):
        """测试 exists 方法"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("动物", (LogicAtom("狗"),)))

        solver = Solver(kb)
        x = LogicVariable("?x")

        assert solver.exists(LogicStruct("动物", (x,))) is True
        assert solver.exists(LogicStruct("植物", (x,))) is False

    def test_count_solutions(self):
        """测试 count_solutions 方法"""
        kb = KnowledgeBase("测试知识库")
        for i in range(5):
            kb.add_fact(LogicStruct("数字", (LogicAtom(i),)))

        solver = Solver(kb)
        x = LogicVariable("?x")

        assert solver.count_solutions(LogicStruct("数字", (x,))) == 5
        assert solver.count_solutions(LogicStruct("数字", (x,)), max_count=3) == 3


class TestSolverWithConstraints:
    """测试包含约束的求解器查询"""

    def test_query_with_range_constraint(self):
        """测试带范围约束的查询"""
        kb = KnowledgeBase("测试知识库")
        for i in range(10):
            kb.add_fact(LogicStruct("数字", (LogicAtom(i),)))

        x = LogicVariable("?x")
        constraints = [NumericRangeConstraint(x, 3, 7)]

        solver = Solver(kb, constraints)
        results = solver.solve(LogicStruct("数字", (x,)))

        assert len(results) == 5
        values = [list(result.to_dict().values())[0] for result in results]
        assert all(3 <= v <= 7 for v in values)

    def test_query_with_invalid_constraints(self):
        """测试包含无效约束的查询"""
        kb = KnowledgeBase("测试知识库")
        for i in range(5):
            kb.add_fact(LogicStruct("数字", (LogicAtom(i),)))

        x = LogicVariable("?x")
        constraints = [NumericRangeConstraint(x, 6, 10)]

        solver = Solver(kb, constraints)
        results = solver.solve(LogicStruct("数字", (x,)))

        assert len(results) == 0

    def test_add_remove_constraints(self):
        """测试添加和删除约束"""
        kb = KnowledgeBase("测试知识库")
        for i in range(5):
            kb.add_fact(LogicStruct("数字", (LogicAtom(i),)))

        x = LogicVariable("?x")
        constraint1 = NumericRangeConstraint(x, 0, 2)
        constraint2 = NumericRangeConstraint(x, 3, 4)

        solver = Solver(kb, [constraint1])
        results1 = solver.solve(LogicStruct("数字", (x,)))
        assert len(results1) == 3

        solver.add_constraint(constraint2)
        results2 = solver.solve(LogicStruct("数字", (x,)))
        assert len(results2) == 0

        solver.remove_constraint(constraint2)
        results3 = solver.solve(LogicStruct("数字", (x,)))
        assert len(results3) == 3


class TestQueryResultFormatting:
    """测试查询结果格式化"""

    def test_query_result_to_dict(self):
        """测试 QueryResult 的 to_dict 方法"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("学生", (LogicAtom("张三"), LogicAtom(18))))

        solver = Solver(kb)
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        result = solver.solve_one(LogicStruct("学生", (x, y)))

        from dao.logic.solver import QueryResult

        assert isinstance(result, QueryResult)
        data = result.to_dict()
        assert data["?x"] == "张三"
        assert data["?y"] == 18

    def test_query_result_repr(self):
        """测试 QueryResult 的 __repr__ 方法"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("水果", (LogicAtom("苹果"), LogicAtom(5))))

        solver = Solver(kb)
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        result = solver.solve_one(LogicStruct("水果", (x, y)))

        assert repr(result).startswith("{")
        assert "?x='苹果'" in repr(result)
        assert "?y=5" in repr(result)


class TestQueryFunction:
    """测试 query 函数"""

    def test_query_function_basic(self):
        """测试 query 函数的基本用法"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("城市", (LogicAtom("北京"), LogicAtom("中国"))))
        kb.add_fact(LogicStruct("城市", (LogicAtom("上海"), LogicAtom("中国"))))

        from dao.logic.solver import query

        results = query(kb, "城市(?x, '中国')")
        assert len(results) == 2
        assert any(result["?x"] == "北京" for result in results)
        assert any(result["?x"] == "上海" for result in results)

    def test_query_function_with_variables(self):
        """测试 query 函数使用变量"""
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("产品", (LogicAtom("手机"), LogicAtom("电子产品"))))
        kb.add_fact(LogicStruct("产品", (LogicAtom("书"), LogicAtom("文具"))))

        from dao.logic.solver import query

        results = query(kb, "产品(?x, ?y)")
        assert len(results) == 2
        assert any(
            result["?x"] == "手机" and result["?y"] == "电子产品" for result in results
        )
        assert any(
            result["?x"] == "书" and result["?y"] == "文具" for result in results
        )

    def test_query_function_invalid_format(self):
        """测试 query 函数的无效格式"""
        kb = KnowledgeBase("测试知识库")
        from dao.logic.exceptions import QueryError

        with pytest.raises(QueryError):
            from dao.logic.solver import query

            query(kb, "无效格式")


class TestQueryPerformance:
    """测试查询性能"""

    def test_query_with_large_knowledge_base(self):
        """测试查询大型知识库的性能"""
        kb = KnowledgeBase("测试知识库")
        for i in range(1000):
            kb.add_fact(LogicStruct("数据", (LogicAtom(i),)))

        solver = Solver(kb)
        x = LogicVariable("?x")
        results = solver.solve(LogicStruct("数据", (x,)), max_solutions=100)
        assert len(results) == 100

    def test_query_with_depth_limit(self):
        """测试查询深度限制"""
        kb = KnowledgeBase("测试知识库")
        solver = Solver(kb)

        # 测试无深度限制的查询（虽然我们的当前实现没有深度限制）
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
