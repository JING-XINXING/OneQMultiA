type Tab = "ask" | "history" | "platforms";

type Props = {
  active: Tab;
  onChange: (tab: Tab) => void;
};

const items: { id: Tab; label: string }[] = [
  { id: "ask", label: "问答" },
  { id: "history", label: "历史" },
  { id: "platforms", label: "平台" },
];

/** 移动端底部 Bento 导航 */
export function MobileNav({ active, onChange }: Props) {
  return (
    <nav className="fixed bottom-0 inset-x-0 z-50 border-t border-surface-border bg-white/92 shadow-[0_-8px_24px_rgba(15,23,42,0.06)] backdrop-blur-md md:hidden safe-area-pb">
      <div className="flex justify-around py-1">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-current={active === item.id ? "page" : undefined}
            onClick={() => onChange(item.id)}
            className={`flex flex-col items-center py-2 px-5 rounded-xl transition-all duration-150 ${
              active === item.id
                ? "text-accent bg-accent-soft"
                : "text-slate-400 hover:text-slate-600"
            }`}
          >
            <span className={`mb-0.5 h-1 w-4 rounded-full ${active === item.id ? "bg-accent" : "bg-transparent"}`} />
            <span className="text-[11px] font-medium">{item.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
