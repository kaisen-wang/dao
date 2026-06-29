import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.log import (
    _stdlib_创建日志器, _stdlib_创建文件处理器, _stdlib_创建控制台处理器,
    DaoLogger, DaoConsoleHandler,
    create_module_env,
)
from dao.errors import 运行时错误


class TestLogger:
    def test_create_logger(self):
        logger = _stdlib_创建日志器("测试")
        assert isinstance(logger, DaoLogger)

    def test_logger_set_level(self):
        logger = _stdlib_创建日志器("级别测试")
        logger.设置级别("调试")
        logger.设置级别("信息")
        logger.设置级别("警告")
        logger.设置级别("错误")

    def test_logger_invalid_level(self):
        logger = _stdlib_创建日志器("无效级别")
        try:
            logger.设置级别("不存在的级别")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestHandlers:
    def test_file_handler(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.log")
            handler = _stdlib_创建文件处理器(path)
            assert handler is not None
            handler.关闭()

    def test_console_handler(self):
        handler = _stdlib_创建控制台处理器()
        assert isinstance(handler, DaoConsoleHandler)


class TestLogModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "创建日志器" in env.values
        assert "创建文件处理器" in env.values