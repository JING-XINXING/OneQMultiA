"""平台适配器。"""

from oneqmultia.platforms.base import (
    AskResult,
    BasePlatformAdapter,
    PlatformRuntimeConfig,
    ProgressEmit,
)
from oneqmultia.platforms.generic import GenericAdapter, build_adapter

__all__ = [
    "AskResult",
    "BasePlatformAdapter",
    "PlatformRuntimeConfig",
    "ProgressEmit",
    "GenericAdapter",
    "build_adapter",
]
