/** 刷新后恢复当前会话，避免主区变成空白新会话。 */
export const WORKSPACE_STORAGE_KEY = "oneqmultia.workspace";

export type WorkspaceSnapshot = {
  sessionId: string | null;
  question: string;
  selectedPlatforms: string[];
};

export type SessionHint = {
  id: string;
  qa_count?: number;
};

const EMPTY: WorkspaceSnapshot = {
  sessionId: null,
  question: "",
  selectedPlatforms: [],
};

/** 读取上次停留的会话与提问草稿。 */
export function loadWorkspaceSnapshot(): WorkspaceSnapshot {
  try {
    const raw = localStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (!raw) return { ...EMPTY };
    const parsed = JSON.parse(raw) as Partial<WorkspaceSnapshot>;
    return {
      sessionId: typeof parsed.sessionId === "string" && parsed.sessionId ? parsed.sessionId : null,
      question: typeof parsed.question === "string" ? parsed.question : "",
      selectedPlatforms: Array.isArray(parsed.selectedPlatforms)
        ? parsed.selectedPlatforms.filter((id): id is string => typeof id === "string")
        : [],
    };
  } catch {
    return { ...EMPTY };
  }
}

export function saveWorkspaceSnapshot(snapshot: WorkspaceSnapshot): void {
  try {
    localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // 隐私模式或配额满时忽略，不影响当次使用
  }
}

/**
 * 刷新后优先回到上次会话；若该会话是空占位或不存在，则改回最近有问答的会话。
 * 空占位不会进历史列表，因此不能只信 storedId。
 */
export function resolveSessionToRestore(
  storedId: string | null,
  sessions: SessionHint[]
): string | null {
  if (storedId) {
    const stored = sessions.find((item) => item.id === storedId);
    if (stored && (stored.qa_count ?? 0) > 0) return stored.id;
  }
  const withQa = sessions.find((item) => (item.qa_count ?? 0) > 0);
  return withQa?.id ?? null;
}
