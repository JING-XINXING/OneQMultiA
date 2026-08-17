"""种子数据与平台注册表测试。"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from oneqmultia.core.platform_registry import PlatformRegistry
from oneqmultia.platform_manager.seed import load_yaml_platforms, seed_platforms_if_empty
from oneqmultia.storage.models import Base, PlatformConfigRow


def test_load_yaml_has_23_platforms() -> None:
    items = load_yaml_platforms()
    assert len(items) == 23
    ids = {x["id"] for x in items}
    assert "chatgpt" in ids
    assert "coze" in ids
    assert "genspark" in ids


def test_genspark_yaml_selectors() -> None:
    """Genspark 预置项必须指向官网并带上首页实测选择器。"""
    items = {x["id"]: x for x in load_yaml_platforms()}
    row = items["genspark"]
    assert row["url"] == "https://www.genspark.ai/"
    assert row["group"] == "international"
    assert row["adapter_type"] == "generic"
    assert "textarea.search-input" in row["selectors"]["input_box"]
    assert ".enter-icon" in row["selectors"]["send_button"]
    assert row["interaction"]["send_method"] == "enter"


@pytest.fixture()
def fresh_memory_db():
    """独立内存库。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_seed_inserts_platforms(fresh_memory_db) -> None:
    n = seed_platforms_if_empty(fresh_memory_db)
    assert n == 23
    n2 = seed_platforms_if_empty(fresh_memory_db)
    assert n2 == 0
    rows = list(fresh_memory_db.scalars(select(PlatformConfigRow)).all())
    assert len(rows) == 23
    assert any(r.id == "genspark" for r in rows)


def test_registry_enabled_adapters(fresh_memory_db) -> None:
    seed_platforms_if_empty(fresh_memory_db)
    reg = PlatformRegistry(fresh_memory_db)
    adapters = reg.get_enabled_adapters()
    assert len(adapters) == 23
    assert all(a.platform_id for a in adapters)
    assert any(a.platform_id == "genspark" for a in adapters)
