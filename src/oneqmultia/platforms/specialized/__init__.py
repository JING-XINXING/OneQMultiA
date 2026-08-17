"""专用平台适配器注册。"""

from oneqmultia.platforms.specialized.chatgpt import ChatGPTAdapter
from oneqmultia.platforms.specialized.deepseek import DeepSeekAdapter
from oneqmultia.platforms.specialized.kimi import KimiAdapter

__all__ = ["ChatGPTAdapter", "DeepSeekAdapter", "KimiAdapter"]
