"""pytest 夹具：在导入 oneqmultia 之前指向临时 SQLite。"""

import os
import tempfile

# 必须在首次 import oneqmultia.storage.database 之前执行
_fd, _TEST_DB = tempfile.mkstemp(suffix="oneqmultia-test.db")
os.close(_fd)
os.environ["ONEQMULTIA_DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
# 覆盖 .env 中的 CDP，避免测试误连本机调试 Chrome
os.environ["ONEQMULTIA_CDP_URL"] = ""
# 测试默认不走真实 LLM，避免读取项目 .env 里的 Key
os.environ["ONEQMULTIA_DEEPSEEK_API_KEY"] = ""
os.environ["ONEQMULTIA_KIMI_API_KEY"] = ""
os.environ["ONEQMULTIA_QWEN_API_KEY"] = ""
os.environ["ONEQMULTIA_GLM_API_KEY"] = ""
os.environ["ONEQMULTIA_MINIMAX_API_KEY"] = ""
os.environ["ONEQMULTIA_DOUBAO_API_KEY"] = ""
os.environ["ONEQMULTIA_LONGCAT_API_KEY"] = ""
os.environ["ONEQMULTIA_MIMO_API_KEY"] = ""
os.environ["ONEQMULTIA_LLM_API_KEY"] = ""
os.environ["ONEQMULTIA_LLM_PROVIDER"] = "auto"

import pytest
from starlette.testclient import TestClient

from oneqmultia.main import app


@pytest.fixture()
def client() -> TestClient:
    """同步 TestClient，自动执行 FastAPI lifespan（建表 + 种子）。"""
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus) -> None:
    try:
        os.unlink(_TEST_DB)
    except OSError:
        pass
