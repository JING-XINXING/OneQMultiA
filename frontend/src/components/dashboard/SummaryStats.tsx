type Props = {
  summary: Record<string, unknown> | null;
};

const ITEMS = [
  { key: "total", label: "参与平台", tone: "text-slate-900", bar: "bg-slate-400" },
  { key: "success", label: "成功", tone: "text-emerald-700", bar: "bg-emerald-500" },
  { key: "timeout", label: "超时", tone: "text-amber-700", bar: "bg-amber-400" },
  { key: "error", label: "错误", tone: "text-rose-700", bar: "bg-rose-500" },
  { key: "skipped", label: "跳过", tone: "text-slate-500", bar: "bg-slate-300" },
  { key: "cancelled", label: "已终止", tone: "text-rose-600", bar: "bg-rose-400" },
] as const;

/** 汇总一次多平台请求的关键运行指标。 */
export function SummaryStats({ summary }: Props) {
  if (!summary) return null;

  return (
    <section className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6" aria-label="回答汇总">
      {ITEMS.map((item) => (
        <div key={item.key} className="metric-card">
          <span className={`absolute inset-x-0 top-0 h-0.5 ${item.bar}`} />
          <div className="text-[11px] font-medium text-slate-500">{item.label}</div>
          <div className={`mt-1 text-[22px] font-bold tracking-tight ${item.tone}`}>
            {String(summary[item.key] ?? "—")}
          </div>
        </div>
      ))}
    </section>
  );
}
