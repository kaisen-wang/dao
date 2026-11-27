"""密码模块：为"道"语言提供哈希、HMAC、UUID 与随机令牌原语。

常用于 webhook 验签与幂等键生成。仅依赖 Python 标准库。
"""

import hashlib
import hmac
import secrets
import uuid

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误

# 合法的小写十六进制字符集合，用于校验签名格式
_十六进制字符 = frozenset("0123456789abcdef")


def _stdlib_SHA256(文本):
    """计算文本的 SHA-256 摘要，返回 64 位小写十六进制字符串。"""
    if not isinstance(文本, str):
        raise 类型错误("SHA256 需要文本类型参数")
    return hashlib.sha256(文本.encode("utf-8")).hexdigest()


def _stdlib_HMACSHA256(密钥, 文本):
    """使用密钥计算文本的 HMAC-SHA256，返回 64 位小写十六进制字符串。"""
    if not isinstance(密钥, str):
        raise 类型错误("HMACSHA256 的密钥必须是文本类型")
    if not isinstance(文本, str):
        raise 类型错误("HMACSHA256 的文本必须是文本类型")
    return hmac.new(密钥.encode("utf-8"), 文本.encode("utf-8"), hashlib.sha256).hexdigest()


def _stdlib_验证HMAC(密钥, 文本, 签名):
    """常量时间校验签名是否等于文本的 HMAC-SHA256。

    签名大小写不敏感；格式非法（非 64 位十六进制）时返回 False 而非抛异常。
    """
    if not isinstance(密钥, str):
        raise 类型错误("验证HMAC 的密钥必须是文本类型")
    if not isinstance(文本, str):
        raise 类型错误("验证HMAC 的文本必须是文本类型")
    if not isinstance(签名, str):
        raise 类型错误("验证HMAC 的签名必须是文本类型")

    待比较签名 = 签名.lower()
    if len(待比较签名) != 64 or not all(c in _十六进制字符 for c in 待比较签名):
        return False

    期望签名 = _stdlib_HMACSHA256(密钥, 文本)
    return hmac.compare_digest(期望签名, 待比较签名)


def _摘要(文本, 算法, 名字):
    """计算文本摘要的通用实现。"""
    if not isinstance(文本, str):
        raise 类型错误(f"{名字}需要文本类型参数")
    return hashlib.new(算法, 文本.encode("utf-8")).hexdigest()


def _stdlib_MD5(文本):
    """计算文本的 MD5 摘要，返回 32 位小写十六进制字符串。"""
    return _摘要(文本, "md5", "MD5")


def _stdlib_SHA1(文本):
    """计算文本的 SHA-1 摘要，返回 40 位小写十六进制字符串。"""
    return _摘要(文本, "sha1", "SHA1")


def _stdlib_SHA512(文本):
    """计算文本的 SHA-512 摘要，返回 128 位小写十六进制字符串。"""
    return _摘要(文本, "sha512", "SHA512")


def _stdlib_UUID():
    """生成一个随机的 UUID v4 字符串。"""
    return str(uuid.uuid4())


def _stdlib_随机令牌(字节数=32):
    """生成指定字节数的随机十六进制令牌，默认 32 字节。"""
    if not isinstance(字节数, int) or isinstance(字节数, bool):
        raise 类型错误("随机令牌的字节数必须是整数类型")
    return secrets.token_hex(字节数)


def _stdlib_随机字节(字节数=32):
    """生成指定字节数的密码学安全随机字节，默认 32 字节。"""
    if not isinstance(字节数, int) or isinstance(字节数, bool):
        raise 类型错误("随机字节的字节数必须是整数类型")
    if 字节数 < 0:
        raise 类型错误("随机字节的字节数不能为负数")
    return secrets.token_bytes(字节数)


def create_module_env(interpreter=None) -> Environment:
    """创建密码模块的导出环境。"""
    env = Environment()
    env.define("SHA256", BuiltinFunction("SHA256", _stdlib_SHA256, 1))
    env.define("MD5", BuiltinFunction("MD5", _stdlib_MD5, 1))
    env.define("SHA1", BuiltinFunction("SHA1", _stdlib_SHA1, 1))
    env.define("SHA512", BuiltinFunction("SHA512", _stdlib_SHA512, 1))
    env.define("HMACSHA256", BuiltinFunction("HMACSHA256", _stdlib_HMACSHA256, 2))
    env.define("验证HMAC", BuiltinFunction("验证HMAC", _stdlib_验证HMAC, 3))
    env.define("UUID", BuiltinFunction("UUID", _stdlib_UUID, 0))
    env.define("随机令牌", BuiltinFunction("随机令牌", _stdlib_随机令牌, -1))
    env.define("随机字节", BuiltinFunction("随机字节", _stdlib_随机字节, -1))
    env.exports = list(env.values.keys())
    return env
