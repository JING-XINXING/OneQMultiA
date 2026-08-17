import { AnswerGrid } from "./AnswerGrid";
import type { PlatformAnswer, QAPair } from "../types/api";

type Props = {
  rounds: QAPair[];
  columns: number;
  liveQuestion?: string;
  liveAnswers?: PlatformAnswer[];
  livePreviews?: Record<string, string>;
  asking?: boolean;
  onCancelPlatform?: (platformId: string) => void;
};

/** 将会话中每一轮问答还原到主界面，支持继续提问时追加「进行中」一轮。 */
export function QaRoundList({
  rounds,
  columns,
  liveQuestion,
  liveAnswers = [],
  livePreviews = {},
  asking = false,
  onCancelPlatform,
}: Props) {
  const showLive = asking || liveAnswers.length > 0;
  const empty = rounds.length === 0 && !showLive;

  if (empty) {
    return <AnswerGrid answers={[]} columns={columns} />;
  }

  return (
    <div className="space-y-5">
      {rounds.map((qa, index) => (
        <section key={qa.id} className="space-y-3">
          <div className="flex items-start justify-between gap-3 rounded-2xl border border-surface-border bg-white/80 px-4 py-3">
            <div className="min-w-0">
              <p className="section-kicker">第 {index + 1} 问</p>
              <p className="mt-1 text-sm font-medium leading-relaxed text-slate-800 whitespace-pre-wrap break-words">
                {qa.question}
              </p>
              {qa.question_time && (
                <p className="mt-1 text-[11px] text-slate-400">{new Date(qa.question_time).toLocaleString()}</p>
              )}
            </div>
            <span className="flex-shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] text-slate-500">
              {qa.answers.length} 个回答
            </span>
          </div>
          <AnswerGrid answers={qa.answers} columns={columns} />
        </section>
      ))}

      {showLive && (
        <section className="space-y-3">
          <div className="rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-3">
            <p className="section-kicker text-accent">{asking ? "正在提问" : `第 ${rounds.length + 1} 问`}</p>
            {liveQuestion && (
              <p className="mt-1 text-sm font-medium leading-relaxed text-slate-800 whitespace-pre-wrap break-words">
                {liveQuestion}
              </p>
            )}
          </div>
          <AnswerGrid
            answers={liveAnswers}
            previews={livePreviews}
            columns={columns}
            onCancelPlatform={asking ? onCancelPlatform : undefined}
          />
        </section>
      )}
    </div>
  );
}
