type Props = {
  sessionId: string | null;
  onShare?: (url: string) => void;
};

const FORMATS: { id: string; label: string }[] = [
  { id: "md", label: "Markdown" },
  { id: "txt", label: "文本" },
  { id: "html", label: "网页" },
  { id: "pdf", label: "PDF" },
  { id: "docx", label: "Word" },
];

/** 导出会话（含最优答案）并复制分享链接。 */
export function ExportMenu({ sessionId, onShare }: Props) {
  if (!sessionId) return null;

  async function share() {
    const r = await fetch(`/api/sessions/${sessionId}/share`, { method: "POST" });
    if (r.ok) {
      const j = await r.json();
      const url = `${window.location.origin}${j.url_path}`;
      onShare?.(url);
      await navigator.clipboard.writeText(url).catch(() => {});
    }
  }

  return (
    <div className="bento-card-sm space-y-2.5">
      <div>
        <h2 className="text-xs font-semibold tracking-wide text-slate-500">导出与分享</h2>
        <p className="mt-0.5 text-[10px] text-slate-400">导出内容已包含整理后的最优答案</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {FORMATS.map((fmt) => (
          <a
            key={fmt.id}
            href={`/api/sessions/${sessionId}/export?format=${fmt.id}`}
            target="_blank"
            rel="noreferrer"
            className="btn-sm text-[10px]"
          >
            {fmt.label}
          </a>
        ))}
      </div>
      <button type="button" className="btn-ghost w-full py-2 text-xs" onClick={() => void share()}>
        复制分享链接
      </button>
    </div>
  );
}
