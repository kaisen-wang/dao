"""国际化模块：为「道」语言提供区域设置、翻译表与本地化格式能力。

仅依赖 Python 标准库 ``locale`` 与 ``datetime``，不引入第三方包。
区域查询/设置均做安全封装：非法区域名转换为清晰的道语言运行时错误；
数字与货币格式使用内置区域格式表，避免测试与运行环境已安装区域集耦合。
"""

import datetime
import locale

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误, 运行时错误

# 翻译表：{语言标识: {原文键: 译文}}，模块级缓存，由 注册翻译/清除翻译 维护
_翻译表: dict[str, dict[str, str]] = {}

# 内置区域格式表：分组符、小数符、货币符、货币是否后置
_区域格式表 = {
    "zh": {"分组符": ",", "小数符": ".", "货币符": "¥", "货币后置": False},
    "en": {"分组符": ",", "小数符": ".", "货币符": "$", "货币后置": False},
    "de": {"分组符": ".", "小数符": ",", "货币符": "€", "货币后置": True},
    "fr": {"分组符": " ", "小数符": ",", "货币符": "€", "货币后置": True},
    "ja": {"分组符": ",", "小数符": ".", "货币符": "¥", "货币后置": False},
}
_默认格式 = _区域格式表["zh"]

_英文星期 = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_中文星期 = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
_英文月份 = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_中文月份 = (
    "一月", "二月", "三月", "四月", "五月", "六月",
    "七月", "八月", "九月", "十月", "十一月", "十二月",
)


def _校验文本(值, 名字):
    """校验参数为文本类型并返回它。"""
    if not isinstance(值, str):
        raise 类型错误(f"{名字}必须是文本类型")
    return 值


def _当前语言():
    """读取当前区域的语言标识，读取失败时回退为 zh_CN。"""
    try:
        名称 = locale.getlocale()[0]
    except (ValueError, OSError):
        名称 = None
    return 名称 or "zh_CN"


def _语言前缀(语言=None):
    """把区域标识归一化为小写语言前缀。"""
    if 语言 is None:
        语言 = _当前语言()
    _校验文本(语言, "语言")
    return 语言.replace("-", "_").split("_")[0].lower()


def _区域格式(语言=None):
    """取得语言对应的格式规则，未知语言回退为中文规则。"""
    return _区域格式表.get(_语言前缀(语言), _默认格式)


def _中文化(文本):
    """把 strftime 输出中的英文星期与月份替换为中文。"""
    for 英文, 中文 in zip(_英文月份, _中文月份):
        文本 = 文本.replace(英文, 中文)
    for 英文, 中文 in zip(_英文星期, _中文星期):
        文本 = 文本.replace(英文, 中文)
    return 文本


def _解析时间(时间):
    """把日期时间参数转换为 datetime 对象。"""
    if 时间 is None:
        return datetime.datetime.now()
    if isinstance(时间, bool):
        raise 类型错误("时间参数不能是布尔值")
    if isinstance(时间, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(时间)
        except (ValueError, OSError, OverflowError) as 错误:
            raise 运行时错误(f"时间戳无效: {错误}")
    if isinstance(时间, datetime.datetime):
        return 时间
    if isinstance(时间, datetime.date):
        return datetime.datetime.combine(时间, datetime.time())
    if isinstance(时间, str):
        try:
            return datetime.datetime.fromisoformat(时间)
        except ValueError as 错误:
            raise 运行时错误(f"时间文本格式无效: {错误}")
    raise 类型错误("时间参数必须是日期、时间戳或 ISO 时间文本")


def _stdlib_当前区域():
    """返回当前进程的区域设置（语言与编码）。"""
    try:
        语言, 编码 = locale.getlocale()
    except (ValueError, OSError) as 错误:
        raise 运行时错误(f"读取区域设置失败: {错误}")
    return {"语言": 语言 or "", "编码": 编码 or ""}


def _stdlib_设置区域(区域名):
    """设置当前进程的全局区域，返回实际生效的区域名。

    传入空文本可恢复系统默认区域；非法区域名抛出运行时错误。
    """
    _校验文本(区域名, "区域名")
    try:
        return locale.setlocale(locale.LC_ALL, 区域名)
    except locale.Error as 错误:
        raise 运行时错误(f"设置区域失败: {错误}")


def _stdlib_区域别名(名称):
    """把区域名称规范化为标准别名（不修改全局区域设置）。"""
    _校验文本(名称, "名称")
    return locale.normalize(名称)


def _stdlib_可用区域():
    """返回当前系统已知的区域别名列表（按名称排序）。"""
    return sorted(set(locale.locale_alias.values()))


def _stdlib_注册翻译(语言, 键, 文本):
    """为指定语言注册一条翻译，语言和键均为文本。"""
    _校验文本(语言, "语言")
    _校验文本(键, "键")
    _校验文本(文本, "文本")
    _翻译表.setdefault(语言, {})[键] = 文本
    return 文本


def _stdlib_翻译(键, 语言=None, 默认=None):
    """按语言查询译文，依次尝试完整区域、语言前缀与默认值。"""
    _校验文本(键, "键")
    名称 = 语言 if 语言 is not None else _当前语言()
    _校验文本(名称, "语言")
    前缀 = _语言前缀(名称)
    for 候选 in dict.fromkeys((名称, 前缀)):
        表 = _翻译表.get(候选)
        if 表 is not None and 键 in 表:
            return 表[键]
    return 默认 if 默认 is not None else 键


def _stdlib_翻译项数(语言=None):
    """返回指定语言翻译表中的条目数；不指定时返回全部语言条目总数。"""
    if 语言 is None:
        return sum(len(表) for 表 in _翻译表.values())
    _校验文本(语言, "语言")
    return len(_翻译表.get(语言, {}))


def _stdlib_清除翻译(语言=None):
    """清除翻译表并返回被删除的条目数；不指定语言时清空全部语言。"""
    if 语言 is None:
        数量 = sum(len(表) for 表 in _翻译表.values())
        _翻译表.clear()
        return 数量
    _校验文本(语言, "语言")
    表 = _翻译表.pop(语言, None)
    return len(表) if 表 is not None else 0


def _stdlib_复数形式(数量, 单数, 复数=None, 语言=None):
    """根据数量与语言返回单数或复数形式。

    中文、日文、韩文始终使用单数形式；其余语言在数量不等于 1 时
    使用复数形式，若未提供复数形式则在单数后加 ``s``。
    """
    if not isinstance(数量, (int, float)) or isinstance(数量, bool):
        raise 类型错误("数量必须是数值")
    _校验文本(单数, "单数")
    if 复数 is not None:
        _校验文本(复数, "复数")
    if _语言前缀(语言) in ("zh", "ja", "ko"):
        return 单数
    if 数量 == 1:
        return 单数
    return 复数 if 复数 is not None else 单数 + "s"


def _stdlib_格式化数字(数值, 语言=None, 分组=True):
    """按区域规则格式化数字，加入千位分组符号与本地化小数点。"""
    if not isinstance(数值, (int, float)) or isinstance(数值, bool):
        raise 类型错误("数值必须是数字")
    if not isinstance(分组, bool):
        raise 类型错误("分组必须是布尔值")
    规则 = _区域格式(语言)
    文本 = format(数值, ",") if 分组 else format(数值, "")
    # 单遍映射，避免先替换分组符再替换小数点时互相覆盖
    转换表 = str.maketrans({",": 规则["分组符"], ".": 规则["小数符"]})
    return 文本.translate(转换表)


def _stdlib_格式化货币(数值, 符号=None, 语言=None):
    """按区域规则格式化货币数值，符号省略时使用该区域的默认货币符。"""
    if not isinstance(数值, (int, float)) or isinstance(数值, bool):
        raise 类型错误("数值必须是数字")
    规则 = _区域格式(语言)
    if 符号 is None:
        符号 = 规则["货币符"]
    else:
        _校验文本(符号, "符号")
    数字文本 = _stdlib_格式化数字(数值, 语言=语言)
    return f"{数字文本} {符号}" if 规则["货币后置"] else f"{符号}{数字文本}"


def _stdlib_格式化日期(时间=None, 格式="%Y-%m-%d", 语言=None):
    """按指定格式输出本地化日期文本，中文环境自动翻译星期与月份。"""
    _校验文本(格式, "格式")
    文本 = _解析时间(时间).strftime(格式)
    return _中文化(文本) if _语言前缀(语言) == "zh" else 文本


def _stdlib_星期名称(时间=None, 语言=None):
    """返回日期对应的本地化星期名称。"""
    return _stdlib_格式化日期(时间, "%A", 语言)


def _stdlib_月份名称(时间=None, 语言=None):
    """返回日期对应的本地化月份名称。"""
    return _stdlib_格式化日期(时间, "%B", 语言)


def create_module_env(interpreter=None) -> Environment:
    """创建国际化模块的导出环境。"""
    env = Environment()
    导出表 = (
        ("当前区域", _stdlib_当前区域, 0),
        ("设置区域", _stdlib_设置区域, 1),
        ("区域别名", _stdlib_区域别名, 1),
        ("可用区域", _stdlib_可用区域, 0),
        ("注册翻译", _stdlib_注册翻译, 3),
        ("翻译", _stdlib_翻译, -1),
        ("翻译项数", _stdlib_翻译项数, -1),
        ("清除翻译", _stdlib_清除翻译, -1),
        ("复数形式", _stdlib_复数形式, -1),
        ("格式化数字", _stdlib_格式化数字, -1),
        ("格式化货币", _stdlib_格式化货币, -1),
        ("格式化日期", _stdlib_格式化日期, -1),
        ("星期名称", _stdlib_星期名称, -1),
        ("月份名称", _stdlib_月份名称, -1),
    )
    for 名字, func, 参数个数 in 导出表:
        env.define(名字, BuiltinFunction(名字, func, 参数个数))
    env.exports = list(env.values.keys())
    return env
