import { useState } from "react";
import type { CompareResult } from "../types/api";

type Props = {
  data: CompareResult | null;
  loading?: boolean;
};

type Pane = "speed" | "length" | "similar" | "diff";

/** 产品化对比面板：速度、篇幅、共识，技术 diff 默认收起。 */
export function AnswerCompare({ data, loading }: Props) {
  const [pane, setPane] = useState<Pane>("speed");
  const [showDiff, setShowDiff] = useState(false);

  if (loading) {
    return (
      <div className="bento-card text-center py-8">
        <span className="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin inline-block" />
        <p className="text-xs text-slate-500 mt-2">正在对比各平台回答…</p>
      </div>
    );
  }
  if (!data || data.compared_count < 1) {
    return (
      <div className="bento-card text-center py-8">
        <p className="text-sm font-medium text-slate-600">暂无可对比的成功回答</p>
        <p className="mt-1 text-xs text-slate-400">成功回答达到 2 个后，这里会显示速度与观点差异。</p>
      </div>
    );
  }

  const maxDuration = Math.max(...data.duration_ranking.map((item) => item.duration_ms || 0), 1);
  const maxChars = Math.max(...data.lengths.map((item) => item.char_count), 1);
  const tabs: { id: Pane; label: string }[] = [
    { id: "speed", label: "响应速度" },
    { id: "length", label: "回答篇幅" },
    { id: "similar", label: "观点接近度" },
    { id: "diff", label: "文本差异" },
  ];

  return (
    <div className="bento-card space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="section-kicker">对比分析</p>
          <h2 className="mt-1 text-sm font-semibold text-slate-800">各助手表现一览</h2>
        </div>
        <span className="badge-info">{data.compared_count} 个有效回答</span>
      </div>

      <div className="view-tab-bar" role="tablist" aria-label="对比维度">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={pane === tab.id}
            className={pane === tab.id ? "view-tab is-active" : "view-tab"}
            onClick={() => setPane(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {pane === "speed" && (
        <section className="space-y-2">
          {data.duration_ranking.length === 0 && (
            <p className="text-xs text-slate-400">没有记录到响应时间。</p>
          )}
          {data.duration_ranking.map((item, index) => {
            const pct = item.duration_ms ? (item.duration_ms / maxDuration) * 100 : 0;
            return (
              <div key={item.platform_id} className="flex items-center gap-2 text-xs">
                <span className="w-5 text-right text-slate-400">{index + 1}</span>
                <span className="w-24 truncate text-slate-700">{item.platform_name}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-accent to-sky-400 transition-all duration-500"
                    style={{ width: `${Math.max(8, pct)}%` }}
                  />
                </div>
                <span className="w-12 text-right font-medium text-accent-dim">
                  {item.duration_ms != null ? `${(item.duration_ms / 1000).toFixed(1)}s` : "—"}
                </span>
              </div>
            );
          })}
        </section>
      )}

      {pane === "length" && (
        <section className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {data.lengths.map((item) => (
            <div key={item.platform_id} className="bento-card-sm py-3">
              <div className="text-xs font-medium truncate text-slate-700">{item.platform_name}</div>
              <div className="mt-1 text-lg font-semibold tracking-tight text-slate-900">{item.char_count}</div>
              <div className="text-[10px] text-slate-400">字 · {item.word_count} 词</div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-teal-400/80"
                  style={{ width: `${(item.char_count / maxChars) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </section>
      )}

      {pane === "similar" && (
        <section className="space-y-1.5">
          {data.similarity_matrix.length === 0 && (
            <p className="text-xs text-slate-400">至少两个成功回答才会计算接近度。</p>
          )}
          {data.similarity_matrix.slice(0, 10).map((item, index) => (
            <div key={index} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-[12px]">
              <span className="truncate text-slate-600">
                {item.platform_a} ↔ {item.platform_b}
              </span>
              <span className="ml-3 font-semibold text-teal-700">{(item.similarity * 100).toFixed(0)}%</span>
            </div>
          ))}
        </section>
      )}

      {pane === "diff" && (
        <section className="space-y-2">
          <p className="text-xs text-slate-500">适合排查原文措辞差异，一般阅读请直接看「最优答案」。</p>
          {data.diff_highlights[0] ? (
            <>
              <button type="button" className="btn-sm" onClick={() => setShowDiff((v) => !v)}>
                {showDiff ? "收起差异" : "展开文本差异"}
              </button>
              {showDiff && (
                <pre className="max-h-48 overflow-auto rounded-bento-sm border border-surface-border bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-600">
                  {data.diff_highlights[0].diff_lines.join("\n")}
                </pre>
              )}
            </>
          ) : (
            <p className="text-xs text-slate-400">暂无文本差异。</p>
          )}
        </section>
      )}
    </div>
  );
}
