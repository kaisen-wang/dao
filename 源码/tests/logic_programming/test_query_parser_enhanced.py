"""增强版 query() 测试：嵌套结构、复合查询、中文错误、排序分页。

覆盖 ``任务/逻辑编程未实现功能.md`` §4 的四项缺口。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.logic.core import KnowledgeBase, LogicAtom, LogicStruct
from dao.logic.exceptions import QueryError
from dao.logic.solver import query


def build_kb() -> KnowledgeBase:
    kb = KnowledgeBase("测试库")
    kb.add_fact(LogicStruct("城市", (LogicAtom("北京"), LogicAtom("中国"))))
    kb.add_fact(LogicStruct("城市", (LogicAtom("上海"), LogicAtom("中国"))))
    kb.add_fact(LogicStruct("城市", (LogicAtom("东京"), LogicAtom("日本"))))
    kb.add_fact(LogicStruct("父母", (LogicAtom("张三"), LogicAtom("小明"))))
    kb.add_fact(LogicStruct("父母", (LogicAtom("张三"), LogicAtom("小红"))))
    kb.add_fact(LogicStruct("父母", (LogicAtom("李四"), LogicAtom("小强"))))
    kb.add_fact(LogicStruct("所在地", (LogicAtom("小明"), LogicAtom("北京"))))
    kb.add_fact(LogicStruct("所在地", (LogicAtom("小红"), LogicAtom("上海"))))
    return kb


class TestNestedQuery:
    """嵌套结构查询"""

    def test_嵌套结构_问号变量(self):
        kb = KnowledgeBase("家族")
        kb.add_fact(
            LogicStruct(
                "parent",
                (LogicStruct("grandparent", (LogicAtom("张三"),)), LogicAtom("小明")),
            )
        )
        results = query(kb, "parent(grandparent(?x), ?y)")
        assert results == [{"?x": "张三", "?y": "小明"}]

    def test_嵌套结构_大写变量兼容(self):
        kb = KnowledgeBase("家族")
        kb.add_fact(
            LogicStruct(
                "parent",
                (LogicStruct("grandparent", (LogicAtom("张三"),)), LogicAtom("小明")),
            )
        )
        results = query(kb, "parent(grandparent(X), Y)")
        assert results == [{"?X": "张三", "?Y": "小明"}]

    def test_嵌套结构_多层嵌套(self):
        kb = KnowledgeBase("家族")
        kb.add_fact(
            LogicStruct(
                "路径",
                (
                    LogicStruct(
                        "起点", (LogicStruct("坐标", (LogicAtom("甲"), LogicAtom("乙"))),)
                    ),
                    LogicAtom("终点"),
                ),
            )
        )
        results = query(kb, "路径(起点(坐标(?x, ?y)), ?z)")
        assert results == [{"?x": "甲", "?y": "乙", "?z": "终点"}]

    def test_嵌套结构_不匹配时返回空(self):
        kb = KnowledgeBase("家族")
        kb.add_fact(LogicStruct("parent", (LogicStruct("grandparent", (LogicAtom("张三"),)), LogicAtom("小明"))))
        assert query(kb, "parent(grandparent(?x), ?y, ?z)") == []


class TestCompoundQuery:
    """复合查询：合取与析取"""

    def test_合取_并且(self):
        results = query(build_kb(), "父母('张三', ?x) 并且 所在地(?x, '北京')")
        assert results == [{"?x": "小明"}]

    def test_合取_顶层逗号(self):
        results = query(build_kb(), "父母('张三', ?x), 所在地(?x, ?y)")
        assert results == [
            {"?x": "小明", "?y": "北京"},
            {"?x": "小红", "?y": "上海"},
        ]

    def test_析取_中文与符号写法(self):
        kb = build_kb()
        期望 = [{"?y": "中国"}, {"?y": "日本"}]
        assert query(kb, "城市('北京', ?y) 或者 城市('东京', ?y)") == 期望
        assert query(kb, "城市('北京', ?y) || 城市('东京', ?y)") == 期望
        assert query(kb, "城市('北京', ?y); 城市('东京', ?y)") == 期望

    def test_析取子句内合取(self):
        results = query(
            build_kb(),
            "父母('张三', ?x) 并且 所在地(?x, '北京') 或者 父母('李四', ?x)",
        )
        assert results == [{"?x": "小明"}, {"?x": "小强"}]

    def test_否定目标(self):
        results = query(build_kb(), "父母('张三', ?x) 并且 非 所在地(?x, '上海')")
        assert results == [{"?x": "小明"}]


class TestQueryErrors:
    """中文语法错误与位置"""

    @pytest.mark.parametrize(
        "文本, 位置",
        [
            ("城市(?x,", 7),
            ("城市 ?x)", 4),
            ("城市(?x, '北京' @)", 13),
            ("", 1),
        ],
    )
    def test_语法错误含中文与位置(self, 文本, 位置):
        with pytest.raises(QueryError) as info:
            query(build_kb(), 文本)
        message = str(info.value)
        assert "查询语法错误" in message
        assert f"第 {位置} 个字符" in message
        assert info.value.column == 位置

    def test_变量声明错误(self):
        with pytest.raises(QueryError, match="变量声明必须是非空文本"):
            query(build_kb(), "城市(?x, ?y)", variables=[""])

    def test_查询目标类型错误(self):
        with pytest.raises(QueryError, match="查询目标必须是文本"):
            query(build_kb(), 123)


class TestSortingPaging:
    """排序与分页"""

    def test_按单变量升序降序(self):
        kb = build_kb()
        升序 = query(kb, "城市(?x, ?y)", 排序="?y")
        降序 = query(kb, "城市(?x, ?y)", 排序="?y", 降序=True)
        assert [行["?x"] for 行 in 升序] == ["北京", "上海", "东京"]
        assert [行["?x"] for 行 in 降序] == ["东京", "北京", "上海"]

    def test_按多变量排序(self):
        results = query(build_kb(), "父母(?x, ?y)", 排序=["?x", "?y"])
        assert [行["?y"] for 行 in results] == ["小明", "小红", "小强"]

    def test_偏移与限制(self):
        kb = build_kb()
        全部 = query(kb, "城市(?x, ?y)", 排序="?x")
        assert query(kb, "城市(?x, ?y)", 排序="?x", 偏移=1) == 全部[1:]
        assert query(kb, "城市(?x, ?y)", 排序="?x", 限制=2) == 全部[:2]
        assert query(kb, "城市(?x, ?y)", 排序="?x", 偏移=1, 限制=1) == 全部[1:2]

    def test_非法分页参数(self):
        kb = build_kb()
        for 参数 in ({"偏移": -1}, {"限制": -2}, {"偏移": True}, {"限制": "1"}):
            with pytest.raises(QueryError, match="必须是非负整数"):
                query(kb, "城市(?x, ?y)", **参数)

    def test_英文别名(self):
        results = query(
            build_kb(),
            "父母(?x, ?y)",
            sort_by="?y",
            descending=True,
            offset=0,
            limit=2,
        )
        assert [行["?y"] for 行 in results] == ["小红", "小明"]

    def test_显式声明变量(self):
        results = query(build_kb(), "城市(x, y)", variables=["x", "y"], 限制=1)
        assert results == [{"?x": "北京", "?y": "中国"}]


class TestBackwardCompatibility:
    """既有查询约定保持不变"""

    def test_简单查询仍返回问号前缀键(self):
        results = query(build_kb(), "城市(?x, '中国')")
        assert len(results) == 2
        assert all("?x" in 行 for 行 in results)

    def test_结果对象模式(self):
        results = query(build_kb(), "城市(?x, '中国')", 结果对象=True)
        assert all(hasattr(行, "to_dict") for 行 in results)
        assert results[0]["?x"] in ("北京", "上海")
