import os
import re
import sys
import uuid as uuid_lib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 类型错误
from dao.stdlib.crypto import (
    _stdlib_HMACSHA256,
    _stdlib_SHA256,
    _stdlib_UUID,
    _stdlib_随机令牌,
    _stdlib_验证HMAC,
    create_module_env,
)

导出名集合 = {"SHA256", "HMACSHA256", "验证HMAC", "UUID", "随机令牌"}


class TestSHA256:
    def test_sha256_已知向量(self):
        # FIPS 180-4 / NIST 标准向量
        assert (
            _stdlib_SHA256("abc")
            == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )

    def test_sha256_中文文本_utf8(self):
        # "你好" 的 UTF-8 字节为 e4 bd a0 e5 a5 bd
        assert (
            _stdlib_SHA256("你好")
            == "670d9743542cae3ea7ebe36af56bd53648b0a1126162e78d81a32934a711302e"
        )

    def test_sha256_返回小写十六进制(self):
        result = _stdlib_SHA256("abc")
        assert len(result) == 64
        assert result == result.lower()
        assert re.fullmatch(r"[0-9a-f]{64}", result)


class TestHMACSHA256:
    def test_hmacsha256_已知向量(self):
        # RFC 4231 Test Case 1：20 字节 0x0b 密钥 + "Hi There"
        assert (
            _stdlib_HMACSHA256("\x0b" * 20, "Hi There")
            == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
        )

    def test_hmacsha256_返回小写十六进制(self):
        result = _stdlib_HMACSHA256("密钥", "文本")
        assert re.fullmatch(r"[0-9a-f]{64}", result)


class Test验证HMAC:
    def test_正确签名返回_true(self):
        密钥, 文本 = "webhook-secret", "{\"event\":\"push\"}"
        签名 = _stdlib_HMACSHA256(密钥, 文本)
        assert _stdlib_验证HMAC(密钥, 文本, 签名) is True

    def test_错误签名返回_false(self):
        签名 = _stdlib_HMACSHA256("正确密钥", "原始内容")
        # 文本被篡改，签名不再匹配
        assert _stdlib_验证HMAC("正确密钥", "被篡改内容", 签名) is False

    def test_大小写宽容(self):
        密钥, 文本 = "secret", "payload"
        签名 = _stdlib_HMACSHA256(密钥, 文本)
        assert _stdlib_验证HMAC(密钥, 文本, 签名.upper()) is True

    def test_非法格式签名返回_false(self):
        for 非法签名 in ("", "abc", "zz" * 32, "a" * 63, "a" * 65):
            assert _stdlib_验证HMAC("secret", "payload", 非法签名) is False


class TestUUID与令牌:
    def test_uuid_格式合法且两次不同(self):
        first = _stdlib_UUID()
        second = _stdlib_UUID()
        assert isinstance(first, str)
        assert uuid_lib.UUID(first).version == 4
        assert first != second

    def test_随机令牌_长度与唯一性(self):
        token = _stdlib_随机令牌()
        assert len(token) == 64  # 默认 32 字节 → 64 个十六进制字符
        assert re.fullmatch(r"[0-9a-f]{64}", token)
        assert _stdlib_随机令牌(16) != _stdlib_随机令牌(16)
        assert len(_stdlib_随机令牌(16)) == 32


class Test类型错误:
    def test_SHA256_非文本参数抛中文类型错误(self):
        try:
            _stdlib_SHA256(123)
            assert False, "应抛出类型错误"
        except 类型错误 as exc:
            assert "文本" in str(exc)

    def test_HMACSHA256_非文本参数抛中文类型错误(self):
        try:
            _stdlib_HMACSHA256(123, "文本")
            assert False, "应抛出类型错误"
        except 类型错误:
            pass
        try:
            _stdlib_HMACSHA256("密钥", 123)
            assert False, "应抛出类型错误"
        except 类型错误:
            pass

    def test_验证HMAC_非文本参数抛中文类型错误(self):
        for 参数组 in ((123, "文本", "签名"), ("密钥", 123, "签名"), ("密钥", "文本", 123)):
            try:
                _stdlib_验证HMAC(*参数组)
                assert False, "应抛出类型错误"
            except 类型错误:
                pass

    def test_随机令牌_非整数参数抛中文类型错误(self):
        try:
            _stdlib_随机令牌("32")
            assert False, "应抛出类型错误"
        except 类型错误:
            pass


class Test模块环境:
    def test_create_module_env_导出集合恰好为五个(self):
        env = create_module_env()
        assert set(env.exports) == 导出名集合
        assert set(env.values) == 导出名集合
        assert len(env.exports) == 5

    def test_create_module_env_元数据稳定(self):
        env1 = create_module_env()
        env2 = create_module_env()
        for 名称 in 导出名集合:
            f1 = env1.values[名称]
            f2 = env2.values[名称]
            # 函数对象必须在模块级定义，重复调用工厂不应重建
            assert f1.func is f2.func
            assert f1.name == 名称 == f2.name
            assert f1.arity() == f2.arity()

    def test_create_module_env_参数个数正确(self):
        env = create_module_env()
        assert env.values["SHA256"].param_count == 1
        assert env.values["HMACSHA256"].param_count == 2
        assert env.values["验证HMAC"].param_count == 3
        assert env.values["UUID"].param_count == 0
        assert env.values["随机令牌"].param_count == -1
