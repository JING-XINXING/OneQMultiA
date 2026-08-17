import type { Platform } from "../types/api";

type Props = {
  platforms: Platform[];
  selected: string[];
  onChange: (ids: string[]) => void;
};

function toggle(ids: string[], id: string, on: boolean): string[] {
  if (on) return ids.includes(id) ? ids : [...ids, id];
  return ids.filter((x) => x !== id);
}

/** Bento 平台 Chip 选择器 */
export function PlatformSelector({ platforms, selected, onChange }: Props) {
  if (!platforms.length) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="section-kicker">回答平台</p>
          <h2 className="mt-1 text-sm font-semibold text-slate-800">选择要询问的助手</h2>
          <p className="mt-0.5 text-[11px] text-slate-500">不选则询问全部已启用平台，登录点为绿色</p>
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-500">
          {selected.length ? `已选 ${selected.length}` : "全部平台"}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {platforms.map((p) => {
          const active = selected.includes(p.id);
          return (
            <button
              key={p.id}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(toggle(selected, p.id, !active))}
              className={active ? "chip-active" : "chip"}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  p.login_status === "logged_in"
                    ? "bg-status-success"
                    : p.url_status === "invalid"
                      ? "bg-status-error"
                      : p.login_status === "logged_out"
                        ? "bg-status-warning"
                        : "bg-slate-300"
                }`}
              />
              {p.display_name}
            </button>
          );
        })}
      </div>
    </div>
  );
}
