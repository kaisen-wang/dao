import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.encoding import (
    _json_encode, _json_decode, _csv_parse, _csv_generate,
    _base64_encode, _base64_decode, _url_encode, _url_decode,
    create_module_env,
)
from dao.errors import 运行时错误, 类型错误


class TestJsonEncode:
    def test_encode_dict(self):
        result = _json_encode({"姓名": "张三", "年龄": 25})
        assert "张三" in result
        assert "25" in result

    def test_encode_with_indent(self):
        result = _json_encode({"a": 1}, 缩进=4)
        assert "\n" in result

    def test_encode_unsupported_type(self):
        try:
            _json_encode({1, 2, 3})
            assert False, "应抛出类型错误"
        except 类型错误:
            pass


class TestJsonDecode:
    def test_decode_normal(self):
        result = _json_decode('{"姓名":"张三","年龄":25}')
        assert result["姓名"] == "张三"

    def test_decode_invalid(self):
        try:
            _json_decode("{invalid}")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_decode_non_string(self):
        try:
            _json_decode(123)
            assert False, "应抛出类型错误"
        except 类型错误:
            pass


class TestCsvParse:
    def test_parse_normal(self):
        result = _csv_parse("姓名,年龄\n张三,25\n李四,30")
        assert len(result) == 2
        assert result[0]["姓名"] == "张三"

    def test_parse_empty(self):
        result = _csv_parse("姓名,年龄\n")
        assert len(result) == 0


class TestCsvGenerate:
    def test_generate_normal(self):
        data = [{"姓名": "张三", "年龄": "25"}]
        result = _csv_generate(data)
        assert "张三" in result
        assert "姓名" in result

    def test_generate_empty(self):
        try:
            _csv_generate([])
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestBase64:
    def test_encode_decode(self):
        original = "你好，世界！"
        encoded = _base64_encode(original)
        decoded = _base64_decode(encoded)
        assert decoded == original

    def test_decode_invalid(self):
        try:
            _base64_decode("!!!不是base64!!!")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestUrl:
    def test_encode_decode(self):
        original = "你好 世界"
        encoded = _url_encode(original)
        decoded = _url_decode(encoded)
        assert decoded == original

    def test_encode_non_string(self):
        try:
            _url_encode(123)
            assert False, "应抛出类型错误"
        except 类型错误:
            pass


class TestEncodingModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "JSON" in env.values
        assert "CSV" in env.values
        assert "Base64" in env.values
        assert "URL" in env.values