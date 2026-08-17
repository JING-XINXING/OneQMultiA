import { useState } from "react";
import { friendlyError } from "../lib/friendlyError";
import { TimingBadge } from "./TimingBadge";
import type { PlatformAnswer } from "../types/api";

type Props = {
  answer: PlatformAnswer;
  preview?: string;
  onCancel?: () => void;
};

const statusColor: Record<string, string> = {
  success: "border-l-status-success",
  error: "border-l-status-error",
  timeout: "border-l-status-warning",
  skipped: "border-l-slate-300",
  pending: "border-l-accent",
  cancelled: "border-l-rose-400",
};

/** 单平台回答卡片：成功展示正文，失败展示可读说明。 */
export function AnswerCard({ answer, preview, onCancel }: Props) {
  const [expanded, setExpanded] = useState(false);
  const text = preview ?? answer.answer_text;
  const pending = answer.status === "pending";
  const failed = ["error", "timeout", "cancelled", "skipped"].includes(answer.status);
  const long = (text || "").length > 360;
  const shown = !expanded && long ? `${text.slice(0, 360)}…` : text;
  const err = answer.error_message ? friendlyError(answer.error_message) : null;

  return (
    <article className={`bento-card border-l-[3px] ${statusColor[answer.status] || statusColor.skipped} animate-slide-up`}>
      <header className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="platform-avatar">{answer.platform_name.charAt(0).toUpperCase()}</div>
          <h3 className="font-semibold text-sm text-slate-800 truncate">{answer.platform_name}</h3>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {pending && onCancel && (
            <button type="button" className="btn-sm text-[10px] text-rose-600" onClick={onCancel}>
              停止
            </button>
          )}
          <TimingBadge durationMs={answer.response_duration_ms} status={answer.status} />
        </div>
      </header>
      {err && failed && (
        <div className="mb-2 rounded-xl bg-rose-50 px-3 py-2">
          <p className="text-xs font-medium text-rose-700">{err.title}</p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-rose-600/80">{err.hint}</p>
        </div>
      )}
      {!failed && (
        <div className="text-sm leading-relaxed whitespace-pre-wrap break-words text-slate-600">
          {shown || (answer.status === "success" ? "（空回答）" : "…")}
        </div>
      )}
      {failed && text && answer.status === "timeout" && (
        <div className="text-sm leading-relaxed whitespace-pre-wrap break-words text-slate-500">{shown}</div>
      )}
      {long && !failed && (
        <button type="button" className="mt-2 text-[11px] font-medium text-accent" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "收起" : "展开全文"}
        </button>
      )}
    </article>
  );
}
