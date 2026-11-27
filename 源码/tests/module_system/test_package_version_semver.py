"""SemVer 比较边界测试：预发布标识符、build 元数据、约束前缀与预发布规则。"""

import itertools
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.package.version import Version, VersionConstraint, compare_identifiers


class TestPreReleaseComparison:
    def test_数字标识符按数值比较而非字典序(self):
        # 字典序会把 "alpha.10" 判在 "alpha.2" 之前，SemVer 必须相反。
        assert Version.parse("1.0.0-alpha.2") < Version.parse("1.0.0-alpha.10")
        assert Version.parse("1.0.0-beta.11") > Version.parse("1.0.0-beta.2")

    def test_数字标识符低于非数字标识符(self):
        assert Version.parse("1.0.0-alpha.1") < Version.parse("1.0.0-alpha.beta")
        assert compare_identifiers("1", "alpha") == -1

    def test_完整预发布优先级链(self):
        ordered = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ]
        versions = [Version.parse(text) for text in ordered]
        for left, right in itertools.pairwise(versions):
            assert left < right, f"{left} 应小于 {right}"
            assert right > left

    def test_段数多者优先级更高(self):
        assert Version.parse("1.0.0-alpha") < Version.parse("1.0.0-alpha.1")
        assert Version.parse("1.0.0-alpha.1") < Version.parse("1.0.0-alpha.1.1")


class TestBuildMetadata:
    def test_相等比较区分不同构建(self):
        first = Version.parse("1.0.0+build.1")
        second = Version.parse("1.0.0+build.2")
        assert first != second
        assert hash(first) != hash(second)
        assert first == Version.parse("1.0.0+build.1")

    def test_build参与排序但保持确定性(self):
        plain = Version.parse("1.0.0")
        first = Version.parse("1.0.0+abc")
        second = Version.parse("1.0.0+xyz")
        assert plain < first < second
        assert not (first > second > first)

    def test_precedence_key忽略build(self):
        first = Version.parse("1.0.0+build.1")
        second = Version.parse("1.0.0+build.2")
        assert first.precedence_key() == second.precedence_key()
        assert first.precedence_key() < Version.parse("1.0.1").precedence_key()

    def test_含连字符的预发布与构建标识符可解析(self):
        version = Version.parse("1.2.3-rc-1+sha-abc")
        assert version.pre_release == "rc-1"
        assert version.build == "sha-abc"


class TestConstraintEdges:
    def test_显式相等前缀可解析(self):
        constraint = VersionConstraint.parse("==1.2.3")
        assert constraint.operator == "=="
        assert constraint.matches(Version.parse("1.2.3"))
        assert not constraint.matches(Version.parse("1.2.4"))

    def test_普通范围不跨基础版本接受预发布(self):
        constraint = VersionConstraint.parse(">=1.0.0")
        assert not constraint.matches(Version.parse("1.5.0-alpha"))
        constraint = VersionConstraint.parse("^1.0.0")
        assert not constraint.matches(Version.parse("1.5.0-rc.1"))

    def test_同基础版本的预发布约束可匹配预发布(self):
        constraint = VersionConstraint.parse(">=1.0.0-alpha")
        assert constraint.matches(Version.parse("1.0.0-alpha"))
        assert constraint.matches(Version.parse("1.0.0-beta"))
        strict = VersionConstraint.parse(">1.0.0-alpha")
        assert not strict.matches(Version.parse("1.0.0-alpha"))
        assert strict.matches(Version.parse("1.0.0-beta"))

    def test_约束相等与哈希(self):
        assert VersionConstraint.parse("^1.0.0") == VersionConstraint.parse("^1.0.0")
        assert len({VersionConstraint.parse("~2.1.0"), VersionConstraint.parse("~2.1.0")}) == 1
