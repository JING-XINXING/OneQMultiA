"""v0.4.0：选择器试跑与会话检索。"""

import pytest
from starlette.testclient import TestClient

from oneqmultia.platform_manager.selector_tester import probe_selectors


class _Node:
    def __init__(self, visible: bool, text: str) -> None:
        self.visible = visible
        self.text = text

    async def is_visible(self) -> bool:
        return self.visible

    async def inner_text(self) -> str:
        return self.text


class _Locator:
    def __init__(self, nodes: list[_Node]) -> None:
        self.nodes = nodes

    async def count(self) -> int:
        return len(self.nodes)

    def nth(self, index: int) -> _Node:
        return self.nodes[index]


class _Page:
    def __init__(self) -> None:
        self.map = {
            "textarea": [_Node(True, "")],
            "button.send": [_Node(False, ""), _Node(True, "发送")],
            ".missing": [],
        }

    def locator(self, selector: str) -> _Locator:
        return _Locator(self.map.get(selector, []))


@pytest.mark.asyncio
async def test_probe_selectors_reports_hits_and_misses() -> None:
    report = await probe_selectors(
        _Page(),
        {"input_box": "textarea", "send_button": "button.send", "response_container": ".missing"},
    )
    assert report["input_box"]["ok"] is True
    assert report["input_box"]["visible"] == 1
    assert report["send_button"]["count"] == 2
    assert report["send_button"]["visible"] == 1
    assert report["send_button"]["preview"] == "发送"
    assert report["response_container"]["ok"] is False


def test_selector_route_without_cdp(client: TestClient) -> None:
    response = client.post("/api/platforms/chatgpt/test-selectors", json={"selectors": {"input_box": "textarea"}})
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["fields"]["input_box"]["selector"] == "textarea"


def test_session_rename_pin_search_delete(client: TestClient) -> None:
    created = client.post("/api/sessions", json={"title": "待检索会话"}).json()
    sid = created["id"]
    asked = client.post(
        f"/api/sessions/{sid}/ask",
        json={"question": "请记住 AlphaToken 这个标记", "platform_ids": ["chatgpt"]},
    )
    assert asked.status_code == 200

    renamed = client.patch(f"/api/sessions/{sid}", json={"title": "已重命名", "pinned": True})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "已重命名"
    assert renamed.json()["pinned"] is True

    found = client.get("/api/sessions/search", params={"q": "AlphaToken"})
    assert found.status_code == 200
    assert any(item["id"] == sid for item in found.json())

    deleted = client.delete(f"/api/sessions/{sid}")
    assert deleted.status_code == 200
    missing = client.get(f"/api/sessions/{sid}")
    assert missing.status_code == 404
