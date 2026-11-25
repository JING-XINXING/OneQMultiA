"""平台适配器基类与运行时配置视图。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

from playwright.async_api import Page

# 流式进度：由 WebSocket 等注入，payload 需可 JSON 序列化（datetime 在外层转换）
ProgressEmit = Optional[Callable[[Dict[str, Any]], Awaitable[None]]]

from oneqmultia.storage.models import PlatformConfigRow


@dataclass
class PlatformRuntimeConfig:
    """适配器使用的不可变配置快照。"""

    id: str
    display_name: str
    url: str
    timeout_seconds: int
    selectors: Dict[str, Any]
    interaction: Dict[str, Any]
    adapter_type: str
    adapter_module: str
    # web_only | api_only | web_with_api_fallback
    execution_mode: str = "web_only"
    api_provider: str = ""
    api_model: str = ""

    @classmethod
    def from_row(cls, row: PlatformConfigRow) -> "PlatformRuntimeConfig":
        return cls(
            id=row.id,
            display_name=row.display_name,
            url=row.url,
            timeout_seconds=row.timeout_seconds,
            selectors=dict(row.selectors or {}),
            interaction=dict(row.interaction or {}),
            adapter_type=row.adapter_type or "generic",
            adapter_module=row.adapter_module or "",
            execution_mode=getattr(row, "execution_mode", None) or "web_only",
            api_provider=getattr(row, "api_provider", None) or "",
            api_model=getattr(row, "api_model", None) or "",
        )


@dataclass
class AskTiming:
    """单次问答时间指标。"""

    request_sent_at: Optional[datetime] = None
    first_token_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AskResult:
    """单平台问答结果（写入 DB 前使用）。"""

    platform_id: str
    platform_name: str
    platform_url: str
    answer_text: str
    status: str  # success | error | timeout | skipped
    error_message: str
    timing: AskTiming
    tokens_count: Optional[int] = None

    @property
    def response_duration_ms(self) -> Optional[int]:
        if self.timing.request_sent_at and self.timing.completed_at:
            delta = self.timing.completed_at - self.timing.request_sent_at
            return int(delta.total_seconds() * 1000)
        return None


class BasePlatformAdapter(ABC):
    """所有平台适配器的抽象基类。"""

    def __init__(self, config: PlatformRuntimeConfig) -> None:
        self.config = config

    @property
    def platform_id(self) -> str:
        return self.config.id

    @abstractmethod
    async def ask(
        self,
        page: Page,
        question: str,
        emit: ProgressEmit = None,
    ) -> AskResult:
        """在给定 Page 上提问并返回答案；emit 用于轮询到的新文本片段（answer_delta）。"""

    async def health_check(self, page: Page) -> bool:
        """默认：当前 URL 含配置域名即视为可用。"""
        try:
            u = page.url
            base = self.config.url.split("://", 1)[-1].split("/")[0]
            return base in u
        except Exception:
            return False
