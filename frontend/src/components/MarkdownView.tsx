import { useState, type ReactNode } from "react";

type Props = {
  text: string;
  className?: string;
};

function renderInline(source: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let index = 0;
  const pushText = (chunk: string) => {
    if (!chunk) return;
    nodes.push(<span key={`${keyPrefix}-t-${index}`}>{chunk}</span>);
    index += 1;
  };
  while ((match = pattern.exec(source))) {
    pushText(source.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("`")) {
      nodes.push(
        <code key={`${keyPrefix}-c-${index}`} className="rounded bg-slate-100 px-1 py-0.5 text-[0.92em] text-slate-800">
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith("**")) {
      nodes.push(<strong key={`${keyPrefix}-b-${index}`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("*")) {
      nodes.push(<em key={`${keyPrefix}-i-${index}`}>{token.slice(1, -1)}</em>);
    } else {
      const linked = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linked) {
        nodes.push(
          <a key={`${keyPrefix}-a-${index}`} href={linked[2]} target="_blank" rel="noreferrer" className="text-accent underline">
            {linked[1]}
          </a>
        );
      }
    }
    index += 1;
    last = match.index + token.length;
  }
  pushText(source.slice(last));
  return nodes;
}

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="my-2 overflow-hidden rounded-xl border border-slate-200 bg-slate-950 text-slate-100">
      <div className="flex items-center justify-between px-3 py-1.5 text-[10px] text-slate-400">
        <span>{lang || "code"}</span>
        <button
          type="button"
          className="rounded-md bg-slate-800 px-2 py-0.5 text-slate-200"
          onClick={() => {
            void navigator.clipboard.writeText(code).then(() => {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1200);
            });
          }}
        >
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre className="overflow-x-auto px-3 pb-3 text-[12px] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function MarkdownTable({ rows }: { rows: string[][] }) {
  if (!rows.length) return null;
  const [head, ...body] = rows;
  return (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr>
            {head.map((cell, index) => (
              <th key={index} className="border border-slate-200 bg-slate-50 px-2 py-1 font-semibold">
                {renderInline(cell, `th-${index}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, index) => (
                <td key={index} className="border border-slate-200 px-2 py-1 align-top">
                  {renderInline(cell, `td-${rowIndex}-${index}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function parseTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function isTableSep(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

/** 轻量 GFM 渲染：转义原文，不把 HTML 当节点插入。 */
export function MarkdownView({ text, className }: Props) {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let blockIndex = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) {
        buf.push(lines[i]);
        i += 1;
      }
      blocks.push(<CodeBlock key={`code-${blockIndex}`} code={buf.join("\n")} lang={lang} />);
      blockIndex += 1;
      i += 1;
      continue;
    }
    if (line.includes("|") && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const rows = [parseTableRow(line)];
      i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        rows.push(parseTableRow(lines[i]));
        i += 1;
      }
      blocks.push(<MarkdownTable key={`table-${blockIndex}`} rows={rows} />);
      blockIndex += 1;
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      const Tag = (`h${Math.min(level, 4)}` as "h1" | "h2" | "h3" | "h4");
      blocks.push(
        <Tag key={`h-${blockIndex}`} className="mt-2 font-semibold text-slate-800">
          {renderInline(heading[2], `h-${blockIndex}`)}
        </Tag>
      );
      blockIndex += 1;
      i += 1;
      continue;
    }
    if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      const ordered = /^\s*\d+\.\s+/.test(line);
      while (i < lines.length && (/^\s*[-*]\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]))) {
        items.push(lines[i].replace(/^\s*(?:[-*]|\d+\.)\s+/, ""));
        i += 1;
      }
      const ListTag = ordered ? "ol" : "ul";
      blocks.push(
        <ListTag key={`list-${blockIndex}`} className={`my-1 pl-5 ${ordered ? "list-decimal" : "list-disc"}`}>
          {items.map((item, index) => (
            <li key={index}>{renderInline(item, `li-${blockIndex}-${index}`)}</li>
          ))}
        </ListTag>
      );
      blockIndex += 1;
      continue;
    }
    const para: string[] = [line];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].startsWith("```") &&
      !lines[i].startsWith("#") &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i])
    ) {
      para.push(lines[i]);
      i += 1;
    }
    blocks.push(
      <p key={`p-${blockIndex}`} className="my-1 whitespace-pre-wrap break-words">
        {renderInline(para.join("\n"), `p-${blockIndex}`)}
      </p>
    );
    blockIndex += 1;
  }

  if (!blocks.length) {
    return <p className={className}>{text || ""}</p>;
  }
  return <div className={className}>{blocks}</div>;
}
