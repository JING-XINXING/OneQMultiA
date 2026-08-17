import type { SessionSummary } from "../types/api";

type Props = {
  sessions: SessionSummary[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onRefresh: () => void;
};

/** 历史会话列表：标题即问题摘要，选中后恢复整轮问答。 */
export function SessionHistory({ sessions, currentId, onSelect, onRefresh }: Props) {
  return (
    <div className="bento-card-sm flex min-h-0 flex-1 flex-col space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold tracking-wide text-slate-500">历史会话</h2>
        <button type="button" className="btn-sm text-[10px]" onClick={onRefresh}>
          刷新
        </button>
      </div>
      {sessions.length === 0 ? (
        <p className="py-6 text-center text-xs text-slate-400">还没有历史会话</p>
      ) : (
        <ul className="max-h-[min(56vh,480px)] space-y-1 overflow-y-auto pr-0.5">
          {sessions.map((s) => {
            const count = s.qa_count ?? 0;
            const showPreview = Boolean(s.preview && s.preview !== s.title);
            const active = currentId === s.id;
            return (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => onSelect(s.id)}
                  className={`w-full rounded-xl px-3 py-2.5 text-left text-xs transition-all duration-150 ${
                    active
                      ? "border border-blue-200 bg-blue-50 text-accent-dim shadow-sm"
                      : "border border-transparent text-slate-600 hover:bg-surface-hover"
                  }`}
                >
                  <div className="truncate font-medium" title={s.title}>
                    {s.title || "未命名"}
                  </div>
                  {showPreview && (
                    <div className="mt-0.5 truncate text-[10px] text-slate-400" title={s.preview}>
                      {s.preview}
                    </div>
                  )}
                  <div className="mt-1 text-[10px] text-slate-400">
                    {count > 0 ? `${count} 问 · ` : ""}
                    {new Date(s.updated_at).toLocaleString()}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
