"""道语言标准库：日志。

提供分级日志输出，可打印到控制台或写入文件，格式完全可配置。
日志自动附带调用位置（文件名:行号），由解释器在调用时注入，调用者无需传入。
可用占位符见 ``DEFAULT_FORMAT`` 与 ``文档/10-标准库.md`` 的日志章节。

此外还桥接 OpenTelemetry 风格的结构化日志：把每条日志构造成 LogRecord，
经处理器管道（属性注入、脱敏、采样、追踪注入）后由导出器输出为 JSON。
结构化日志能力通过 ``配置结构化日志`` 等函数导出，实现位于 ``dao.logmodel``。

典型用法::

    从 日志 导入 配置日志, 默认格式
    日志器 = 配置日志(输出="两者", 路径="应用.log", 格式=默认格式)
    日志器.信息("服务启动")
"""

from __future__ import annotations

import json
import logging

from ..builtins.callables import BuiltinFunction
from ..callsite import current_call_site
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
    "{描述}": "%(message)s",
    "{消息}": "%(message)s",
    "{文件名}": "%(filename)s",
    "{行号}": "%(lineno)d",
    "{函数名}": "%(funcName)s",
}

# 默认格式
DEFAULT_FORMAT = "{级别} {时间戳} {线程ID} {代码位置} | {描述信息}"


def _current_location() -> str:
    """返回解释器记录的当前调用位置（文件名:行号）。"""
    site = current_call_site.get()
    return site.describe() if site is not None else ""


def _dao_format_to_logging(fmt: str) -> str:
    """把道语言日志格式占位符转换为 logging 格式。

    字面 ``%`` 先转义为 ``%%``，避免格式里写 ``100%`` 时被 logging 误当作
    格式符；占位符随后替换为 ``%(...)s``，不受转义影响。
    """
    result = str(fmt).replace("%", "%%")
    for dao_fmt, py_fmt in sorted(_FORMAT_MAP.items(), key=lambda item: -len(item[0])):
        result = result.replace(dao_fmt, py_fmt)
    return result


class DaoLogger:
    """道语言日志器：分级日志、格式设置与多处理器输出。"""

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._formatter: logging.Formatter | None = None

    def _write(self, level: int, 消息):
        self._logger.log(level, 消息, extra={"location": _current_location()})

    def 调试(self, 消息):
        """记录调试级别日志，自动附带调用位置。"""
        self._write(logging.DEBUG, 消息)

    def 信息(self, 消息):
        """记录信息级别日志，自动附带调用位置。"""
        self._write(logging.INFO, 消息)

    def 警告(self, 消息):
        """记录警告级别日志，自动附带调用位置。"""
        self._write(logging.WARNING, 消息)

    def 错误(self, 消息):
        """记录错误级别日志，自动附带调用位置。"""
        self._write(logging.ERROR, 消息)

    def 致命(self, 消息):
        """记录致命级别日志，自动附带调用位置。"""
        self._write(logging.CRITICAL, 消息)

    def 记录(self, 级别, 消息):
        """按中文级别名记录日志（调试/信息/警告/错误/致命）。"""
        if 级别 not in _LEVEL_MAP:
            raise 运行时错误(
                f"无效的日志级别: {级别}，有效值: {', '.join(_LEVEL_MAP.keys())}"
            )
        self._write(_LEVEL_MAP[级别], 消息)

    def 设置级别(self, 级别):
        """设置日志器的最低级别，低于该级别的日志不再输出。"""
        if 级别 not in _LEVEL_MAP:
            raise 运行时错误(
                f"无效的日志级别: {级别}，有效值: {', '.join(_LEVEL_MAP.keys())}"
            )
        self._logger.setLevel(_LEVEL_MAP[级别])

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


def _stdlib_创建日志器(名称):
    """创建一个指定名称的日志器。"""
    return DaoLogger(名称)


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


# ---------------------------------------------------------------------------
# 结构化日志（OpenTelemetry 风格）桥接
# ---------------------------------------------------------------------------


def _logmodel():
    """延迟导入结构化日志内核，返回 (context, exporters, model, pipeline, processors)。

    延迟导入让纯文本日志在管道模块尚未就绪时仍可独立使用，也避免模块级循环导入。
    """
    from ..logmodel import context as _context
    from ..logmodel import exporters as _exporters
    from ..logmodel import model as _model
    from ..logmodel import pipeline as _pipeline
    from ..logmodel import processors as _processors

    return _context, _exporters, _model, _pipeline, _processors


def _otlp():
    """延迟导入 OTLP 导出器模块，避免纯文本日志依赖网络栈。"""
    from ..logmodel import otlp as _otlp

    return _otlp


def _结构化字典(值, 名称: str) -> dict:
    """把道语言传入的字典规范为 Python dict；空值视为空字典。"""
    if 值 is None:
        return {}
    if isinstance(值, dict):
        return dict(值)
    raise 运行时错误(f"{名称}必须是字典")


def _结构化列表(值) -> list | None:
    """把单个值或序列规范为列表；空值保持为空。"""
    if 值 is None:
        return None
    if isinstance(值, (list, tuple)):
        return list(值)
    return [值]


# 资源字典的中英文键别名，便于道语言脚本使用中文键名。
_RESOURCE_ALIASES = {
    "服务名": "service.name",
    "主机名": "host.name",
    "环境": "environment",
}


def _设置结构化资源(资源) -> None:
    """把道语言资源字典设置到全局 Resource，兼容中英文键名。"""
    if not 资源:
        return
    context, _, _, _, _ = _logmodel()
    data = _结构化字典(资源, "资源")
    service_name = None
    host_name = None
    environment = None
    for key in list(data):
        value = data.pop(key)
        mapped = _RESOURCE_ALIASES.get(str(key), str(key))
        if mapped == "service.name":
            service_name = value
        elif mapped == "host.name":
            host_name = value
        elif mapped == "environment":
            environment = value
        else:
            data[mapped] = value
    context.set_resource(
        service_name=service_name,
        host_name=host_name,
        environment=environment,
        attributes=data,
    )


class _扇出导出器:
    """把同一批记录同时交给多个导出器，用于「两者」输出。"""

    def __init__(self, *导出器):
        self._导出器列表 = list(导出器)

    def export(self, records) -> None:
        """把一批记录转发给每个子导出器。"""
        for 导出器 in self._导出器列表:
            导出器.export(records)

    # 兼容管道可能使用的英文方法名。
    emit = export

    def flush(self) -> None:
        """刷新所有子导出器。"""
        for 导出器 in self._导出器列表:
            if hasattr(导出器, "flush"):
                导出器.flush()

    刷新 = flush

    def close(self) -> None:
        """关闭所有子导出器。"""
        for 导出器 in self._导出器列表:
            if hasattr(导出器, "close"):
                导出器.close()

    关闭 = close


class _追踪头(str):
    """traceparent 文本，同时支持请求头字典式访问。

    道语言解释器仅对 ``dict`` 支持字符串键索引，故通过 ``__class__`` 让
    ``isinstance(头, dict)`` 成立，使 ``头["traceparent"]`` 在脚本中可用；
    对象本身仍是 ``str`` 子类，可直接与 traceparent 文本比较。
    """

    @property
    def __class__(self):
        return dict

    def __new__(cls, 文本: str, 头: dict | None = None):
        obj = super().__new__(cls, 文本)
        object.__setattr__(obj, "_头", dict(头 or {}))
        return obj

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._头.get(key, "")
        return str.__getitem__(self, key)

    def __contains__(self, key):
        if isinstance(key, str):
            return key in self._头
        return str.__contains__(self, key)

    def get(self, key, default=None):
        """按键获取请求头值，不存在时返回默认值。"""
        return self._头.get(key, default)

    def keys(self):
        """返回请求头键集合。"""
        return self._头.keys()

    def values(self):
        """返回请求头值集合。"""
        return self._头.values()

    def items(self):
        """返回请求头键值对。"""
        return self._头.items()

    def to_dict(self):
        """返回普通请求头字典。"""
        return dict(self._头)

    def as_headers(self):
        """返回普通请求头字典（``to_dict`` 的别名）。"""
        return dict(self._头)


class _记录字典(dict):
    """结构化日志记录字典，同时支持属性式字段访问与序列化。"""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self):
        """返回普通字典。"""
        return dict(self)

    def to_json(self, ensure_ascii=False):
        """序列化为单行 JSON。"""
        return json.dumps(self, ensure_ascii=ensure_ascii)


def _找内存导出器(导出器):
    """在导出器中查找内存导出器；支持穿透常见的包装导出器属性。"""
    _, exporters, _, _, _ = _logmodel()
    pending = [导出器]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, exporters.MemoryExporter):
            return current
        for name in (
            "_wrapped",
            "_exporter",
            "_导出器",
            "_内部导出器",
            "wrapped",
            "exporter",
        ):
            wrapped = getattr(current, name, None)
            if wrapped is not None:
                pending.append(wrapped)
    return None


class DaoStructuredLogger:
    """道语言结构化日志器：把每条日志构造成 LogRecord，经处理管道导出。"""

    def __init__(self, 名称, 管道, 导出器, 级别="信息"):
        self._名称 = 名称
        self._管道 = 管道
        self._导出器 = 导出器
        _, _, model, _, _ = _logmodel()
        self._阈值 = model.severity_of(级别)[1]

    def _写入(self, 级别, 消息, 属性) -> None:
        _, _, model, _, _ = _logmodel()
        _, number = model.severity_of(级别)
        if number < self._阈值:
            return
        record = model.create_record(
            消息,
            number,
            属性=_结构化字典(属性, "日志属性"),
            作用域={"name": self._名称},
            位置=_current_location(),
        )
        self._管道.emit(record)

    def 调试(self, 消息, 属性=None):
        """记录调试级别结构化日志，自动附带调用位置。"""
        self._写入("调试", 消息, 属性)

    def 信息(self, 消息, 属性=None):
        """记录信息级别结构化日志，自动附带调用位置。"""
        self._写入("信息", 消息, 属性)

    def 警告(self, 消息, 属性=None):
        """记录警告级别结构化日志，自动附带调用位置。"""
        self._写入("警告", 消息, 属性)

    def 错误(self, 消息, 属性=None):
        """记录错误级别结构化日志，自动附带调用位置。"""
        self._写入("错误", 消息, 属性)

    def 致命(self, 消息, 属性=None):
        """记录致命级别结构化日志，自动附带调用位置。"""
        self._写入("致命", 消息, 属性)

    def 记录(self, 级别, 消息, 属性=None):
        """按中文级别名记录结构化日志（调试/信息/警告/错误/致命）。"""
        self._写入(级别, 消息, 属性)

    def 刷新(self):
        """刷新处理管道，把缓冲中的记录立即写出。"""
        self._管道.flush()

    def 关闭(self):
        """关闭处理管道并释放导出器资源。"""
        self._管道.close()

    def 取记录(self):
        """返回内存导出器收集到的记录字典列表；非内存导出器抛运行时错误。"""
        memory = _找内存导出器(self._导出器)
        if memory is None:
            raise 运行时错误(
                "取记录需要内存导出器，请使用输出=\"内存\"或传入创建内存导出器的结果"
            )
        self._管道.flush()
        records = getattr(memory, "records", None)
        if records is None:
            records = getattr(memory, "记录", None)
        if not isinstance(records, (list, tuple)):
            raise 运行时错误("内存导出器未提供可读取的记录列表")
        result = []
        for record in records:
            if hasattr(record, "to_dict"):
                result.append(_记录字典(record.to_dict()))
            elif isinstance(record, dict):
                result.append(_记录字典(dict(record)))
            else:
                result.append(_记录字典({"body": str(record)}))
        return result

    def __repr__(self):
        return f"<结构化日志器 {self._名称}>"


def _stdlib_配置结构化日志(
    名称="道",
    输出="控制台",
    路径=None,
    级别="信息",
    资源=None,
    处理器=None,
    批量大小=1,
    异步=False,
    导出器=None,
):
    """一步配置结构化日志器：构造 LogRecord 经处理器管道导出为 JSON。

    输出可为 控制台 / 文件 / 两者 / 内存；内存输出配合 ``取记录()`` 读取记录。
    处理器为处理器对象列表，链首自动注入追踪与资源信息。传入 ``导出器`` 时
    优先使用它（忽略 输出/路径 对应的默认导出器），输出取值仍会被校验。
    """
    _, exporters, _, pipeline, processors = _logmodel()
    if 输出 not in ("控制台", "文件", "两者", "内存"):
        raise 运行时错误(
            f"无效的日志输出方式: {输出}，有效值: 控制台 / 文件 / 两者 / 内存"
        )
    if 导出器 is None and 输出 in ("文件", "两者") and not 路径:
        raise 运行时错误(f"输出为{输出}时必须提供路径")

    _设置结构化资源(资源)

    chain = [processors.TraceInjector()]
    for item in (处理器 or []):
        if not isinstance(item, (list, tuple)):
            chain.append(item)
    if 导出器 is not None:
        exporter = 导出器
    elif 输出 == "控制台":
        exporter = exporters.ConsoleExporter()
    elif 输出 == "文件":
        exporter = exporters.FileExporter(路径)
    elif 输出 == "两者":
        exporter = _扇出导出器(
            exporters.ConsoleExporter(), exporters.FileExporter(路径)
        )
    else:
        exporter = exporters.MemoryExporter()

    pipeline_cls = pipeline.AsyncLogPipeline if 异步 else pipeline.LogPipeline
    管道 = pipeline_cls(chain, exporter, 批量大小)
    return DaoStructuredLogger(名称, 管道, exporter, 级别)


def _stdlib_创建追踪(属性=None, 追踪ID=None, 跨度ID=None):
    """创建并激活一条新追踪，可携带 baggage 属性，返回追踪上下文。"""
    context, _, _, _, _ = _logmodel()
    return context.start_trace(
        baggage=_结构化字典(属性, "追踪属性"),
        trace_id=追踪ID,
        span_id=跨度ID,
    )


def _stdlib_取追踪头():
    """返回当前追踪的 W3C traceparent 头；无追踪时返回空文本。

    结果为 traceparent 字符串子类，同时支持 ``["traceparent"]`` / ``.get()`` /
    ``to_dict()`` / ``as_headers()`` 等字典式访问；无追踪时返回空字符串子类。
    """
    context, _, _, _, _ = _logmodel()
    current = context.current_trace_context()
    if current is None:
        return _追踪头("")
    return _追踪头(current.traceparent(), context.inject_headers())


def _stdlib_载入追踪头(头):
    """解析并激活 W3C traceparent 头；接受字符串或请求头字典，无效返回空。"""
    context, _, _, _, _ = _logmodel()
    if isinstance(头, dict):
        current = context.extract_headers(头)
    else:
        current = context.parse_traceparent(头)
    if current is None:
        return None
    context.current_trace.set(current)
    return current


def _stdlib_设置资源(服务名=None, 主机名=None, 环境=None, 属性=None):
    """设置全局资源元数据；未传参数保留原值，返回设置后的 Resource。"""
    context, _, _, _, _ = _logmodel()
    return context.set_resource(
        service_name=服务名,
        host_name=主机名,
        environment=环境,
        attributes=_结构化字典(属性, "资源属性"),
    )


def _stdlib_创建脱敏处理器(键=None, 规则=None, 掩码="***", 模式=None):
    """创建脱敏处理器：按键名或正则规则（别名：模式）匹配属性值并替换为掩码。"""
    _, _, _, _, processors = _logmodel()
    if 规则 is None:
        规则 = 模式
    return processors.RedactionProcessor(
        keys=_结构化列表(键), patterns=_结构化列表(规则), mask=掩码
    )


_未指定比率 = object()


def _stdlib_创建采样处理器(比率=_未指定比率, 保留错误=True, 比例=None):
    """创建采样处理器：按比率（别名：比例）保留记录，出错记录可始终保留。"""
    _, _, _, _, processors = _logmodel()
    if 比率 is _未指定比率:
        比率 = 1.0 if 比例 is None else 比例
    return processors.SamplingProcessor(ratio=比率, keep_errors=保留错误)


def _stdlib_创建属性处理器(属性=None):
    """创建属性注入处理器：把给定属性合并到每条日志记录。"""
    _, _, _, _, processors = _logmodel()
    return processors.AttributeInjector(attributes=_结构化字典(属性, "注入属性"))


def _stdlib_创建内存导出器():
    """创建内存导出器，用于收集日志记录并在测试中查看。"""
    _, exporters, _, _, _ = _logmodel()
    return exporters.MemoryExporter()


def _stdlib_从环境加载资源():
    """从环境变量加载资源元数据并激活，返回加载后的 Resource。"""
    context, _, _, _, _ = _logmodel()
    resource = context.resource_from_env()
    context.current_resource.set(resource)
    return resource


def _stdlib_创建OTLP导出器(端点, 头=None, 超时=5.0):
    """创建 OTLP/HTTP 导出器：端点为收集器地址，头为请求头字典，超时单位为秒。"""
    if not 端点:
        raise 运行时错误("OTLP 导出器端点不能为空")
    otlp = _otlp()
    return otlp.OTLPHTTPExporter(
        endpoint=端点,
        headers=_结构化字典(头, "OTLP 请求头"),
        timeout=超时,
    )


def _stdlib_创建尾部采样导出器(导出器, 比率=1.0, 保留错误=True, 最大追踪数=1000):
    """创建尾部采样导出器：按追踪采样后转发给内部导出器。"""
    if not callable(getattr(导出器, "export", None)):
        raise 运行时错误("尾部采样导出器需要一个提供 export 方法的导出器")
    _, exporters, _, _, _ = _logmodel()
    return exporters.TailSamplingExporter(
        exporter=导出器,
        ratio=比率,
        keep_errors=保留错误,
        max_traces=最大追踪数,
    )


def create_module_env(interpreter=None) -> Environment:
    """创建日志模块的导出环境。"""
    env = Environment()
    env.define("创建日志器", BuiltinFunction("创建日志器", _stdlib_创建日志器, -1))
    env.define("创建文件处理器", BuiltinFunction("创建文件处理器", _stdlib_创建文件处理器, -1))
    env.define("创建控制台处理器", BuiltinFunction("创建控制台处理器", _stdlib_创建控制台处理器, -1))
    env.define("配置日志", BuiltinFunction("配置日志", _stdlib_配置日志, -1))
    env.define("配置结构化日志", BuiltinFunction("配置结构化日志", _stdlib_配置结构化日志, -1))
    env.define("创建追踪", BuiltinFunction("创建追踪", _stdlib_创建追踪, -1))
    env.define("取追踪头", BuiltinFunction("取追踪头", _stdlib_取追踪头, -1))
    env.define("载入追踪头", BuiltinFunction("载入追踪头", _stdlib_载入追踪头, -1))
    env.define("设置资源", BuiltinFunction("设置资源", _stdlib_设置资源, -1))
    env.define("创建脱敏处理器", BuiltinFunction("创建脱敏处理器", _stdlib_创建脱敏处理器, -1))
    env.define("创建采样处理器", BuiltinFunction("创建采样处理器", _stdlib_创建采样处理器, -1))
    env.define("创建属性处理器", BuiltinFunction("创建属性处理器", _stdlib_创建属性处理器, -1))
    env.define("创建内存导出器", BuiltinFunction("创建内存导出器", _stdlib_创建内存导出器, -1))
    env.define("从环境加载资源", BuiltinFunction("从环境加载资源", _stdlib_从环境加载资源, -1))
    env.define("创建OTLP导出器", BuiltinFunction("创建OTLP导出器", _stdlib_创建OTLP导出器, -1))
    env.define(
        "创建尾部采样导出器",
        BuiltinFunction("创建尾部采样导出器", _stdlib_创建尾部采样导出器, -1),
    )
    env.define("默认格式", DEFAULT_FORMAT)
    env.exports = list(env.values.keys())
    return env
