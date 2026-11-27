"""逻辑编程与常规代码集成测试（任务 §7）。

覆盖：便捷调用语法、结果映射为道语言列表/字典、逻辑变量互操作、
查询结果作为函数返回值，并验证既有 ``查询(kb, 谓词(?x))`` 语义未破坏。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import pytest

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter.core import Interpreter


def 执行(源码: str):
    tree = Parser(Lexer(源码).tokenize()).parse()
    Interpreter().execute(tree, source=源码)


class TestLogicQueryBuiltin:
    """便捷调用语法：逻辑查询()"""

    def test_基本查询(self, capsys):
        执行(
            '''
逻辑 数据
    事实: 城市("北京", "中国")
    事实: 城市("上海", "中国")
定义 r = 逻辑查询(数据, "城市(?x, ?y)")
打印(r)
'''
        )
        输出 = capsys.readouterr().out
        assert "?x" in 输出 and "北京" in 输出 and "上海" in 输出

    def test_复合查询与排序分页(self, capsys):
        执行(
            '''
逻辑 数据
    事实: 城市("北京", "中国")
    事实: 城市("上海", "中国")
    事实: 城市("东京", "日本")
定义 r = 逻辑查询(数据, "城市(?x, ?y)", 排序="?x", 限制=2)
打印(r)
'''
        )
        输出 = capsys.readouterr().out
        assert "东京" in 输出 and "上海" in 输出 and "北京" not in 输出

    def test_非法知识库参数(self):
        with pytest.raises(Exception, match="必须是知识库"):
            执行('定义 r = 逻辑查询(123, "城市(?x)")')

    def test_语法错误在道语言中传播(self):
        with pytest.raises(Exception, match="查询语法错误"):
            执行(
                '''
逻辑 数据
    事实: 城市("北京", "中国")
定义 r = 逻辑查询(数据, "城市(?x,")
'''
            )


class TestResultBuiltins:
    """格式化、列表与字典导出"""

    def test_格式化结果表格(self, capsys):
        执行(
            '''
逻辑 数据
    事实: 城市("北京", "中国")
定义 r = 逻辑查询(数据, "城市(?x, ?y)")
打印(格式化结果(r))
'''
        )
        输出 = capsys.readouterr().out
        assert "共 1 个解" in 输出 and "?x" in 输出 and "北京" in 输出

    def test_结果转列表与字典(self, capsys):
        执行(
            '''
逻辑 数据
    事实: 城市("北京", "中国")
定义 r = 逻辑查询(数据, "城市(?x, ?y)")
打印(结果转列表(r))
打印(结果转字典(r))
'''
        )
        输出 = capsys.readouterr().out
        assert "[['?x', '北京']" in 输出
        assert "{'?x': '北京'" in 输出

    def test_格式化结果错误路径(self):
        with pytest.raises(Exception, match="未知的结果格式"):
            执行('打印(格式化结果([], "饼图"))')


class TestLogicVariableInterop:
    """逻辑变量与道语言变量互操作"""

    def test_逻辑变量文本转换(self, capsys):
        执行(
            '''
定义 v1 = 逻辑变量("x")
定义 v2 = 逻辑变量("?y")
打印(v1)
打印(v2)
'''
        )
        输出 = capsys.readouterr().out
        assert "?x" in 输出 and "?y" in 输出

    def test_逻辑变量错误路径(self):
        with pytest.raises(Exception, match="必须是非空文本"):
            执行('定义 v = 逻辑变量(123)')

    def test_显式声明变量查询(self, capsys):
        执行(
            '''
逻辑 数据
    事实: 城市("北京", "中国")
定义 r = 逻辑查询(数据, "城市(x, y)", 变量=["x", "y"])
打印(r)
'''
        )
        输出 = capsys.readouterr().out
        assert "?x" in 输出 and "北京" in 输出

    def test_取绑定(self, capsys):
        执行(
            '''
逻辑 数据
    事实: 城市("北京", "中国")
定义 r = 逻辑查询(数据, "城市(?x, ?y)", 结果对象=真)
打印(取绑定(r[0], "x"))
'''
        )
        输出 = capsys.readouterr().out
        assert "北京" in 输出


class TestQueryAsReturnValue:
    """查询结果作为函数返回值"""

    def test_函数返回查询列表(self, capsys):
        执行(
            '''
逻辑 数据
    事实: 城市("北京", "中国")
    事实: 城市("上海", "中国")
函数 找城市(k)
    返回 逻辑查询(k, "城市(?x, ?y)")
定义 r = 找城市(数据)
打印(格式化结果(r))
'''
        )
        输出 = capsys.readouterr().out
        assert "共 2 个解" in 输出 and "北京" in 输出

    def test_既有查询表达式返回绑定(self, capsys):
        执行(
            '''
逻辑 数据
    事实: 城市("北京", "中国")
函数 找城市(k)
    返回 查询(k, 城市(?x, ?y))
定义 r = 找城市(数据)
打印(r[0]["?x"])
'''
        )
        输出 = capsys.readouterr().out
        assert "北京" in 输出
