import base64
import csv
import io
import json
import urllib.parse

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误, 类型错误


def _json_encode(数据, 缩进=0):
    try:
        if 缩进 and 缩进 > 0:
            return json.dumps(数据, ensure_ascii=False, indent=缩进)
        return json.dumps(数据, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        raise 类型错误(f"无法编码为JSON: {e}")


def _json_decode(文本):
    if not isinstance(文本, str):
        raise 类型错误("JSON解码需要文本类型参数")
    try:
        return json.loads(文本)
    except json.JSONDecodeError as e:
        raise 运行时错误(f"无效的JSON格式: {e}")


def _csv_parse(文本):
    if not isinstance(文本, str):
        raise 类型错误("CSV解析需要文本类型参数")
    try:
        reader = csv.DictReader(io.StringIO(文本))
        return [dict(row) for row in reader]
    except csv.Error as e:
        raise 运行时错误(f"CSV格式错误: {e}")


def _csv_generate(数据):
    if not isinstance(数据, list) or len(数据) == 0:
        raise 运行时错误("CSV生成需要非空列表")
    output = io.StringIO()
    fieldnames = list(数据[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(数据)
    return output.getvalue()


def _base64_encode(文本):
    if not isinstance(文本, str):
        raise 类型错误("Base64编码需要文本类型参数")
    return base64.b64encode(文本.encode("utf-8")).decode("ascii")


def _base64_decode(文本):
    if not isinstance(文本, str):
        raise 类型错误("Base64解码需要文本类型参数")
    try:
        return base64.b64decode(文本).decode("utf-8")
    except Exception as e:
        raise 运行时错误(f"Base64解码失败: {e}")


def _url_encode(文本):
    if not isinstance(文本, str):
        raise 类型错误("URL编码需要文本类型参数")
    return urllib.parse.quote(文本)


def _url_decode(文本):
    if not isinstance(文本, str):
        raise 类型错误("URL解码需要文本类型参数")
    return urllib.parse.unquote(文本)


def create_module_env(interpreter=None) -> Environment:
    env = Environment()

    json_namespace = {
        "编码": BuiltinFunction("编码", _json_encode, -1),
        "解码": BuiltinFunction("解码", _json_decode, 1),
    }
    env.define("JSON", json_namespace)

    csv_namespace = {
        "解析": BuiltinFunction("解析", _csv_parse, 1),
        "生成": BuiltinFunction("生成", _csv_generate, 1),
    }
    env.define("CSV", csv_namespace)

    base64_namespace = {
        "编码": BuiltinFunction("编码", _base64_encode, 1),
        "解码": BuiltinFunction("解码", _base64_decode, 1),
    }
    env.define("Base64", base64_namespace)

    url_namespace = {
        "编码": BuiltinFunction("编码", _url_encode, 1),
        "解码": BuiltinFunction("解码", _url_decode, 1),
    }
    env.define("URL", url_namespace)

    env.exports = list(env.values.keys())
    return env