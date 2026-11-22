"""内置大模型 Provider。

导入本包会触发各 Provider 的自注册（通过 ``register_provider`` 装饰器）。
各 Provider 独立实现，互不依赖；新增后端只需在此处增加一行导入。
"""

from . import (
    anthropic,  # noqa: F401
    ollama,  # noqa: F401
    openai,  # noqa: F401
)
