"""平台注册表：从数据库加载适配器，支持热更新。"""

from typing import List, Optional

from sqlalchemy.orm import Session

from oneqmultia.platform_manager import crud
from oneqmultia.platforms.base import BasePlatformAdapter
from oneqmultia.platforms.generic import build_adapter
from oneqmultia.storage.models import PlatformConfigRow


class PlatformRegistry:
    """
    运行时平台注册表。
    当前无内存缓存，每次调用从 DB 读取；后续可加 TTL 缓存。
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_enabled_rows(self) -> List[PlatformConfigRow]:
        """启用平台的数据库行。"""
        return crud.list_platforms(self._db, enabled_only=True)

    def get_enabled_adapters(self) -> List[BasePlatformAdapter]:
        """构造全部启用平台的适配器实例。"""
        return [build_adapter(r) for r in self.list_enabled_rows()]

    def get_adapter(self, platform_id: str) -> Optional[BasePlatformAdapter]:
        """单个平台适配器。"""
        row = crud.get_platform(self._db, platform_id)
        if row is None or not row.enabled:
            return None
        return build_adapter(row)

    def reload(self, platform_id: str) -> None:
        """占位：热更新时使前端重新拉列表即可；此处预留缓存失效钩子。"""
        del platform_id  # 无缓存时无需操作

    def invalidate_all(self) -> None:
        """占位：批量失效缓存。"""
