"""语义化版本（SemVer 2.0.0）解析、比较与约束匹配。

比较规则严格遵循 SemVer：

* 主版本/次版本/修订号按数值逐段比较；
* 预发布版本低于对应的正式版本；
* 预发布标识符逐段比较：纯数字标识符按数值比较，含字母/连字符的按
  ASCII 字典序比较，数字标识符始终低于非数字标识符；前面各段都相等时，
  段数多的一方优先级更高（``1.0.0-alpha.1 < 1.0.0-alpha.beta``、
  ``1.0.0-beta.2 < 1.0.0-beta.11``）；
* ``build`` 元数据按规范不影响版本优先级，但用于区分不同构建产物：
  :meth:`Version.__eq__` 与 :meth:`Version.__hash__` 均包含 ``build``，
  排序时仅把它当作最后一级确定性 tie-breaker。这样"相等"与"排序"一致，
  不会出现 ``a > b`` 且 ``b > a`` 同时成立的情况。
"""

from __future__ import annotations

import re

_VERSION_RE = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _identifier_key(identifier: str) -> tuple[int, object]:
    """把一个点分标识符转换成可比较的键。

    返回的二元组的首项区分「数字 / 非数字」，保证数字标识符永远排在
    非数字标识符之前，且两者比较时不会把 ``int`` 与 ``str`` 混比。
    """
    if identifier.isascii() and identifier.isdigit():
        return (0, int(identifier))
    return (1, identifier)


def compare_identifiers(left: str | None, right: str | None) -> int:
    """按 SemVer 规则比较两个点分标识符串。

    ``None`` 被视为「无标识符」，其优先级高于任何有标识符的版本（用于
    预发布版本比较：正式版本 > 预发布版本）。返回 -1 / 0 / 1。
    """
    if left is None and right is None:
        return 0
    if left is None:
        return 1
    if right is None:
        return -1

    left_keys = [_identifier_key(part) for part in left.split(".")]
    right_keys = [_identifier_key(part) for part in right.split(".")]
    for left_key, right_key in zip(left_keys, right_keys):
        if left_key < right_key:
            return -1
        if left_key > right_key:
            return 1
    # 前面各段相同：段数多者优先级更高。
    if len(left_keys) < len(right_keys):
        return -1
    if len(left_keys) > len(right_keys):
        return 1
    return 0


class Version:
    __slots__ = ("build", "major", "minor", "patch", "pre_release")

    def __init__(
        self,
        major: int = 0,
        minor: int = 0,
        patch: int = 0,
        pre_release: str | None = None,
        build: str | None = None,
    ):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.pre_release = pre_release
        self.build = build

    @classmethod
    def parse(cls, version_str: str) -> Version:
        version_str = version_str.strip()
        match = _VERSION_RE.match(version_str)
        if not match:
            raise ValueError(f"无效的版本号格式: '{version_str}'")
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            pre_release=match.group(4),
            build=match.group(5),
        )

    def __str__(self) -> str:
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            result += f"-{self.pre_release}"
        if self.build:
            result += f"+{self.build}"
        return result

    def __repr__(self) -> str:
        return f"Version('{self}')"

    def precedence_key(self) -> tuple:
        """返回忽略 ``build`` 元数据的 SemVer 优先级键。

        排序/比较运算把 ``build`` 当作最后一级 tie-breaker，而本方法给出
        规范意义上（完全忽略 build）的优先级，便于需要纯 SemVer 次序的场景。
        """
        release = (0,)
        if self.pre_release is not None:
            release = (1, tuple(_identifier_key(p) for p in self.pre_release.split(".")))
        return (self.major, self.minor, self.patch, release)

    def compare(self, other: Version) -> int:
        """返回 -1 / 0 / 1 表示本版本小于 / 等于 / 大于 ``other``。"""
        left_base = (self.major, self.minor, self.patch)
        right_base = (other.major, other.minor, other.patch)
        if left_base != right_base:
            return -1 if left_base < right_base else 1

        pre = compare_identifiers(self.pre_release, other.pre_release)
        if pre != 0:
            return pre

        # build 不影响 SemVer 优先级，但作为确定性 tie-breaker 使
        # __eq__（区分 build）与排序运算保持一致。
        if self.build is None and other.build is None:
            return 0
        if self.build is None:
            return -1
        if other.build is None:
            return 1
        return compare_identifiers(self.build, other.build)

    def _compare(self, other: object) -> object:
        if not isinstance(other, Version):
            return NotImplemented
        return self.compare(other)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.pre_release == other.pre_release
            and self.build == other.build
        )

    def __lt__(self, other: Version) -> bool:
        result = self._compare(other)
        return NotImplemented if result is NotImplemented else result < 0

    def __le__(self, other: Version) -> bool:
        result = self._compare(other)
        return NotImplemented if result is NotImplemented else result <= 0

    def __gt__(self, other: Version) -> bool:
        result = self._compare(other)
        return NotImplemented if result is NotImplemented else result > 0

    def __ge__(self, other: Version) -> bool:
        result = self._compare(other)
        return NotImplemented if result is NotImplemented else result >= 0

    def __hash__(self) -> int:
        # build 参与相等判断，就必须同样参与哈希，否则破坏哈希不变量。
        return hash((self.major, self.minor, self.patch, self.pre_release, self.build))


class VersionConstraint:
    __slots__ = ("operator", "version")

    def __init__(self, operator: str, version: Version):
        self.operator = operator
        self.version = version

    @classmethod
    def parse(cls, constraint_str: str) -> VersionConstraint:
        constraint_str = constraint_str.strip()
        for prefix in (">=", "<=", "==", "^", "~", ">", "<", "="):
            if constraint_str.startswith(prefix):
                return cls("==" if prefix == "=" else prefix, Version.parse(constraint_str[len(prefix):]))
        # 裸版本号等价于「精确匹配」。
        return cls("==", Version.parse(constraint_str))

    def matches(self, version: Version) -> bool:
        # SemVer 预发布规则：普通范围约束默认不接受「另一个基础版本」的预发布版。
        # 只有当约束本身是同一 major.minor.patch 的预发布约束时才放开。
        if (
            version.pre_release is not None
            and self.version.pre_release is None
            and (version.major, version.minor, version.patch)
            != (self.version.major, self.version.minor, self.version.patch)
        ):
            return False

        if self.operator == "==":
            return version == self.version
        if self.operator == ">=":
            return version >= self.version
        if self.operator == "<=":
            return version <= self.version
        if self.operator == ">":
            return version > self.version
        if self.operator == "<":
            return version < self.version
        if self.operator == "^":
            if version.major != self.version.major:
                return False
            # 0.x 属于不稳定 API，^0.x.y 只锁定同一 minor。
            if version.major == 0 and version.minor != self.version.minor:
                return False
            return version >= self.version
        if self.operator == "~":
            if version.major != self.version.major or version.minor != self.version.minor:
                return False
            return version >= self.version
        return False

    def __str__(self) -> str:
        return f"{self.operator}{self.version}"

    def __repr__(self) -> str:
        return f"VersionConstraint('{self}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionConstraint):
            return NotImplemented
        return self.operator == other.operator and self.version == other.version

    def __hash__(self) -> int:
        return hash((self.operator, self.version))
