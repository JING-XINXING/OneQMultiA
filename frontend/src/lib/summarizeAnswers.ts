import type { PlatformAnswer } from "../types/api";

/** 由已落库的平台回答生成与 WebSocket complete.summary 同结构的汇总。 */
export function summarizeAnswers(answers: PlatformAnswer[]): Record<string, unknown> {
  const total = answers.length;
  const count = (status: string) => answers.filter((a) => a.status === status).length;
  const durations = answers
    .map((a) => a.response_duration_ms)
    .filter((ms): ms is number => ms != null);
  return {
    total,
    success: count("success"),
    skipped: count("skipped"),
    error: count("error"),
    timeout: count("timeout"),
    cancelled: count("cancelled"),
    avg_duration_ms: durations.length
      ? Math.round(durations.reduce((s, n) => s + n, 0) / durations.length)
      : null,
  };
}
