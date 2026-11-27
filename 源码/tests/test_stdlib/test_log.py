import os
import re
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 运行时错误
from dao.stdlib.log import (
    DEFAULT_FORMAT,
    DaoConsoleHandler,
    DaoLogger,
    _dao_format_to_logging,
    _stdlib_创建控制台处理器,
    _stdlib_创建文件处理器,
    _stdlib_创建日志器,
    _stdlib_配置日志,
    create_module_env,
)


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
        assert "配置日志" in env.values
        assert env.values["默认格式"] == DEFAULT_FORMAT


class TestFormatPlaceholders:
    def test_全部占位符转换(self):
        fmt = (
            "{时间戳}|{日志级别}|{级别}|{线程ID}|{线程名}|{代码位置}|"
            "{错误码}|{描述信息}|{描述}|{消息}|{名称}|{时间}|"
            "{位置}|{文件名}|{行号}|{函数名}"
        )
        py = _dao_format_to_logging(fmt)
        for field in (
            "asctime", "levelname", "thread)d", "threadName", "location",
            "error_code", "message", "name", "filename", "lineno", "funcName",
        ):
            assert field in py

    def test_字面百分号被转义(self):
        assert _dao_format_to_logging("完成 100% {消息}") == "完成 100%% %(message)s"

    def test_默认格式字段齐全(self):
        for token in ("{时间戳}", "{级别}", "{线程ID}", "{代码位置}", "{错误码}", "{描述信息}"):
            assert token in DEFAULT_FORMAT


class TestConfiguredLogging:
    @staticmethod
    def _make(path, **kwargs):
        return _stdlib_配置日志(输出="文件", 路径=path, 级别="调试", **kwargs)

    def test_文件包含全部字段(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "app.log")
            logger = self._make(path)
            logger.信息("服务启动", 错误码="E0001", 位置="入口.道:12")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            assert "INFO" in text
            assert "E0001" in text
            assert "入口.道:12" in text
            assert "服务启动" in text
            assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text), text
            assert re.search(r"\| \d+ \|", text), text

    def test_设置位置作为默认值(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "app.log")
            logger = self._make(path)
            logger.设置位置("模块.道:3")
            logger.警告("未传位置")
            logger.警告("覆盖位置", 位置="另一.道:9")
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            assert "模块.道:3" in lines[0]
            assert "另一.道:9" in lines[1]
            assert "模块.道:3" not in lines[1]

    def test_时间格式可配置(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "app.log")
            logger = self._make(path, 时间格式="%Y年%m月%d日")
            logger.信息("中文日期")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            assert re.search(r"\d{4}年\d{2}月\d{2}日", text), text

    def test_级别过滤(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "app.log")
            logger = _stdlib_配置日志(输出="文件", 路径=path, 级别="警告")
            logger.信息("不应出现")
            logger.警告("应当出现")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            assert "不应出现" not in text
            assert "应当出现" in text

    def test_记录方法按级别分派(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "app.log")
            logger = self._make(path)
            logger.记录("错误", "分派消息", 错误码="E900", 位置="分发.道:1")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            assert "ERROR" in text and "E900" in text and "分发.道:1" in text

    def test_无效级别抛中文错误(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._make(os.path.join(tmpdir, "app.log"))
            with pytest.raises(运行时错误, match="无效的日志级别"):
                logger.记录("不存在", "消息")

    def test_无效输出方式抛中文错误(self):
        with pytest.raises(运行时错误, match="无效的日志输出方式"):
            _stdlib_配置日志(输出="数据库")

    def test_文件输出缺少路径抛中文错误(self):
        with pytest.raises(运行时错误, match="必须提供路径"):
            _stdlib_配置日志(输出="文件")

    def test_处理器重复添加不会重复输出(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "app.log")
            logger = self._make(path)
            handler = _stdlib_创建文件处理器(path)
            logger.添加处理器(handler)
            logger.信息("只应出现一次")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            assert text.count("只应出现一次") == 1
            handler.关闭()


class TestDaoLanguageLogging:
    @staticmethod
    def _run(source):
        from dao.interpreter import Interpreter
        from dao.lexer import Lexer
        from dao.parser import Parser

        return Interpreter().execute(Parser(Lexer(source).tokenize()).parse())

    def test_道语言端到端文件日志(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "app.log")
            source = (
                '从 日志 导入 配置日志, 默认格式\n'
                f'日志器 = 配置日志(输出="文件", 路径="{path}", 格式=默认格式, 级别="调试")\n'
                '日志器.信息("端到端消息", 错误码="E100", 位置="测试.道:7")\n'
            )
            self._run(source)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            assert "端到端消息" in text
            assert "E100" in text
            assert "测试.道:7" in text