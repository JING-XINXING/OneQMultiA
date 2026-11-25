"""HTTP 请求/响应模型。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from oneqmultia.platform_manager.url_validator import validate_url_format


class AskBody(BaseModel):
    """提问请求体。"""

    question: str = Field(..., min_length=1, max_length=32000)
    platform_ids: Optional[List[str]] = Field(
        default=None,
        description="若指定则仅向这些已启用平台提问；默认全部启用平台",
    )


class SessionCreateBody(BaseModel):
    title: str = ""


class LlmChoiceBody(BaseModel):
    """用户选择的最优答案生成模型。"""

    provider: Optional[str] = None
    model: Optional[str] = None


class PlatformCreateBody(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    display_name: str
    url: str
    icon: str = ""
    group: str = "custom"
    enabled: bool = True
    sort_order: int = 0
    timeout_seconds: int = 120
    selectors: Dict[str, Any] = Field(default_factory=dict)
    interaction: Dict[str, Any] = Field(default_factory=dict)
    adapter_type: str = "generic"
    adapter_module: str = ""
    expected_host: str = ""

    @field_validator("url")
    @classmethod
    def _url_must_be_http(cls, v: str) -> str:
        result = validate_url_format(v)
        if not result.ok:
            raise ValueError(result.message)
        return v.strip()


class PlatformPatchBody(BaseModel):
    display_name: Optional[str] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    group: Optional[str] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None
    timeout_seconds: Optional[int] = None
    selectors: Optional[Dict[str, Any]] = None
    interaction: Optional[Dict[str, Any]] = None
    adapter_type: Optional[str] = None
    adapter_module: Optional[str] = None
    expected_host: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _url_must_be_http(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        result = validate_url_format(v)
        if not result.ok:
            raise ValueError(result.message)
        return v.strip()


class PlatformBatchEnableBody(BaseModel):
    """批量启用/禁用平台。"""

    platform_ids: List[str] = Field(..., min_length=1)
    enabled: bool


class PlatformImportBody(BaseModel):
    """JSON 数组导入平台配置（全量替换）。"""

    platforms: List[Dict[str, Any]] = Field(..., min_length=1)


class PlatformOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    display_name: str
    url: str
    icon: str
    group: str
    enabled: bool
    sort_order: int
    timeout_seconds: int
    selectors: Dict[str, Any]
    interaction: Dict[str, Any]
    adapter_type: str
    adapter_module: str
    health_status: str
    health_checked_at: Optional[datetime] = None
    login_status: str = "unknown"
    login_checked_at: Optional[datetime] = None
    login_message: str = ""
    url_status: str = "unknown"
    url_checked_at: Optional[datetime] = None
    url_check_message: str = ""
    expected_host: str = ""


class AnswerOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    platform_id: str
    platform_name: str
    platform_url: str
    answer_text: str
    request_sent_at: Optional[datetime] = None
    first_token_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    response_duration_ms: Optional[int] = None
    status: str
    error_message: str
    tokens_count: Optional[int] = None


class QAPairOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    question: str
    question_time: datetime
    answers: List[AnswerOut] = []
    # 分享页需要展示已缓存的最优解；没有缓存时为空
    optimal_answer: Optional[Dict[str, Any]] = None


class SessionSummary(BaseModel):
    """会话列表项（不含问答明细，避免列表接口过重）。"""

    model_config = {"from_attributes": True}

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    # 首问摘要 + 轮次，便于历史列表区分主题
    preview: str = ""
    qa_count: int = 0


class SessionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    qa_pairs: List[QAPairOut] = []


class AskResponse(BaseModel):
    qa_pair_id: str
    summary: Dict[str, Any]
    answers: List[AnswerOut]
