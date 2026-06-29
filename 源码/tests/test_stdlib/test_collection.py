import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.collection import (
    DaoHeap, DaoCounter, DaoDeque, DaoFrozenSet,
    _stdlib_创建堆, _stdlib_入堆, _stdlib_出堆,
    _stdlib_计数, _stdlib_最常见,
    create_module_env,
)
from dao.errors import 索引错误, 运行时错误


class TestHeap:
    def test_heap_basic(self):
        h = _stdlib_创建堆()
        _stdlib_入堆(h, 3)
        _stdlib_入堆(h, 1)
        _stdlib_入堆(h, 2)
        assert _stdlib_出堆(h) == 1
        assert _stdlib_出堆(h) == 2
        assert _stdlib_出堆(h) == 3

    def test_heap_empty_pop(self):
        h = DaoHeap()
        try:
            h.pop()
            assert False, "应抛出索引错误"
        except 索引错误:
            pass

    def test_heap_peek(self):
        h = DaoHeap()
        h.push(5)
        h.push(3)
        assert h.peek() == 3

    def test_heap_empty_peek(self):
        h = DaoHeap()
        try:
            h.peek()
            assert False, "应抛出索引错误"
        except 索引错误:
            pass


class TestCounter:
    def test_counter_basic(self):
        c = _stdlib_计数(["甲", "乙", "甲", "丙", "甲"])
        assert c.取值("甲") == 3
        assert c.取值("乙") == 1

    def test_counter_most_common(self):
        c = _stdlib_计数(["甲", "乙", "甲", "丙", "甲"])
        result = _stdlib_最常见(c, 2)
        assert result[0][0] == "甲"

    def test_counter_keys(self):
        c = DaoCounter(["a", "b", "a"])
        keys = c.取键列表()
        assert "a" in keys
        assert "b" in keys


class TestDeque:
    def test_deque_basic(self):
        d = DaoDeque()
        d.右入(1)
        d.右入(2)
        d.左入(0)
        assert d.左出() == 0
        assert d.右出() == 2

    def test_deque_empty_pop(self):
        d = DaoDeque()
        try:
            d.左出()
            assert False, "应抛出索引错误"
        except 索引错误:
            pass

    def test_deque_peek(self):
        d = DaoDeque()
        d.右入(1)
        d.右入(2)
        assert d.左窥() == 1
        assert d.右窥() == 2


class TestFrozenSet:
    def test_frozenset_contains(self):
        fs = DaoFrozenSet([1, 2, 3])
        assert fs.包含(1) is True
        assert fs.包含(4) is False

    def test_frozenset_size(self):
        fs = DaoFrozenSet([1, 2, 3])
        assert fs.size() == 3


class TestCollectionModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "创建堆" in env.values
        assert "有序字典" in env.values