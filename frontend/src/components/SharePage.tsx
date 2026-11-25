import { useEffect, useState } from "react";
import { MarkdownView } from "./MarkdownView";
import type { SessionDetail } from "../types/api";

type Props = {
  token: string;
};

/** 只读分享页：展示问题、最优答案和各平台回答，不提供编辑。 */
export function SharePage({ token }: Props) {
  const [data, setData] = useState<SessionDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/public/share/${encodeURIComponent(token)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("分享不存在或已失效");
        return (await response.json()) as SessionDetail;
      })
      .then((body) => {
        if (!cancelled) setData(body);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="min-h-screen bg-surface px-4 py-8 text-slate-800">
      <div className="mx-auto w-full max-w-3xl space-y-4">
        <header className="bento-card">
          <p className="text-xs font-medium tracking-wide text-slate-400">OneQMultiA 分享</p>
          <h1 className="mt-1 text-xl font-semibold">{data?.title || "只读会话"}</h1>
          <p className="mt-1 text-xs text-slate-500">此页面仅供查看，不能继续提问或修改平台配置。</p>
        </header>
        {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        {!data && !error && <p className="text-sm text-slate-500">正在加载分享内容…</p>}
        {data?.qa_pairs?.map((qa) => (
          <section key={qa.id} className="space-y-3">
            <article className="bento-card">
              <h2 className="text-sm font-semibold text-slate-500">问题</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{qa.question}</p>
            </article>
            {qa.optimal_answer?.text && (
              <article className="optimal-card">
                <h2 className="optimal-title">最优答案</h2>
                <div className="mt-3">
                  <MarkdownView text={qa.optimal_answer.text} />
                </div>
              </article>
            )}
            {qa.answers.map((answer) => (
              <article key={answer.id} className="bento-card">
                <h3 className="text-sm font-semibold">{answer.platform_name}</h3>
                <div className="mt-2 text-sm text-slate-600">
                  <MarkdownView text={answer.answer_text || answer.error_message || "（无内容）"} />
                </div>
              </article>
            ))}
          </section>
        ))}
      </div>
    </main>
  );
}
