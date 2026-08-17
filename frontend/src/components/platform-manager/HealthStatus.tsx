type Props = { status: string };

/** 平台健康状态指示器 */
export function HealthStatus({ status }: Props) {
  const map: Record<string, { label: string; cls: string }> = {
    healthy: { label: "正常", cls: "badge-success" },
    unhealthy: { label: "异常", cls: "badge-error" },
    unknown: { label: "未知", cls: "badge text-slate-500 bg-slate-100 border border-slate-200" },
  };
  const s = map[status] || map.unknown;
  return <span className={s.cls}>{s.label}</span>;
}
