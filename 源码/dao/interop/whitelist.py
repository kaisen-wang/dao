"""
Python 互操作桥的白名单
======================

本模块是互操作桥的**唯一授权来源**。它定义了：

1. 允许加载的 Python 模块（含中文别名）；
2. 每个模块允许访问的**属性白名单**（函数或常量）。

安全设计要点
------------
- 模块对象通过静态 ``import`` 语句在解释器进程启动时一次性导入，
  **绝不**根据道语言传入的字符串执行动态 ``import`` / ``exec`` / ``eval``。
- 模块名和属性名都必须命中白名单；下划线开头的属性（``__builtins__``、
  ``__import__``、``__globals__`` 等）一律拒绝，杜绝沙箱逃逸。
- 白名单之外的模块（如 ``os``、``subprocess``、``sys``）根本不会被导入。
"""

import base64
import collections
import datetime
import functools
import hashlib
import itertools
import json
import math
import pathlib
import re
import statistics
from urllib import parse as urllib_parse

# ---------------------------------------------------------------------------
# 模块白名单：规范名 -> 模块对象
# ---------------------------------------------------------------------------
# 注意：这里全部是字面量静态导入，用户的输入永远不会成为 import 的参数。
_规范模块: dict[str, object] = {
    "math": math,
    "json": json,
    "statistics": statistics,
    "collections": collections,
    "itertools": itertools,
    "functools": functools,
    "re": re,
    "datetime": datetime,
    "pathlib": pathlib,
    "hashlib": hashlib,
    "base64": base64,
    "urllib.parse": urllib_parse,
}

# 中文别名，方便在道语言中使用；指向同一个规范模块对象。
_中文别名: dict[str, str] = {
    "数学": "math",
    "统计": "statistics",
    "集合工具": "collections",
    "迭代工具": "itertools",
    "函数工具": "functools",
    "正则": "re",
    "日期时间": "datetime",
    "路径": "pathlib",
    "哈希": "hashlib",
    "编码": "base64",
    "网址解析": "urllib.parse",
}

允许模块: dict[str, object] = dict(_规范模块)
for _别名, _规范名 in _中文别名.items():
    允许模块[_别名] = _规范模块[_规范名]


def 规范模块名(名称: str) -> str | None:
    """把用户提供的模块名解析为规范名；不在白名单则返回 ``None``。"""
    if 名称 in _规范模块:
        return 名称
    return _中文别名.get(名称)


# ---------------------------------------------------------------------------
# 属性白名单：规范模块名 -> 允许访问的属性名
# ---------------------------------------------------------------------------
# 只收录返回安全、可转换值的函数与常量。刻意排除：
#   - 涉及文件 I/O 的函数（json.load/dump、pathlib.Path.read_text 等）；
#   - 无限迭代器（itertools.count/cycle/repeat）；
#   - 返回不可序列化对象的函数（re.compile、re.match、hashlib.shake_* 等）；
#   - 所有下划线开头的 dunder 属性。
_允许属性表: dict[str, frozenset[str]] = {
    "math": frozenset({
        "sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
        "floor", "ceil", "trunc", "log", "log10", "log2", "exp", "expm1",
        "pow", "fabs", "factorial", "gcd", "lcm", "hypot", "fmod",
        "degrees", "radians", "isfinite", "isinf", "isnan", "copysign",
        "fsum", "prod", "perm", "comb", "dist", "erf", "erfc", "gamma",
        "lgamma", "pi", "e", "tau", "inf", "nan",
    }),
    "json": frozenset({"dumps", "loads"}),
    "statistics": frozenset({
        "mean", "fmean", "median", "median_low", "median_high", "mode",
        "multimode", "stdev", "pstdev", "variance", "pvariance",
        "harmonic_mean", "geometric_mean", "quantiles",
    }),
    "collections": frozenset({
        "Counter", "OrderedDict", "defaultdict", "deque",
    }),
    "itertools": frozenset({
        "product", "permutations", "combinations", "combinations_with_replacement",
        "chain", "chain_from_iterable", "compress", "dropwhile", "takewhile",
        "filterfalse", "accumulate", "zip_longest", "pairwise", "starmap",
        "islice",
    }),
    "functools": frozenset({"reduce"}),
    "re": frozenset({"findall", "sub", "subn", "split", "escape", "purge"}),
    "datetime": frozenset({
        "date", "datetime", "time", "timedelta", "MINYEAR", "MAXYEAR",
    }),
    "pathlib": frozenset({
        "Path", "PurePath", "PurePosixPath", "PureWindowsPath",
    }),
    "hashlib": frozenset({
        "md5", "sha1", "sha224", "sha256", "sha384", "sha512",
        "sha3_224", "sha3_256", "sha3_384", "sha3_512",
        "blake2b", "blake2s", "algorithms_available", "algorithms_guaranteed",
    }),
    "base64": frozenset({
        "b64encode", "b64decode", "b32encode", "b32decode",
        "b16encode", "b16decode", "standard_b64encode", "standard_b64decode",
        "urlsafe_b64encode", "urlsafe_b64decode",
    }),
    "urllib.parse": frozenset({
        "quote", "unquote", "quote_plus", "unquote_plus", "urlencode",
        "urlparse", "urlsplit", "urlunparse", "urlunsplit", "parse_qs",
        "parse_qsl", "urljoin",
    }),
}


def 允许的属性(规范名: str) -> frozenset[str]:
    """返回指定规范模块允许访问的属性集合。"""
    return _允许属性表.get(规范名, frozenset())


def 列出模块名() -> list[str]:
    """列出全部可加载的模块名（规范名 + 中文别名），排序后返回。"""
    return sorted(允许模块)


# 需要对字符串参数做 UTF-8 编码的模块（bytes 类 API）。
需编码字符串参数模块: frozenset[str] = frozenset({"base64", "hashlib"})


__all__ = [
    "允许模块",
    "允许的属性",
    "列出模块名",
    "规范模块名",
    "需编码字符串参数模块",
]
