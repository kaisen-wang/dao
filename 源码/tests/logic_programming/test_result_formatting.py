"""查询结果格式化与导出测试（任务 §5）。"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.errors import 类型错误
from dao.logic.core import KnowledgeBase, LogicAtom, LogicStruct
from dao.logic.solver import query
from dao.logic.result_utils import 格式化结果, 结果转字典, 结果转列表, 展示变量值


def make_results():
    kb = KnowledgeBase("测试库")
    kb.add_fact(LogicStruct("城市", (LogicAtom("北京"), LogicAtom("中国"))))
    kb.add_fact(LogicStruct("城市", (LogicAtom("上海"), LogicAtom("中国"))))
    return query(kb, "城市(?x, ?y)", 结果对象=True)


class TestFormatResult:
    """中文可读表格与绑定变量展示"""

    def test_表格文本(self):
        文本 = 格式化结果(make_results())
        assert "共 2 个解" in 文本
        assert "?x" in 文本 and "?y" in 文本
        assert "北京" in 文本 and "上海" in 文本
        assert "|" in 文本 and "-" in 文本

    def test_简洁文本(self):
        文本 = 格式化结果(make_results(), "简洁")
        assert "解1: ?x=北京, ?y=中国" in 文本
        assert "解2: ?x=上海, ?y=中国" in 文本

    def test_空结果(self):
        assert 格式化结果([]) == "无匹配结果"

    def test_字典输入(self):
        文本 = 格式化结果([{"?行动": "跑步", "?分数": 90}])
        assert "?行动" in 文本 and "跑步" in 文本

    def test_未知格式报错(self):
        with pytest.raises(类型错误, match="未知的结果格式"):
            格式化结果(make_results(), "饼图")

    def test_非法结果类型报错(self):
        with pytest.raises(类型错误, match="查询结果必须是"):
            格式化结果(123)

    def test_展示变量值(self):
        assert 展示变量值(True) == "真"
        assert 展示变量值(False) == "假"
        assert 展示变量值(None) == "未绑定"
        assert 展示变量值("北京") == "北京"


class TestExportResult:
    """导出为道语言列表/字典"""

    def test_结果转字典(self):
        结果 = 结果转字典(make_results())
        assert 结果 == [
            {"?x": "北京", "?y": "中国"},
            {"?x": "上海", "?y": "中国"},
        ]

    def test_结果转列表_含变量名(self):
        结果 = 结果转列表(make_results())
        assert 结果[0] == [["?x", "北京"], ["?y", "中国"]]

    def test_结果转列表_仅值(self):
        结果 = 结果转列表(make_results(), 含变量名=False)
        assert 结果 == [["北京", "中国"], ["上海", "中国"]]

    def test_结果转字典_单字典输入(self):
        assert 结果转字典({"?x": 1}) == [{"?x": 1}]


class TestQueryResultProtocol:
    """QueryResult 的字典式协议与自格式化"""

    def test_下标与键访问(self):
        结果 = make_results()[0]
        assert 结果["?x"] in ("北京", "上海")
        assert 结果.get("?y") == "中国"
        assert 结果.get("?不存在", "默认") == "默认"
        assert "?x" in 结果.keys()
        assert len(结果) == 2

    def test_to_list(self):
        结果 = make_results()[0]
        assert [对[0] for 对 in 结果.to_list()] == ["?x", "?y"]

    def test_自格式化(self):
        文本 = make_results()[0].格式化("简洁")
        assert "解1:" in 文本 and "?x=" in 文本
