type Props = { status?: string };

/** 账号绑定 / 登录态 */
export function LoginStatus({ status }: Props) {
  const map: Record<string, { label: string; cls: string }> = {
    logged_in: { label: "已登录", cls: "badge-success" },
    logged_out: { label: "未登录", cls: "badge-warning" },
    unknown: { label: "未绑定", cls: "badge text-slate-500 bg-slate-100 border border-slate-200" },
  };
  const s = map[status || "unknown"] || map.unknown;
  return <span className={s.cls}>{s.label}</span>;
}
