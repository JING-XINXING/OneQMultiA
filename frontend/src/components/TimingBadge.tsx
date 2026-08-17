type Props = {
  durationMs: number | null | undefined;
  status: string;
};

/** Bento 响应时间徽标 */
export function TimingBadge({ durationMs, status }: Props) {
  const dur = durationMs != null ? `${(durationMs / 1000).toFixed(1)}s` : "—";
  const styles: Record<string, string> = {
    success: "badge-success",
    error: "badge-error",
    timeout: "badge-warning",
    skipped: "badge-info",
    pending: "badge-info",
    cancelled: "badge-error",
  };
  const label = status === "pending" ? "进行中" : status === "cancelled" ? "已终止" : dur;
  return (
    <span className={styles[status] || styles.skipped}>
      {label}
    </span>
  );
}
