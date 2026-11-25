import { useState } from "react";
import { MarkdownView } from "./MarkdownView";
import type { LlmStatus, OptimalAnswer as OptimalAnswerData } from "../types/api";

type Props = {
  data: OptimalAnswerData | null | undefined;
  loading?: boolean;
  asking?: boolean;
  llmStatus?: LlmStatus | null;
  onRegenerate?: () => void;
};

/** 多平台回答经大模型重写后的最优解；无 Key 时展示本地整理结果。 */
export function OptimalAnswer({ data, loading, asking, llmStatus, onRegenerate }: Props) {
  const [copied, setCopied] = useState(false);
  const ready = Boolean(data?.text);
  const fromLlm = data?.method === "llm";

  async function copyText() {
    if (!data?.text) return;
    await navigator.clipboard.writeText(data.text).catch(() => {});
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  if (asking) {
    return (
      <section className="optimal-card">
        <p className="section-kicker">最优答案</p>
        <h2 className="optimal-title">正在汇集各平台观点</h2>
        <p className="mt-2 text-sm text-amber-900/70">全部完成后，会据此重写一份完整最优解。</p>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="optimal-card">
        <p className="section-kicker">最优答案</p>
        <h2 className="optimal-title">
          {llmStatus?.configured ? `正在用 ${llmStatus.label || "大模型"} 重写` : "正在整理最优答案"}
        </h2>
        <div className="mt-3 h-20 animate-pulse rounded-xl bg-amber-100/70" />
      </section>
    );
  }

  if (!ready) {
    return (
      <section className="optimal-card">
        <p className="section-kicker">最优答案</p>
        <h2 className="optimal-title">还没有可整理的回答</h2>
        <p className="mt-2 text-sm leading-relaxed text-amber-900/70">
          至少需要一个成功回答。配置 DeepSeek / Kimi 的 API Key 后，会把各家回答重写成一篇完整答案。
        </p>
      </section>
    );
  }

  const sourceLabel = fromLlm
    ? `${data?.provider_label || "大模型"} 重写`
    : llmStatus?.configured
      ? "本地整理（可重新生成）"
      : "本地整理";

  return (
    <section className="optimal-card animate-slide-up">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="section-kicker">最优答案</p>
          <h2 className="optimal-title mt-1">综合重写后的推荐解答</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="badge-warning">{sourceLabel}</span>
          <span className="badge-info">{(data?.sources ?? []).length} 个来源</span>
          {onRegenerate && (
            <button type="button" className="btn-sm" onClick={onRegenerate}>
              重新生成
            </button>
          )}
          <button type="button" className="btn-sm" onClick={() => void copyText()}>
            {copied ? "已复制" : "复制答案"}
          </button>
        </div>
      </div>

      {data?.summary && fromLlm && (
        <p className="mt-3 text-sm font-medium leading-relaxed text-amber-950/80">{data.summary}</p>
      )}

      <div className="optimal-body mt-4">
        <MarkdownView text={data?.text || ""} />
      </div>

      {!fromLlm && !llmStatus?.configured && (
        <p className="mt-3 text-[11px] leading-relaxed text-amber-900/60">
          在项目根目录 .env 填写 ONEQMULTIA_DEEPSEEK_API_KEY 或 ONEQMULTIA_KIMI_API_KEY 后重启服务，即可用大模型重写完整答案。
        </p>
      )}

      <footer className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-amber-200/80 pt-3">
        <p className="text-xs leading-relaxed text-amber-900/70">{data?.rationale}</p>
        {data?.recommended_source && (
          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-amber-900">
            参考原文 · {data.recommended_source.platform_name}
          </span>
        )}
      </footer>
    </section>
  );
}
