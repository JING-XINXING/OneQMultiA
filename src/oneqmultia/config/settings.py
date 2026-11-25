"""全局配置（环境变量 + 默认值）。"""

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from oneqmultia.paths import env_file_candidates, is_frozen, user_data_dir

# Playwright page.goto 的 wait_until 合法取值
GotoWaitUntil = Literal["load", "domcontentloaded", "networkidle", "commit"]


def _default_database_url() -> str:
    """开发用仓库 data/；安装包用系统用户数据目录，避免写到只读 App bundle。"""
    if is_frozen():
        return f"sqlite:///{(user_data_dir() / 'oneqmultia.db').as_posix()}"
    return "sqlite:///./data/oneqmultia.db"


class Settings(BaseSettings):
    """应用级配置，可通过环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_prefix="ONEQMULTIA_",
        env_file=tuple(str(p) for p in env_file_candidates()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite：开发默认仓库 data/，打包后默认用户数据目录
    database_url: str = Field(default_factory=_default_database_url)
    # 连接已登录 Chrome：chrome --remote-debugging-port=9222
    cdp_url: Optional[str] = None
    api_title: str = "OneQMultiA API"
    api_version: str = "0.4.0"
    # 打开平台首页的最大等待（毫秒）；跨境或弱网可调大，如 120000
    goto_timeout_ms: int = 90000
    # domcontentloaded：常规；commit：首包即继续（适合极慢/挂起在加载条的 SPA，后续 ask 仍可能失败）
    goto_wait_until: GotoWaitUntil = "domcontentloaded"
    # 并发平台数上限，避免全部预置平台同时打开导致资源耗尽
    max_concurrent_platforms: int = 5
    # CDP 断连后自动重连间隔（秒），0 表示禁用
    cdp_reconnect_interval_sec: int = 30

    # 最优答案 LLM：auto 按已填 Key 选择；用户也可在页面指定厂商/模型
    llm_provider: str = "auto"
    deepseek_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    glm_api_key: Optional[str] = None
    minimax_api_key: Optional[str] = None
    doubao_api_key: Optional[str] = None
    longcat_api_key: Optional[str] = None
    mimo_api_key: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_timeout_sec: int = 75
    # 送入模型的全部回答总字数上限，避免超上下文
    llm_max_input_chars: int = 24000

    @field_validator("goto_wait_until", mode="before")
    @classmethod
    def _normalize_goto_wait(cls, v: object) -> str:
        if v is None:
            return "domcontentloaded"
        s = str(v).strip().lower()
        allowed = frozenset({"load", "domcontentloaded", "networkidle", "commit"})
        if s not in allowed:
            raise ValueError(f"goto_wait_until must be one of {sorted(allowed)}")
        return s


def get_data_dir() -> Path:
    """解析 SQLite 文件所在目录，用于确保目录存在。"""
    settings = Settings()
    url = settings.database_url
    if url.startswith("sqlite:///"):
        path_part = url.replace("sqlite:///", "", 1)
        p = Path(path_part)
        if not p.is_absolute():
            # 相对路径：相对 cwd
            p = Path.cwd() / p
        return p.parent
    return Path.cwd() / "data"


def ensure_data_dir() -> None:
    """创建 data 目录（若使用本地 SQLite 文件）。"""
    settings = Settings()
    if settings.database_url.startswith("sqlite:///"):
        get_data_dir().mkdir(parents=True, exist_ok=True)
