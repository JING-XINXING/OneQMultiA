type Props = { status?: string };

/** 服务网址校验状态 */
export function UrlStatus({ status }: Props) {
  const map: Record<string, { label: string; cls: string }> = {
    valid: { label: "网址正确", cls: "badge-success" },
    invalid: { label: "网址异常", cls: "badge-error" },
    unknown: { label: "未校验", cls: "badge text-slate-500 bg-slate-100 border border-slate-200" },
  };
  const s = map[status || "unknown"] || map.unknown;
  return <span className={s.cls}>{s.label}</span>;
}
