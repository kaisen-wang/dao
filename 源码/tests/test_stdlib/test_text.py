import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.text import (
    _stdlib_分割, _stdlib_连接, _stdlib_替换, _stdlib_包含,
    _stdlib_去空格, _stdlib_查找, _stdlib_截取, _stdlib_大写,
    _stdlib_小写, _stdlib_正则匹配, _stdlib_分割全部, _stdlib_替换全部,
    create_module_env,
)
from dao.errors import 类型错误, 运行时错误


class TestTextSplit:
    def test_split_normal(self):
        assert _stdlib_分割("苹果,香蕉,橙子", ",") == ["苹果", "香蕉", "橙子"]

    def test_split_empty_separator(self):
        try:
            _stdlib_分割("你好世界", "")
            assert False, "应抛出类型错误"
        except 类型错误:
            pass

    def test_split_non_string(self):
        try:
            _stdlib_分割(123, ",")
            assert False, "应抛出类型错误"
        except 类型错误:
            pass


class TestTextJoin:
    def test_join_normal(self):
        assert _stdlib_连接(["苹果", "香蕉", "橙子"], " 和 ") == "苹果 和 香蕉 和 橙子"

    def test_join_empty_list(self):
        assert _stdlib_连接([], ",") == ""

    def test_join_non_list(self):
        try:
            _stdlib_连接("不是列表", ",")
            assert False, "应抛出类型错误"
        except 类型错误:
            pass


class TestTextReplace:
    def test_replace_normal(self):
        assert _stdlib_替换("你好世界", "世界", "道语言") == "你好道语言"

    def test_replace_with_count(self):
        assert _stdlib_替换("aaa", "a", "b", 次数=2) == "bba"

    def test_replace_not_found(self):
        assert _stdlib_替换("你好", "世界", "道") == "你好"


class TestTextContains:
    def test_contains_true(self):
        assert _stdlib_包含("你好世界", "世界") is True

    def test_contains_false(self):
        assert _stdlib_包含("你好世界", "宇宙") is False

    def test_contains_non_string(self):
        try:
            _stdlib_包含(123, "1")
            assert False, "应抛出类型错误"
        except 类型错误:
            pass


class TestTextTrim:
    def test_trim_normal(self):
        assert _stdlib_去空格("  你好，世界！  ") == "你好，世界！"

    def test_trim_no_whitespace(self):
        assert _stdlib_去空格("你好") == "你好"

    def test_trim_tabs(self):
        assert _stdlib_去空格("\t你好\t") == "你好"


class TestTextFind:
    def test_find_found(self):
        assert _stdlib_查找("你好世界", "世界") == 2

    def test_find_not_found(self):
        assert _stdlib_查找("你好世界", "宇宙") == -1

    def test_find_empty_string(self):
        assert _stdlib_查找("你好", "") == 0


class TestTextSlice:
    def test_slice_with_end(self):
        assert _stdlib_截取("你好世界", 2, 4) == "世界"

    def test_slice_without_end(self):
        assert _stdlib_截取("你好世界", 2) == "世界"

    def test_slice_non_string(self):
        try:
            _stdlib_截取(123, 0, 1)
            assert False, "应抛出类型错误"
        except 类型错误:
            pass


class TestTextCase:
    def test_upper(self):
        assert _stdlib_大写("hello") == "HELLO"

    def test_lower(self):
        assert _stdlib_小写("HELLO") == "hello"

    def test_upper_chinese(self):
        assert _stdlib_大写("你好") == "你好"


class TestTextRegex:
    def test_regex_match(self):
        assert _stdlib_正则匹配("我的电话是13812345678", "[0-9]{11}") == ["13812345678"]

    def test_regex_match_no_match(self):
        assert _stdlib_正则匹配("无数字", "[0-9]+") == []

    def test_regex_match_invalid_pattern(self):
        try:
            _stdlib_正则匹配("文本", "[")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_regex_split(self):
        assert _stdlib_分割全部("苹果12香蕉34橙子", "[0-9]+") == ["苹果", "香蕉", "橙子"]

    def test_regex_replace(self):
        assert _stdlib_替换全部("a1b2c3", "[0-9]", "X") == "aXbXcX"


class TestTextModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "分割" in env.values
        assert "连接" in env.values
        assert len(env.exports) == 12