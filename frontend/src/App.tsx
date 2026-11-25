import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MobileExportSheet } from "./components/MobileExportSheet";
import { MobileNav } from "./components/MobileNav";
import { SharePage } from "./components/SharePage";
import { SessionHistory } from "./components/SessionHistory";
import { AskWorkspace } from "./components/dashboard/AskWorkspace";
import { DashboardHeader } from "./components/dashboard/DashboardHeader";
import { DashboardSidebar } from "./components/dashboard/DashboardSidebar";
import { PlatformForm } from "./components/platform-manager/PlatformForm";
import { PlatformList } from "./components/platform-manager/PlatformList";
import { usePWA } from "./hooks/usePWA";
import { useResponsive } from "./hooks/useResponsive";
import { useWebSocketAsk } from "./hooks/useWebSocketAsk";
import { DesktopLayout } from "./layouts/DesktopLayout";
import { MobileLayout } from "./layouts/MobileLayout";
import { compareQuery, loadStoredLlmChoice, resolveLlmChoice, saveLlmChoice } from "./lib/llmChoice";
import { loadWorkspaceSnapshot, resolveSessionToRestore, saveWorkspaceSnapshot } from "./lib/sessionPersist";
import { summarizeAnswers } from "./lib/summarizeAnswers";
import type { CompareResult, LlmChoice, LlmStatus, Platform, PlatformAnswer, QAPair, SessionDetail, SessionSummary } from "./types/api";

type Tab = "ask" | "history" | "platforms";

function readShareToken(): string {
  const matched = window.location.pathname.match(/^\/share\/([^/]+)\/?$/);
  if (matched) return decodeURIComponent(matched[1]);
  return new URLSearchParams(window.location.search).get("share") || "";
}

export default function App() {
  const shareToken = readShareToken();
  const { isMobile } = useResponsive();
  const { canInstall, install } = usePWA();
  const [tab, setTab] = useState<Tab>("ask");

  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [restoredQaPairs, setRestoredQaPairs] = useState<QAPair[]>([]);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [question, setQuestion] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [shareUrl, setShareUrl] = useState("");
  const [editPlatform, setEditPlatform] = useState<Platform | null>(null);
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const comparedQaIdRef = useRef<string | null>(null);
  const [cdpConnected, setCdpConnected] = useState<boolean | null>(null);
  const [cdpMessage, setCdpMessage] = useState("");
  const [busyPlatformId, setBusyPlatformId] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);
  const [llmChoice, setLlmChoice] = useState<LlmChoice | null>(() => loadStoredLlmChoice());
  const llmChoiceRef = useRef<LlmChoice | null>(llmChoice);
  llmChoiceRef.current = llmChoice;
  const [workspaceReady, setWorkspaceReady] = useState(false);

  const { events, connected, asking, lastSummary, lastQaPairId, runAsk, cancelAsk, clear } = useWebSocketAsk();

  const loadPlatforms = useCallback(async () => {
    const r = await fetch("/api/platforms");
    if (r.ok) setPlatforms(await r.json());
  }, []);

  const loadSessions = useCallback(async () => {
    const r = await fetch("/api/sessions");
    if (r.ok) setSessions(await r.json());
  }, []);

  const loadSessionDetail = useCallback(async (id: string, options?: { quiet?: boolean }) => {
    // 本轮刚结束时静默刷新，避免出现「正在恢复历史会话」造成内容被收走的错觉
    if (!options?.quiet) setSessionLoading(true);
    try {
      const r = await fetch(`/api/sessions/${id}`);
      if (!r.ok) {
        setRestoredQaPairs([]);
        return;
      }
      const detail = (await r.json()) as SessionDetail;
      const pairs = [...(detail.qa_pairs || [])].sort(
        (a, b) => new Date(a.question_time).getTime() - new Date(b.question_time).getTime()
      );
      setRestoredQaPairs(pairs);
      const last = pairs[pairs.length - 1];
      // 刷新/点开历史时回填最近一问，主区看起来仍是当前会话
      if (!options?.quiet && last?.question) setQuestion(last.question);
      if (last?.id) {
        comparedQaIdRef.current = last.id;
        setCompareLoading(true);
        fetch(`/api/sessions/${id}/qa/${last.id}/compare${compareQuery(llmChoiceRef.current)}`)
          .then((cr) => (cr.ok ? cr.json() : null))
          .then((data) => setCompare(data))
          .finally(() => setCompareLoading(false));
      } else {
        setCompare(null);
      }
    } finally {
      setSessionLoading(false);
    }
  }, []);

  const loadLlmStatus = useCallback(async () => {
    const r = await fetch("/api/llm/status");
    if (!r.ok) return;
    const status = (await r.json()) as LlmStatus;
    setLlmStatus(status);
    setLlmChoice((prev) => {
      const next = resolveLlmChoice(status, prev);
      if (next) saveLlmChoice(next);
      return next;
    });
  }, []);

  const loadCdpStatus = useCallback(async () => {
    const r = await fetch("/api/platforms/cdp-status");
    if (r.ok) {
      const j = await r.json();
      setCdpConnected(Boolean(j.connected));
      setCdpMessage(String(j.message || ""));
    }
  }, []);

  const restoreWorkspace = useCallback(async () => {
    const snap = loadWorkspaceSnapshot();
    if (snap.selectedPlatforms.length) setSelected(snap.selectedPlatforms);
    setSessionLoading(true);
    try {
      const r = await fetch("/api/sessions");
      if (!r.ok) return;
      const list = (await r.json()) as SessionSummary[];
      setSessions(list);

      const preferred = resolveSessionToRestore(snap.sessionId, list);
      // 存储的会话可能是空占位（不在列表里），先试详情再回退到有内容的会话
      const tryIds = [snap.sessionId, preferred].filter(
        (id, index, all): id is string => Boolean(id) && all.indexOf(id) === index
      );
      for (const id of tryIds) {
        const detail = await fetch(`/api/sessions/${id}`);
        if (!detail.ok) continue;
        const data = (await detail.json()) as SessionDetail;
        const pairs = [...(data.qa_pairs || [])].sort(
          (a, b) => new Date(a.question_time).getTime() - new Date(b.question_time).getTime()
        );
        if (pairs.length === 0 && id !== preferred) continue;
        setSessionId(id);
        setRestoredQaPairs(pairs);
        const last = pairs[pairs.length - 1];
        setQuestion(snap.question || last?.question || "");
        if (last?.id) {
          comparedQaIdRef.current = last.id;
          setCompareLoading(true);
          fetch(`/api/sessions/${id}/qa/${last.id}/compare${compareQuery(llmChoiceRef.current)}`)
            .then((cr) => (cr.ok ? cr.json() : null))
            .then((cmp) => setCompare(cmp))
            .finally(() => setCompareLoading(false));
        } else {
          setCompare(null);
        }
        return;
      }
    } finally {
      setSessionLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPlatforms();
    void loadCdpStatus();
    void loadLlmStatus();
    void restoreWorkspace().finally(() => setWorkspaceReady(true));
  }, [loadPlatforms, loadCdpStatus, loadLlmStatus, restoreWorkspace]);

  // 恢复完成后再写入，避免首屏空状态把上次会话 ID 冲掉
  useEffect(() => {
    if (!workspaceReady) return;
    saveWorkspaceSnapshot({
      sessionId,
      question,
      selectedPlatforms: selected,
    });
  }, [workspaceReady, sessionId, question, selected]);

  const previews = useMemo(() => {
    const m: Record<string, string> = {};
    for (const e of events) {
      if (e.type === "answer_delta") m[e.platform_id] = e.preview;
      if (e.type === "platform_done") m[e.platform_id] = e.answer_text || e.error_message || "";
    }
    return m;
  }, [events]);

  const answers: PlatformAnswer[] = useMemo(() => {
    const m = new Map<string, PlatformAnswer>();
    for (const e of events) {
      if (e.type === "platform_start") {
        if (!m.has(e.platform_id)) {
          m.set(e.platform_id, {
            platform_id: e.platform_id,
            platform_name: e.platform_name,
            platform_url: "",
            answer_text: "",
            status: "pending",
            error_message: "",
            request_sent_at: null,
            first_token_at: null,
            completed_at: null,
            response_duration_ms: null,
          });
        }
      }
      if (e.type === "platform_done") {
        m.set(e.platform_id, {
          platform_id: e.platform_id,
          platform_name: e.platform_name,
          platform_url: e.platform_url,
          answer_text: e.answer_text,
          status: e.status,
          error_message: e.error_message,
          request_sent_at: e.request_sent_at,
          first_token_at: e.first_token_at,
          completed_at: e.completed_at,
          response_duration_ms: e.response_duration_ms,
        });
      }
    }
    return [...m.values()];
  }, [events]);

  useEffect(() => {
    if (lastQaPairId && sessionId && !asking && comparedQaIdRef.current !== lastQaPairId) {
      comparedQaIdRef.current = lastQaPairId;
      setCompareLoading(true);
      fetch(`/api/sessions/${sessionId}/qa/${lastQaPairId}/compare${compareQuery(llmChoiceRef.current)}`)
        .then((r) => r.json())
        .then(setCompare)
        .finally(() => setCompareLoading(false));
      void loadSessions();
      void loadSessionDetail(sessionId, { quiet: true });
    }
  }, [lastQaPairId, sessionId, asking, loadSessions, loadSessionDetail]);

  async function ensureSession(): Promise<string | null> {
    if (sessionId) return sessionId;
    // 空标题由后端在首问时写成问题摘要
    const r = await fetch("/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "" }) });
    if (!r.ok) return null;
    const j = await r.json();
    setSessionId(j.id);
    return j.id as string;
  }

  async function submitAsk() {
    const sid = await ensureSession();
    if (!sid || !question.trim()) return;
    runAsk({ session_id: sid, question: question.trim(), platform_ids: selected.length ? selected : null });
  }

  async function selectSession(id: string) {
    if (asking) cancelAsk();
    clear();
    setQuestion("");
    setShareUrl("");
    setCompare(null);
    comparedQaIdRef.current = null;
    setSessionId(id);
    setTab("ask");
    await loadSessionDetail(id);
  }

  async function newSession() {
    if (asking) cancelAsk();
    clear();
    setQuestion("");
    setCompare(null);
    setRestoredQaPairs([]);
    comparedQaIdRef.current = null;
    const r = await fetch("/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "新会话" }) });
    if (r.ok) setSessionId((await r.json()).id);
  }

  async function togglePlatform(id: string, enabled: boolean) {
    await fetch(`/api/platforms/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled }) });
    void loadPlatforms();
  }

  async function batchEnable(ids: string[], enabled: boolean) {
    await fetch("/api/platforms/batch-enable", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ platform_ids: ids, enabled }) });
    void loadPlatforms();
  }

  async function healthCheck(id: string) {
    const r = await fetch(`/api/platforms/${id}/health`, { method: "POST" });
    if (r.ok) void loadPlatforms();
  }

  async function validateUrl(id: string) {
    setBusyPlatformId(id);
    try {
      await fetch(`/api/platforms/${id}/url/validate`, { method: "POST" });
      void loadPlatforms();
    } finally {
      setBusyPlatformId(null);
    }
  }

  async function openLogin(id: string) {
    setBusyPlatformId(id);
    try {
      const r = await fetch(`/api/platforms/${id}/login/open`, { method: "POST" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        window.alert(j.detail || "无法打开登录页，请确认已启动调试版 Chrome");
      }
      void loadPlatforms();
      void loadCdpStatus();
    } finally {
      setBusyPlatformId(null);
    }
  }

  async function checkLogin(id: string) {
    setBusyPlatformId(id);
    try {
      const r = await fetch(`/api/platforms/${id}/login/check`, { method: "POST" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        window.alert(j.detail || "无法检测登录态，请确认已启动调试版 Chrome");
      }
      void loadPlatforms();
      void loadCdpStatus();
    } finally {
      setBusyPlatformId(null);
    }
  }

  async function validateAllUrls() {
    setBusyPlatformId("all");
    try {
      for (const p of platforms) {
        await fetch(`/api/platforms/${p.id}/url/validate?check_network=true`, { method: "POST" });
      }
      void loadPlatforms();
    } finally {
      setBusyPlatformId(null);
    }
  }

  async function scanAllAccounts() {
    setBusyPlatformId("all");
    try {
      const r = await fetch("/api/platforms/accounts/scan?check_network=true", { method: "POST" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        window.alert(j.detail || "扫描失败");
      }
      void loadPlatforms();
      void loadCdpStatus();
    } finally {
      setBusyPlatformId(null);
    }
  }

  async function savePlatform(id: string, patch: Partial<Platform>) {
    await fetch(`/api/platforms/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) });
    void loadPlatforms();
  }

  async function regenerateOptimal(choice = llmChoiceRef.current) {
    const qaId = lastQaPairId || restoredQaPairs[restoredQaPairs.length - 1]?.id;
    if (!sessionId || !qaId) return;
    setCompareLoading(true);
    try {
      const r = await fetch(`/api/sessions/${sessionId}/qa/${qaId}/compare/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: choice?.provider || "", model: choice?.model || "" }),
      });
      if (r.ok) setCompare(await r.json());
    } finally {
      setCompareLoading(false);
    }
  }

  function changeLlmChoice(choice: LlmChoice) {
    setLlmChoice(choice);
    saveLlmChoice(choice);
    const hasAnswers = restoredQaPairs.length > 0 || lastQaPairId;
    if (hasAnswers && !asking) void regenerateOptimal(choice);
  }

  if (shareToken) {
    return <SharePage token={shareToken} />;
  }

  const header = (
    <DashboardHeader
      connected={asking || connected}
      canInstall={canInstall}
      onInstall={() => void install()}
      llmStatus={llmStatus}
      llmChoice={llmChoice}
    />
  );

  const sidebar = (
    <DashboardSidebar
      sessions={sessions}
      sessionId={sessionId}
      shareUrl={shareUrl}
      onNewSession={() => void newSession()}
      onSelectSession={(id) => void selectSession(id)}
      onRefreshSessions={loadSessions}
      onShare={setShareUrl}
    />
  );

  const lastRestored = restoredQaPairs[restoredQaPairs.length - 1];
  // 历史已含本轮则不再叠一层实时卡片，避免恢复后重复
  const showLiveRound = asking || (answers.length > 0 && lastQaPairId !== lastRestored?.id);
  const displaySummary =
    lastSummary ?? (lastRestored?.answers.length ? summarizeAnswers(lastRestored.answers) : null);

  const askPanel = (
    <AskWorkspace
      platforms={platforms.filter((platform) => platform.enabled)}
      selectedPlatforms={selected}
      question={question}
      connected={asking}
      answers={showLiveRound ? answers : []}
      previews={showLiveRound ? previews : {}}
      rounds={restoredQaPairs}
      sessionLoading={sessionLoading}
      summary={displaySummary}
      compare={compare}
      compareLoading={compareLoading}
      columns={isMobile ? 1 : 3}
      onSelectedPlatformsChange={setSelected}
      onQuestionChange={setQuestion}
      onSubmit={() => void submitAsk()}
      onCancel={() => cancelAsk()}
      onCancelPlatform={(id) => cancelAsk(id)}
      llmStatus={llmStatus}
      llmChoice={llmChoice}
      onLlmChoiceChange={changeLlmChoice}
      onRegenerateOptimal={() => void regenerateOptimal()}
    />
  );

  const historyPanel = (
    <SessionHistory sessions={sessions} currentId={sessionId} onSelect={(id) => void selectSession(id)} onRefresh={loadSessions} />
  );

  const platformsPanel = (
    <>
      <PlatformList
        platforms={platforms}
        cdpConnected={cdpConnected}
        cdpMessage={cdpMessage}
        busyId={busyPlatformId}
        onToggle={togglePlatform}
        onHealthCheck={healthCheck}
        onValidateUrl={validateUrl}
        onOpenLogin={openLogin}
        onCheckLogin={checkLogin}
        onEdit={setEditPlatform}
        onBatchEnable={batchEnable}
        onScanAll={() => void scanAllAccounts()}
        onValidateAll={() => void validateAllUrls()}
      />
      {editPlatform && (
        <PlatformForm platform={editPlatform} onSave={savePlatform} onClose={() => setEditPlatform(null)} />
      )}
    </>
  );

  const mainContent = tab === "ask" ? askPanel : tab === "history" ? historyPanel : platformsPanel;

  return (
    <>
      {isMobile ? (
        <MobileLayout header={
          <div className="flex w-full items-center justify-between gap-2">
            <div className="min-w-0 flex-1">{header}</div>
            <MobileExportSheet sessionId={sessionId} onShare={setShareUrl} />
          </div>
        }>{mainContent}</MobileLayout>
      ) : (
        <DesktopLayout sidebar={sidebar} header={header}>{mainContent}</DesktopLayout>
      )}
      <MobileNav active={tab} onChange={setTab} />
    </>
  );
}
