import { AnswerCard } from "./AnswerCard";
import type { PlatformAnswer } from "../types/api";

type Props = {
  answers: PlatformAnswer[];
  previews?: Record<string, string>;
  columns?: number;
  onCancelPlatform?: (platformId: string) => void;
};

/** 各平台回答网格；空态引导用户发出第一问。 */
export function AnswerGrid({ answers, previews = {}, columns = 3, onCancelPlatform }: Props) {
  if (!answers.length) {
    return (
      <div className="bento-card flex min-h-44 flex-col items-center justify-center px-6 text-center">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent text-lg font-bold text-white shadow-glow">
          Q
        </div>
        <p className="text-base font-semibold text-slate-800">一个问题，多种视角</p>
        <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-slate-500">
          选择助手后发送问题。回答齐了会自动整理「最优答案」，方便直接采用或继续追问。
        </p>
      </div>
    );
  }

  const sorted = [...answers].sort((a, b) => {
    const order = (s: string) => (s === "success" ? 0 : s === "pending" ? 1 : s === "timeout" ? 2 : 3);
    return order(a.status) - order(b.status) || a.platform_name.localeCompare(b.platform_name);
  });

  return (
    <div
      className="grid gap-3"
      style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
    >
      {sorted.map((a) => (
        <AnswerCard
          key={a.platform_id}
          answer={a}
          preview={previews[a.platform_id]}
          onCancel={onCancelPlatform ? () => onCancelPlatform(a.platform_id) : undefined}
        />
      ))}
    </div>
  );
}
