import type { LlmChoice, LlmStatus } from "../../types/api";

type Props = {
  connected: boolean;
  canInstall: boolean;
  onInstall: () => void;
  llmStatus?: LlmStatus | null;
  llmChoice?: LlmChoice | null;
};

/** 全局工作台页眉，在桌面端和移动端复用。 */
export function DashboardHeader({ connected, canInstall, onInstall, llmStatus, llmChoice }: Props) {
  const modelHint = llmChoice?.model || llmStatus?.model;
  return (
    <div className="flex w-full items-center justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <div className="brand-mark" aria-hidden="true">
          Q
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-[15px] font-bold tracking-[-0.02em] text-slate-900">OneQMultiA</h1>
            <span className="hidden rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent sm:inline">
              多模型工作台
            </span>
          </div>
          <p className="hidden text-[10px] text-slate-500 sm:block">一个问题，多种视角，再整理成最优答案</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className={`connection-pill ${llmStatus?.configured ? "is-active" : ""} hidden sm:inline-flex`}>
          <span className={llmStatus?.configured ? "status-dot-success" : "status-dot bg-slate-300"} />
          {llmStatus?.configured ? `最优解 · ${modelHint || llmStatus.label}` : "最优解 · 本地"}
        </span>
        <span className={`connection-pill ${connected ? "is-active" : ""}`}>
          <span className={connected ? "status-dot-success animate-pulse-slow" : "status-dot bg-slate-300"} />
          {connected ? "正在汇集回答" : "服务就绪"}
        </span>
        {canInstall && (
          <button type="button" className="btn-sm hidden sm:inline-flex" onClick={onInstall}>
            安装应用
          </button>
        )}
      </div>
    </div>
  );
}
