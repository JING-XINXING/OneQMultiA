import { useState } from "react";
import { AnswerCompare } from "../AnswerCompare";
import { LlmModelPicker } from "../LlmModelPicker";
import { OptimalAnswer } from "../OptimalAnswer";
import { PlatformSelector } from "../PlatformSelector";
import { QaRoundList } from "../QaRoundList";
import { QuestionInput } from "../QuestionInput";
import { SummaryStats } from "./SummaryStats";
import type { CompareResult, LlmChoice, LlmStatus, Platform, PlatformAnswer, QAPair } from "../../types/api";

type ResultView = "optimal" | "answers" | "compare";

type Props = {
  platforms: Platform[];
  selectedPlatforms: string[];
  question: string;
  connected: boolean;
  answers: PlatformAnswer[];
  previews: Record<string, string>;
  rounds: QAPair[];
  sessionLoading?: boolean;
  summary: Record<string, unknown> | null;
  compare: CompareResult | null;
  compareLoading: boolean;
  columns: number;
  onSelectedPlatformsChange: (ids: string[]) => void;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  onCancelPlatform?: (platformId: string) => void;
  llmStatus?: LlmStatus | null;
  llmChoice?: LlmChoice | null;
  onLlmChoiceChange?: (choice: LlmChoice) => void;
  onRegenerateOptimal?: () => void;
};

const VIEWS: { id: ResultView; label: string }[] = [
  { id: "optimal", label: "最优答案" },
  { id: "answers", label: "各平台回答" },
  { id: "compare", label: "对比分析" },
];

/** 问答页：提问区 + 最优解 / 原答 / 对比三种产品视图。 */
export function AskWorkspace({
  platforms,
  selectedPlatforms,
  question,
  connected,
  answers,
  previews,
  rounds,
  sessionLoading,
  summary,
  compare,
  compareLoading,
  columns,
  onSelectedPlatformsChange,
  onQuestionChange,
  onSubmit,
  onCancel,
  onCancelPlatform,
  llmStatus,
  llmChoice,
  onLlmChoiceChange,
  onRegenerateOptimal,
}: Props) {
  const [view, setView] = useState<ResultView>("answers");
  const hasResults = rounds.length > 0 || answers.length > 0;
  const latestQuestion =
    (connected && question.trim()) ||
    rounds[rounds.length - 1]?.question ||
    question.trim();

  // 完成后停留在「各平台回答」，不自动切走，避免主区看起来像被收进历史、只剩空白提问框。

  return (
    <div className="space-y-4">
      <section className="bento-card-primary overflow-hidden">
        <div className="workspace-accent" aria-hidden="true" />
        <div className="relative">
          <PlatformSelector
            platforms={platforms}
            selected={selectedPlatforms}
            onChange={onSelectedPlatformsChange}
          />
          <div className="mt-4 border-t border-surface-border pt-4">
            <LlmModelPicker
              status={llmStatus ?? null}
              value={llmChoice ?? null}
              onChange={onLlmChoiceChange ?? (() => undefined)}
              disabled={connected}
            />
          </div>
          <div className="mt-4 border-t border-surface-border pt-4">
            <QuestionInput
              value={question}
              onChange={onQuestionChange}
              onSubmit={onSubmit}
              onCancel={onCancel}
              disabled={connected}
              loading={connected}
            />
          </div>
        </div>
      </section>

      {sessionLoading && (
        <p className="text-center text-xs text-slate-400">正在恢复历史会话…</p>
      )}
      <SummaryStats summary={summary} />

      {hasResults && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="view-tab-bar" role="tablist" aria-label="结果视图">
              {VIEWS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={view === item.id}
                  className={view === item.id ? "view-tab is-active" : "view-tab"}
                  onClick={() => setView(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-slate-400">本轮问答会留在当前页，历史里只是同步一份</p>
          </div>
          {view !== "answers" && latestQuestion && (
            <p className="rounded-2xl border border-surface-border bg-white px-4 py-3 text-sm font-medium leading-relaxed text-slate-800">
              {latestQuestion}
            </p>
          )}
        </div>
      )}

      {hasResults && view === "optimal" && (
        <OptimalAnswer
          data={compare?.optimal_answer}
          loading={compareLoading}
          asking={connected}
          llmStatus={llmStatus}
          onRegenerate={onRegenerateOptimal}
        />
      )}

      {hasResults && view === "compare" && (
        <AnswerCompare data={compare} loading={compareLoading} />
      )}

      {/* 各平台卡片始终保留，切换 Tab 只叠加最优答案/对比，不拆掉当前问答 */}
      <QaRoundList
        rounds={rounds}
        columns={columns}
        liveQuestion={connected ? question : undefined}
        liveAnswers={answers}
        livePreviews={previews}
        asking={connected}
        onCancelPlatform={onCancelPlatform}
      />
    </div>
  );
}
