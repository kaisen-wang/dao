"""道语言标准库：日志。

提供分级日志输出，可打印到控制台或写入文件，格式完全可配置。
可用占位符见 ``DEFAULT_FORMAT`` 与 ``文档/10-标准库.md`` 的日志章节。

典型用法::

    从 日志 导入 配置日志, 默认格式
    日志器 = 配置日志(输出="两者", 路径="应用.log", 格式=默认格式)
    日志器.信息("服务启动", 错误码="E0001", 位置="入口.道:12")
"""

from __future__ import annotations

import logging
from typing import Any

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误

# 中文级别名 -> Python logging 级别
_LEVEL_MAP = {
    "调试": logging.DEBUG,
    "信息": logging.INFO,
    "警告": logging.WARNING,
    "错误": logging.ERROR,
    "致命": logging.CRITICAL,
}

# 道语言格式占位符 -> logging 格式化字段。
# 替换时按占位符长度降序，避免短名先替换破坏长名。
_FORMAT_MAP = {
    "{时间戳}": "%(asctime)s",
    "{日志级别}": "%(levelname)s",
    "{线程ID}": "%(thread)d",
    "{线程名}": "%(threadName)s",
    "{代码位置}": "%(location)s",
    "{描述信息}": "%(message)s",
    "{时间}": "%(asctime)s",
    "{级别}": "%(levelname)s",
    "{名称}": "%(name)s",
    "{位置}": "%(location)s",
    "{错误码}": "%(error_code)s",
    "{描述}": "%(message)s",
    "{消息}": "%(message)s",
    "{文件名}": "%(filename)s",
    "{行号}": "%(lineno)d",
    "{函数名}": "%(funcName)s",
}

# 默认格式：时间戳 | 日志级别 | 线程ID | 代码位置 | 错误码 | 描述信息
DEFAULT_FORMAT = "{时间戳} | {级别} | {线程ID} | {代码位置} | {错误码} | {描述信息}"


def _dao_format_to_logging(fmt: str) -> str:
    """把道语言日志格式占位符转换为 logging 格式。

    字面 ``%`` 先转义为 ``%%``，避免格式里写 ``100%`` 时被 logging 误当作
    格式符；占位符随后替换为 ``%(...)s``，不受转义影响。
    """
    result = str(fmt).replace("%", "%%")
    for dao_fmt, py_fmt in sorted(_FORMAT_MAP.items(), key=lambda item: -len(item[0])):
        result = result.replace(dao_fmt, py_fmt)
    return result


class _DaoAdapter(logging.LoggerAdapter):
    """合并默认字段与逐条日志传入的字段。

    标准 ``LoggerAdapter.process`` 会用 ``self.extra`` 无条件覆盖调用时的
    ``extra``，导致逐条的错误码/位置丢失；这里改为合并，调用方优先。
    """

    def process(self, msg, kwargs):
        extra = dict(self.extra or {})
        extra.update(kwargs.get("extra") or {})
        kwargs["extra"] = extra
        return msg, kwargs


class DaoLogger:
    """道语言日志器：分级日志、格式设置与多处理器输出。"""

    def __init__(self, name: str, 位置: str = ""):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._位置 = 位置
        self._adapter = _DaoAdapter(self._logger, {"error_code": "", "location": 位置})
        self._formatter: logging.Formatter | None = None

    def _write(self, level: int, 消息, 错误码: str, 位置):
        extra: dict[str, Any] = {}
        if 错误码:
            extra["error_code"] = 错误码
        if 位置 is not None:
            extra["location"] = 位置
        self._adapter.log(level, 消息, extra=extra)

    def 调试(self, 消息, 错误码="", 位置=None):
        """记录调试级别日志，可附带错误码与代码位置。"""
        self._write(logging.DEBUG, 消息, 错误码, 位置)

    def 信息(self, 消息, 错误码="", 位置=None):
        """记录信息级别日志，可附带错误码与代码位置。"""
        self._write(logging.INFO, 消息, 错误码, 位置)

    def 警告(self, 消息, 错误码="", 位置=None):
        """记录警告级别日志，可附带错误码与代码位置。"""
        self._write(logging.WARNING, 消息, 错误码, 位置)

    def 错误(self, 消息, 错误码="", 位置=None):
        """记录错误级别日志，可附带错误码与代码位置。"""
        self._write(logging.ERROR, 消息, 错误码, 位置)

    def 致命(self, 消息, 错误码="", 位置=None):
        """记录致命级别日志，可附带错误码与代码位置。"""
        self._write(logging.CRITICAL, 消息, 错误码, 位置)

    def 记录(self, 级别, 消息, 错误码="", 位置=None):
        """按中文级别名记录日志（调试/信息/警告/错误/致命）。"""
        if 级别 not in _LEVEL_MAP:
            raise 运行时错误(
                f"无效的日志级别: {级别}，有效值: {', '.join(_LEVEL_MAP.keys())}"
            )
        self._write(_LEVEL_MAP[级别], 消息, 错误码, 位置)

    def 设置级别(self, 级别):
        """设置日志器的最低级别，低于该级别的日志不再输出。"""
        if 级别 not in _LEVEL_MAP:
            raise 运行时错误(
                f"无效的日志级别: {级别}，有效值: {', '.join(_LEVEL_MAP.keys())}"
            )
        self._logger.setLevel(_LEVEL_MAP[级别])

    def 设置位置(self, 位置):
        """设置默认代码位置（如 入口.道:12），后续日志可省略位置参数。"""
        self._位置 = 位置
        self._adapter.extra["location"] = 位置

    def 添加处理器(self, 处理器):
        """添加文件或控制台处理器；同一对象或同一文件不会重复添加。"""
        if not isinstance(处理器, (DaoFileHandler, DaoConsoleHandler)):
            raise 运行时错误("无效的处理器类型")
        handler = 处理器._handler
        for existing in self._logger.handlers:
            if existing is handler:
                return
            if (
                isinstance(existing, logging.FileHandler)
                and isinstance(handler, logging.FileHandler)
                and existing.baseFilename == handler.baseFilename
            ):
                return
        if self._formatter is not None:
            handler.setFormatter(self._formatter)
        self._logger.addHandler(handler)

    def 设置格式(self, 格式, 时间格式=None):
        """设置所有处理器的日志格式，可同时指定 strftime 风格时间格式。"""
        py_fmt = _dao_format_to_logging(格式)
        formatter = logging.Formatter(py_fmt, datefmt=时间格式)
        self._formatter = formatter
        for handler in self._logger.handlers:
            handler.setFormatter(formatter)

    def __repr__(self):
        return f"<日志器 {self._logger.name}>"


class DaoFileHandler:
    """日志文件处理器：把日志写入指定路径，可单独指定格式。"""

    def __init__(self, path: str, 格式=None, 时间格式=None):
        try:
            self._handler = logging.FileHandler(path, encoding="utf-8")
            self._handler.setLevel(logging.DEBUG)
            if 格式 is not None:
                self._handler.setFormatter(
                    logging.Formatter(_dao_format_to_logging(格式), datefmt=时间格式)
                )
        except Exception as e:
            raise 运行时错误(f"无法创建日志文件: {e}") from e

    def 关闭(self):
        """关闭日志文件句柄。"""
        self._handler.close()

    def __repr__(self):
        return "<文件处理器>"


class DaoConsoleHandler:
    """控制台日志处理器：输出到标准错误流，可单独指定格式。"""

    def __init__(self, 格式=None, 时间格式=None):
        self._handler = logging.StreamHandler()
        self._handler.setLevel(logging.DEBUG)
        if 格式 is not None:
            self._handler.setFormatter(
                logging.Formatter(_dao_format_to_logging(格式), datefmt=时间格式)
            )

    def __repr__(self):
        return "<控制台处理器>"


def _stdlib_创建日志器(名称, 位置=""):
    """创建一个指定名称的日志器，可选设置默认代码位置。"""
    return DaoLogger(名称, 位置)


def _stdlib_创建文件处理器(路径, 格式=None, 时间格式=None):
    """创建写入指定文件的日志处理器，可选指定格式与时间格式。"""
    return DaoFileHandler(路径, 格式, 时间格式)


def _stdlib_创建控制台处理器(格式=None, 时间格式=None):
    """创建输出到控制台的日志处理器，可选指定格式与时间格式。"""
    return DaoConsoleHandler(格式, 时间格式)


def _stdlib_配置日志(名称="道", 输出="控制台", 路径=None, 格式=None, 级别="信息", 时间格式=None):
    """一步配置日志器：指定输出目标（控制台/文件/两者）、格式、级别与时间格式。"""
    if 格式 is None:
        格式 = DEFAULT_FORMAT
    日志器 = DaoLogger(名称)
    # 配置是一次性设置：清掉同名日志器原有的处理器，避免重复配置后同一条日志被写出多份
    for existing in list(日志器._logger.handlers):
        日志器._logger.removeHandler(existing)
        existing.close()
    if 输出 == "控制台":
        日志器.添加处理器(DaoConsoleHandler(格式, 时间格式))
    elif 输出 == "文件":
        if not 路径:
            raise 运行时错误("输出为文件时必须提供路径")
        日志器.添加处理器(DaoFileHandler(路径, 格式, 时间格式))
    elif 输出 == "两者":
        if not 路径:
            raise 运行时错误("输出为两者时必须提供路径")
        日志器.添加处理器(DaoConsoleHandler(格式, 时间格式))
        日志器.添加处理器(DaoFileHandler(路径, 格式, 时间格式))
    else:
        raise 运行时错误(f"无效的日志输出方式: {输出}，有效值: 控制台 / 文件 / 两者")
    日志器.设置格式(格式, 时间格式)
    日志器.设置级别(级别)
    return 日志器


def create_module_env(interpreter=None) -> Environment:
    """创建日志模块的导出环境。"""
    env = Environment()
    env.define("创建日志器", BuiltinFunction("创建日志器", _stdlib_创建日志器, -1))
    env.define("创建文件处理器", BuiltinFunction("创建文件处理器", _stdlib_创建文件处理器, -1))
    env.define("创建控制台处理器", BuiltinFunction("创建控制台处理器", _stdlib_创建控制台处理器, -1))
    env.define("配置日志", BuiltinFunction("配置日志", _stdlib_配置日志, -1))
    env.define("默认格式", DEFAULT_FORMAT)
    env.exports = list(env.values.keys())
    return env
