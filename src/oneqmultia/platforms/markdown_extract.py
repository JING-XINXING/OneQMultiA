"""浏览器 DOM → GitHub Flavored Markdown。

在页面上下文执行，尽量保住代码围栏、表格、列表、链接和公式；
脚本失败时由调用方退回 inner_text。
"""

from __future__ import annotations

# Playwright locator.evaluate 接受函数源码：入参是命中的根节点。
MARKDOWN_EXTRACT_JS = r"""(el) => {
  if (!el) return "";
  const blockTags = new Set(["DIV","P","SECTION","ARTICLE","BLOCKQUOTE","UL","OL","LI","H1","H2","H3","H4","H5","H6","PRE","TABLE","HR","FIGURE"]);

  function textOf(node) {
    return (node && node.textContent ? node.textContent : "").replace(/\u00a0/g, " ");
  }

  function langOf(code) {
    const cls = ((code && code.className) || "") + " " + ((code && code.parentElement && code.parentElement.className) || "");
    const m = cls.match(/language-([\w#+.-]+)/);
    return m ? m[1] : "";
  }

  function isMath(node) {
    if (!node || node.nodeType !== 1) return false;
    const cls = node.classList;
    if (!cls) return false;
    return cls.contains("katex") || cls.contains("katex-display") || cls.contains("MathJax") || cls.contains("math-inline") || cls.contains("math-display");
  }

  function mathOf(node) {
    const ann = node.querySelector && node.querySelector("annotation");
    const tex = (ann && ann.textContent) || node.getAttribute("data-tex") || textOf(node);
    const display = node.classList.contains("katex-display") || node.classList.contains("math-display");
    const body = (tex || "").trim();
    if (!body) return "";
    return display ? "\n$$\n" + body + "\n$$\n" : "$" + body + "$";
  }

  function inline(node) {
    if (!node) return "";
    if (node.nodeType === 3) return node.nodeValue || "";
    if (node.nodeType !== 1) return "";
    if (isMath(node)) return mathOf(node);
    const tag = node.tagName;
    if (tag === "BR") return "\n";
    if (tag === "CODE" && node.parentElement && node.parentElement.tagName !== "PRE") {
      return "`" + textOf(node).trim() + "`";
    }
    const inner = Array.from(node.childNodes).map(inline).join("");
    if (tag === "STRONG" || tag === "B") return "**" + inner.trim() + "**";
    if (tag === "EM" || tag === "I") return "*" + inner.trim() + "*";
    if (tag === "A") {
      const href = node.getAttribute("href") || "";
      const label = inner.trim() || href;
      return href ? "[" + label + "](" + href + ")" : label;
    }
    return inner;
  }

  function tableOf(table) {
    const rows = Array.from(table.querySelectorAll("tr")).map((tr) =>
      Array.from(tr.children).filter((c) => c.tagName === "TH" || c.tagName === "TD").map((c) => inline(c).replace(/\|/g, "\\|").replace(/\n/g, " ").trim())
    ).filter((r) => r.length);
    if (!rows.length) return textOf(table);
    const width = Math.max(...rows.map((r) => r.length));
    const norm = rows.map((r) => {
      const copy = r.slice();
      while (copy.length < width) copy.push("");
      return "| " + copy.join(" | ") + " |";
    });
    const sep = "| " + Array(width).fill("---").join(" | ") + " |";
    return [norm[0], sep, ...norm.slice(1)].join("\n");
  }

  function listOf(list, ordered) {
    const items = Array.from(list.children).filter((c) => c.tagName === "LI");
    return items.map((li, i) => {
      const prefix = ordered ? (i + 1) + ". " : "- ";
      const body = Array.from(li.childNodes).map((n) => {
        if (n.nodeType === 1 && (n.tagName === "UL" || n.tagName === "OL")) return "\n" + listOf(n, n.tagName === "OL");
        if (n.nodeType === 1 && blockTags.has(n.tagName) && n.tagName !== "P") return block(n);
        return inline(n);
      }).join("").trim();
      return prefix + body;
    }).join("\n");
  }

  function block(node) {
    if (!node || node.nodeType !== 1) return inline(node);
    if (isMath(node)) return mathOf(node);
    const tag = node.tagName;
    if (tag === "PRE") {
      const code = node.querySelector("code");
      const lang = langOf(code || node);
      const raw = (code ? code.textContent : node.textContent) || "";
      return "```" + lang + "\n" + raw.replace(/\n$/, "") + "\n```";
    }
    if (tag === "TABLE") return tableOf(node);
    if (tag === "UL") return listOf(node, false);
    if (tag === "OL") return listOf(node, true);
    if (/^H[1-6]$/.test(tag)) {
      const level = Number(tag.slice(1));
      return "#".repeat(level) + " " + inline(node).trim();
    }
    if (tag === "HR") return "---";
    if (tag === "BLOCKQUOTE") {
      return blockChildren(node).split("\n").map((line) => "> " + line).join("\n");
    }
    return blockChildren(node);
  }

  function blockChildren(node) {
    const parts = [];
    node.childNodes.forEach((child) => {
      if (child.nodeType === 3) {
        const t = child.nodeValue || "";
        if (t.trim()) parts.push(t);
        return;
      }
      if (child.nodeType !== 1) return;
      if (blockTags.has(child.tagName) || isMath(child) || child.tagName === "PRE") {
        parts.push(block(child));
      } else {
        const t = inline(child);
        if (t.trim()) parts.push(t);
      }
    });
    return parts.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
  }

  return blockChildren(el).trim();
}"""
