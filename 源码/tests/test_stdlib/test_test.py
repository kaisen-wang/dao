import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.test import (
    _stdlib_断言等于, _stdlib_断言不等于, _stdlib_断言为真,
    _stdlib_断言为假, _stdlib_断言为空, _stdlib_断言包含,
    _stdlib_测试套件, _stdlib_测试报告, DaoTestSuite,
    create_module_env,
)
from dao.errors import 断言失败


class TestAssertions:
    def test_assert_equal_pass(self):
        _stdlib_断言等于(5, 5)

    def test_assert_equal_fail(self):
        try:
            _stdlib_断言等于(5, 3)
            assert False, "应抛出断言失败"
        except 断言失败:
            pass

    def test_assert_not_equal_pass(self):
        _stdlib_断言不等于(5, 3)

    def test_assert_not_equal_fail(self):
        try:
            _stdlib_断言不等于(5, 5)
            assert False, "应抛出断言失败"
        except 断言失败:
            pass

    def test_assert_true_pass(self):
        _stdlib_断言为真(True)

    def test_assert_true_fail(self):
        try:
            _stdlib_断言为真(False)
            assert False, "应抛出断言失败"
        except 断言失败:
            pass

    def test_assert_false_pass(self):
        _stdlib_断言为假(False)

    def test_assert_empty_pass(self):
        _stdlib_断言为空("")

    def test_assert_contains_pass(self):
        _stdlib_断言包含([1, 2, 3], 2)

    def test_assert_contains_fail(self):
        try:
            _stdlib_断言包含([1, 2, 3], 4)
            assert False, "应抛出断言失败"
        except 断言失败:
            pass


class TestTestSuite:
    def test_suite_basic(self):
        suite = _stdlib_测试套件("示例测试")
        assert isinstance(suite, DaoTestSuite)
        assert suite.name == "示例测试"

    def test_suite_report(self):
        suite = DaoTestSuite("测试")
        suite.start()
        suite.record_pass("测试1")
        suite.record_fail("测试2", expected=5, actual=3)
        suite.end_time = suite.start_time + 0.1
        report = _stdlib_测试报告(suite)
        assert "通过: 1" in report
        assert "失败: 1" in report


class TestTestModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "断言等于" in env.values
        assert "测试套件" in env.values