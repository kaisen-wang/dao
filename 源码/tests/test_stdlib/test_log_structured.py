"""结构化日志标准库桥接测试。

覆盖道语言 API 的导出、Python 侧管道行为，以及真实 ``.道`` 脚本端到端执行。
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.callsite import CallSite, current_call_site
from dao.errors import 运行时错误
from dao.logmodel.context import current_resource, current_trace
from dao.logmodel.exporters import MemoryExporter
from dao.stdlib.log import (
    DEFAULT_FORMAT,
    DaoStructuredLogger,
    _stdlib_创建内存导出器,
    _stdlib_创建属性处理器,
    _stdlib_创建脱敏处理器,
    _stdlib_创建追踪,
    _stdlib_创建采样处理器,
    _stdlib_取追踪头,
    _stdlib_设置资源,
    _stdlib_载入追踪头,
    _stdlib_配置日志,
    _stdlib_配置结构化日志,
    create_module_env,
)


@pytest.fixture(autouse=True)
def _重置上下文():
    """每个用例隔离追踪与资源 ContextVar。"""
    trace_token = current_trace.set(None)
    resource_token = current_resource.set(None)
    yield
    current_trace.reset(trace_token)
    current_resource.reset(resource_token)


def _主程序路径() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "main.py")
    )


def _运行脚本(路径: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, _主程序路径(), 路径],
        check=True,
        capture_output=True,
        text=True,
    )


class Test模块导出:
    """新增 API 必须完整导出，且不能破坏现有 API。"""

    def test_新增九个导出全部存在(self):
        env = create_module_env()
        for name in (
            "配置结构化日志",
            "创建追踪",
            "取追踪头",
            "载入追踪头",
            "设置资源",
            "创建脱敏处理器",
            "创建采样处理器",
            "创建属性处理器",
            "创建内存导出器",
        ):
            assert name in env.values, name
            assert name in env.exports, name

    def test_现有导出保持不变(self):
        env = create_module_env()
        for name in ("创建日志器", "创建文件处理器", "创建控制台处理器", "配置日志"):
            assert name in env.values, name
        assert env.values["默认格式"] == DEFAULT_FORMAT


class Test结构化日志器:
    """DaoStructuredLogger 的核心行为。"""

    def test_内存导出器收集记录字典(self):
        logger = _stdlib_配置结构化日志(输出="内存")
        logger.信息("支付成功")
        records = logger.取记录()
        assert len(records) == 1
        record = records[0]
        assert record["body"] == "支付成功"
        assert record["severity_text"] == "INFO"
        assert record["severity_number"] == 9
        assert record["timestamp"].endswith("Z")
        assert record["observed_timestamp"].endswith("Z")
        assert isinstance(record["attributes"], dict)
        assert isinstance(record["resource"], dict)

    def test_五个分级方法与记录方法(self):
        logger = _stdlib_配置结构化日志(输出="内存", 级别="调试")
        logger.调试("d")
        logger.信息("i")
        logger.警告("w")
        logger.错误("e")
        logger.致命("f")
        logger.记录("警告", "r")
        texts = [record["severity_text"] for record in logger.取记录()]
        assert texts == ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "WARN"]
        numbers = [record["severity_number"] for record in logger.取记录()]
        assert numbers == [5, 9, 13, 17, 21, 13]

    def test_级别过滤生效(self):
        logger = _stdlib_配置结构化日志(输出="内存", 级别="警告")
        logger.信息("被过滤")
        logger.错误("被保留")
        records = logger.取记录()
        assert len(records) == 1
        assert records[0]["body"] == "被保留"

    def test_无效级别抛中文运行时错误(self):
        with pytest.raises(运行时错误, match="无效的日志级别"):
            _stdlib_配置结构化日志(输出="内存", 级别="不存在")

    def test_无效记录级别抛中文运行时错误(self):
        logger = _stdlib_配置结构化日志(输出="内存")
        with pytest.raises(运行时错误, match="无效的日志级别"):
            logger.记录("不存在", "消息")

    def test_调用位置自动注入(self):
        logger = _stdlib_配置结构化日志(输出="内存")
        token = current_call_site.set(CallSite("模块.道", 7, 1))
        try:
            logger.信息("带位置")
        finally:
            current_call_site.reset(token)
        assert logger.取记录()[0]["location"] == "模块.道:7"

    def test_每次调用的属性写入记录(self):
        logger = _stdlib_配置结构化日志(输出="内存")
        logger.信息("下单", {"订单号": "A-1", "金额": 99})
        attributes = logger.取记录()[0]["attributes"]
        assert attributes == {"订单号": "A-1", "金额": 99}

    def test_非字典属性抛中文错误(self):
        logger = _stdlib_配置结构化日志(输出="内存")
        with pytest.raises(运行时错误, match="属性.*字典"):
            logger.信息("消息", "不是字典")

    def test_刷新与关闭可用(self):
        logger = _stdlib_配置结构化日志(输出="内存", 批量大小=10)
        logger.信息("先刷新")
        logger.刷新()
        assert len(logger.取记录()) == 1
        logger.关闭()
        with pytest.raises(运行时错误, match="已关闭"):
            logger.信息("关闭后")

    def test_取记录支持属性访问与序列化(self):
        logger = _stdlib_配置结构化日志(输出="内存")
        logger.信息("可序列化")
        record = logger.取记录()[0]
        assert record.body == "可序列化"
        assert record.to_dict()["body"] == "可序列化"
        assert json.loads(record.to_json())["body"] == "可序列化"

    def test_非内存导出器取记录抛中文错误(self, capsys):
        logger = _stdlib_配置结构化日志(输出="控制台")
        logger.信息("仅控制台")
        capsys.readouterr()
        with pytest.raises(运行时错误, match="内存导出器"):
            logger.取记录()

    def test_异步管道记录可读取(self):
        logger = _stdlib_配置结构化日志(输出="内存", 异步=True)
        logger.信息("异步消息")
        records = logger.取记录()
        assert [record["body"] for record in records] == ["异步消息"]
        logger.关闭()

    def test_批量大小达到阈值才导出(self):
        logger = _stdlib_配置结构化日志(输出="内存", 批量大小=3)
        logger.信息("第一条")
        logger.信息("第二条")
        assert len(logger._导出器.records) == 0
        logger.信息("第三条")
        assert len(logger._导出器.records) == 3


class Test导出输出:
    """JSON 输出格式与导出器选择。"""

    def test_文件输出为JSON行(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "structured.log")
            logger = _stdlib_配置结构化日志(输出="文件", 路径=path)
            logger.信息("文件消息", {"键": "值"})
            logger.关闭()
            lines = Path(path).read_text(encoding="utf-8").splitlines()
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["body"] == "文件消息"
            assert record["attributes"] == {"键": "值"}

    def test_控制台输出为JSON(self, capsys):
        logger = _stdlib_配置结构化日志(输出="控制台")
        logger.警告("控制台消息")
        logger.关闭()
        captured = capsys.readouterr()
        assert "控制台消息" in captured.err
        assert json.loads(captured.err.strip())["severity_text"] == "WARN"

    def test_两者输出同时写控制台和文件(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "both.log")
            logger = _stdlib_配置结构化日志(输出="两者", 路径=path)
            logger.错误("双写消息")
            logger.关闭()
            captured = capsys.readouterr()
            assert "双写消息" in captured.err
            content = Path(path).read_text(encoding="utf-8")
            assert json.loads(content.strip())["body"] == "双写消息"

    def test_文件输出缺少路径抛中文错误(self):
        with pytest.raises(运行时错误, match="必须提供路径"):
            _stdlib_配置结构化日志(输出="文件")

    def test_两者输出缺少路径抛中文错误(self):
        with pytest.raises(运行时错误, match="必须提供路径"):
            _stdlib_配置结构化日志(输出="两者")

    def test_无效输出方式抛中文错误(self):
        with pytest.raises(运行时错误, match="无效的日志输出方式"):
            _stdlib_配置结构化日志(输出="数据库")


class Test处理器:
    """属性注入、脱敏与采样。"""

    def test_属性注入处理器合并静态属性(self):
        处理器 = _stdlib_创建属性处理器({"服务模块": "订单"})
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("消息", {"请求号": "r1"})
        attributes = logger.取记录()[0]["attributes"]
        assert attributes["服务模块"] == "订单"
        assert attributes["请求号"] == "r1"

    def test_脱敏处理器按键替换(self):
        处理器 = _stdlib_创建脱敏处理器(键=["密码", "token"])
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("登录", {"密码": "123456", "token": "abc", "用户": "张三"})
        attributes = logger.取记录()[0]["attributes"]
        assert attributes["密码"] == "***"
        assert attributes["token"] == "***"
        assert attributes["用户"] == "张三"

    def test_脱敏处理器接受单个键名(self):
        处理器 = _stdlib_创建脱敏处理器(键="密码")
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("登录", {"密码": "123456", "用户": "张三"})
        attributes = logger.取记录()[0]["attributes"]
        assert attributes["密码"] == "***"
        assert attributes["用户"] == "张三"

    def test_脱敏处理器按正则替换正文与属性(self):
        处理器 = _stdlib_创建脱敏处理器(规则=[r"\d{11}"], 掩码="[手机号]")
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("手机号 13800138000", {"联系方式": "13900139000"})
        record = logger.取记录()[0]
        assert record["body"] == "手机号 [手机号]"
        assert record["attributes"]["联系方式"] == "[手机号]"

    def test_采样比率为零丢弃普通记录(self):
        处理器 = _stdlib_创建采样处理器(比率=0.0, 保留错误=False)
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("被丢弃")
        assert logger.取记录() == []

    def test_采样保留错误记录(self):
        处理器 = _stdlib_创建采样处理器(比率=0.0, 保留错误=True)
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("被丢弃")
        logger.错误("被保留")
        records = logger.取记录()
        assert [record["body"] for record in records] == ["被保留"]

    def test_脱敏处理器模式别名(self):
        处理器 = _stdlib_创建脱敏处理器(模式=[r"\d{11}"])
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("手机号 13800138000")
        assert "13800138000" not in logger.取记录()[0]["body"]

    def test_脱敏处理器规则优先于模式(self):
        处理器 = _stdlib_创建脱敏处理器(规则=[r"\d{11}"], 模式=[r"[A-Z]+"])
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("手机号 13800138000 ABC", {"值": "13800138000"})
        record = logger.取记录()[0]
        assert "13800138000" not in record["body"]
        assert "ABC" in record["body"]
        assert record["attributes"]["值"] == "***"

    def test_采样处理器比例别名(self):
        处理器 = _stdlib_创建采样处理器(比例=0.0, 保留错误=False)
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("被丢弃")
        assert logger.取记录() == []

    def test_采样处理器比率优先于比例(self):
        处理器 = _stdlib_创建采样处理器(比率=1.0, 比例=0.0, 保留错误=False)
        assert 处理器.ratio == 1.0
        logger = _stdlib_配置结构化日志(输出="内存", 处理器=[处理器])
        logger.信息("因比率优先而保留")
        assert len(logger.取记录()) == 1

    def test_非法采样比率抛中文错误(self):
        with pytest.raises(运行时错误, match="采样比例"):
            _stdlib_创建采样处理器(比率=2.0)

    def test_创建内存导出器返回导出器而非处理器(self):
        exporter = _stdlib_创建内存导出器()
        assert isinstance(exporter, MemoryExporter)
        assert callable(exporter.export)
        assert not callable(getattr(exporter, "process", None))

    def test_内存导出器可直接收集记录(self):
        from dao.logmodel.model import create_record

        exporter = _stdlib_创建内存导出器()
        exporter.export([create_record("直接导出")])
        assert len(exporter.records) == 1
        assert exporter.records[0].body == "直接导出"


class Test追踪与资源:
    """W3C 追踪上下文与 Resource 元数据。"""

    def test_创建追踪注入追踪ID与跨度ID(self):
        context = _stdlib_创建追踪({"租户": "acme"})
        logger = _stdlib_配置结构化日志(输出="内存")
        logger.信息("跨服务调用")
        record = logger.取记录()[0]
        assert record["trace_id"] == context.trace_id
        assert record["span_id"] == context.span_id

    def test_取追踪头无追踪时为空文本子类(self):
        头 = _stdlib_取追踪头()
        assert isinstance(头, str)
        assert 头 == ""
        assert 头["traceparent"] == ""
        assert 头.to_dict() == {}

    def test_取追踪头与载入追踪头往返(self):
        _stdlib_创建追踪({"租户": "acme"})
        header = _stdlib_取追踪头()
        assert header.startswith("00-")
        current_trace.set(None)
        restored = _stdlib_载入追踪头(header)
        assert restored is not None
        assert _stdlib_取追踪头() == header

    def test_创建追踪可指定追踪ID与跨度ID(self):
        context = _stdlib_创建追踪(
            {"租户": "acme"},
            追踪ID="a" * 32,
            跨度ID="b" * 16,
        )
        assert context.trace_id == "a" * 32
        assert context.span_id == "b" * 16

    def test_取追踪头支持字符串与字典双重访问(self):
        _stdlib_创建追踪({"租户": "acme"})
        头 = _stdlib_取追踪头()
        assert isinstance(头, str)
        assert 头 == str(头)
        assert 头.startswith("00-")
        assert 头["traceparent"] == str(头)
        assert 头["baggage"] == "租户=acme"
        assert "traceparent" in 头
        assert 头.get("baggage") == "租户=acme"
        assert 头["不存在"] == ""
        assert 头.to_dict() == {"traceparent": str(头), "baggage": "租户=acme"}
        assert 头.as_headers() == 头.to_dict()

    def test_载入追踪头接受请求头字典(self):
        _stdlib_创建追踪({"租户": "acme"})
        头 = _stdlib_取追踪头()
        current_trace.set(None)
        restored = _stdlib_载入追踪头(dict(头.items()))
        assert restored is not None
        assert restored.baggage == {"租户": "acme"}
        assert _stdlib_取追踪头() == str(头)

    def test_载入追踪头接受traceparent字符串(self):
        _stdlib_创建追踪({"租户": "acme"})
        头 = _stdlib_取追踪头()
        current_trace.set(None)
        restored = _stdlib_载入追踪头(str(头))
        assert restored is not None
        # 纯 traceparent 字符串不携带 baggage
        assert _stdlib_取追踪头()["baggage"] == ""
        assert _stdlib_取追踪头().to_dict() == {"traceparent": str(头)}

    def test_载入无效追踪头返回空不抛错(self):
        assert _stdlib_载入追踪头("无效头") is None
        assert _stdlib_取追踪头() == ""

    def test_资源注入兼容中英文键(self):
        logger = _stdlib_配置结构化日志(
            输出="内存", 资源={"服务名": "支付服务", "host.name": "节点一"}
        )
        logger.信息("带资源")
        resource = logger.取记录()[0]["resource"]
        assert resource["service.name"] == "支付服务"
        assert resource["host.name"] == "节点一"

    def test_设置资源未传参数保留原值(self):
        _stdlib_设置资源(服务名="订单服务")
        resource = _stdlib_设置资源(主机名="节点二")
        assert resource.service_name == "订单服务"
        assert resource.host_name == "节点二"

    def test_设置资源属性合并(self):
        _stdlib_设置资源(属性={"区域": "华南"})
        resource = _stdlib_设置资源(属性={"版本": "1.0"})
        assert resource.attributes == {"区域": "华南", "版本": "1.0"}


class Test现有API回归:
    """确保结构化扩展没有改变原有文本日志行为。"""

    def test_原有配置日志仍写文本格式(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "text.log")
            logger = _stdlib_配置日志(输出="文件", 路径=path, 级别="调试")
            logger.信息("文本消息")
            content = Path(path).read_text(encoding="utf-8")
            assert "INFO" in content
            assert "文本消息" in content
            assert content.strip().startswith("INFO")

    def test_原有日志器与结构化日志器类型不同(self):
        from dao.stdlib.log import DaoLogger

        logger = _stdlib_配置日志(输出="控制台")
        structured = _stdlib_配置结构化日志(输出="内存")
        assert isinstance(logger, DaoLogger)
        assert isinstance(structured, DaoStructuredLogger)
        assert not isinstance(structured, DaoLogger)


class Test道语言端到端:
    """用真实解释器执行 .道 脚本验证桥接。"""

    def test_道语言结构化日志内存取记录(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "结构化.道")
            Path(script).write_text(
                '从 日志 导入 配置结构化日志, 创建属性处理器\n'
                '处理器 = [创建属性处理器({"来源": "端到端"})]\n'
                '日志器 = 配置结构化日志(输出="内存", 处理器=处理器)\n'
                '日志器.信息("道语言消息", {"键": "值"})\n'
                '记录 = 日志器.取记录()\n'
                '打印(记录[0]["body"])\n'
                '打印(记录[0]["attributes"]["来源"])\n',
                encoding="utf-8",
            )
            result = _运行脚本(script)
            assert "道语言消息" in result.stdout
            assert "端到端" in result.stdout

    def test_道语言结构化日志写JSON文件(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "structured.log")
            script = os.path.join(tmpdir, "文件结构化.道")
            Path(script).write_text(
                '从 日志 导入 配置结构化日志\n'
                f'日志器 = 配置结构化日志(输出="文件", 路径="{log_path}")\n'
                '日志器.警告("文件端到端")\n'
                '日志器.关闭()\n',
                encoding="utf-8",
            )
            _运行脚本(script)
            record = json.loads(Path(log_path).read_text(encoding="utf-8").strip())
            assert record["body"] == "文件端到端"
            assert record["severity_text"] == "WARN"

    def test_道语言追踪头往返(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "追踪.道")
            Path(script).write_text(
                '从 日志 导入 创建追踪, 取追踪头, 载入追踪头, 配置结构化日志\n'
                '创建追踪({"租户": "acme"})\n'
                '头 = 取追踪头()\n'
                '日志器 = 配置结构化日志(输出="内存")\n'
                '日志器.信息("追踪消息")\n'
                '记录 = 日志器.取记录()\n'
                '打印(头)\n'
                '打印(记录[0]["trace_id"])\n'
                '打印(载入追踪头(头) != 空)\n',
                encoding="utf-8",
            )
            result = _运行脚本(script)
            lines = result.stdout.strip().splitlines()
            assert lines[0].startswith("00-")
            assert lines[0].split("-")[1] == lines[1]
            assert "真" in lines[2]

    def test_道语言追踪头字典式访问与处理器别名(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "文档风格.道")
            Path(script).write_text(
                '从 日志 导入 配置结构化日志, 创建追踪, 取追踪头, 载入追踪头, '
                '创建属性处理器, 创建脱敏处理器, 创建采样处理器\n'
                '创建追踪(属性={"租户": "acme"})\n'
                '头 = 取追踪头()\n'
                '打印(头["traceparent"] == 头)\n'
                '打印(头["baggage"])\n'
                '打印(载入追踪头(头) != 空)\n'
                '日志器 = 配置结构化日志(\n'
                '    输出="内存", 资源={"服务名": "支付服务"},\n'
                '    处理器=[创建属性处理器(属性={"环境": "生产"}),\n'
                '            创建脱敏处理器(键=["user.id"]),\n'
                '            创建采样处理器(比例=1.0)],\n'
                ')\n'
                '日志器.信息("支付成功", 属性={"user.id": "123"})\n'
                '记录 = 日志器.取记录()\n'
                '打印(记录[0]["body"])\n'
                '打印(记录[0].severity_text)\n'
                '打印(记录[0]["resource"]["service.name"])\n',
                encoding="utf-8",
            )
            result = _运行脚本(script)
            lines = result.stdout.strip().splitlines()
            assert lines[:3] == ["真", "租户=acme", "真"]
            assert lines[3:] == ["支付成功", "INFO", "支付服务"]

    def test_道语言原有配置日志不受影响(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "text.log")
            script = os.path.join(tmpdir, "文本.道")
            Path(script).write_text(
                '从 日志 导入 配置日志, 默认格式\n'
                f'日志器 = 配置日志(输出="文件", 路径="{log_path}", 级别="调试")\n'
                '日志器.信息("原有端到端")\n',
                encoding="utf-8",
            )
            _运行脚本(script)
            content = Path(log_path).read_text(encoding="utf-8")
            assert "原有端到端" in content
            assert "INFO" in content
