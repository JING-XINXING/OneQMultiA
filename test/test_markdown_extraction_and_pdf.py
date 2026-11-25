"""v0.3.0：HTML→Markdown 保真，以及中文 PDF 可提取。"""

from io import BytesIO

import pytest
from starlette.testclient import TestClient

from oneqmultia.platforms.generic import _extract_markdown

_FIXTURE = """
<article id="ans">
  <h2>标题</h2>
  <p>查看 <a href="https://example.com/docs">文档</a> 与 <strong>重点</strong></p>
  <pre><code class="language-python">print(1)</code></pre>
  <table>
    <tr><th>A</th><th>B</th></tr>
    <tr><td>1</td><td>2</td></tr>
  </table>
  <span class="katex" data-tex="E=mc^2">E=mc^2</span>
</article>
"""


@pytest.mark.asyncio
async def test_extract_markdown_keeps_code_and_table() -> None:
    """用无头 Chromium 验证代码围栏和表格语法还在。"""
    playwright = pytest.importorskip("playwright.async_api")
    async with playwright.async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"当前环境没有可用的 Chromium：{exc}")
        page = await browser.new_page()
        await page.set_content(_FIXTURE)
        markdown = await _extract_markdown(page.locator("#ans"))
        await browser.close()

    assert "```python" in markdown
    assert "print(1)" in markdown
    assert "| A | B |" in markdown
    assert "| 1 | 2 |" in markdown
    assert "文档" in markdown
    assert "E=mc^2" in markdown


def test_pdf_export_keeps_chinese_text(client: TestClient) -> None:
    """导出的 PDF 应能提取出中文，而不是整页方框。"""
    pypdf = pytest.importorskip("pypdf")
    title = "中文会话犇"
    question = "请用中文说明犇这个字"
    sid = client.post("/api/sessions", json={"title": title}).json()["id"]
    asked = client.post(
        f"/api/sessions/{sid}/ask",
        json={"question": question, "platform_ids": ["chatgpt"]},
    )
    assert asked.status_code == 200
    exported = client.get(f"/api/sessions/{sid}/export", params={"format": "pdf"})
    assert exported.status_code == 200
    reader = pypdf.PdfReader(BytesIO(exported.content))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    assert "中文" in text
    assert "犇" in text
