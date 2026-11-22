"""道（Dao）编程语言 —— 版本信息单一来源。

所有需要版本号的地方（包元数据、命令行 ``--version``、REPL 横幅、
编辑器插件等）都应从此模块读取，避免版本号多处硬编码导致不一致。
"""

__version__ = "1.1.1"
__author__ = "道语言项目组"

# 供 argparse 的 ``--version`` 与 REPL 横幅共用的中文展示文本。
# 使用函数而非常量，保证调用方始终拿到当前 __version__。
def version_text() -> str:
    """返回供命令行展示的中文版本信息（单行）。"""
    return f"道（Dao）编程语言 v{__version__}"


def banner_text() -> str:
    """返回 REPL 横幅中的版本行。"""
    return f"  道（Dao）编程语言 v{__version__}"
