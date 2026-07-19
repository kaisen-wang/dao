"""
内置宏定义
==========

提供道语言的内置宏，这些宏在宏展开器初始化时自动注册。

内置宏列表：
- @除非：条件取反宏（除非 条件 → 如果 不是 条件）
- @计时：执行计时宏（自动包裹计时逻辑）
- @重试：重试宏（失败时自动重试指定次数）
- @日志：日志宏（自动添加函数进入/退出日志）
- @缓存：缓存宏（函数结果缓存）
- @延迟：延迟计算宏

每个内置宏通过构造对应的 AST 节点来实现展开逻辑，
无需通过词法/语法分析器，直接在 Python 层面构建 AST。
"""

import logging
from typing import List

from ..ast_nodes import (
    Assignment,
    BinaryOp,
    BlockExpr,
    BooleanLiteral,
    ConditionalExpr,
    Expression,
    ExpressionStmt,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStmt,
    IndexAccess,
    ListLiteral,
    MacroDefinition,
    MemberAccess,
    NullLiteral,
    NumberLiteral,
    QuoteBlock,
    ReturnStmt,
    Statement,
    StringLiteral,
    ThrowStmt,
    TryStmt,
    UnaryOp,
    VariableDecl,
    WhileStmt,
)
from .registry import MacroInfo, MacroRegistry

logger = logging.getLogger('dao.macros')


def register_builtin_macros(registry: MacroRegistry):
    """
    向宏注册表注册所有内置宏

    Args:
        registry: 宏注册表实例
    """
    _register_除非(registry)
    _register_计时(registry)
    _register_重试(registry)
    _register_日志(registry)
    _register_缓存(registry)
    _register_延迟(registry)
    logger.debug("已注册 %d 个内置宏", 6)


def _make_macro_info(
    name: str,
    parameters: List[str],
    body: Expression,
    source_code: str = "",
) -> MacroInfo:
    """创建内置宏的 MacroInfo 对象"""
    return MacroInfo(
        name=name,
        parameters=parameters,
        body=body,
        line=0,
        column=0,
        source_code=source_code,
        scope_depth=0,
        is_pattern_macro=False,
    )


# ============================================================
# @除非 宏
# ============================================================

def _register_除非(registry: MacroRegistry):
    """
    注册 @除非 内置宏

    用法：!除非(条件) 代码块
    展开：如果 不是 条件 代码块

    示例：
        !除非(温度 > 20)
            打印("天气冷")
        →
        如果 不是 (温度 > 20)
            打印("天气冷")
    """
    body = QuoteBlock(body=[
        IfStmt(
            condition=UnaryOp(
                operator="不是",
                operand=Identifier(name="条件"),
            ),
            body=[ExpressionStmt(expression=Identifier(name="代码块"))],
        )
    ])
    info = _make_macro_info("除非", ["条件", "代码块"], body, "内置宏: 除非(条件, 代码块)")
    _safe_register(registry, info)


# ============================================================
# @计时 宏
# ============================================================

def _register_计时(registry: MacroRegistry):
    """
    注册 @计时 内置宏

    用法：!计时(代码块) 或 !计时(标签, 代码块)
    展开：记录代码块执行前后的时间差并打印

    示例：
        !计时("排序")
            排序(数据)
        →
        设 _计时开始 = 时间()
        设 _计时 结果 = 排序(数据)
        设 _计时 结束 = 时间()
        打印("排序 耗时:", _计时 结束 - _计时 开始, "秒")
        _计时 结果
    """
    body = QuoteBlock(body=[
        # 设 _计时开始 = 时间戳()
        VariableDecl(
            name="_计时开始",
            value=FunctionCall(
                callee=Identifier(name="时间戳"),
            ),
        ),
        # 设 _计时结果 = 代码块
        VariableDecl(
            name="_计时结果",
            value=Identifier(name="代码块"),
        ),
        # 设 _计时结束 = 时间戳()
        VariableDecl(
            name="_计时结束",
            value=FunctionCall(
                callee=Identifier(name="时间戳"),
            ),
        ),
        # 打印(标签, "耗时:", _计时结束 - _计时开始, "秒")
        ExpressionStmt(
            expression=FunctionCall(
                callee=Identifier(name="打印"),
                arguments=[
                    Identifier(name="标签"),
                    StringLiteral(value="耗时:"),
                    BinaryOp(
                        left=Identifier(name="_计时结束"),
                        operator="-",
                        right=Identifier(name="_计时开始"),
                    ),
                    StringLiteral(value="秒"),
                ],
            ),
        ),
        # 返回 _计时结果
        ReturnStmt(value=Identifier(name="_计时结果")),
    ])
    info = _make_macro_info("计时", ["标签=\"\"", "代码块"], body, "内置宏: 计时(标签, 代码块)")
    _safe_register(registry, info)


# ============================================================
# @重试 宏
# ============================================================

def _register_重试(registry: MacroRegistry):
    """
    注册 @重试 内置宏

    用法：!重试(次数, 代码块) 或 !重试(次数, 间隔, 代码块)
    展开：尝试执行代码块，失败时重试指定次数

    示例：
        !重试(3)
            连接服务器()
        →
        设 _重试次数 = 0
        设 _重试结果 = 空
        当 _重试次数 < 3
            尝试
                _重试结果 = 连接服务器()
                跳出
            捕获 _重试错误
                _重试次数 = _重试次数 + 1
                如果 _重试次数 >= 3
                    抛出 _重试错误
        _重试结果
    """
    body = QuoteBlock(body=[
        # 设 _重试次数 = 0
        VariableDecl(
            name="_重试次数",
            value=NumberLiteral(value=0),
        ),
        # 设 _重试结果 = 空
        VariableDecl(
            name="_重试结果",
            value=NullLiteral(),
        ),
        # 当 _重试次数 < 次数
        WhileStmt(
            condition=BinaryOp(
                left=Identifier(name="_重试次数"),
                operator="<",
                right=Identifier(name="次数"),
            ),
            body=[
                # 尝试
                TryStmt(
                    try_body=[
                        # _重试结果 = 代码块
                        Assignment(
                            target=Identifier(name="_重试结果"),
                            value=Identifier(name="代码块"),
                        ),
                        # 跳出
                        ReturnStmt(value=Identifier(name="_重试结果")),
                    ],
                    catches=[{
                        "catch_var": "_重试错误",
                        "catch_body": [
                            # _重试次数 = _重试次数 + 1
                            Assignment(
                                target=Identifier(name="_重试次数"),
                                value=BinaryOp(
                                    left=Identifier(name="_重试次数"),
                                    operator="+",
                                    right=NumberLiteral(value=1),
                                ),
                            ),
                            # 如果 _重试次数 >= 次数
                            IfStmt(
                                condition=BinaryOp(
                                    left=Identifier(name="_重试次数"),
                                    operator=">=",
                                    right=Identifier(name="次数"),
                                ),
                                body=[
                                    # 抛出 _重试错误
                                    ExpressionStmt(
                                        expression=FunctionCall(
                                            callee=Identifier(name="抛出"),
                                            arguments=[Identifier(name="_重试错误")],
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    }],
                ),
            ],
        ),
        # 返回 _重试结果
        ReturnStmt(value=Identifier(name="_重试结果")),
    ])
    info = _make_macro_info("重试", ["次数=3", "代码块"], body, "内置宏: 重试(次数, 代码块)")
    _safe_register(registry, info)


# ============================================================
# @日志 宏
# ============================================================

def _register_日志(registry: MacroRegistry):
    """
    注册 @日志 内置宏

    用法：!日志(函数名, 代码块)
    展开：在代码块执行前后添加日志输出

    示例：
        !日志("处理数据")
            处理(数据)
        →
        打印(">>> 进入: 处理数据")
        设 _日志结果 = 处理(数据)
        打印("<<< 退出: 处理数据")
        _日志结果
    """
    body = QuoteBlock(body=[
        # 打印(">>> 进入: 函数名")
        ExpressionStmt(
            expression=FunctionCall(
                callee=Identifier(name="打印"),
                arguments=[
                    BinaryOp(
                        left=StringLiteral(value=">>> 进入: "),
                        operator="+",
                        right=Identifier(name="函数名"),
                    ),
                ],
            ),
        ),
        # 设 _日志结果 = 代码块
        VariableDecl(
            name="_日志结果",
            value=Identifier(name="代码块"),
        ),
        # 打印("<<< 退出: 函数名")
        ExpressionStmt(
            expression=FunctionCall(
                callee=Identifier(name="打印"),
                arguments=[
                    BinaryOp(
                        left=StringLiteral(value="<<< 退出: "),
                        operator="+",
                        right=Identifier(name="函数名"),
                    ),
                ],
            ),
        ),
        # 返回 _日志结果
        ReturnStmt(value=Identifier(name="_日志结果")),
    ])
    info = _make_macro_info("日志", ["函数名", "代码块"], body, "内置宏: 日志(函数名, 代码块)")
    _safe_register(registry, info)


# ============================================================
# @缓存 宏
# ============================================================

def _register_缓存(registry: MacroRegistry):
    """
    注册 @缓存 内置宏

    用法：!缓存(键, 代码块)
    展开：如果缓存中存在键则返回缓存值，否则执行代码块并缓存结果

    示例：
        !缓存(查询键)
            查询数据库(查询键)
        →
        如果 键 在 _缓存表
            返回 _缓存表[键]
        否则
            设 _缓存结果 = 查询数据库(查询键)
            _缓存表[键] = _缓存结果
            返回 _缓存结果
    """
    body = QuoteBlock(body=[
        # 如果 键 在 _缓存表
        IfStmt(
            condition=BinaryOp(
                left=Identifier(name="键"),
                operator="在",
                right=Identifier(name="_缓存表"),
            ),
            body=[
                # 返回 _缓存表[键]
                ReturnStmt(
                    value=IndexAccess(
                        object=Identifier(name="_缓存表"),
                        index=Identifier(name="键"),
                    ),
                ),
            ],
            else_body=[
                # 设 _缓存结果 = 代码块
                VariableDecl(
                    name="_缓存结果",
                    value=Identifier(name="代码块"),
                ),
                # _缓存表[键] = _缓存结果
                Assignment(
                    target=IndexAccess(
                        object=Identifier(name="_缓存表"),
                        index=Identifier(name="键"),
                    ),
                    value=Identifier(name="_缓存结果"),
                ),
                # 返回 _缓存结果
                ReturnStmt(value=Identifier(name="_缓存结果")),
            ],
        ),
    ])
    info = _make_macro_info("缓存", ["键", "代码块"], body, "内置宏: 缓存(键, 代码块)")
    _safe_register(registry, info)


# ============================================================
# @延迟 宏
# ============================================================

def _register_延迟(registry: MacroRegistry):
    """
    注册 @延迟 内置宏

    用法：!延迟(代码块)
    展开：创建一个延迟计算的值，首次访问时才执行

    示例：
        设 值 = !延迟(昂贵计算())
        →
        设 _延迟已计算 = 假
        设 _延迟值 = 空
        如果 不是 _延迟已计算
            _延迟值 = 昂贵计算()
            _延迟已计算 = 真
        _延迟值
    """
    body = QuoteBlock(body=[
        # 设 _延迟已计算 = 假
        VariableDecl(
            name="_延迟已计算",
            value=BooleanLiteral(value=False),
        ),
        # 设 _延迟值 = 空
        VariableDecl(
            name="_延迟值",
            value=NullLiteral(),
        ),
        # 如果 不是 _延迟已计算
        IfStmt(
            condition=UnaryOp(
                operator="不是",
                operand=Identifier(name="_延迟已计算"),
            ),
            body=[
                # _延迟值 = 代码块
                Assignment(
                    target=Identifier(name="_延迟值"),
                    value=Identifier(name="代码块"),
                ),
                # _延迟已计算 = 真
                Assignment(
                    target=Identifier(name="_延迟已计算"),
                    value=BooleanLiteral(value=True),
                ),
            ],
        ),
        # _延迟值（作为最后一个表达式语句返回值）
        ExpressionStmt(expression=Identifier(name="_延迟值")),
    ])
    info = _make_macro_info("延迟", ["代码块"], body, "内置宏: 延迟(代码块)")
    _safe_register(registry, info)


# ============================================================
# 辅助函数
# ============================================================

def _safe_register(registry: MacroRegistry, info: MacroInfo):
    """安全注册内置宏，避免与用户定义的宏冲突"""
    if registry.find_macro(info.name) is None:
        if info.name not in registry._macros:
            registry._macros[info.name] = []
        registry._macros[info.name].append(info)
        logger.debug("注册内置宏 '%s'", info.name)
    else:
        logger.debug("内置宏 '%s' 已被用户定义覆盖，跳过注册", info.name)
