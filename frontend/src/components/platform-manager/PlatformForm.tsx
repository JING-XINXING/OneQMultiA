import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { Platform } from "../../types/api";

type Props = {
  platform: Platform | null;
  onSave: (id: string, patch: Partial<Platform>) => Promise<void>;
  onClose: () => void;
};

/** 编辑平台网址与选择器 */
export function PlatformForm({ platform, onSave, onClose }: Props) {
  const [url, setUrl] = useState("");
  const [selectorsJson, setSelectorsJson] = useState("{}");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (platform) {
      setUrl(platform.url || "");
      setSelectorsJson(JSON.stringify(platform.selectors || {}, null, 2));
      setError("");
    }
  }, [platform]);

  if (!platform) return null;

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const trimmed = url.trim();
      if (!/^https?:\/\//i.test(trimmed)) {
        setError("网址必须以 http:// 或 https:// 开头");
        return;
      }
      const selectors = JSON.parse(selectorsJson) as Record<string, string>;
      await onSave(platform!.id, { url: trimmed, selectors });
      onClose();
    } catch {
      setError("Selectors JSON 格式无效，请检查逗号、引号和括号。");
    } finally {
      setSaving(false);
    }
  }

  function handleDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      onClose();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;

    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-900/30 backdrop-blur-sm p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="platform-form-title"
        onKeyDown={handleDialogKeyDown}
        className="bento-card w-full max-w-lg max-h-[90vh] overflow-y-auto space-y-4 shadow-bento-hover"
      >
        <h2 id="platform-form-title" className="font-semibold text-slate-900">编辑 {platform.display_name}</h2>
        <label className="block text-sm text-slate-700">
          服务网址
          <input
            value={url}
            autoFocus
            onChange={(e) => setUrl(e.target.value)}
            className="input-bento mt-1"
            placeholder="https://..."
            aria-label="服务网址"
          />
        </label>
        {platform.expected_host && (
          <p className="text-xs text-slate-500">期望域名：{platform.expected_host}</p>
        )}
        <label className="block text-sm text-slate-700">
          Selectors (JSON)
          <textarea
            value={selectorsJson}
            onChange={(e) => setSelectorsJson(e.target.value)}
            rows={10}
            className="input-bento mt-1 font-mono text-xs"
          />
        </label>
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
        <div className="flex gap-2 justify-end">
          <button type="button" className="btn-ghost min-h-[44px]" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn min-h-[44px]" disabled={saving} onClick={() => void handleSave()}>
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
