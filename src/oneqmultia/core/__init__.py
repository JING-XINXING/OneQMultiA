"""核心业务：注册表、调度、会话。"""

from oneqmultia.core.aggregator import summarize_results
from oneqmultia.core.dispatcher import dispatch_to_adapters, persist_answers
from oneqmultia.core.platform_registry import PlatformRegistry
from oneqmultia.core.session_manager import add_qa_pair, create_session, get_session, load_session_with_qa

__all__ = [
    "PlatformRegistry",
    "dispatch_to_adapters",
    "persist_answers",
    "summarize_results",
    "create_session",
    "get_session",
    "add_qa_pair",
    "load_session_with_qa",
]
