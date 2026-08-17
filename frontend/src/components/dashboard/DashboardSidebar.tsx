import { ExportMenu } from "../ExportMenu";
import { SessionHistory } from "../SessionHistory";
import type { SessionSummary } from "../../types/api";

type Props = {
  sessions: SessionSummary[];
  sessionId: string | null;
  shareUrl: string;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
  onRefreshSessions: () => void;
  onShare: (url: string) => void;
};

/** 桌面端会话与导出工具栏。 */
export function DashboardSidebar({
  sessions,
  sessionId,
  shareUrl,
  onNewSession,
  onSelectSession,
  onRefreshSessions,
  onShare,
}: Props) {
  return (
    <>
      <button type="button" className="btn w-full" onClick={onNewSession}>
        <span className="text-base leading-none" aria-hidden="true">＋</span>
        新建会话
      </button>
      <SessionHistory
        sessions={sessions}
        currentId={sessionId}
        onSelect={onSelectSession}
        onRefresh={onRefreshSessions}
      />
      <ExportMenu sessionId={sessionId} onShare={onShare} />
      {shareUrl && (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-status-success break-all">
          分享链接已复制
        </p>
      )}
    </>
  );
}
