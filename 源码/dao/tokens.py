"""
词元（Token）类型定义
====================

定义"道"语言中所有的词元类型，包括关键字、运算符、标点符号和字面量。
词法分析器（lexer）将源代码转换为这些Token的序列。
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    """词元类型枚举"""

    # ========================
    # 字面量 (Literals)
    # ========================
    数值 = auto()  # 42, 3.14, 1_000_000
    文本 = auto()  # "你好", '世界'
    模板文本 = auto()  # `你好 {名字}`
    真 = auto()  # 真
    假 = auto()  # 假
    空 = auto()  # 空

    # ========================
    # 标识符
    # ========================
    标识符 = auto()  # 变量名、函数名等

    # ========================
    # 基础关键字
    # ========================
    定义 = auto()
    常量 = auto()
    函数 = auto()
    返回 = auto()

    # ========================
    # 控制流关键字
    # ========================
    如果 = auto()
    否则如果 = auto()
    否则 = auto()
    当 = auto()  # while
    遍历 = auto()  # for
    对于 = auto()  # for (alias)
    在 = auto()  # in
    从 = auto()  # from (range)
    到 = auto()  # to (range)
    步长 = auto()  # step
    跳出 = auto()  # break
    默认 = auto()  # default
    继续 = auto()  # continue
    匹配 = auto()  # match
    情况 = auto()  # case
    产出 = auto()  # yield

    # ========================
    # 错误处理关键字
    # ========================
    尝试 = auto()
    捕获 = auto()
    最终 = auto()
    抛出 = auto()
    断言 = auto()

    # ========================
    # 逻辑运算关键字
    # ========================
    并且 = auto()  # and
    或者 = auto()  # or
    不是 = auto()  # not
    不在 = auto()  # not in

    # ========================
    # 运算符 (Operators)
    # ========================
    加 = auto()  # +
    减 = auto()  # -
    乘 = auto()  # *
    除 = auto()  # /
    整除 = auto()  # //（表达式上下文）
    取余 = auto()  # %
    幂 = auto()  # **
    赋值 = auto()  # =
    等于 = auto()  # ==
    不等于 = auto()  # !=
    大于 = auto()  # >
    小于 = auto()  # <
    大于等于 = auto()  # >=
    小于等于 = auto()  # <=
    箭头 = auto()  # =>
    管道 = auto()  # |>
    展开 = auto()  # ...
    点 = auto()  # .

    # ========================
    # 标点符号 (Punctuation)
    # ========================
    左括号 = auto()  # ( 或 （
    右括号 = auto()  # ) 或 ）
    左方括号 = auto()  # [
    右方括号 = auto()  # ]
    左花括号 = auto()  # {
    右花括号 = auto()  # }
    逗号 = auto()  # , 或 ，
    冒号 = auto()  # : 或 ：
    感叹号 = auto()  # !（宏调用前缀）

    # ========================
    # OOP 关键字
    # ========================
    运算符 = auto()  # operator
    抽象 = auto()  # abstract
    类型 = auto()  # class
    枚举 = auto()  # enum
    继承自 = auto()  # extends
    初始化 = auto()  # constructor
    本对象 = auto()  # this/self
    父对象 = auto()  # super
    私有 = auto()  # private
    静态 = auto()  # static
    特征 = auto()  # trait
    实现 = auto()  # implements
    获取 = auto()  # get (property getter)
    设置 = auto()  # set (property setter)

    # ========================
    # 模块关键字
    # ========================
    导入 = auto()  # import
    导出 = auto()  # export
    作为 = auto()  # as

    # ========================
    # 逻辑编程关键字
    # ========================
    逻辑 = auto()  # logic - 逻辑代码块
    事实 = auto()  # fact - 事实声明
    规则 = auto()  # rule - 规则声明
    查询 = auto()  # query - 查询表达式
    剪枝 = auto()  # cut - 剪枝操作符

    # ========================
    # 并发编程关键字
    # ========================
    异步 = auto()  # async - 异步函数
    等待 = auto()  # await - 等待异步操作
    全部 = auto()  # all - 并发等待所有
    竞速 = auto()  # race - 竞速等待
    并行 = auto()  # parallel - 启动协程
    通道 = auto()  # channel - 通道
    发送 = auto()  # send - 发送数据
    接收 = auto()  # receive - 接收数据
    选择 = auto()  # select - 选择器
    超时 = auto()  # timeout - 超时
    互斥锁 = auto()  # mutex - 互斥锁
    原子整数 = auto()  # atomic_int - 原子整数
    原子布尔 = auto()  # atomic_bool - 原子布尔
    同步 = auto()  # sync - 同步块

    # ========================
    # 缩进控制（由词法分析器生成）
    # ========================
    缩进 = auto()  # INDENT - 缩进增加
    回退 = auto()  # DEDENT - 缩进减少
    换行 = auto()  # NEWLINE

    # ========================
    # 特殊
    # ========================
    文件结束 = auto()  # EOF


@dataclass(frozen=True)
class Token:
    """
    词元：词法分析的最小单位

    属性：
        type   : 词元类型
        value  : 词元的原始值
        line   : 所在行号（从1开始）
        column : 所在列号（从1开始）
    """

    type: TokenType
    value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, 行{self.line}:列{self.column})"


# ========================
# 关键字映射表
# ========================
# 将中文关键字字符串映射到对应的TokenType
KEYWORDS: dict[str, TokenType] = {
    # 按照长度降序排列，确保最长的关键字最先匹配
    "否则如果": TokenType.否则如果,
    "原子整数": TokenType.原子整数,
    "原子布尔": TokenType.原子布尔,
    # OOP
    "运算符": TokenType.运算符,
    "继承自": TokenType.继承自,
    "初始化": TokenType.初始化,
    "本对象": TokenType.本对象,
    "父对象": TokenType.父对象,
    "私有": TokenType.私有,
    "静态": TokenType.静态,
    "特征": TokenType.特征,
    "实现": TokenType.实现,
    "获取": TokenType.获取,
    "设置": TokenType.设置,
    # 并发编程
    "异步": TokenType.异步,
    "等待": TokenType.等待,
    "全部": TokenType.全部,
    "竞速": TokenType.竞速,
    "并行": TokenType.并行,
    "通道": TokenType.通道,
    "发送": TokenType.发送,
    "接收": TokenType.接收,
    "选择": TokenType.选择,
    "超时": TokenType.超时,
    "互斥锁": TokenType.互斥锁,
    "同步": TokenType.同步,
    "运行异步": TokenType.标识符,  # 运行异步是函数名而非关键字
    # OOP
    "类型": TokenType.类型,
    "抽象": TokenType.抽象,
    "枚举": TokenType.枚举,
    # 逻辑编程
    "逻辑": TokenType.逻辑,
    "事实": TokenType.事实,
    "规则": TokenType.规则,
    "查询": TokenType.查询,
    "剪枝": TokenType.剪枝,
    # 控制流
    "定义": TokenType.定义,
    "常量": TokenType.常量,
    "函数": TokenType.函数,
    "返回": TokenType.返回,
    "如果": TokenType.如果,
    "否则": TokenType.否则,
    "当": TokenType.当,
    "遍历": TokenType.遍历,
    "对于": TokenType.对于,
    "在": TokenType.在,
    "从": TokenType.从,
    "到": TokenType.到,
    "步长": TokenType.步长,
    "跳出": TokenType.跳出,
    "默认": TokenType.默认,
    "继续": TokenType.继续,
    "匹配": TokenType.匹配,
    "情况": TokenType.情况,
    "产出": TokenType.产出,
    # 错误处理
    "尝试": TokenType.尝试,
    "捕获": TokenType.捕获,
    "最终": TokenType.最终,
    "抛出": TokenType.抛出,
    "断言": TokenType.断言,
    # 逻辑运算
    "并且": TokenType.并且,
    "或者": TokenType.或者,
    "不是": TokenType.不是,
    "不在": TokenType.不在,
    # 基础类型
    "真": TokenType.真,
    "假": TokenType.假,
    "空": TokenType.空,
    # 模块
    "导入": TokenType.导入,
    "导出": TokenType.导出,
    "作为": TokenType.作为,
}
