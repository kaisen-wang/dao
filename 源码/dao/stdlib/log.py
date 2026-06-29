import logging

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误

_LEVEL_MAP = {
    "调试": logging.DEBUG,
    "信息": logging.INFO,
    "警告": logging.WARNING,
    "错误": logging.ERROR,
}

_FORMAT_MAP = {
    "{级别}": "%(levelname)s",
    "{时间}": "%(asctime)s",
    "{名称}": "%(name)s",
    "{消息}": "%(message)s",
}


def _dao_format_to_logging(fmt: str) -> str:
    for dao_fmt, py_fmt in _FORMAT_MAP.items():
        fmt = fmt.replace(dao_fmt, py_fmt)
    return fmt


class DaoLogger:
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)

    def 调试(self, 消息):
        self._logger.debug(消息)

    def 信息(self, 消息):
        self._logger.info(消息)

    def 警告(self, 消息):
        self._logger.warning(消息)

    def 错误(self, 消息):
        self._logger.error(消息)

    def 设置级别(self, 级别):
        if 级别 not in _LEVEL_MAP:
            raise 运行时错误(f"无效的日志级别: {级别}，有效值: {', '.join(_LEVEL_MAP.keys())}")
        self._logger.setLevel(_LEVEL_MAP[级别])

    def 添加处理器(self, 处理器):
        if isinstance(处理器, DaoFileHandler):
            self._logger.addHandler(处理器._handler)
        elif isinstance(处理器, DaoConsoleHandler):
            self._logger.addHandler(处理器._handler)
        else:
            raise 运行时错误("无效的处理器类型")

    def 设置格式(self, 格式):
        py_fmt = _dao_format_to_logging(格式)
        formatter = logging.Formatter(py_fmt)
        for handler in self._logger.handlers:
            handler.setFormatter(formatter)

    def __repr__(self):
        return f"<日志器 {self._logger.name}>"


class DaoFileHandler:
    def __init__(self, path: str):
        try:
            self._handler = logging.FileHandler(path, encoding="utf-8")
            self._handler.setLevel(logging.DEBUG)
        except Exception as e:
            raise 运行时错误(f"无法创建日志文件: {e}")

    def 关闭(self):
        self._handler.close()

    def __repr__(self):
        return "<文件处理器>"


class DaoConsoleHandler:
    def __init__(self):
        self._handler = logging.StreamHandler()
        self._handler.setLevel(logging.DEBUG)

    def __repr__(self):
        return "<控制台处理器>"


def _stdlib_创建日志器(名称):
    return DaoLogger(名称)


def _stdlib_创建文件处理器(路径):
    return DaoFileHandler(路径)


def _stdlib_创建控制台处理器():
    return DaoConsoleHandler()


def create_module_env(interpreter=None) -> Environment:
    env = Environment()
    env.define("创建日志器", BuiltinFunction("创建日志器", _stdlib_创建日志器, 1))
    env.define("创建文件处理器", BuiltinFunction("创建文件处理器", _stdlib_创建文件处理器, 1))
    env.define("创建控制台处理器", BuiltinFunction("创建控制台处理器", _stdlib_创建控制台处理器, 0))
    env.exports = list(env.values.keys())
    return env