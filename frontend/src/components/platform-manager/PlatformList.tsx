import { useState } from "react";
import type { Platform } from "../../types/api";
import { HealthStatus } from "./HealthStatus";
import { LoginStatus } from "./LoginStatus";
import { UrlStatus } from "./UrlStatus";

type Props = {
  platforms: Platform[];
  cdpConnected: boolean | null;
  cdpMessage: string;
  busyId: string | null;
  onToggle: (id: string, enabled: boolean) => void;
  onHealthCheck: (id: string) => void;
  onValidateUrl: (id: string) => void;
  onOpenLogin: (id: string) => void;
  onCheckLogin: (id: string) => void;
  onEdit: (p: Platform) => void;
  onBatchEnable: (ids: string[], enabled: boolean) => void;
  onScanAll: () => void;
  onValidateAll: () => void;
};

/** 平台列表：启用、网址校验、账号绑定 */
export function PlatformList({
  platforms,
  cdpConnected,
  cdpMessage,
  busyId,
  onToggle,
  onHealthCheck,
  onValidateUrl,
  onOpenLogin,
  onCheckLogin,
  onEdit,
  onBatchEnable,
  onScanAll,
  onValidateAll,
}: Props) {
  const allIds = platforms.map((p) => p.id);
  const [notice, setNotice] = useState("");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-bold text-slate-900">平台管理</h2>
          <p className="text-xs text-slate-500">校验服务网址，并在调试版 Chrome 中绑定各助手账号（不保存密码）</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost text-sm min-h-[44px]" onClick={onValidateAll}>
            全部校验网址
          </button>
          <button type="button" className="btn-ghost text-sm min-h-[44px]" onClick={onScanAll}>
            扫描登录态
          </button>
          <button type="button" className="btn-ghost text-sm min-h-[44px]" onClick={() => onBatchEnable(allIds, true)}>
            全部启用
          </button>
          <button type="button" className="btn-ghost text-sm min-h-[44px]" onClick={() => onBatchEnable(allIds, false)}>
            全部禁用
          </button>
        </div>
      </div>

      <div className={`bento-card-sm text-xs ${cdpConnected ? "text-emerald-700 bg-emerald-50" : "text-amber-700 bg-amber-50"}`}>
        {cdpConnected === null ? "正在检查调试版 Chrome…" : cdpMessage}
        {!cdpConnected && cdpConnected !== null && (
          <span className="ml-1">绑定登录前请运行 <code>./scripts/start_chrome_cdp.sh</code> 并重启 API。</span>
        )}
      </div>

      {notice && <p className="text-xs text-slate-500">{notice}</p>}

      <ul className="grid gap-3 lg:grid-cols-2">
        {platforms.map((p) => (
          <li key={p.id} className="bento-card space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-slate-800">{p.display_name}</div>
                <div className="text-xs text-slate-400 truncate" title={p.url}>{p.url}</div>
              </div>
              <label className="inline-flex items-center gap-2 text-sm min-h-[44px]">
                <input type="checkbox" checked={p.enabled} onChange={(e) => onToggle(p.id, e.target.checked)} />
                启用
              </label>
            </div>

            <div className="flex flex-wrap gap-1.5">
              <UrlStatus status={p.url_status} />
              <LoginStatus status={p.login_status} />
              <HealthStatus status={p.health_status} />
            </div>

            {(p.url_check_message || p.login_message) && (
              <p className="text-[11px] text-slate-500 leading-relaxed">
                {p.url_check_message}
                {p.url_check_message && p.login_message ? " · " : ""}
                {p.login_message}
              </p>
            )}

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-ghost text-xs min-h-[40px]"
                disabled={busyId === p.id}
                onClick={() => onValidateUrl(p.id)}
              >
                校验网址
              </button>
              <button
                type="button"
                className="btn-ghost text-xs min-h-[40px]"
                disabled={busyId === p.id}
                onClick={() => {
                  if (!cdpConnected) {
                    setNotice("请先启动调试版 Chrome 再绑定登录");
                    return;
                  }
                  onOpenLogin(p.id);
                }}
              >
                绑定登录
              </button>
              <button
                type="button"
                className="btn-ghost text-xs min-h-[40px]"
                disabled={busyId === p.id}
                onClick={() => onCheckLogin(p.id)}
              >
                检测登录
              </button>
              <button type="button" className="btn-ghost text-xs min-h-[40px]" onClick={() => onHealthCheck(p.id)}>
                连通检测
              </button>
              <button type="button" className="btn-ghost text-xs min-h-[40px]" onClick={() => onEdit(p)}>
                编辑网址
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
