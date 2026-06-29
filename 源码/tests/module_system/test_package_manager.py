"""
包管理系统测试
"""

import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.package.version import Version, VersionConstraint
from dao.package.config import PackageConfig, Dependency
from dao.package.resolver import PackageResolver
from dao.package.manager import PackageManager
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


class TestVersion:
    def test_parse_basic(self):
        v = Version.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_with_pre_release(self):
        v = Version.parse("1.0.0-alpha")
        assert v.pre_release == "alpha"

    def test_parse_with_build(self):
        v = Version.parse("1.0.0+build.1")
        assert v.build == "build.1"

    def test_parse_invalid(self):
        try:
            Version.parse("invalid")
            assert False, "应该抛出 ValueError"
        except ValueError:
            pass

    def test_str(self):
        v = Version(1, 2, 3)
        assert str(v) == "1.2.3"

    def test_str_with_pre_release(self):
        v = Version(1, 0, 0, pre_release="beta.1")
        assert str(v) == "1.0.0-beta.1"

    def test_equality(self):
        v1 = Version(1, 2, 3)
        v2 = Version(1, 2, 3)
        assert v1 == v2

    def test_inequality(self):
        v1 = Version(1, 2, 3)
        v2 = Version(1, 2, 4)
        assert v1 != v2

    def test_less_than(self):
        v1 = Version(1, 2, 3)
        v2 = Version(1, 2, 4)
        assert v1 < v2

    def test_less_than_major(self):
        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)
        assert v1 < v2

    def test_pre_release_less_than_release(self):
        v1 = Version(1, 0, 0, pre_release="alpha")
        v2 = Version(1, 0, 0)
        assert v1 < v2

    def test_greater_than(self):
        v1 = Version(1, 2, 4)
        v2 = Version(1, 2, 3)
        assert v1 > v2


class TestVersionConstraint:
    def test_parse_exact(self):
        c = VersionConstraint.parse("1.2.3")
        assert c.operator == "=="
        assert c.version == Version(1, 2, 3)

    def test_parse_gte(self):
        c = VersionConstraint.parse(">=2.0.0")
        assert c.operator == ">="
        assert c.version == Version(2, 0, 0)

    def test_parse_lte(self):
        c = VersionConstraint.parse("<=1.5.0")
        assert c.operator == "<="

    def test_parse_caret(self):
        c = VersionConstraint.parse("^1.5.0")
        assert c.operator == "^"

    def test_parse_tilde(self):
        c = VersionConstraint.parse("~1.5.0")
        assert c.operator == "~"

    def test_matches_exact(self):
        c = VersionConstraint.parse("1.2.3")
        assert c.matches(Version(1, 2, 3))
        assert not c.matches(Version(1, 2, 4))

    def test_matches_gte(self):
        c = VersionConstraint.parse(">=2.0.0")
        assert c.matches(Version(2, 0, 0))
        assert c.matches(Version(2, 1, 0))
        assert c.matches(Version(3, 0, 0))
        assert not c.matches(Version(1, 9, 9))

    def test_matches_caret(self):
        c = VersionConstraint.parse("^1.5.0")
        assert c.matches(Version(1, 5, 0))
        assert c.matches(Version(1, 9, 9))
        assert not c.matches(Version(2, 0, 0))
        assert not c.matches(Version(0, 9, 9))

    def test_matches_caret_zero(self):
        c = VersionConstraint.parse("^0.5.0")
        assert c.matches(Version(0, 5, 0))
        assert c.matches(Version(0, 5, 9))
        assert not c.matches(Version(0, 6, 0))

    def test_matches_tilde(self):
        c = VersionConstraint.parse("~1.5.0")
        assert c.matches(Version(1, 5, 0))
        assert c.matches(Version(1, 5, 9))
        assert not c.matches(Version(1, 6, 0))
        assert not c.matches(Version(2, 0, 0))


class TestDependency:
    def test_parse_name_only(self):
        d = Dependency.parse("网络框架")
        assert d.name == "网络框架"
        assert d.constraint is None

    def test_parse_with_version(self):
        d = Dependency.parse("网络框架 >=2.0.0")
        assert d.name == "网络框架"
        assert d.constraint is not None
        assert d.constraint.operator == ">="

    def test_parse_with_caret(self):
        d = Dependency.parse("数据库驱动 ^1.5.0")
        assert d.name == "数据库驱动"
        assert d.constraint.operator == "^"

    def test_parse_exact_version(self):
        d = Dependency.parse("日志工具 1.2.3")
        assert d.name == "日志工具"
        assert d.constraint.operator == "=="

    def test_str(self):
        d = Dependency.parse("网络框架 >=2.0.0")
        assert "网络框架" in str(d)
        assert ">=2.0.0" in str(d)


class TestPackageConfig:
    def test_parse_basic(self):
        content = """名称 我的项目
版本 1.0.0
作者 张三
描述 一个示例项目
入口 主程序.道"""
        config = PackageConfig.parse(content)
        assert config.name == "我的项目"
        assert config.version == Version(1, 0, 0)
        assert config.author == "张三"
        assert config.description == "一个示例项目"
        assert config.entry == "主程序.道"

    def test_parse_with_dependencies(self):
        content = """名称 我的项目
版本 1.0.0

依赖
    网络框架 >=2.0.0
    数据库驱动 ^1.5.0
    日志工具 1.2.3"""
        config = PackageConfig.parse(content)
        assert len(config.dependencies) == 3
        assert config.dependencies[0].name == "网络框架"
        assert config.dependencies[0].constraint.operator == ">="
        assert config.dependencies[1].name == "数据库驱动"
        assert config.dependencies[1].constraint.operator == "^"
        assert config.dependencies[2].name == "日志工具"
        assert config.dependencies[2].constraint.operator == "=="

    def test_parse_with_dev_dependencies(self):
        content = """名称 我的项目
版本 1.0.0

依赖
    网络框架 >=2.0.0

开发依赖
    测试框架 >=3.0.0"""
        config = PackageConfig.parse(content)
        assert len(config.dependencies) == 1
        assert len(config.dev_dependencies) == 1
        assert config.dev_dependencies[0].name == "测试框架"
        assert config.dev_dependencies[0].is_dev is True

    def test_parse_with_comments(self):
        content = """// 这是注释
名称 我的项目
版本 1.0.0"""
        config = PackageConfig.parse(content)
        assert config.name == "我的项目"

    def test_parse_empty_lines(self):
        content = """名称 我的项目

版本 1.0.0"""
        config = PackageConfig.parse(content)
        assert config.name == "我的项目"
        assert config.version == Version(1, 0, 0)

    def test_from_file(self):
        temp_dir = tempfile.mkdtemp()
        try:
            config_path = os.path.join(temp_dir, "道.配置")
            with open(config_path, "w", encoding="utf-8") as f:
                f.write("名称 测试项目\n版本 0.1.0\n")

            config = PackageConfig.from_file(config_path)
            assert config.name == "测试项目"
            assert config.version == Version(0, 1, 0)
        finally:
            shutil.rmtree(temp_dir)

    def test_str_roundtrip(self):
        content = """名称 我的项目
版本 1.0.0
作者 张三
描述 一个示例项目
入口 主程序.道
依赖
    网络框架 >=2.0.0"""
        config = PackageConfig.parse(content)
        result = str(config)
        assert "名称 我的项目" in result
        assert "版本 1.0.0" in result
        assert "依赖" in result
        assert "网络框架 >=2.0.0" in result


class TestPackageResolver:
    def test_resolve_package(self):
        temp_dir = tempfile.mkdtemp()
        try:
            pkg_dir = os.path.join(temp_dir, "网络框架")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 网络框架\n版本 2.1.0\n入口 主程序.道\n")

            resolver = PackageResolver(search_paths=[temp_dir])
            resolved = resolver.resolve("网络框架")
            assert resolved is not None
            assert resolved.name == "网络框架"
            assert resolved.version == Version(2, 1, 0)
        finally:
            shutil.rmtree(temp_dir)

    def test_resolve_with_constraint(self):
        temp_dir = tempfile.mkdtemp()
        try:
            pkg_dir = os.path.join(temp_dir, "数据库驱动")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 数据库驱动\n版本 1.5.2\n")

            resolver = PackageResolver(search_paths=[temp_dir])
            constraint = VersionConstraint.parse("^1.5.0")
            resolved = resolver.resolve("数据库驱动", constraint)
            assert resolved is not None
            assert resolved.version == Version(1, 5, 2)
        finally:
            shutil.rmtree(temp_dir)

    def test_resolve_not_found(self):
        resolver = PackageResolver(search_paths=[])
        resolved = resolver.resolve("不存在的包")
        assert resolved is None

    def test_resolve_version_mismatch(self):
        temp_dir = tempfile.mkdtemp()
        try:
            pkg_dir = os.path.join(temp_dir, "日志工具")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 日志工具\n版本 0.9.0\n")

            resolver = PackageResolver(search_paths=[temp_dir])
            constraint = VersionConstraint.parse(">=1.0.0")
            resolved = resolver.resolve("日志工具", constraint)
            assert resolved is None
        finally:
            shutil.rmtree(temp_dir)

    def test_resolve_caching(self):
        temp_dir = tempfile.mkdtemp()
        try:
            pkg_dir = os.path.join(temp_dir, "缓存测试")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 缓存测试\n版本 1.0.0\n")

            resolver = PackageResolver(search_paths=[temp_dir])
            r1 = resolver.resolve("缓存测试")
            r2 = resolver.resolve("缓存测试")
            assert r1 is r2
        finally:
            shutil.rmtree(temp_dir)


class TestPackageManager:
    def test_no_config(self):
        temp_dir = tempfile.mkdtemp()
        try:
            mgr = PackageManager(project_dir=temp_dir)
            assert mgr.config is None
            assert mgr.get_dependency_paths() == []
        finally:
            shutil.rmtree(temp_dir)

    def test_with_config(self):
        temp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(temp_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 测试项目\n版本 1.0.0\n依赖\n    网络框架 >=2.0.0\n")

            pkg_dir = os.path.join(temp_dir, "道包", "网络框架")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 网络框架\n版本 2.1.0\n")

            mgr = PackageManager(project_dir=temp_dir)
            assert mgr.config is not None
            assert mgr.config.name == "测试项目"
            paths = mgr.get_dependency_paths()
            assert len(paths) == 1
        finally:
            shutil.rmtree(temp_dir)

    def test_resolve_module(self):
        temp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(temp_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 测试项目\n版本 1.0.0\n依赖\n    网络框架 >=2.0.0\n")

            pkg_dir = os.path.join(temp_dir, "道包", "网络框架")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 网络框架\n版本 2.1.0\n入口 主程序.道\n")
            with open(os.path.join(pkg_dir, "主程序.道"), "w", encoding="utf-8") as f:
                f.write("导出 函数 创建服务器()\n    返回 \"服务器已创建\"\n")

            mgr = PackageManager(project_dir=temp_dir)
            path = mgr.resolve_module("网络框架")
            assert path is not None
            assert "网络框架" in path
        finally:
            shutil.rmtree(temp_dir)

    def test_resolve_module_submodule(self):
        temp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(temp_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 测试项目\n版本 1.0.0\n依赖\n    网络框架 >=2.0.0\n")

            pkg_dir = os.path.join(temp_dir, "道包", "网络框架")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 网络框架\n版本 2.1.0\n")
            with open(os.path.join(pkg_dir, "路由.道"), "w", encoding="utf-8") as f:
                f.write("导出 函数 路由()\n    返回 \"路由\"\n")

            mgr = PackageManager(project_dir=temp_dir)
            path = mgr.resolve_module("网络框架.路由")
            assert path is not None
            assert path.endswith("路由.道")
        finally:
            shutil.rmtree(temp_dir)


class TestPackageManagerIntegration:
    def test_import_from_package(self):
        temp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(temp_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 测试项目\n版本 1.0.0\n依赖\n    数学工具 >=1.0.0\n")

            pkg_dir = os.path.join(temp_dir, "道包", "数学工具")
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "道.配置"), "w", encoding="utf-8") as f:
                f.write("名称 数学工具\n版本 1.0.0\n入口 主程序.道\n")
            with open(os.path.join(pkg_dir, "主程序.道"), "w", encoding="utf-8") as f:
                f.write("导出 函数 加(甲, 乙)\n    返回 甲 + 乙\n")

            main_source = '从 数学工具 导入 加\n打印(加(1, 2))\n'

            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                import io
                from contextlib import redirect_stdout

                interpreter = Interpreter(project_dir=temp_dir)
                lexer = Lexer(main_source)
                tokens = lexer.tokenize()
                parser = Parser(tokens)
                ast = parser.parse()

                output = io.StringIO()
                with redirect_stdout(output):
                    interpreter.execute(ast)

                assert "3" in output.getvalue()
            finally:
                os.chdir(original_cwd)
        finally:
            shutil.rmtree(temp_dir)