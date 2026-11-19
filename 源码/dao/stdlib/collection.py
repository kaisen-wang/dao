import collections
import heapq

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 索引错误, 运行时错误


class DaoHeap:
    """道语言最小堆，基于 heapq 实现。"""

    def __init__(self):
        self._data: list = []

    def push(self, item):
        heapq.heappush(self._data, item)

    def pop(self):
        if not self._data:
            raise 索引错误("不能从空堆中弹出元素")
        return heapq.heappop(self._data)

    def peek(self):
        if not self._data:
            raise 索引错误("不能查看空堆的顶部元素")
        return self._data[0]

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def size(self) -> int:
        return len(self._data)

    def __repr__(self):
        return f"<堆 大小={len(self._data)}>"


class DaoCounter:
    """道语言计数器，统计元素出现次数。"""

    def __init__(self, data=None):
        self._counter = collections.Counter(data)

    def 取值(self, key, default=0):
        return self._counter.get(key, default)

    def 取键列表(self):
        return list(self._counter.keys())

    def 最常见(self, n=None):
        return self._counter.most_common(n)

    def __repr__(self):
        return f"<计数器 {dict(self._counter)}>"


class DaoOrderedDict:
    """道语言有序字典，保持键的插入顺序。"""

    def __init__(self):
        self._od = collections.OrderedDict()

    def 设置(self, key, value):
        self._od[key] = value

    def 取值(self, key, default=None):
        return self._od.get(key, default)

    def 取键列表(self):
        return list(self._od.keys())

    def 取值列表(self):
        return list(self._od.values())

    def 删除(self, key):
        if key in self._od:
            del self._od[key]
        else:
            raise 运行时错误(f"键 '{key}' 不存在")

    def __repr__(self):
        return f"<有序字典 {dict(self._od)}>"


class DaoDeque:
    """道语言双端队列，两端均可入出。"""

    def __init__(self):
        self._deque = collections.deque()

    def 左入(self, item):
        self._deque.appendleft(item)

    def 右入(self, item):
        self._deque.append(item)

    def 左出(self):
        if not self._deque:
            raise 索引错误("不能从空队列中弹出元素")
        return self._deque.popleft()

    def 右出(self):
        if not self._deque:
            raise 索引错误("不能从空队列中弹出元素")
        return self._deque.pop()

    def 左窥(self):
        if not self._deque:
            raise 索引错误("不能查看空队列的元素")
        return self._deque[0]

    def 右窥(self):
        if not self._deque:
            raise 索引错误("不能查看空队列的元素")
        return self._deque[-1]

    def size(self) -> int:
        return len(self._deque)

    def is_empty(self) -> bool:
        return len(self._deque) == 0

    def __repr__(self):
        return f"<双端队列 大小={len(self._deque)}>"


class DaoDefaultDict:
    """道语言默认字典，缺失键时生成默认值。"""

    def __init__(self, default_factory=None):
        self._dd = collections.defaultdict(default_factory)

    def 取值(self, key):
        return self._dd[key]

    def 设置(self, key, value):
        self._dd[key] = value

    def 取键列表(self):
        return list(self._dd.keys())

    def __repr__(self):
        return f"<默认字典 {dict(self._dd)}>"


class DaoFrozenSet:
    """道语言不可变集合。"""

    def __init__(self, items=None):
        if items is not None:
            self._fset = frozenset(items)
        else:
            self._fset = frozenset()

    def 包含(self, item) -> bool:
        return item in self._fset

    def size(self) -> int:
        return len(self._fset)

    def __repr__(self):
        return f"<冻结集合 {set(self._fset)}>"


def _stdlib_创建堆():
    """创建一个空的堆对象。"""
    return DaoHeap()


def _stdlib_入堆(堆, 元素):
    """把一个元素压入堆中。"""
    if not isinstance(堆, DaoHeap):
        raise 运行时错误("入堆需要堆类型参数")
    堆.push(元素)


def _stdlib_出堆(堆):
    """弹出并返回堆中最小的元素。"""
    if not isinstance(堆, DaoHeap):
        raise 运行时错误("出堆需要堆类型参数")
    return 堆.pop()


def _stdlib_计数(列表):
    """统计列表元素出现次数，返回计数器对象。"""
    return DaoCounter(列表)


def _stdlib_最常见(计数器, n=None):
    """返回计数器中最常见的 n 个元素及其次数。

    参数：n 省略时返回全部元素，结果按出现次数降序排列。
    """
    if not isinstance(计数器, DaoCounter):
        raise 运行时错误("最常见需要计数器类型参数")
    return 计数器.最常见(n)


def create_module_env(interpreter=None) -> Environment:
    """创建集合模块的导出环境。"""
    env = Environment()
    env.define("创建堆", BuiltinFunction("创建堆", _stdlib_创建堆, 0))
    env.define("入堆", BuiltinFunction("入堆", _stdlib_入堆, 2))
    env.define("出堆", BuiltinFunction("出堆", _stdlib_出堆, 1))
    env.define("计数", BuiltinFunction("计数", _stdlib_计数, 1))
    env.define("最常见", BuiltinFunction("最常见", _stdlib_最常见, -1))
    env.define("有序字典", DaoOrderedDict)
    env.define("双端队列", DaoDeque)
    env.define("默认字典", DaoDefaultDict)
    env.define("冻结集合", DaoFrozenSet)
    env.exports = list(env.values.keys())
    return env
